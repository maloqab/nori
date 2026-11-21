"""The full-screen notepad."""

from __future__ import annotations

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Input, ListItem, ListView, Static, TextArea

from . import look, organize
from .store import Note, Store

SAVE_DELAY = 0.4  # seconds of quiet typing before writing to disk
LOOK_EVERY = 3.0  # seconds between checks of the terminal's wa look (it follows day/night)


class Page(TextArea):
    """The editor. A paste lands as-is, then the app may organize it."""

    async def _on_paste(self, event: events.Paste) -> None:
        # Textual runs every class's handler in turn; this one does the insert, so stop TextArea's.
        event.prevent_default()
        event.stop()
        if self.read_only:
            return
        was_empty = not self.text.strip()
        start = min(self.selection.start, self.selection.end)
        if result := self._replace_via_keyboard(event.text, *self.selection):
            self.move_cursor(result.end_location)
            self.focus()
            end = result.end_location
            self.app.pasted(self.get_text_range(start, end), start, end, was_empty)  # type: ignore[attr-defined]


class History(ListView):
    """Sidebar list. Single keys only work here, never in the editor."""

    BINDINGS = [
        Binding("l", "lock", "lock"),
        Binding("d", "delete", "delete"),
        Binding("slash", "search", "search"),
    ]

    def action_lock(self) -> None:
        self.app.lock_highlighted()  # type: ignore[attr-defined]

    def action_delete(self) -> None:
        self.app.delete_highlighted()  # type: ignore[attr-defined]

    def action_search(self) -> None:
        self.app.query_one("#search", Input).focus()


class NoteItem(ListItem):
    def __init__(self, note: Note, active: bool) -> None:
        mark = "● " if note.locked else "  "
        when = note.modified.strftime("%b %d")
        super().__init__(Static(f"{mark}{note.title}\n  [dim]{when}[/]", markup=True))
        self.note = note
        if active:
            self.add_class("active")


