#!/usr/bin/env python3
"""render_wiki.py — turn docs/*.md into a static, dependency-free HTML wiki.

Why: the Markdown in docs/ is the source of truth (it versions with the data and
diffs cleanly), but a set of nine linked pages is easier to read with a sidebar.
This produces one plain HTML file per page plus an index, with a nav column, no
JavaScript and no CDN — drop it behind any static web server.

    python3 tools/render_wiki.py            # docs/ -> wiki/
    python3 tools/render_wiki.py --check     # only verify cross-page anchors

The Markdown support is deliberately partial and exactly as large as these
documents need: headings, paragraphs, ordered/unordered lists (one nesting
level), tables with column alignment, fenced code, blockquotes, rules, task
boxes, and inline code/bold/italic/links. Anything else is passed through as
text, so nothing is silently dropped.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "wiki"

TITLE_OVERRIDES = {"index": "Age grading — documentation"}


# ---------------------------------------------------------------- inline ----
def slug(text: str) -> str:
    """GitHub-style heading anchor: lowercase, drop punctuation, spaces->hyphens."""
    text = re.sub(r"`|\*|\[|\]\([^)]*\)", "", text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9 _-]", "", text)
    return re.sub(r" +", "-", text.strip())


def inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<span class="img">[\1]</span>', out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"(?<![\w_])_([^_\n]+)_(?![\w_])", r"<em>\1</em>", out)
    return out


# ----------------------------------------------------------------- block ----
def is_table(block: list[str]) -> bool:
    return len(block) >= 2 and block[0].lstrip().startswith("|") and \
        set(block[1].replace("|", "").replace(" ", "")) <= set("-:")


def render_table(block: list[str]) -> str:
    def cells(row: str) -> list[str]:
        row = row.strip()
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        return [c.strip() for c in row.split("|")]

    align = []
    for spec in cells(block[1]):
        if spec.startswith(":") and spec.endswith(":"):
            align.append("center")
        elif spec.endswith(":"):
            align.append("right")
        else:
            align.append("left")
    head, body = cells(block[0]), [cells(r) for r in block[2:]]
    out = ['<table>', "<thead><tr>"]
    for i, c in enumerate(head):
        a = align[i] if i < len(align) else "left"
        out.append(f'<th style="text-align:{a}">{inline(c)}</th>')
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>")
        for i, c in enumerate(row):
            a = align[i] if i < len(align) else "left"
            out.append(f'<td style="text-align:{a}">{inline(c)}</td>')
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def render_list(lines: list[str]) -> str:
    """Render bullets/numbers with one nesting level.

    Continuation lines (a wrapped sentence inside a bullet) belong to the item
    above them; dropping them would silently lose prose, so they are appended.
    """
    items: list[tuple[int, str, bool, str]] = []  # indent, kind, checkbox, text
    for raw in lines:
        m = LIST_RE.match(raw)
        if m:
            indent = len(m.group(1))
            kind = "ol" if m.group(2)[0].isdigit() else "ul"
            body = m.group(3)
            box = ""
            tm = re.match(r"\[([ xX])\]\s+(.*)", body)
            if tm:
                box = ('<input type="checkbox" disabled' +
                       (' checked' if tm.group(1).lower() == "x" else "") + "> ")
                body = tm.group(2)
            items.append((indent, kind, bool(box), (box, body)))
        elif items:
            indent, kind, box, (b, text) = items[-1]
            items[-1] = (indent, kind, box, (b, text + " " + raw.strip()))
        else:
            items.append((0, "ul", False, ("", raw.strip())))

    out: list[str] = []
    stack: list[tuple[int, str]] = []

    def close_to(indent: int) -> None:
        while stack and stack[-1][0] > indent:
            out.append(f"</{stack.pop()[1]}>")

    for indent, kind, box, (b, text) in items:
        close_to(indent)
        if not stack or stack[-1][0] < indent:
            out.append(f"<{kind}>")
            stack.append((indent, kind))
        cls = ' class="task"' if box else ""
        out.append(f"<li{cls}>{b}{inline(text.strip())}</li>")
    while stack:
        out.append(f"</{stack.pop()[1]}>")
    return "\n".join(out)


def render_markdown(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (html, headings) where headings is [(level, slug, text)]."""
    lines = text.replace("\r\n", "\n").split("\n")
    blocks: list[list[str]] = []
    cur: list[str] = []
    in_fence = False
    fence: list[str] = []

    for line in lines:
        if line.strip().startswith("```"):
            if in_fence:
                blocks.append(["```"] + fence + ["```"])
                fence, in_fence = [], False
            else:
                in_fence = True
            continue
        if in_fence:
            fence.append(line)
            continue
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(line)
    if cur:
        blocks.append(cur)

    out: list[str] = []
    headings: list[tuple[str, str, str]] = []
    for block in blocks:
        first = block[0]
        if first == "```":
            code = "\n".join(block[1:-1])
            out.append(f"<pre><code>{html.escape(code)}</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", first)
        if m and len(block) == 1:
            level = len(m.group(1))
            text = m.group(2).strip()
            sid = slug(text)
            headings.append((level, sid, text))
            out.append(f'<h{level} id="{sid}">{inline(text)}</h{level}>')
            continue
        if len(block) == 1 and re.fullmatch(r"\s*(-{3,}|\*{3,})\s*", first):
            out.append("<hr>")
            continue
        if is_table(block):
            out.append(render_table(block))
            continue
        if all(LIST_RE.match(b) for b in block):
            out.append(render_list(block))
            continue
        if first.lstrip().startswith(">"):
            body = " ".join(b.lstrip("> ").strip() for b in block)
            out.append(f"<blockquote>{inline(body)}</blockquote>")
            continue
        # paragraph, or a bullet followed by continuation lines
        m = LIST_RE.match(first)
        if m:
            out.append(render_list(block))
            continue
        out.append("<p>" + inline(" ".join(b.strip() for b in block)) + "</p>")

    return "\n".join(out), headings


