"""Reproduce the recommendation experiments:

    uv run python -m app.scripts.evaluate_recommendations --seeds 42 43 44 45 46 --out ../docs/research/results

Everything is generated from the seeds; re-running with the same arguments yields identical results.
"""

import argparse
from pathlib import Path

from app.modules.recommendations.evaluation.runner import run_seeds, write_outputs
from app.modules.recommendations.evaluation.synthetic import SyntheticConfig


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--items", type=int, default=120)
    ap.add_argument("--users", type=int, default=300)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--lambda", dest="lam", type=float, default=0.7)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--out", type=Path, default=Path("../docs/research/results"))
    a = ap.parse_args()
    base = SyntheticConfig(n_items=a.items, n_test_users=a.users)
    result = run_seeds(a.seeds, base, k=a.k, mmr_lambda=a.lam, n_boot=a.bootstrap)
    for p in write_outputs(result, a.out):
        print("wrote", p)
    print("runtime per seed (s):", [r["runtime_seconds"] for r in result["runs"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
