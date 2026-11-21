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


async def test_editing_the_pasted_text_meanwhile_keeps_it_as_pasted(store, monkeypatch):
    app = Nori(store)

    def slow(text, new_note):
        app.call_from_thread(lambda: app.query_one("#editor", TextArea).insert("!", (0, 2)))
        return "# Organized"

    monkeypatch.setattr(organize, "run", slow)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor", TextArea)
        editor.post_message(events.Paste(TABLE))
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "# Organized" not in editor.text and editor.text.startswith("na!me")


async def test_typing_after_the_paste_meanwhile_is_kept_and_the_paste_still_organized(store, monkeypatch):
    app = Nori(store)

    def slow(text, new_note):
        app.call_from_thread(lambda: app.query_one("#editor", TextArea).insert("\nmy own line"))
        return "# Organized"

    monkeypatch.setattr(organize, "run", slow)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor", TextArea)
        editor.post_message(events.Paste(TABLE))
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert editor.text == "# Organized\nmy own line"


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


# ---- tables in code (no AI, lossless at any size) -----------------------------
CSV40 = "date,ticker,open,close\n" + "\n".join(f"2026-11-{d:02d},NBK,{1 + d / 1000:.3f},{1 + d / 990:.3f}" for d in range(1, 41))


def test_csv_becomes_a_table_with_every_row():
    out = organize.table_markdown(CSV40)
    rows = [l for l in out.splitlines() if l.startswith("|")]
    assert len(rows) == 42                                   # header, separator, 40 rows
    assert "| 2026-11-40 | NBK" in out
    assert organize.keeps_the_numbers(CSV40, out)


def test_quoted_csv_commas_stay_in_their_cell():
    out = organize.table_markdown('name,city\n"Zain, Group",Kuwait\nNBK,Kuwait\nKFH,Kuwait')
    assert "| Zain, Group |" in out


def test_tab_and_space_aligned_columns_become_tables():
    tsv = "name\tqty\napples\t3\npears\t5"
    assert "| apples | 3   |" in organize.table_markdown(tsv)
    spaced = ("Company    Ticker   Close\nNational Bank of Kuwait   NBK   1.012\n"
              "Kuwait Finance House  KFH   0.789\nZain   ZAIN   0.468")
    out = organize.table_markdown(spaced)
    assert "| National Bank of Kuwait | NBK    | 1.012 |" in out


def test_lines_around_the_table_are_kept_as_text():
    text = "close prices:\nname\tclose\nNBK\t1.012\nKFH\t0.789\nprices in KWD"
    out = organize.table_markdown(text)
    assert out.startswith("close prices:\n\n|") and out.endswith("\n\nprices in KWD")


def test_prose_is_not_a_table():
    assert organize.table_markdown("we met on monday, then tuesday, and agreed on prices, terms, dates") is None
    assert organize.table_markdown("one line\nanother line\nthird line here") is None


def test_tables_are_titled_by_the_ai_but_built_by_code(monkeypatch):
    calls = []
    monkeypatch.setattr(organize, "_claude", lambda system, text: calls.append(system) or "# NBK daily prices")
    out = organize.run(CSV40, True)
    assert out.startswith("# NBK daily prices\n\n|") and out.count("\n| 2026-11-") == 40
    assert "title" in calls[0].lower() and len(calls) == 1


def test_a_table_still_lands_when_the_title_call_fails(monkeypatch):
    monkeypatch.setattr(organize, "_claude", lambda system, text: None)
    assert organize.run(CSV40, True).startswith("| date")


# ---- Ctrl+T: tidy on demand ------------------------------------------------------
async def test_ctrl_t_tidies_the_whole_note(store, monkeypatch):
    seen = {}
    monkeypatch.setattr(organize, "run", lambda text, new_note: seen.update(args=(text, new_note)) or "# Tidy\n\nok")
    store.save(store.current(), "messy words")
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+t")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert seen["args"] == ("messy words", True)
        assert app.query_one("#editor", TextArea).text == "# Tidy\n\nok"


async def test_ctrl_t_tidies_just_the_selection(store, monkeypatch):
    seen = {}
    monkeypatch.setattr(organize, "run", lambda text, new_note: seen.update(args=(text, new_note)) or "### Bit")
    store.save(store.current(), "keep this\nmessy bit")
    app = Nori(store)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor", TextArea)
        editor.selection = editor.selection.__class__((1, 0), (1, 9))
        await pilot.press("ctrl+t")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert seen["args"] == ("messy bit", False)
        assert editor.text == "keep this\n### Bit"


# ---- Markdown colored in the wa palette ---------------------------------------
def test_each_look_has_an_editor_theme_with_accent_headings():
    t = look.text_area_theme("wa-traditional-night")
    assert t.name == "wa-traditional-night"
    assert t.syntax_styles["heading"].color.triplet.hex.upper() == "#C4553C"
    assert t.syntax_styles["punctuation.special"].color.triplet.hex.upper() == "#A59584"


async def test_the_page_is_markdown_and_follows_the_look(store, monkeypatch):
    monkeypatch.setenv("NORI_THEME", "wa-modern-night")
    app = Nori(store)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor", TextArea)
        assert editor.language == "markdown"
        assert app.theme == "wa-modern-night" and editor.theme == "wa-modern-night"
        app._apply_look("wa-traditional")
        await pilot.pause()
        assert editor.theme == "wa-traditional"
