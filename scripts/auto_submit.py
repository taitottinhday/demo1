"""Best-effort background submission for newly written AI log entries."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def submit_if_enabled() -> None:
    """Submit the pending log without slowing down the calling AI hook."""
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass
    enabled = os.environ.get("AI_LOG_AUTO_SUBMIT", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return
    command = [sys.executable, str(ROOT / "scripts" / "submit_log.py")]
    kwargs = {
        "cwd": str(ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        subprocess.Popen(command, **kwargs)
    except OSError:
        # The pre-push hook remains the reliable fallback if a child process
        # cannot be started by the editor's hook host.
        return
