#!/usr/bin/env python3
"""
Shared AI hook logger — works with Claude Code, Gemini CLI, Codex, Cursor, Copilot.
Reads JSON from stdin, normalizes to common format, appends to .ai-log/session.jsonl
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from auto_submit import submit_if_enabled

ROOT = Path(__file__).resolve().parent.parent
VN_TZ = timezone(timedelta(hours=7))

_SENSITIVE_KEY = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|auth(?:orization)?|cookie|password|secret|session|request[_-]?key|refresh[_-]?token|private[_-]?key)"
)
_SECRET_TEXT = re.compile(
    r"(?i)(bearer\s+|sk-[a-z0-9_-]{12,}|(?:api[_-]?key|access[_-]?token|password|secret|token)\s*[:=]\s*)([^\s,;]+)"
)
_EMAIL_TEXT = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_TEXT = re.compile(r"(?<!\d)(?:\+?\d[\d .()\-]{7,}\d)(?!\d)")


def _redact_text(value: object, limit: int = 1000) -> str:
    """Return a short, safe summary without credentials or direct identifiers."""
    text = str(value or "")
    text = _SECRET_TEXT.sub(lambda match: f"{match.group(1)}[REDACTED]", text)
    text = _EMAIL_TEXT.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_TEXT.sub("[REDACTED_PHONE]", text)
    return text[:limit]


def _sanitize(value: object, depth: int = 0) -> object:
    """Recursively remove sensitive fields before a tool payload is logged."""
    if depth > 4:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else _sanitize(item, depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item, depth + 1) for item in value[:30]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _redact_text(value) if isinstance(value, str) else value
    return _redact_text(value)


def _safe_summary(value: object, limit: int = 1000) -> str:
    sanitized = _sanitize(value)
    if isinstance(sanitized, str):
        return sanitized[:limit]
    try:
        return json.dumps(sanitized, ensure_ascii=False, separators=(",", ":"))[:limit]
    except (TypeError, ValueError):
        return _redact_text(sanitized, limit)


def git(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def detect_tool(data: dict) -> str:
    """Detect which AI tool sent this hook event.

    Priority:
      1. --tool=NAME CLI argument (cross-platform: works in cmd.exe, PowerShell, bash)
      2. AI_TOOL_NAME env var (legacy, bash-only when set inline)
      3. Heuristics from payload shape
    """
    for arg in sys.argv[1:]:
        if arg.startswith("--tool="):
            return arg.split("=", 1)[1].lower()
    tool_env = os.environ.get("AI_TOOL_NAME", "").lower()
    if tool_env:
        return tool_env
    # Heuristics
    if "transcript_path" in data:
        return "codex"
    if data.get("hook_event_name", "").startswith(("Before", "After", "Session", "Pre", "Notification")):
        return "gemini"
    if data.get("hook_event_name", "")[0:1].islower():
        # camelCase event names → Cursor or Copilot
        if "workspace_roots" in data:
            return "cursor"
        if "toolName" in data:
            return "copilot"
    if "hook_event_name" in data:
        return "claude"
    return "unknown"


def normalize(data: dict, tool: str) -> dict | None:
    """Normalize tool-specific payload to common log entry."""
    event = data.get("hook_event_name") or data.get("event", "")
    ts = datetime.now(VN_TZ).isoformat()

    # Resolve repo from git origin. When cwd is not a git working tree (or
    # origin isn't set), skip the event entirely — these entries can't be
    # tied back to a team on the server and would just clutter the pending
    # queue forever.
    origin = git("git remote get-url origin")
    if not origin:
        return None
    repo = origin.rstrip("/").split("/")[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    base = {
        "ts": ts,
        "tool": tool,
        "event": event,
        # Session/conversation identifiers are deliberately not persisted.
        "session_id": "",
        "model": data.get("model", ""),
        "repo": repo,
        "branch": git("git rev-parse --abbrev-ref HEAD"),
        "commit": git("git rev-parse --short HEAD"),
        # Keep the required field shape without storing a user's email.
        "student": "configured" if git("git config user.email") else "",
    }

    if tool == "claude":
        prompt = ""
        # UserPromptSubmit: prompt is at top level
        if event == "UserPromptSubmit":
            prompt = data.get("prompt", "")[:1000]
        # PostToolUse: extract from tool_input
        elif isinstance(data.get("tool_input"), dict):
            prompt = data["tool_input"].get("prompt") or data["tool_input"].get("content") or ""
        base.update({
            "prompt": _redact_text(prompt),
            "tool_name": data.get("tool_name", ""),
            "tool_input_summary": _safe_summary(data.get("tool_input")) if event != "UserPromptSubmit" else "",
            "tool_response_summary": _safe_summary(data.get("tool_response"), 500),
        })

    elif tool == "gemini":
        if event == "BeforeAgent":
            prompt = data.get("prompt", "")[:1000]
            base.update({"prompt": _redact_text(prompt)})
        else:
            req = data.get("request", {})
            contents = req.get("contents", [])
            prompt = ""
            for c in reversed(contents):
                for part in c.get("parts", []):
                    if part.get("text"):
                        prompt = part["text"][:1000]
                        break
                if prompt:
                    break
            resp = data.get("response", {})
            answer = ""
            try:
                answer = resp["candidates"][0]["content"]["parts"][0]["text"][:500]
            except Exception:
                pass
            base.update({"prompt": _redact_text(prompt), "response_summary": _redact_text(answer, 500)})

    elif tool == "codex":
        base.update({
            "prompt": _redact_text(data.get("prompt", "")),
            "tool_name": data.get("tool_name", data.get("toolName", "")),
            "tool_input_summary": _safe_summary(data.get("tool_input", data.get("tool_input_summary", ""))),
            "tool_output_summary": _safe_summary(data.get("tool_output", data.get("tool_response", "")), 500),
        })

    elif tool == "cursor":
        base.update({
            "prompt": _redact_text(data.get("prompt", "")),
            "files_context": _safe_summary(data.get("attachments", [])),
        })

    elif tool == "copilot":
        base.update({
            "prompt": _redact_text(data.get("prompt", "")),
            "tool_name": data.get("toolName", ""),
            "tool_args_summary": _safe_summary(data.get("toolArgs")),
        })

    # Skip only true noise: no prompt AND no tool-specific payload (tool_input,
    # response_summary, tool_response, tool_args, files_context). Previously
    # this only checked `prompt`, which dropped Claude Bash/Edit events (their
    # tool_input has `command` / `file_path`, not `prompt` or `content`) and
    # any Gemini/Cursor/Copilot turn that carried context but no plain prompt.
    payload_keys = ("prompt", "tool_input_summary", "tool_output_summary",
                    "tool_response_summary", "response_summary", "tool_args_summary", "files_context")
    lifecycle_events = ("Stop", "stop", "SessionEnd", "sessionEnd", "AfterModel")
    has_payload = any(base.get(k) for k in payload_keys)
    if not has_payload and event not in lifecycle_events:
        return None

    return base


def main():
    # Read stdin as UTF-8 explicitly. On Windows, sys.stdin defaults to the
    # system code page (e.g. cp1252), which corrupts non-Latin1 prompts
    # (Vietnamese, CJK, emoji) into mojibake. The hook payload is always UTF-8.
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    if not raw:
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    tool = detect_tool(data)
    entry = normalize(data, tool)
    if not entry:
        sys.exit(0)

    configured_log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    log_dir = configured_log_dir if configured_log_dir.is_absolute() else ROOT / configured_log_dir
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "session.jsonl"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Tool events can be frequent. They are flushed in batches at Stop/
    # SessionEnd; prompt/manual events still trigger the existing best-effort
    # background submit immediately.
    if entry.get("event") not in {"PostToolUse", "postToolUse"}:
        submit_if_enabled()

    # Codex requires a response matching its hook schema.
    print(json.dumps({} if tool == "codex" else {"status": "logged"}))


if __name__ == "__main__":
    main()
