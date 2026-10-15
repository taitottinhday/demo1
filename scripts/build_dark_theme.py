"""Generate dark-theme override stylesheets from the light CSS.

For every rule in a source stylesheet, each colour-bearing declaration is copied
under an ``html[data-theme="dark"]`` prefix with its colours remapped by role
(background, text, border). Every colour declaration is copied, even when the
colour itself is kept, so the uniform specificity bump preserves the original
cascade order.

    python scripts/build_dark_theme.py

Writes src/web/<name>.dark.css next to each source. Re-run after editing the
light stylesheets.
"""

import colorsys
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "web"
SOURCES = ["style.css", "account.css", "enhance.css", "login.css", "dashboard.css"]
PREFIX = 'html[data-theme="dark"]'

COLOR_PROPS = re.compile(
    r"^(background(-color|-image)?|color|fill|stroke|caret-color|accent-color|text-decoration-color|"
    r"border(-(top|right|bottom|left|block|inline))?(-color)?|outline(-color)?|box-shadow|scrollbar-color|--[\w-]+)$"
)
HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
RGB = re.compile(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)\s*(?:[/,]\s*([\d.]+)(%?))?\s*\)")
NAMED = re.compile(r"(?<![\w-])(white|black)(?![\w-])")
URL = re.compile(r"url\([^)]*\)")


def role_for(prop, value):
    if prop.startswith("--"):
        name = prop.lower()
        if "shadow" in name:
            return "shadow"
        if "line" in name or "border" in name:
            return "border"
        if any(k in name for k in ("ink", "muted", "text")):
            return "text"
        if name in ("--green", "--red", "--brand", "--brand-700"):
            return "keep"
        if name == "--brand-600":
            return "text"
        return "auto"
    if prop.startswith(("background",)):
        return "bg"
    if prop.startswith(("border", "outline", "scrollbar")):
        return "border"
    if prop == "box-shadow":
        return "shadow"
    return "text"


def to_hex(r, g, b, a):
    out = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
    if a < 0.999:
        out += "%02x" % round(a * 255)
    return out


SLATE_HUE = 222 / 360  # neutral greys get a faint cool tint


def remap(r, g, b, a, role):
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    chroma = max(r, g, b) - min(r, g, b)
    # Greys and warm beiges count as neutral; brand pinks keep their hue.
    neutral = chroma < 0.035 or (chroma < 0.07 and 20 / 360 < h < 80 / 360)
    if role in ("keep", "shadow"):
        return r, g, b, a
    if role == "auto":
        role = "bg" if l >= 0.78 else ("text" if l < 0.4 and (neutral or l < 0.3) else "keep")
        if role == "keep":
            return r, g, b, a
    # Faint overlays: dark tints (dot grids, hairlines) flip to white tints.
    if a < 0.45:
        if l < 0.5 and role in ("bg", "border"):
            return 1, 1, 1, min(a * 1.2, 1)
        return r, g, b, a
    hue, sat = (SLATE_HUE, 0.14) if neutral else (h, 0.38)
    if role == "bg":
        if l >= 0.78:
            # Keep elevation order: white cards end up slightly lighter than
            # the off-white page canvas; tinted fills (chips, hovers) lighter still.
            nl = 0.10 + (l - 0.94) * 0.7 if l >= 0.94 else 0.16 + (0.94 - l) * 0.5
            return (*colorsys.hls_to_rgb(hue, nl, sat), a)
        return r, g, b, a
    if role == "border":
        if l >= 0.7:
            return (*colorsys.hls_to_rgb(hue, 0.21 + (1 - l) * 0.4, sat * 0.8), a)
        return r, g, b, a
    # text
    if (neutral or l < 0.3 or s < 0.3) and l < 0.75:
        return (*colorsys.hls_to_rgb(SLATE_HUE, 0.94 - l * 0.68, 0.12), a)
    if l < 0.62:
        return (*colorsys.hls_to_rgb(h, max(l, 0.68), min(s, 0.85)), a)
    return r, g, b, a


def map_value(prop, value):
    role = role_for(prop, value)
    urls = []

    def stash(m):
        urls.append(m.group(0))
        return f"\0{len(urls) - 1}\0"

    value = URL.sub(stash, value)

    def hex_sub(m):
        digits = m.group(1)
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        r, g, b = (int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4))
        a = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
        return to_hex(*remap(r, g, b, a, role))

    def rgb_sub(m):
        r, g, b = (int(m.group(i)) / 255 for i in (1, 2, 3))
        a = 1.0
        if m.group(4):
            a = float(m.group(4)) / (100 if m.group(5) else 1)
        return to_hex(*remap(r, g, b, a, role))

    def named_sub(m):
        v = 1.0 if m.group(1) == "white" else 0.0
        return to_hex(*remap(v, v, v, 1.0, role))

    value = HEX.sub(hex_sub, value)
    value = RGB.sub(rgb_sub, value)
    value = NAMED.sub(named_sub, value)
    return re.sub("\0(\\d+)\0", lambda m: urls[int(m.group(1))], value)


def prefix_selector(sel):
    sel = sel.strip()
    if not sel:
        return sel
    if sel.startswith(":root"):
        return PREFIX + sel[len(":root"):]
    if re.match(r"html\b", sel):
        return PREFIX + sel[4:]
    return f"{PREFIX} {sel}"


def split_top(text, sep):
    """Split on sep outside parentheses/brackets/quotes."""
    parts, depth, quote, cur = [], 0, None, []
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    return parts


def parse_blocks(css, i=0):
    """Yield (prelude, body_or_children, is_group) until the matching '}'."""
    items = []
    while i < len(css):
        j = i
        while j < len(css) and css[j] not in "{}":
            j += 1
        if j >= len(css):
            break
        if css[j] == "}":
            return items, j + 1
        prelude = css[i:j].strip()
        if prelude.startswith("@media") or prelude.startswith("@supports"):
            children, i = parse_blocks(css, j + 1)
            items.append((prelude, children, True))
            continue
        depth, k = 1, j + 1
        while k < len(css) and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        items.append((prelude, css[j + 1:k - 1], False))
        i = k
    return items, i


def convert(items):
    out = []
    for prelude, body, is_group in items:
        if is_group:
            inner = convert(body)
            if inner:
                out.append(f"{prelude}{{\n{inner}\n}}")
            continue
        if prelude.startswith("@"):
            continue  # @keyframes, @font-face, ...
        decls = []
        for decl in split_top(body, ";"):
            if ":" not in decl:
                continue
            prop, value = decl.split(":", 1)
            prop, value = prop.strip(), value.strip()
            if not COLOR_PROPS.match(prop):
                continue
            if prop.startswith("--") and not (HEX.search(value) or RGB.search(value) or NAMED.search(value)):
                continue
            decls.append(f"{prop}:{map_value(prop, value)}")
        if decls:
            selectors = ",".join(prefix_selector(s) for s in split_top(prelude, ","))
            out.append(f"{selectors}{{{';'.join(decls)}}}")
    return "\n".join(out)


def main():
    for name in SOURCES:
        css = re.sub(r"/\*.*?\*/", "", (WEB / name).read_text(encoding="utf-8-sig"), flags=re.S)
        items, _ = parse_blocks(css)
        target = WEB / name.replace(".css", ".dark.css")
        target.write_text(
            f"/* Generated by scripts/build_dark_theme.py from {name}. Do not edit by hand. */\n"
            + convert(items) + "\n",
            encoding="utf-8",
        )
        print(f"{target.name}: {target.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
