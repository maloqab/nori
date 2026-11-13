import pytest
from textual.widgets import TextArea

from nori_term.app import SAVE_DELAY, Nori
from nori_term.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))  # so delete goes to a fake ~/.Trash
    (tmp_path / ".Trash").mkdir()
    return Store(tmp_path / "notes")


# ---- store ---------------------------------------------------------------
def test_quick_note_does_not_become_current(store):
    first = store.current()
    store.new("bought milk\n", make_current=False)
    assert store.current().id == first.id


def test_locked_notes_sort_first_and_search_filters(store):
    a = store.new("alpha idea")
    b = store.new("beta plan")
    store.toggle_lock(a)
    assert [n.id for n in store.notes()] == [a.id, b.id]
    assert [n.id for n in store.notes("beta")] == [b.id]


def test_delete_moves_to_trash(store, tmp_path):
    n = store.new("bye")
    store.delete(n)
    assert not n.path.exists()
    assert (tmp_path / ".Trash" / n.id).exists()


def test_title_from_first_line(store):
    assert store.new("# Bank call\nfollow up").title == "Bank call"
    assert store.new("").title == "untitled"


# ---- app -----------------------------------------------------------------
async def test_typing_autosaves_and_esc_quits(store):
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.press(*"hello")
        await pilot.pause(SAVE_DELAY + 0.2)
        assert app.note.read() == "hello"
        await pilot.press("escape")
    assert store.current().read() == "hello"  # reopening picks it back up


async def test_esc_with_empty_note_leaves_nothing_behind(store):
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.press("escape")
    assert store.notes() == []


async def test_new_note_and_history_switching(store):
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.press(*"first")
        await pilot.press("ctrl+n")
        await pilot.press(*"second")
        await pilot.press("ctrl+o")  # open notes; newest highlighted first
        await pilot.press("down", "enter")  # pick the older one
        assert app.query_one("#editor", TextArea).text == "first"
        assert not app.query_one("#sidebar").has_class("open")
    assert sorted(n.read() for n in store.notes()) == ["first", "second"]


async def test_lock_and_delete_from_history(store):
    keep = store.new("keep me")
    store.new("delete me")
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+o")
        await pilot.press("d")  # newest = "delete me" (current)
        await pilot.pause()
        assert [n.read() for n in store.notes()] == ["keep me"]
        await pilot.press("l")
        assert store.get(keep.id).locked


async def test_letters_type_normally_in_editor(store):
    """l / d / slash are sidebar keys only; they must never trigger while writing."""
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.press("l", "d", "slash")
        await pilot.pause(SAVE_DELAY + 0.2)
    assert store.current().read() == "ld/"
