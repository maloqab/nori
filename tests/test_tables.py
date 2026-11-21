"""Box tables: how Nori shows tables (like Claude Code), while the note file keeps Markdown pipe tables."""
from nori_term import tables

HEADER = ["Moment", "What saves the session to the vault"]
ROWS = [["10 minutes after the agent's last reply", "The quiet-timer handoff (the Stop hook). Long before the 1-hour mark."],
        ["Session closed", "The SessionEnd hook"]]


def test_box_fits_the_width_and_wraps_cells_inside_their_column():
    out = tables.render(HEADER, ROWS, 60)
    lines = out.splitlines()
    assert lines[0].startswith("┌") and lines[0].endswith("┐") and "┬" in lines[0]
    assert lines[-1].startswith("└") and lines[-1].endswith("┘")
    assert all(len(l) == len(lines[0]) <= 60 for l in lines)            # a clean rectangle, never wider
    assert sum(l.startswith("├") for l in lines) == 2                    # under the header, between rows
    assert "│ Session closed" in out


def test_a_narrow_table_keeps_its_natural_width():
    out = tables.render(["a", "b"], [["1", "2"]], 80)
    assert out.splitlines()[0] == "┌───┬───┐"


def test_parse_reads_back_wrapped_cells_whole():
    box = tables.render(HEADER, ROWS, 50)
    header, rows = tables.parse(box.splitlines())
    assert header == HEADER and rows == ROWS


def test_parse_reads_a_table_pasted_from_claude_code():
    pasted = """┌──────────────────────┬─────────────────────────────────────┐
│         Item         │                 Ask                 │
├──────────────────────┼─────────────────────────────────────┤
│ Size                 │ 4 vCPU, 8 GB memory (same as        │
│                      │ staging); about 80 GB disk          │
├──────────────────────┼─────────────────────────────────────┤
│ Backups              │ Daily, kept at least 7 days         │
└──────────────────────┴─────────────────────────────────────┘"""
    header, rows = tables.parse(pasted.splitlines())
    assert header == ["Item", "Ask"]
    assert rows == [["Size", "4 vCPU, 8 GB memory (same as staging); about 80 GB disk"], ["Backups", "Daily, kept at least 7 days"]]


def test_note_file_keeps_markdown_and_the_page_shows_boxes_round_trip():
    md = "# Vault\n\n| Moment | What saves it |\n|---|---|\n| Session closed | The SessionEnd hook |\n\nafter"
    shown = tables.to_display(md, 60)
    assert "┌" in shown and "| Moment" not in shown
    assert shown.startswith("# Vault\n\n┌") and shown.endswith("┘\n\nafter")
    back = tables.to_markdown(shown)
    assert back.startswith("# Vault\n\n| Moment") and "| Session closed | The SessionEnd hook" in back
    assert back.endswith("\n\nafter")
    assert tables.to_display(back, 60) == shown


def test_pipes_inside_cells_survive():
    md = "| cmd | note |\n|---|---|\n| a \\| b | pipe |"
    assert "a \\| b" in tables.to_markdown(tables.to_display(md, 40))


def test_a_broken_box_is_left_as_text():
    broken = "┌────┬────┐\n│ a  │\n└────┘"
    assert tables.to_markdown(broken) == broken


def test_text_without_tables_is_untouched():
    text = "# Title\n\n- one\n- two"
    assert tables.to_display(text, 40) == text and tables.to_markdown(text) == text
