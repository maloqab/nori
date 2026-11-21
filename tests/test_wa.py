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
        assert editor.text.startswith("# Fruit stock\n\n┌")          # shown as a box table
        assert "│ apples │ 3   │" in editor.text
        app.save_now()
        assert "| apples | 3 |" in app.note.read()                    # the file keeps Markdown
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
    assert look.heading_style("wa-traditional-night", 2).color.triplet.hex.upper() == "#C4553C"
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


# ---- box tables ---------------------------------------------------------------------
SERVER = """# Server Requirements Request

| Item | Ask |
|---|---|
| Size | 4 vCPU, 8 GB memory (same as staging); about 80 GB disk (my estimate) |
| System | Ubuntu 24.04, which is what the setup script is written for |
| Access | SSH for you, as a normal user with sudo; no root login |
| Outbound (HTTPS only) | openrouter.ai, slack.com and *.slack.com, api.agentmail.to, api.atlassian.com, github.com |
| Backups | Daily, kept at least 7 days |"""

CLAUDE_BOX = """┌──────────────────────┬─────────────────────────────────────┐
│         Item         │                 Ask                 │
├──────────────────────┼─────────────────────────────────────┤
│ Size                 │ 4 vCPU, 8 GB memory (same as        │
│                      │ staging); about 80 GB disk          │
├──────────────────────┼─────────────────────────────────────┤
│ Backups              │ Daily, kept at least 7 days         │
└──────────────────────┴─────────────────────────────────────┘"""


def test_a_box_table_pasted_from_claude_code_is_read_whole_and_titled(monkeypatch):
    monkeypatch.setattr(organize, "_claude", lambda system, text: "Server requirements")
    out = organize.run(CLAUDE_BOX, True)
    assert out.startswith("# Server requirements\n\n| Item | Ask |")
    assert "| Size | 4 vCPU, 8 GB memory (same as staging); about 80 GB disk |" in out
    assert organize.should_organize(CLAUDE_BOX)


async def test_a_note_with_a_table_opens_as_a_box_and_saves_as_markdown(store):
    store.save(store.current(), SERVER)
    app = Nori(store)
    async with app.run_test(size=(90, 40)) as pilot:
        await pilot.pause()
        text = app.query_one("#editor", TextArea).text
        assert "┌" in text and "| Size" not in text
        assert max(len(l) for l in text.splitlines()) <= 84
        app.save_now()
        assert app.note.read() .startswith("# Server Requirements Request\n\n| Item | Ask |")


async def test_ctrl_t_on_an_already_organized_note_refits_it_without_the_ai(store, monkeypatch):
    monkeypatch.setattr(organize, "_claude", lambda *a: pytest.fail("called the AI on organized Markdown"))
    store.save(store.current(), SERVER)
    app = Nori(store)
    async with app.run_test(size=(90, 40)) as pilot:
        await pilot.press("ctrl+t")
        await app.workers.wait_for_complete()
        await pilot.pause()
        text = app.query_one("#editor", TextArea).text
        assert text.startswith("# Server Requirements Request\n\n┌") and "│ Size" in text


KEY_VALUE = """Server requirements - what we need from IT
Size: 4 vCPU, 8 GB memory (same as staging); about 80 GB disk (my estimate)
System: Ubuntu 24.04, which is what the setup script is written for
Access: SSH for you, as a normal user with sudo; no root login
Inbound: Nothing except SSH; the agents open their own connections out
Backups: Daily, kept at least 7 days"""


def test_label_value_lines_become_a_two_column_table_not_csv():
    import re
    out = re.sub(r" {2,}", " ", organize.table_markdown(KEY_VALUE))     # ignore column padding
    assert out.startswith("Server requirements - what we need from IT\n\n| Item")
    assert "| Size | 4 vCPU, 8 GB memory (same as staging); about 80 GB disk (my estimate) |" in out
    assert out.count("\n| ") == 7                                   # header, rule, 5 rows


def test_urls_times_and_a_lone_label_are_not_label_value_tables():
    assert organize.table_markdown("see https://x.com\nmeet at 10:30 today\nNote: call back later") is None


def test_real_csv_still_is():
    assert organize.table_markdown("name,qty,price\napples,3,1.20\npears,5,0.90\nkiwi,12,0.40").count("\n| ") == 4


def test_the_model_is_told_not_to_escape_characters():
    assert "escape" in organize.SYSTEM.lower()