# ------------------------------------------------------------------ page ----
CSS = """
:root { --ink:#1b2330; --dim:#5c6673; --line:#dfe3e8; --bg:#fbfaf7;
        --accent:#8a4b1f; --code:#f2f0ec; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:16px/1.62 -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
.wrap { display:flex; min-height:100vh; }
nav { flex:0 0 268px; padding:26px 20px 40px; border-right:1px solid var(--line);
      background:#fff; position:sticky; top:0; align-self:flex-start; height:100vh;
      overflow-y:auto; }
nav .brand { font-weight:600; font-size:1.02rem; margin-bottom:4px; }
nav .sub { color:var(--dim); font-size:.8rem; margin-bottom:18px; }
nav a { display:block; color:var(--ink); text-decoration:none; font-size:.9rem;
        padding:4px 8px; border-radius:4px; }
nav a:hover { background:#f3efe9; }
nav a.here { background:#f3efe9; font-weight:600; border-left:2px solid var(--accent); }
main { flex:1; min-width:0; padding:34px 46px 90px; max-width:1000px; }
h1 { font-size:1.9rem; margin:0 0 18px; letter-spacing:-.01em; }
h2 { font-size:1.28rem; margin:34px 0 10px; padding-bottom:6px;
     border-bottom:1px solid var(--line); }
h3 { font-size:1.05rem; margin:26px 0 8px; }
h4 { font-size:.96rem; margin:20px 0 6px; color:var(--dim); }
p { margin:10px 0; }
a { color:var(--accent); }
code { background:var(--code); padding:1px 4px; border-radius:3px;
       font:.88em/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
pre { background:#22282f; color:#e8e6e1; padding:14px 16px; border-radius:6px;
      overflow-x:auto; font-size:.84rem; line-height:1.5; }
pre code { background:none; padding:0; color:inherit; font-size:inherit; }
table { border-collapse:collapse; margin:16px 0; font-size:.88rem; width:100%; }
th, td { border:1px solid var(--line); padding:6px 10px; vertical-align:top; }
th { background:#f3efe9; font-weight:600; }
tbody tr:nth-child(even) { background:#fdfcfa; }
blockquote { margin:14px 0; padding:2px 16px; border-left:3px solid var(--line);
             color:var(--dim); }
ul, ol { margin:10px 0; padding-left:24px; }
li { margin:4px 0; }
li.task { list-style:none; margin-left:-18px; }
hr { border:none; border-top:1px solid var(--line); margin:28px 0; }
.pager { margin-top:46px; padding-top:16px; border-top:1px solid var(--line);
         display:flex; justify-content:space-between; font-size:.88rem; }
@media (max-width: 820px) {
  .wrap { display:block; }
  nav { position:static; height:auto; border-right:none; border-bottom:1px solid var(--line); }
  main { padding:22px 18px 60px; }
}
"""


