"""Headed Tapstitch login for the product automation.

Evan logs in inside his real Google Chrome (a dedicated profile on debug port
9223, kept apart from 9222, which an older automation profile used). This
script only opens the window and watches for the logged-in state; it automates
no input and never sees his password. The session persists in the profile.

Login:  ./.venv.nosync/bin/python scripts/tapstitch_login.py
Check:  ./.venv.nosync/bin/python scripts/tapstitch_login.py --check

FIRST-RUN NOTE: the login and dashboard URLs in browser_session.TAPSTITCH are
best guesses and have never been exercised. Correct them during the first live
session if Tapstitch redirects somewhere else.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from browser_session import TAPSTITCH, check, login


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify the saved session still works")
    a = ap.parse_args()
    sys.exit(check(TAPSTITCH) if a.check else login(TAPSTITCH))


if __name__ == "__main__":
    main()
