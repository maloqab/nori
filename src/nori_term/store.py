"""Notes on disk: one Markdown file per note, plus a hidden state file.

Notes live in a plain folder (default ~/notes, or $NORI_DIR) so Obsidian sees them too.
Nori-only state (locked notes, last open note) lives in `.nori.json` in that
folder; Obsidian ignores dotfiles, so it never shows up as a note.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_DIR = Path.home() / "notes"
STATE_FILE = ".nori.json"
TITLE_MAX = 40


def notes_dir() -> Path:
    return Path(os.environ.get("NORI_DIR", DEFAULT_DIR)).expanduser()


@dataclass
class Note:
    path: Path
    locked: bool = False

    @property
    def id(self) -> str:
        return self.path.name

    def read(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    @property
    def title(self) -> str:
        for line in self.read().splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                return line if len(line) <= TITLE_MAX else line[: TITLE_MAX - 1] + "…"
        return "untitled"

    @property
    def modified(self) -> datetime:
        return datetime.fromtimestamp(self.path.stat().st_mtime)


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or notes_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- hidden state -------------------------------------------------
    def _state(self) -> dict:
        try:
            return json.loads((self.root / STATE_FILE).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_state(self, state: dict) -> None:
        (self.root / STATE_FILE).write_text(json.dumps(state, indent=2))

    # ---- notes --------------------------------------------------------
    def notes(self, query: str = "") -> list[Note]:
        """All notes, locked first, then newest first. Optional text filter."""
        locked = set(self._state().get("locked", []))
        notes = [Note(p, p.name in locked) for p in self.root.glob("*.md") if p.is_file()]
        if query:
            q = query.lower()
            notes = [n for n in notes if q in n.read().lower() or q in n.id.lower()]
        return sorted(notes, key=lambda n: (not n.locked, -n.path.stat().st_mtime))

    def new(self, text: str = "", make_current: bool = True) -> Note:
        stamp = datetime.now().strftime("%Y-%m-%d %H%M%S")
        path = self.root / f"{stamp}.md"
        n = 1
        while path.exists():
            n += 1
            path = self.root / f"{stamp}-{n}.md"
        path.write_text(text, encoding="utf-8")
        if make_current:
            self.set_current(path.name)
        return Note(path)

    def get(self, note_id: str) -> Note | None:
        path = self.root / note_id
        if not path.is_file():
            return None
        return Note(path, note_id in self._state().get("locked", []))

    def save(self, note: Note, text: str) -> None:
        if note.read() != text:
            note.path.write_text(text, encoding="utf-8")

    def current(self) -> Note:
        """The note you were last on, else the most recently edited, else a fresh one."""
        note_id = self._state().get("current")
        note = self.get(note_id) if note_id else None
        if note:
            return note
        existing = self.notes()
        if existing:
            latest = max(existing, key=lambda n: n.path.stat().st_mtime)
            self.set_current(latest.id)
            return latest
        return self.new()

    def set_current(self, note_id: str) -> None:
        state = self._state()
        state["current"] = note_id
        self._save_state(state)

    def toggle_lock(self, note: Note) -> bool:
        state = self._state()
        locked = set(state.get("locked", []))
        locked ^= {note.id}
        state["locked"] = sorted(locked)
        self._save_state(state)
        return note.id in locked

    def delete(self, note: Note) -> None:
        """Move to the macOS Trash (recoverable) rather than unlinking."""
        trash = Path.home() / ".Trash"
        if trash.is_dir():
            dest = trash / note.id
            if dest.exists():
                dest = trash / f"{note.path.stem} {datetime.now():%H%M%S}.md"
            shutil.move(str(note.path), dest)
        else:
            note.path.unlink(missing_ok=True)
        state = self._state()
        state["locked"] = [i for i in state.get("locked", []) if i != note.id]
        if state.get("current") == note.id:
            state.pop("current")
        self._save_state(state)

    def drop_if_empty(self, note: Note) -> bool:
        """Blank notes aren't worth keeping; remove them quietly."""
        if note.path.exists() and not note.read().strip():
            note.path.unlink()
            return True
        return False
