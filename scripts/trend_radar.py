from agewell.trends import run
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    raise SystemExit(run(root / "config/trend-seeds.json", root / ".state/trend-radar.json"))
