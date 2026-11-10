"""uv run python -m app.scripts.evaluate_routing --seeds 42 43 44 45 46 --out ../docs/research/results"""

import argparse
from pathlib import Path

from app.modules.routing.evaluation import RoutingEvalConfig, run_seeds, write_outputs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--trips", type=int, default=60)
    ap.add_argument("--out", type=Path, default=Path("../docs/research/results"))
    a = ap.parse_args()
    for p in write_outputs(run_seeds(a.seeds, RoutingEvalConfig(n_trips=a.trips)), a.out):
        print("wrote", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
