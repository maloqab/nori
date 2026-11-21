"""Agents write to Nori only when Miteb asks: `nori --add` and `nori --list`, and an open Nori picks up
what was written to its note from outside instead of saving over it."""
import io

import pytest
from textual.widgets import TextArea

from nori_term import cli
from nori_term.app import Nori
from nori_term.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".Trash").mkdir()
    monkeypatch.setenv("NORI_DIR", str(tmp_path / "notes"))
    return Store(tmp_path / "notes")


def run(monkeypatch, capsys, *args, stdin=""):
    monkeypatch.setattr("sys.argv", ["nori", *args])
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    try:
        cli.main()
        code = 0
    except SystemExit as e:
        code = e.code or 0
    out = capsys.readouterr()
    return code, out.out + out.err


# ---- nori --add ---------------------------------------------------------------------
def test_add_makes_a_new_titled_note_from_stdin(store, monkeypatch, capsys):
    current = store.current()
    code, out = run(monkeypatch, capsys, "--add", "--title", "Agent tests", stdin="- Sentinel\n- QA\n")
    assert code == 0
    new = [n for n in store.notes() if n.id != current.id]
    assert len(new) == 1 and new[0].read() == "# Agent tests\n\n- Sentinel\n- QA\n"
    assert store.current().id == current.id                      # Miteb's open note stays his
    assert "Agent tests" in out and str(new[0].path) in out


def test_add_takes_text_after_the_options_too(store, monkeypatch, capsys):
    code, _ = run(monkeypatch, capsys, "--add", "call the bank at 3")
    assert code == 0
    assert any(n.read() == "call the bank at 3\n" for n in store.notes())


def test_add_to_appends_to_the_note_named(store, monkeypatch, capsys):
    note = store.new("# Groceries\n\n- milk\n", make_current=False)
    store.new("# Plans\n", make_current=False)
    code, out = run(monkeypatch, capsys, "--add", "--to", "groceries", stdin="- eggs\n")
    assert code == 0
    assert note.read() == "# Groceries\n\n- milk\n\n- eggs\n"
    code, _ = run(monkeypatch, capsys, "--add", "--to", note.id, "--title", "Later", stdin="- rice")
    assert note.read() == "# Groceries\n\n- milk\n\n- eggs\n\n### Later\n\n- rice\n"


def test_add_to_an_unknown_or_ambiguous_note_writes_nothing(store, monkeypatch, capsys):
    store.new("# Trip plan\n", make_current=False)
    store.new("# Work plan\n", make_current=False)
    before = {n.id: n.read() for n in store.notes()}
    code, out = run(monkeypatch, capsys, "--add", "--to", "plan", stdin="x")
    assert code == 1 and "Trip plan" in out and "Work plan" in out
    code, out = run(monkeypatch, capsys, "--add", "--to", "nothing like it", stdin="x")
    assert code == 1
    assert {n.id: n.read() for n in store.notes()} == before
    code, _ = run(monkeypatch, capsys, "--add", "--to", "work plan", stdin="x")   # exact title wins
    assert code == 0


def test_add_with_no_text_fails(store, monkeypatch, capsys):
    code, _ = run(monkeypatch, capsys, "--add", "--title", "Empty", stdin="  \n")
    assert code == 1


def test_list_shows_file_and_title(store, monkeypatch, capsys):
    note = store.new("# Groceries\n\n- milk\n", make_current=False)
    code, out = run(monkeypatch, capsys, "--list")
    assert code == 0 and f"{note.id}  ·  Groceries" in out


def test_a_quick_note_starting_with_add_is_still_a_quick_note(store, monkeypatch, capsys):
    code, _ = run(monkeypatch, capsys, "add", "eggs")
    assert any(n.read() == "add eggs\n" for n in store.notes())


# ---- an open Nori and its note changing outside ---------------------------------------
async def test_open_nori_shows_what_an_agent_added_and_does_not_save_over_it(store):
    note = store.current()
    store.save(note, "# Groceries\n\n- milk\n")
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.pause()
        note.path.write_text("# Groceries\n\n- milk\n\n- eggs\n")
        app._sync_disk()
        await pilot.pause()
        assert app.query_one("#editor", TextArea).text.endswith("- eggs\n")
        await pilot.press("escape")
    assert note.read() == "# Groceries\n\n- milk\n\n- eggs\n"


async def test_typing_and_an_agent_adding_at_the_end_keeps_both(store):
    note = store.current()
    store.save(note, "# Groceries\n\n- milk\n")
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.query_one("#editor", TextArea)
        editor.insert("Shopping: ", (0, 2))                      # Miteb types, not saved yet
        note.path.write_text("# Groceries\n\n- milk\n\n- eggs\n")
        app.save_now()
        await pilot.pause()
    assert note.read() == "# Shopping: Groceries\n\n- milk\n\n- eggs\n"


async def test_a_different_change_outside_is_kept_as_its_own_note(store):
    note = store.current()
    store.save(note, "# Groceries\n\n- milk\n")
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#editor", TextArea).insert("Shopping: ", (0, 2))
        note.path.write_text("# Groceries\n\n- oat milk\n")      # rewritten elsewhere
        app.save_now()
        await pilot.pause()
    assert note.read() == "# Shopping: Groceries\n\n- milk\n"
    assert any(n.read() == "# Groceries\n\n- oat milk\n" for n in store.notes())


async def test_a_note_briefly_missing_or_empty_on_disk_is_not_picked_up(store):
    note = store.current()
    store.save(note, "# Groceries\n\n- milk\n")
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.pause()
        note.path.write_text("")                                 # a sync tool mid-write
        app._sync_disk()
        note.path.unlink()
        app._sync_disk()
        await pilot.press("escape")
    assert note.read() == "# Groceries\n\n- milk\n"


async def test_a_note_with_a_table_written_differently_takes_an_edit_from_elsewhere(store):
    note = store.current()
    store.save(note, "# Costs\n\n| Item | Price |\n| --- | --- |\n| tea | 2 |\n")
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.pause()
        note.path.write_text("# Costs\n\n| Item | Price |\n| --- | --- |\n| tea | 3 |\n")   # synced edit
        app._sync_disk()
        await pilot.press("escape")
    assert len(store.notes()) == 1                               # no "changed elsewhere" copy
    assert "| tea | 3 |" in note.read()


def test_add_to_with_a_title_matches_the_notes_own_section_level(store, monkeypatch, capsys):
    note = store.new("# Review\n\n## Tests\n\n- one\n\n## Rules\n\n- two\n", make_current=False)
    run(monkeypatch, capsys, "--add", "--to", note.id, "--title", "Follow ups", stdin="- ask Talal")
    assert note.read().endswith("## Rules\n\n- two\n\n## Follow ups\n\n- ask Talal\n")