def page(title: str, nav: str, body: str, pager: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style></head>
<body><div class="wrap"><nav>{nav}</nav><main>{body}{pager}</main></div></body></html>
"""


def build(check_only: bool = False) -> int:
    files = sorted(p for p in DOCS.glob("*.md"))
    if not files:
        print(f"no markdown in {DOCS}")
        return 1

    rendered: dict[str, tuple[str, list]] = {}
    for path in files:
        body, headings = render_markdown(path.read_text(encoding="utf-8"))
        rendered[path.stem] = (body, headings)

    # ---- cross-page anchor check ---------------------------------------
    problems = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        for target, anchor in re.findall(r"\(([\w./-]+\.md)(?:#([\w-]+))?\)", text):
            stem = Path(target).stem
            if stem not in rendered:
                # A link out of docs/ (e.g. ../xll/README.md): only the file can
                # be checked, not its anchors, because it is not part of the wiki.
                if (path.parent / target).exists():
                    continue
                print(f"  BROKEN PAGE  {path.name} -> {target}")
                problems += 1
                continue
            if anchor and anchor not in {h[1] for h in rendered[stem][1]}:
                print(f"  BROKEN ANCHOR {path.name} -> {target}#{anchor}")
                problems += 1
    print(f"links: {problems} problem(s)")

    if check_only:
        return 0 if problems == 0 else 1

    # ---- write pages ---------------------------------------------------
    OUT.mkdir(exist_ok=True)
    stems = [p.stem for p in files]

    def nav_html(current: str) -> str:
        items = []
        for stem in stems:
            _, headings = rendered[stem]
            title = TITLE_OVERRIDES.get(stem) or (
                headings[0][2] if headings else stem)
            href = "index.html" if stem == "index" else f"{stem}.html"
            cls = ' class="here"' if stem == current else ""
            items.append(f'<a href="{href}"{cls}>{html.escape(title)}</a>')
        return ('<div class="brand">Road age grading</div>'
                '<div class="sub">USATF MLDR 2025 tables</div>' + "\n".join(items))

    for i, stem in enumerate(stems):
        body, headings = rendered[stem]
        title = TITLE_OVERRIDES.get(stem) or (headings[0][2] if headings else stem)
        prev_stem = stems[i - 1] if i else None
        next_stem = stems[i + 1] if i + 1 < len(stems) else None

        def link(s: str | None, label: str) -> str:
            if not s:
                return "<span></span>"
            href = "index.html" if s == "index" else f"{s}.html"
            text = TITLE_OVERRIDES.get(s) or rendered[s][1][0][2]
            return f'<a href="{href}">{label} {html.escape(text)}</a>'

        pager = f'<div class="pager">{link(prev_stem, "←")}{link(next_stem, "→")}</div>'
        out = OUT / ("index.html" if stem == "index" else f"{stem}.html")
        out.write_text(page(title, nav_html(stem), body, pager), encoding="utf-8")

    print(f"wrote {len(stems)} page(s) to {OUT.relative_to(ROOT)}/")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only check links")
    sys.exit(build(ap.parse_args().check))
