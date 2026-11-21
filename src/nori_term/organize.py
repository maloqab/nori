"""AI organize: a messy paste (a table copied from a page, a wall of text) becomes tidy Markdown with a
title that fits it. Runs `claude -p` (Miteb's Claude Code login; no hooks, tools or saved session).
The paste lands as-is first; the organized version replaces it only if nothing was typed over it
meanwhile, and Ctrl+Z brings the original back. NORI_AI=0 turns it off.
"""

from __future__ import annotations

from . import tables

import csv
import io
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
TITLE_ONLY = """Reply with only a short title (2-6 words) naming what this table is: no quotes, no '#',
no punctuation at the end, nothing else."""
TITLE_NEW = "Begin with a line '# ' + a short title (2-6 words) naming what this is."
TITLE_SECTION = "Begin with a line '### ' + a short heading (2-6 words) naming what this block is."


def enabled() -> bool:
    return os.environ.get("NORI_AI", "1") != "0"


def is_markdown(text: str) -> bool:
    """Already structured: most lines are table rows, headings or list items."""
    lines = [l for l in text.strip().splitlines() if l.strip()]
    marked = sum(bool(re.match(r"\s*(\||#|[-*+] |\d+[.)] )", l)) for l in lines)
    return bool(lines) and marked >= max(2, len(lines) * 0.6)


def should_organize(text: str) -> bool:
    """Worth organizing: tabular or long, and not already Markdown."""
    lines = [l for l in text.strip().splitlines() if l.strip()]
    if tables.to_markdown(text) != text:                     # a box table (copied from Claude Code etc.)
        return True
    if not lines or is_markdown(text):
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
    # a comma is a thousands separator only before exactly three digits ("3,215,880"; not "1.001,1.002")
    nums = lambda s: set(re.findall(r"\d+(?:,\d{3}(?!\d))*(?:\.\d+)?", s))
    return nums(original) <= nums(organized)


# ---- tables, built in code -----------------------------------------------------
# A model shortens long tables (and the number guard then rejects them), so clearly delimited data is
# turned into a table here: instant and lossless at any size. The model only names it.
def _split_tab(line: str) -> list[str]:
    return [c.strip() for c in line.split("\t")]


def _split_spaces(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"\s{2,}|\t", line.strip())]


def _split_csv(line: str) -> list[str]:
    try:
        return [c.strip() for c in next(csv.reader(io.StringIO(line)))]
    except (StopIteration, csv.Error):
        return [line]


def _best_run(rows: list[list[str]]) -> tuple[int, int]:
    """Longest run of consecutive lines with the same number (2+) of cells: (start, length)."""
    best, i = (0, 0), 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and len(rows[j + 1]) == len(rows[i]) >= 2:
            j += 1
        if len(rows[i]) >= 2 and j - i + 1 > best[1]:
            best = (i, j - i + 1)
        i = j + 1
    return best


def table_markdown(text: str) -> str | None:
    """Delimited data (tab, aligned columns, CSV) as a Markdown table, with lines around it kept as text.
    None when it isn't a table."""
    boxed = tables.to_markdown(text)                         # box tables pasted from a terminal app
    if boxed != text:
        return boxed.strip()
    lines = [l for l in text.strip("\n").splitlines()]
    choice = None
    for split in (_split_tab, _split_spaces, _split_csv):        # thousands commas make CSV the last resort
        rows = [split(l) if l.strip() else [] for l in lines]
        start, n = _best_run(rows)
        if n >= 3 and (choice is None or n > choice[2]):
            cells = [c for r in rows[start:start + n] for c in r]
            if sum(len(c) for c in cells) / len(cells) <= 40:      # short cells: data, not prose
                choice = (rows, start, n)
    if not choice:
        return None
    rows, start, n = choice
    esc = lambda c: c.replace("|", "\\|")
    table = ["| " + " | ".join(esc(c) for c in rows[start]) + " |", "|" + "---|" * len(rows[start])]
    table += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows[start + 1:start + n]]
    before, after = "\n".join(lines[:start]).strip(), "\n".join(lines[start + n:]).strip()
    return "\n\n".join(x for x in (before, align_tables("\n".join(table)), after) if x)


# ---- the model ---------------------------------------------------------------------
def _claude(system: str, text: str) -> str | None:
    try:
        r = subprocess.run(
            ["claude", "-p", "--model", MODEL, "--tools", "", "--no-session-persistence",
             "--setting-sources", "", "--disable-slash-commands", "--system-prompt", system,
             "The text is on stdin."],
            input=text, capture_output=True, text=True, timeout=TIMEOUT, cwd=os.path.expanduser("~"),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = clean(r.stdout) if r.returncode == 0 else ""
    return out or None


def run(text: str, new_note: bool) -> str | None:
    """Organized Markdown, or None (failed, timed out, or it lost data)."""
    if is_markdown(text):          # already organized: the app just fits its tables to the page
        return text
    table = table_markdown(text)
    if table:
        title = _claude(TITLE_ONLY, "\n".join(table.splitlines()[:40]))
        title = (title or "").splitlines()[0].strip().lstrip("#").strip().strip('"') if title else ""
        if not title or len(title) > 80:
            return table
        return f"{'#' if new_note else '###'} {title}\n\n{table}"
    out = _claude(SYSTEM.format(title=TITLE_NEW if new_note else TITLE_SECTION), text)
    if not out or not keeps_the_numbers(text, out):
        return None
    return align_tables(out)
