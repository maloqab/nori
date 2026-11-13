"""`nori` opens the notepad; `nori some words` saves a one-line note."""

from __future__ import annotations

import sys

from .store import Store

USAGE = """nori: a quiet notepad that saves as you type

  nori              open the notepad (picks up your last note)
  nori <words...>   save a quick note without opening anything
  nori --where      show where notes are saved

in the notepad:  esc close · ctrl+n new note · ctrl+o your notes
"""


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(USAGE)
        return
    if args and args[0] == "--where":
        print(Store().root)
        return
    if args:
        note = Store().new(" ".join(args) + "\n", make_current=False)
        print(f"saved · {note.title}")
        return

    from .app import Nori  # imported lazily so quick notes stay instant

    Nori().run()


if __name__ == "__main__":
    main()