class Nori(App):
    TITLE = "nori"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen { background: $background; }
    #page { width: 1fr; align-horizontal: center; }
    #status, #editor, #hints { width: 100%; max-width: 88; }
    #status { height: 1; padding: 0 2; color: $text-muted; margin-top: 1; }
    #editor {
        height: 1fr; border: none; padding: 1 2; background: $background;
    }
    #editor:focus { border: none; background-tint: transparent; }
    #editor .text-area--cursor-line { background: transparent; }
    #hints { height: 1; padding: 0 2; color: $text-disabled; margin-bottom: 1; }

    #sidebar {
        display: none; width: 34; padding: 1 1 1 2;
        border-right: vkey $surface-lighten-2;
    }
    #sidebar.open { display: block; }
    #search { border: none; height: 1; padding: 0 1; margin-bottom: 1; background: $surface; }
    #history { background: transparent; height: 1fr; }
    #history > ListItem { padding: 0 0 1 0; background: transparent; }
    #history > ListItem.active { color: $accent; }
    #history:focus > ListItem.-highlight { background: $surface-lighten-1; }
    #sidebar-hints { height: 2; color: $text-disabled; }
    """

    BINDINGS = [
        Binding("escape", "escape", "close", priority=True),
        Binding("ctrl+o", "toggle_history", "history", priority=True),
        Binding("ctrl+n", "new_note", "new", priority=True),
    ]

    def __init__(self, store: Store | None = None) -> None:
        super().__init__()
        self.store = store or Store()
        self.note = self.store.current()
        self._save_timer: Timer | None = None
        self._next_status = "saved"   # what the status says after the next save ("organized · …" once)

    # ---- layout -------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Input(placeholder="search notes", id="search")
                yield History(id="history")
                yield Static("enter open · l lock · d delete\n/ search · esc back", id="sidebar-hints")
            with Vertical(id="page"):
                yield Static(id="status")
                yield Page(
                    self.note.read(),
                    id="editor",
                    soft_wrap=True,
                    show_line_numbers=False,
                    tab_behavior="indent",
                    placeholder="write your thoughts...",
                )
                yield Static("esc close · ctrl+n new · ctrl+o notes", id="hints")

    def on_mount(self) -> None:
        for theme in look.themes():
            self.register_theme(theme)
        self._apply_look(look.current_look())
        self.set_interval(LOOK_EVERY, self._check_look)
        editor = self.query_one("#editor", TextArea)
        editor.focus()
        editor.move_cursor(editor.document.end)
        self._set_status("saved")

    # ---- the wa look ---------------------------------------------------
    def _apply_look(self, name: str | None) -> None:
        if name and name != self.theme:
            self.theme = name

    def _check_look(self) -> None:
        self.run_worker(self._fetch_look, thread=True, group="look", exclusive=True)

    def _fetch_look(self) -> None:
        name = look.current_look()
        self.call_from_thread(self._apply_look, name)

    # ---- AI organize ----------------------------------------------------
    def pasted(self, text: str, start, end, was_empty: bool) -> None:
        if not (organize.enabled() and organize.should_organize(text)):
            return
        editor = self.query_one("#editor", TextArea)
        snapshot = editor.text
        self._set_status("organizing…")

        def work() -> None:
            result = organize.run(text, was_empty)
            self.call_from_thread(self._organized, result, start, end, snapshot)

        self.run_worker(work, thread=True, group="organize")

    def _organized(self, result: str | None, start, end, snapshot: str) -> None:
        editor = self.query_one("#editor", TextArea)
        if result is None:
            self._set_status("kept as pasted")
            return
        if editor.text != snapshot:          # typed meanwhile: never overwrite their words
            self._set_status("kept as pasted")
            return
        editor.history.checkpoint()          # so Ctrl+Z brings the paste back, not nothing
        done = editor.replace(organize.align_tables(result), start, end)
        editor.history.checkpoint()
        editor.move_cursor(done.end_location)
        # the replace fires a change; its autosave shows this hint once instead of plain "saved"
        self._next_status = "organized  [dim]· ctrl+z for the original[/]"
        self.save_now()
        self._next_status = "organized  [dim]· ctrl+z for the original[/]"

    # ---- saving -------------------------------------------------------
    def _set_status(self, state: str) -> None:
        title = self.note.title if self.note.read().strip() else "new note"
        self.query_one("#status", Static).update(f"[$accent]筆[/]  {title}  [dim]· {state}[/]")

    @on(TextArea.Changed, "#editor")
    def _on_type(self) -> None:
        if self._save_timer:
            self._save_timer.stop()
        self._save_timer = self.set_timer(SAVE_DELAY, self.save_now)
        self._set_status("…")

    def save_now(self) -> None:
        if self._save_timer:
            self._save_timer.stop()
            self._save_timer = None
        self.store.save(self.note, self.query_one("#editor", TextArea).text)
        self._set_status(self._next_status)
        self._next_status = "saved"

    def _open(self, note: Note) -> None:
        """Save the current note, then switch the editor to another one."""
        self.save_now()
        if note.id != self.note.id:
            self.store.drop_if_empty(self.note)
        self.note = note
        self.store.set_current(note.id)
        editor = self.query_one("#editor", TextArea)
        editor.load_text(note.read())
        editor.move_cursor(editor.document.end)
        self._set_status("saved")

    # ---- actions ------------------------------------------------------
    def action_escape(self) -> None:
        sidebar = self.query_one("#sidebar")
        if sidebar.has_class("open"):
            self._close_history()
        else:
            self.save_now()
            self.store.drop_if_empty(self.note)
            self.exit()

    def action_new_note(self) -> None:
        if not self.query_one("#editor", TextArea).text.strip():
            self._close_history()
            return  # already on a blank note
        self.save_now()
        self._open(self.store.new())
        self._close_history()

    def action_toggle_history(self) -> None:
        if self.query_one("#sidebar").has_class("open"):
            self._close_history()
        else:
            self.save_now()
            self.query_one("#sidebar").add_class("open")
            self._refresh_history()
            self.query_one("#history", History).focus()

    def _close_history(self) -> None:
        self.query_one("#sidebar").remove_class("open")
        self.query_one("#search", Input).value = ""
        self.query_one("#editor", TextArea).focus()

    def _refresh_history(self, keep_index: int | None = None) -> None:
        history = self.query_one("#history", History)
        query = self.query_one("#search", Input).value.strip()
        history.clear()
        notes = self.store.notes(query)
        history.extend(NoteItem(n, n.id == self.note.id) for n in notes)
        if notes:
            history.index = min(keep_index or 0, len(notes) - 1)

    def _highlighted(self) -> NoteItem | None:
        item = self.query_one("#history", History).highlighted_child
        return item if isinstance(item, NoteItem) else None

    def lock_highlighted(self) -> None:
        if item := self._highlighted():
            locked = self.store.toggle_lock(item.note)
            self.notify("locked" if locked else "unlocked", timeout=1.5)
            self._refresh_history()

    def delete_highlighted(self) -> None:
        item = self._highlighted()
        if not item:
            return
        index = self.query_one("#history", History).index
        deleting_current = item.note.id == self.note.id
        self.store.delete(item.note)
        self.notify("moved to Trash", timeout=1.5)
        if deleting_current:
            self.note = self.store.current()
            editor = self.query_one("#editor", TextArea)
            editor.load_text(self.note.read())
            self._set_status("saved")
        self._refresh_history(index)

    @on(ListView.Selected, "#history")
    def _pick(self, event: ListView.Selected) -> None:
        if isinstance(event.item, NoteItem):
            self._open(event.item.note)
            self._close_history()

    @on(Input.Changed, "#search")
    def _search(self) -> None:
        self._refresh_history()

    @on(Input.Submitted, "#search")
    def _search_done(self) -> None:
        self.query_one("#history", History).focus()
