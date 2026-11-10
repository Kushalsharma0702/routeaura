"""uv run python -m app.scripts.evaluate_itineraries --seeds 42 43 44 45 46 --out ../docs/research/results"""

import argparse
from pathlib import Path

from app.modules.itinerary.evaluation import ItineraryEvalConfig, run_seeds, write_outputs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--trips", type=int, default=300)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--out", type=Path, default=Path("../docs/research/results"))
    a = ap.parse_args()
    result = run_seeds(a.seeds, ItineraryEvalConfig(n_trips=a.trips), a.bootstrap)
    for p in write_outputs(result, a.out):
        print("wrote", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
