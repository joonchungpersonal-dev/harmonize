"""Standalone CLI. No LLM — runs entirely from a frozen crosswalk.

  harmonize profile  <file...>
  harmonize validate <crosswalk.yaml>
  harmonize apply    <crosswalk.yaml> --out DIR [--data-dir DIR] [--force]
  harmonize schema   (export JSON Schema of the crosswalk contract)
  harmonize hash     <crosswalk.yaml> --data-dir DIR
"""

from __future__ import annotations

import argparse
import json
import sys

from . import engine
from .cache import content_key
from .config import canonical_spec, load_crosswalk
from .schema import Crosswalk


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="harmonize")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("profile")
    pp.add_argument("files", nargs="+")

    pv = sub.add_parser("validate")
    pv.add_argument("crosswalk")

    pa = sub.add_parser("apply")
    pa.add_argument("crosswalk")
    pa.add_argument("--out", required=True)
    pa.add_argument("--data-dir", default=None)
    pa.add_argument("--force", action="store_true")

    sub.add_parser("schema")

    ph = sub.add_parser("hash")
    ph.add_argument("crosswalk")
    ph.add_argument("--data-dir", default=None)

    a = p.parse_args(argv)

    if a.cmd == "profile":
        print(json.dumps(engine.profile(a.files), indent=2))
    elif a.cmd == "validate":
        cw = load_crosswalk(a.crosswalk)
        print(f"OK: {cw.construct_name} — {len(cw.items)} items, key={cw.key}")
    elif a.cmd == "apply":
        res = engine.apply(a.crosswalk, a.out, data_dir=a.data_dir, force=a.force)
        status = "CLEAN" if res["clean"] else "FAILED GATES"
        print(f"[{status}] cache_key={res['cache_key']} cached={res['cached']}")
        for g in res["gates"]:
            mark = "ok" if g["passed"] else "X"
            print(f"  [{mark}] {g['name']}: {g['detail']}")
        print(f"  pooled -> {res['outputs']['pooled']}")
        print(f"  provenance -> {res['outputs']['provenance']}")
        if not res["clean"]:
            return 1
    elif a.cmd == "schema":
        print(json.dumps(Crosswalk.model_json_schema(), indent=2))
    elif a.cmd == "hash":
        from pathlib import Path

        cw = load_crosswalk(a.crosswalk)
        base = Path(a.data_dir) if a.data_dir else Path(a.crosswalk).parent
        srcs = [str((base / s.path).resolve()) for s in cw.sources]
        print(content_key(srcs, engine.ENGINE_VERSION, canonical_spec(cw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
