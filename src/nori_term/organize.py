"""AI organize: a messy paste (a table copied from a page, a wall of text) becomes tidy Markdown with a
title that fits it. Runs `claude -p` (Miteb's Claude Code login; no hooks, tools or saved session).
The paste lands as-is first; the organized version replaces it only if nothing was typed over it
meanwhile, and Ctrl+Z brings the original back. NORI_AI=0 turns it off.
"""

from __future__ import annotations

import os
import re
import subprocess

MODEL = os.environ.get("NORI_AI_MODEL", "haiku")
TIMEOUT = 90

SYSTEM = """You tidy text that was just pasted into a plain-Markdown notes app.
Return Markdown only: no commentary, no code fences.
Keep every piece of information exactly as given: names, numbers, dates, wording. Never summarize, drop,
add, translate or invent anything.
Fix only the structure:
- rows and columns (tab- or space-separated, or copied from a web table) → a GitHub pipe table with a header row
- items → a bullet or numbered list
- prose → short paragraphs
- clearly separate parts → short headings
{title}"""
TITLE_NEW = "Begin with a line '# ' + a short title (2-6 words) naming what this is."
TITLE_SECTION = "Begin with a line '### ' + a short heading (2-6 words) naming what this block is."


def enabled() -> bool:
    return os.environ.get("NORI_AI", "1") != "0"


def should_organize(text: str) -> bool:
    """Worth organizing: tabular or long, and not already Markdown."""
    lines = [l for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return False
    marked = sum(bool(re.match(r"\s*(\||#|[-*+] |\d+[.)] )", l)) for l in lines)
    if marked >= max(2, len(lines) * 0.6):
        return False
    tab_rows = sum("\t" in l for l in lines)
    gap_rows = sum(len(re.findall(r"\S {2,}\S", l)) >= 1 for l in lines)
    if len(lines) >= 3 and (tab_rows >= 2 or gap_rows >= 3):
        return True
    return len(text.strip()) >= 280 or len(lines) >= 6


def clean(out: str) -> str:
    out = out.strip()
    m = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", out, re.S)
    return (m.group(1) if m else out).strip()


def _cells(line: str) -> list[str]:
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") else s
    return [c.strip() for c in s.split("|")]


def _align_block(rows: list[str]) -> list[str]:
    table = [_cells(r) for r in rows]
    n = max(len(r) for r in table)
    table = [r + [""] * (n - len(r)) for r in table]
    is_sep = [all(re.fullmatch(r":?-+:?", c) or c == "" for c in r) and any(c for c in r) for r in table]
    width = [max([3] + [len(r[i]) for r, sep in zip(table, is_sep) if not sep]) for i in range(n)]
    out = []
    for r, sep in zip(table, is_sep):
        if sep:
            cells = [(":" if c.startswith(":") else "-") + "-" * (w - 2) + (":" if c.endswith(":") and len(c) > 1 else "-")
                     for c, w in zip(r, width)]
        else:
            cells = [c.ljust(w) for c, w in zip(r, width)]
        out.append("| " + " | ".join(cells) + " |")
    return out


def align_tables(md: str) -> str:
    """Pad pipe tables so their columns line up on a monospace page."""
    lines, out, block = md.splitlines(), [], []
    for line in lines + [""]:
        if line.lstrip().startswith("|"):
            block.append(line)
            continue
        if block:
            out.extend(_align_block(block) if len(block) >= 2 else block)
            block = []
        out.append(line)
    return "\n".join(out[:-1])


def keeps_the_numbers(original: str, organized: str) -> bool:
    """A cheap guard against dropped data: every number in the paste is still there."""
    nums = lambda s: set(re.findall(r"\d+(?:[.,]\d+)*", s))
    return nums(original) <= nums(organized)


def run(text: str, new_note: bool) -> str | None:
    """Organized Markdown, or None (failed, timed out, or it lost data)."""
    system = SYSTEM.format(title=TITLE_NEW if new_note else TITLE_SECTION)
    try:
        r = subprocess.run(
            ["claude", "-p", "--model", MODEL, "--tools", "", "--no-session-persistence",
             "--setting-sources", "", "--disable-slash-commands", "--system-prompt", system,
             "Organize the pasted text from stdin."],
            input=text, capture_output=True, text=True, timeout=TIMEOUT, cwd=os.path.expanduser("~"),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = clean(r.stdout) if r.returncode == 0 else ""
    if not out or not keeps_the_numbers(text, out):
        return None
    return align_tables(out)
