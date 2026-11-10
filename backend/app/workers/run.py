"""python -m app.workers.run --once        (cron-style)   |   python -m app.workers.run --loop --interval 60"""

import argparse
import json
import time

from app.core.logging import configure_logging
from app.workers.scheduler import run_once


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    configure_logging()
    if a.loop:
        while True:
            print(json.dumps(run_once()))
            time.sleep(a.interval)
    print(json.dumps(run_once(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
