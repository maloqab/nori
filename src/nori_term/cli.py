"""`nori` opens the notepad; `nori some words` saves a one-line note; `nori --add` is how an agent
writes a note Miteb asked for."""

from __future__ import annotations

import argparse
import sys

from .store import Store

USAGE = """nori: a quiet notepad that saves as you type

  nori              open the notepad (picks up your last note)
  nori <words...>   save a quick note without opening anything
  nori --where      show where notes are saved
  nori --list       list notes: file name and title, newest first

  nori --add [--title T] [text...]     new note from the text (or stdin)
  nori --add --to NOTE [--title T]     add the text to the end of NOTE
                                       (its file name or title)

in the notepad:  esc close · ctrl+n new note · ctrl+o your notes
"""


def _fail(message: str) -> None:
    print(f"nori: {message}", file=sys.stderr)
    raise SystemExit(1)


def _add(argv: list[str]) -> None:
    p = argparse.ArgumentParser(prog="nori --add", add_help=False)
    p.add_argument("--title")
    p.add_argument("--to")
    p.add_argument("text", nargs="*")
    a = p.parse_args(argv)
    text = (" ".join(a.text) if a.text else sys.stdin.read()).strip("\n")
    if not text.strip():
        _fail("nothing to save: put the text after the options or pipe it in")
    store = Store()
    if a.to:
        found = store.find(a.to)
        if len(found) != 1:
            names = "\n".join(f"  {n.id}  ·  {n.heading}" for n in found) or "  (no note matches)"
            _fail(f"--to {a.to!r} must name one note; matches:\n{names}\nuse its file name")
        note = found[0]
        if a.title:
            text = f"### {a.title}\n\n{text}"
        old = note.read().rstrip("\n")
        store.save(note, (old + "\n\n" if old else "") + text + "\n")
    else:
        if a.title:
            text = f"# {a.title}\n\n{text}"
        note = store.new(text + "\n", make_current=False)
    print(f"saved · {note.title} · {note.path}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(USAGE)
        return
    if args and args[0] == "--where":
        print(Store().root)
        return
    if args and args[0] == "--list":
        for n in Store().notes():
            print(f"{n.id}  ·  {n.heading}")
        return
    if args and args[0] == "--add":
        _add(args[1:])
        return
    if args:
        note = Store().new(" ".join(args) + "\n", make_current=False)
        print(f"saved · {note.title}")
        return

    from .app import Nori  # imported lazily so quick notes stay instant

    Nori().run()


if __name__ == "__main__":
    main()