WIDE = """# Agents

| Agent | Own context? | Own permissions? | Own trigger and human owner? | Verdict |
|---|---|---|---|---|
| Demand | Requester emails and attachments | Emails requesters; writes intake records | A new email; Fay screens | ✅ Separate. Live today. |
| Product Owner | Approved request, Zain pages, the mock-up | Writes PRD and story pages | Discovery approved; you review | ✅ Separate. In testing. Already does the test case writing, which is the right job |"""


def _widest(app):
    from rich.cells import cell_len
    return max(cell_len(l) for l in app.query_one("#editor", TextArea).text.splitlines())


async def test_tables_redraw_when_the_pane_gets_narrower(store):
    store.save(store.current(), WIDE)
    app = Nori(store)
    async with app.run_test(size=(130, 60)) as pilot:
        await pilot.pause()
        assert _widest(app) <= app.query_one("#editor", TextArea).wrap_width
        await pilot.resize_terminal(70, 60)
        await pilot.pause(0.5)
        assert _widest(app) <= app.query_one("#editor", TextArea).wrap_width
        app.save_now()
        assert "| Demand | Requester emails and attachments |" in app.note.read()   # file unchanged in meaning


async def test_a_tall_table_still_fits_once_the_scrollbar_appears(store):
    store.save(store.current(), WIDE)
    app = Nori(store)
    async with app.run_test(size=(80, 12)) as pilot:          # short pane: the table needs a scrollbar
        await pilot.pause(0.5)
        assert _widest(app) <= app.query_one("#editor", TextArea).wrap_width


# ---- the page: no scrollbar, headings that look like headings --------------------------
async def test_the_page_has_no_scrollbar_even_when_the_note_is_long(store):
    store.save(store.current(), "\n".join(f"line {i}" for i in range(200)))
    app = Nori(store)
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        editor = app.query_one("#editor", TextArea)
        assert editor.max_scroll_y > 0                                   # it still scrolls
        assert editor.scrollable_content_region.width == editor.region.width - 4   # only the padding, no bar


HEADINGS = "# Title\n\nbody\n\n## Sub\n\n### Small\n\n```sh\n# comment\n```\n\nend"


def _shown(editor, row):
    """What the page shows for a document row (rows don't wrap or scroll in these tests)."""
    return editor.render_line(row).text.rstrip()


def _style_of(editor, row, word):
    strip = editor.render_line(row)
    x = 0
    for seg in strip:
        if word in seg.text:
            return seg.style
        x += len(seg.text)
    raise AssertionError(f"{word!r} not on row {row}: {strip.text!r}")


async def test_heading_marks_are_hidden_except_on_the_line_being_edited(store, monkeypatch):
    monkeypatch.setenv("NORI_THEME", "wa-traditional-night")
    store.save(store.current(), HEADINGS)
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.query_one("#editor", TextArea)
        assert _shown(editor, 0) == "Title"
        assert _shown(editor, 4) == "Sub"
        assert _shown(editor, 6) == "Small"
        assert _shown(editor, 9) == "# comment"                          # code, not a heading
        editor.move_cursor((4, 6))
        await pilot.pause()
        assert _shown(editor, 4) == "## Sub"                             # editing it: marks back
        assert _shown(editor, 0) == "Title"
        app.save_now()
        assert app.note.read() == HEADINGS                               # the file keeps the marks


async def test_heading_levels_look_different(store, monkeypatch):
    monkeypatch.setenv("NORI_THEME", "wa-traditional-night")
    store.save(store.current(), HEADINGS)
    app = Nori(store)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.query_one("#editor", TextArea)
        h1, h2, h3 = (_style_of(editor, r, w) for r, w in ((0, "Title"), (4, "Sub"), (6, "Small")))
        assert h1.bold and h2.bold and h3.bold
        assert h1.color.triplet.hex.upper() == "#C4553C" == h2.color.triplet.hex.upper()
        assert h3.color.triplet.hex.upper() == "#EFE6D8"                 # body text color
        assert h1.underline and not h2.underline


async def test_clicking_a_heading_lands_on_the_letter_clicked(store):
    store.save(store.current(), HEADINGS)
    app = Nori(store)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        editor = app.query_one("#editor", TextArea)
        left, top = editor.content_region.x - editor.region.x, editor.content_region.y - editor.region.y
        await pilot.click("#editor", offset=(left + 1, top + 4))         # the "u" of a shown "Sub"
        await pilot.pause()
        assert editor.cursor_location == (4, 4)
