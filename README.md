# 🌿 Nori — notes that flow with you, in your terminal

Type `nori` and a quiet, full-screen notepad opens. Just write. It saves as you type, with no modes, no save key and no editor to learn.

```sh
nori                 # open the notepad (picks up your last note)
nori bought milk     # save a quick note without opening anything
nori --where         # show where notes are saved
```

## Keys

| Key | What it does |
|---|---|
| just type | writes; saves automatically after a short pause |
| `esc` | close (next `nori` reopens the same note) |
| `ctrl+n` | new note |
| `ctrl+o` | your notes: `enter` open · `l` lock · `d` delete · `/` search · `esc` back |

Locked notes stay pinned at the top. Deleted notes go to the macOS Trash, so they can be recovered. Empty notes are discarded when you leave them.

## Where notes live

Each note is a plain Markdown file in `~/notes/`, so it works with Obsidian or any editor. Set `NORI_DIR` to use a different folder, such as one inside an Obsidian vault:

```sh
export NORI_DIR=~/Obsidian/Nori
```

## Install

Needs [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/maloqab/nori
```

For development:

```sh
git clone https://github.com/maloqab/nori && cd nori
uv sync
uv tool install -e .   # `nori` now runs your working copy
uv run pytest
```

Built with [Textual](https://textual.textualize.io/).

## Also

Nori started as a Chrome extension: a glassy notepad overlay you summon on any page with `Option+W`. It lives at [maloqab/nori-chrome](https://github.com/maloqab/nori-chrome).

## License

[MIT](LICENSE)

## In Herdr (the wa look)

Inside Miteb's Herdr setup, Nori takes the look of the space it opens in (Traditional or Modern, day or
night) from its terminal's `wa.theme` label, and follows the day/night switch. `NORI_THEME=wa-modern-night`
forces one; outside Herdr it keeps Textual's default look.

## Organize a paste

Paste a messy table (copied from a web page, tab- or space-separated, or a box table copied from Claude
Code) or a wall of text, and Nori tidies it into Markdown a few seconds later: tables, lists, paragraphs, and a title that
fits (`#` on a new note, `###` when it's added to one). It never drops or invents content; if any number
from the paste is missing from the result, the paste stays as it was. Ctrl+Z brings the original back.
Short pastes are left alone; Ctrl+T tidies the selection, or the whole note, on demand. Clearly delimited
data (CSV, tab-separated, aligned columns) is turned into a table by code, so it's instant and lossless at
any size; the model only names it. Markdown is colored in the look's palette (accent headings, muted marks).
It runs `claude -p` (haiku by default, `NORI_AI_MODEL` to change it);
`NORI_AI=0` turns it off.

## Tables

Nori draws tables the way Claude Code does: box borders, cells that wrap inside their column, the table
fitted to the page. The note file keeps a plain Markdown pipe table, so Obsidian shows a real table too.
Ctrl+T redraws a note's tables for the current width.
