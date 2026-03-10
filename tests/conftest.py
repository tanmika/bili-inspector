import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in ("", str(ROOT), str(SRC)):
    while path in sys.path:
        sys.path.remove(path)
sys.path.insert(0, str(SRC))
