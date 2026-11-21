"""Nori's look: the wa palettes from Miteb's Herdr setup (herdr-wa), day and night.

Inside Herdr, the wa switcher labels every terminal `wa.theme=custom:wa-<look>[-night]` for its space's
look and the current appearance. Nori reads that label for its own terminal ($HC_TERMINAL_ID), so it
matches the space it opens in and follows day/night. NORI_THEME=<name> overrides; outside Herdr
(or without a wa label) Nori keeps Textual's default look.
"""

from __future__ import annotations

import json
import os
import subprocess

from rich.style import Style
from textual.theme import Theme
from textual.widgets.text_area import TextAreaTheme

# The four wa palettes (herdr-wa/app/themes/*.json).
PALETTES = {
    "wa-traditional": dict(bg="#EFE1D4", fg="#2A211C", surface="#E6D6C5", selection="#DBC5AD",
                           border="#D2C2B2", muted="#7A6A5D", accent="#982A18", dark=False),
    "wa-traditional-night": dict(bg="#1A1514", fg="#EFE6D8", surface="#241E1B", selection="#3A302A",
                                 border="#3A322D", muted="#A59584", accent="#C4553C", dark=True),
    "wa-modern": dict(bg="#EBF1F7", fg="#141A26", surface="#E4ECF4", selection="#C5D6E6",
                      border="#C5D0E1", muted="#5E718A", accent="#E73C09", dark=False),
    "wa-modern-night": dict(bg="#0B121B", fg="#E4ECF4", surface="#131B25", selection="#334454",
                            border="#3C4751", muted="#8FA3BA", accent="#F0541E", dark=True),
}


def themes() -> list[Theme]:
    out = []
    for name, p in PALETTES.items():
        out.append(Theme(
            name=name, primary=p["accent"], accent=p["accent"], secondary=p["muted"],
            foreground=p["fg"], background=p["bg"], surface=p["surface"], panel=p["surface"],
            dark=p["dark"],
            variables={
                "text-muted": p["muted"],
                "text-disabled": p["muted"] + "AA",
                "border": p["border"],
                "text-area-selection": p["selection"],
                "text-area-cursor-line": "transparent",
                "input-selection-background": p["selection"],
                "scrollbar": p["border"],
                "scrollbar-background": p["bg"],
                "scrollbar-hover": p["muted"],
                "scrollbar-active": p["muted"],
            },
        ))
    return out


def text_area_theme(name: str) -> TextAreaTheme:
    """The page's Markdown colors for a look: list marks in the accent, syntax marks muted. Heading text is
    styled by level in the editor (heading_style), since the grammar gives every level the same name."""
    p = PALETTES[name]
    fg, muted, accent = Style(color=p["fg"]), Style(color=p["muted"]), Style(color=p["accent"])
    return TextAreaTheme(
        name=name,
        base_style=Style(color=p["fg"], bgcolor=p["bg"]),
        cursor_style=Style(color=p["bg"], bgcolor=p["accent"]),
        selection_style=Style(bgcolor=p["selection"]),
        syntax_styles={
            "heading.marker": muted,
            "list.marker": accent,
            "punctuation.special": muted,        # table pipes and rules
            "punctuation.delimiter": muted,
            "link.label": Style(color=p["accent"], underline=True),
            "link.uri": muted,
            "text.literal": Style(color=p["fg"], italic=True),
            "string.escape": muted,
        },
    )


def heading_style(name: str, level: int) -> Style:
    """A terminal can't make text bigger, so levels differ by weight, color and a rule:
    # accent, bold, underlined · ## accent, bold · ### and deeper: bold body text."""
    p = PALETTES.get(name)
    if level >= 3:
        return Style(color=p and p["fg"], bold=True)
    return Style(color=p and p["accent"], bold=True, underline=level == 1)


def look_from_hc(raw: str) -> str | None:
    """`hc get <terminal> --json` → the wa look its label names, or None."""
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    labels = (d.get("terminal") or d).get("labels") or {}
    name = str(labels.get("wa.theme", "")).removeprefix("custom:")
    return name if name in PALETTES else None


def current_look() -> str | None:
    if os.environ.get("NORI_THEME") in PALETTES:
        return os.environ["NORI_THEME"]
    term = os.environ.get("HC_TERMINAL_ID")
    if not term:
        return None
    try:
        r = subprocess.run(["hc", "get", term, "--json"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return look_from_hc(r.stdout)
