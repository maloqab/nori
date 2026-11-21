"""Tables, the way Claude Code draws them: box borders, cells that wrap inside their column, the whole
table fitted to the page. Nori shows tables this way, but the note file keeps Markdown pipe tables (so
Obsidian shows real tables): to_display() on open, to_markdown() on save. parse() also reads box tables
pasted from Claude Code or any other terminal app.
"""

from __future__ import annotations

import re

from rich.cells import cell_len, chop_cells

H, V = "─", "│"
BOX_START = ("┌", "│", "├", "└")


# ---- drawing ----------------------------------------------------------------------
def _widths(header: list[str], rows: list[list[str]], width: int) -> list[int]:
    cols = list(zip(header, *rows))
    natural = [max(cell_len(c) for c in col) for col in cols]
    floor = [min(n, max(6, max((cell_len(w) for c in col for w in c.split()), default=1))) for n, col in zip(natural, cols)]
    room = width - (3 * len(cols) + 1)                     # "│ " + " │" per column, one shared border
    w = natural[:]
    while sum(w) > room:                                   # take from the widest column that can still give
        i = max((k for k in range(len(w)) if w[k] > floor[k]), key=lambda k: w[k], default=None)
        if i is None:                                      # every column at its floor: break long words
            i = max(range(len(w)), key=lambda k: w[k])
            if w[i] <= 3:
                break
            floor[i] = 3
        w[i] -= 1
    return [max(1, x) for x in w]


def _wrap(text: str, width: int) -> list[str]:
    """Words into lines of at most `width` screen columns (an emoji counts 2); long words are cut."""
    lines, cur = [], ""
    for word in text.split():
        pieces = chop_cells(word, width) if cell_len(word) > width else [word]
        for piece in pieces:
            if not cur:
                cur = piece
            elif cell_len(cur) + 1 + cell_len(piece) <= width:
                cur += " " + piece
            else:
                lines.append(cur)
                cur = piece
    return lines + [cur] if cur else (lines or [""])


def _pad(text: str, width: int, center: bool) -> str:
    gap = max(0, width - cell_len(text))
    return " " * (gap // 2) + text + " " * (gap - gap // 2) if center else text + " " * gap


def render(header: list[str], rows: list[list[str]], width: int) -> str:
    n = len(header)
    rows = [r + [""] * (n - len(r)) for r in rows]
    w = _widths(header, rows, width)
    rule = lambda l, m, r: l + m.join(H * (x + 2) for x in w) + r

    def line_set(cells: list[str], center: bool) -> list[str]:
        parts = [_wrap(c, x) for c, x in zip(cells, w)]
        out = []
        for i in range(max(len(p) for p in parts)):
            cell = [(p[i] if i < len(p) else "") for p in parts]
            out.append(V + V.join(" " + _pad(c, x, center) + " " for c, x in zip(cell, w)) + V)
        return out

    lines = [rule("┌", "┬", "┐"), *line_set(header, True)]
    for r in rows:
        lines += [rule("├", "┼", "┤"), *line_set(r, False)]
    return "\n".join(lines + [rule("└", "┴", "┘")])


# ---- reading --------------------------------------------------------------------------
def parse(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
    """A box table's lines → (header, rows), wrapped cell lines joined back. None if it isn't one."""
    lines = [l.strip() for l in lines if l.strip()]
    if len(lines) < 3 or not lines[0].startswith("┌") or not lines[-1].startswith("└"):
        return None
    groups, cur = [], []
    for l in lines[1:-1]:
        if l.startswith("├"):
            groups.append(cur)
            cur = []
        elif l.startswith(V) and l.endswith(V):
            cur.append([c.strip() for c in l[1:-1].split(V)])
        else:
            return None
    groups.append(cur)
    n = len(lines[0].split("┬"))
    if any(len(r) != n for g in groups for r in g) or not groups or not groups[0]:
        return None
    joined = [[" ".join(x for x in (r[i] for r in g) if x) for i in range(n)] for g in groups if g]
    return joined[0], joined[1:]


def _cells(line: str) -> list[str]:
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def _is_rule(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-+:?", c) or c == "" for c in cells) and any(cells)


def _pipe_table(header: list[str], rows: list[list[str]]) -> list[str]:
    esc = lambda c: c.replace("|", "\\|")
    out = ["| " + " | ".join(esc(c) for c in header) + " |", "|" + "---|" * len(header)]
    return out + ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]


def _blocks(lines: list[str], starts) -> list[tuple[int, int]]:
    """(start, end) of runs of lines that begin with one of `starts`."""
    out, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith(starts):
            j = i
            while j + 1 < len(lines) and lines[j + 1].lstrip().startswith(starts):
                j += 1
            out.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return out


def to_display(md: str, width: int) -> str:
    """Markdown pipe tables → box tables fitted to `width`. Everything else untouched."""
    lines = md.split("\n")
    for a, b in reversed(_blocks(lines, ("|",))):
        rows = [_cells(l) for l in lines[a:b]]
        if b - a >= 2 and _is_rule(rows[1]):
            lines[a:b] = render(rows[0], [r for r in rows[2:] if not _is_rule(r)], width).split("\n")
    return "\n".join(lines)


def to_markdown(text: str) -> str:
    """Box tables → Markdown pipe tables (what the note file keeps). A broken box stays as text."""
    lines = text.split("\n")
    for a, b in reversed(_blocks(lines, BOX_START)):
        table = parse(lines[a:b])
        if table:
            lines[a:b] = _pipe_table(*table)
    return "\n".join(lines)
