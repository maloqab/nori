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
