"""Migrate legacy raw Parquet sidecars to UUID footer/sidecar identities."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _bootstrap import add_repo_src

add_repo_src(__file__)

from autotrade.data_sources.tushare.io import committed_partition_intact, migrate_partition_identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--dataset", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    raw = Path(args.raw_dir).resolve()
    roots = [raw / name for name in args.dataset] if args.dataset else [raw]
    paths = sorted(path for root in roots for path in root.rglob("*.parquet"))
    if args.limit is not None:
        paths = paths[: max(0, args.limit)]
    pending = [path for path in paths if not committed_partition_intact(path)]
    if args.dry_run:
        print(f"pending={len(pending)} scanned={len(paths)}")
        return 0
    for index, path in enumerate(pending, 1):
        migrate_partition_identity(path)
        if index % 1000 == 0:
            print(f"migrated={index}/{len(pending)}")
    print(f"migrated={len(pending)} scanned={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
