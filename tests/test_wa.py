"""The wa look and AI organize."""
import json

import pytest
from textual import events
from textual.widgets import TextArea

from nori_term import look, organize
from nori_term.app import Nori
from nori_term.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".Trash").mkdir()
    return Store(tmp_path / "notes")


# ---- look ------------------------------------------------------------------
def test_look_comes_from_the_terminal_wa_label():
    hc = json.dumps({"labels": {"wa.theme": "custom:wa-modern-night", "herdr.space": "x"}})
    assert look.look_from_hc(hc) == "wa-modern-night"
    assert look.look_from_hc(json.dumps({"terminal": {"labels": {"wa.theme": "custom:wa-traditional"}}})) == "wa-traditional"


def test_unknown_or_missing_label_means_no_wa_look():
    assert look.look_from_hc(json.dumps({"labels": {"wa.theme": "custom:batman"}})) is None
    assert look.look_from_hc(json.dumps({"labels": {}})) is None
    assert look.look_from_hc("not json") is None


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("NORI_THEME", "wa-traditional-night")
    assert look.current_look() == "wa-traditional-night"


def test_four_themes_with_the_wa_palettes():
    themes = {t.name: t for t in look.themes()}
    assert set(themes) == {"wa-traditional", "wa-traditional-night", "wa-modern", "wa-modern-night"}
    assert themes["wa-traditional-night"].background.upper() == "#1A1514"
    assert themes["wa-modern"].dark is False and themes["wa-modern-night"].dark is True


# ---- when to organize ----------------------------------------------------------
def test_short_pastes_are_left_alone():
    assert not organize.should_organize("a url https://x.com")
    assert not organize.should_organize("two\nlines")


def test_tables_and_longer_text_get_organized():
    assert organize.should_organize("name\tqty\tprice\napples\t3\t1.20\npears\t5\t0.90")
    assert organize.should_organize("Bank call notes " * 25)


def test_already_structured_markdown_is_left_alone():
    assert not organize.should_organize("| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |")
    assert not organize.should_organize("# Plan\n- one\n- two\n- three")


# ---- output cleanup -------------------------------------------------------------
def test_pipe_tables_are_aligned_for_a_monospace_page():
    md = "# Fruit\n\n| name | qty |\n|---|---|\n| apples | 3 |\n| kiwi | 12 |\n\nafter"
    out = organize.align_tables(md)
    rows = out.splitlines()[2:6]
    assert len({len(r) for r in rows}) == 1, rows
    assert rows[1].startswith("| ---")
    assert out.endswith("after")


def test_model_output_is_unwrapped_from_code_fences():
    assert organize.clean("```markdown\n# T\n\ntext\n```") == "# T\n\ntext"


# ---- the paste, end to end with a fake organizer --------------------------------
TABLE = "name\tqty\napples\t3\npears\t5"


async def test_big_paste_is_replaced_by_the_organized_version_and_undo_restores_it(store, monkeypatch):
    seen = {}

    def fake(text, new_note):
        seen["args"] = (text, new_note)
        return "# Fruit stock\n\n| name | qty |\n|---|---|\n| apples | 3 |\n| pears | 5 |"

    monkeypatch.setattr(organize, "run", fake)
    app = Nori(store)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor", TextArea)
        editor.post_message(events.Paste(TABLE))
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert seen["args"] == (TABLE, True)
        await pilot.pause(0.6)                      # past the autosave
        assert "ctrl+z" in str(app.query_one("#status").render())
        assert editor.text.startswith("# Fruit stock")
        assert "| apples | 3     |" in editor.text or "| apples | 3   |" in editor.text
        editor.undo()
        await pilot.pause()
        assert editor.text == TABLE


async def test_text_typed_over_the_paste_meanwhile_is_never_overwritten(store, monkeypatch):
    app = Nori(store)

    def slow(text, new_note):
        app.call_from_thread(lambda: app.query_one("#editor", TextArea).insert("!"))
        return "# Organized"

    monkeypatch.setattr(organize, "run", slow)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor", TextArea)
        editor.post_message(events.Paste(TABLE))
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "# Organized" not in editor.text and TABLE in editor.text


async def test_failed_organize_keeps_the_paste(store, monkeypatch):
    monkeypatch.setattr(organize, "run", lambda text, new_note: None)
    app = Nori(store)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor", TextArea)
        editor.post_message(events.Paste(TABLE))
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert editor.text == TABLE


async def test_small_paste_never_calls_the_ai(store, monkeypatch):
    monkeypatch.setattr(organize, "run", lambda *a: pytest.fail("called the AI for a small paste"))
    app = Nori(store)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor", TextArea)
        editor.post_message(events.Paste("hello"))
        await pilot.pause()
        await app.workers.wait_for_complete()
        assert editor.text == "hello"
