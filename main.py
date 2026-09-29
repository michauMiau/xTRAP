"""AppImage/Android entry point for xTRAP.

buildozer uses `source.dir = .` and expects `main.py` in the repository root.
All the real modules live in `src/`, and they import each other by bare name
(`from state import state`), which only resolves if `src/` is on sys.path.

So this shim does one thing: put `src/` on sys.path, then hand over to
src/main.py. Everything else stays in the real modules — this file has no
app logic on purpose.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")

if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Kivy parses argv itself; a desktop-file/launcher argv can make it exit 2.
os.environ.setdefault("KIVY_NO_ARGS", "1")

# pylint: disable=wrong-import-position,import-self
# The import below MUST stay below the sys.path setup: importing it earlier is
# what this file exists to prevent. Both warnings are false positives here.
from main import RCControlCenterApp  # noqa: E402

if __name__ == "__main__":
    RCControlCenterApp().run()
