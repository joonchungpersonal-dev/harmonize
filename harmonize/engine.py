"""Deterministic harmonization engine.

Python orchestrates (validate config, cache, gates, provenance); R does the data
transforms. No LLM is ever called here — this runs standalone from a frozen
crosswalk. The only non-determinism (file reads) is content-addressed.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .cache import content_key
from .config import canonical_spec, load_crosswalk
from .gates import is_clean, run_gates
from .provenance import build_provenance
from .schema import PROVENANCE_COLUMNS, Crosswalk

ENGINE_VERSION = "0.1.0"
_RLIB = Path(__file__).parent / "rlib"


def _rscript(script: str, *args: str) -> str:
    if shutil.which("Rscript") is None:
        raise RuntimeError("Rscript not found on PATH; the R engine is required")
    proc = subprocess.run(
        ["Rscript", "--vanilla", str(_RLIB / script), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{script} failed:\n{proc.stderr}")
    return proc.stdout


def _resolve_sources(cw: Crosswalk, data_dir: Path) -> list[str]:
    paths = []
    for s in cw.sources:
        p = (data_dir / s.path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"source {s.id!r} not found: {p}")
        paths.append(str(p))
    return paths


def profile(paths: list[str | Path]) -> dict:
    """Deterministic per-variable profile (types, missingness, candidate sentinels)."""
    out = _rscript("profile.R", *[str(p) for p in paths])
    return json.loads(out)


def apply(
    crosswalk_path: str | Path,
    out_dir: str | Path,
    data_dir: str | Path | None = None,
    force: bool = False,
) -> dict:
    cw = load_crosswalk(crosswalk_path)
    base = Path(data_dir) if data_dir else Path(crosswalk_path).parent
    sources = _resolve_sources(cw, base)
    spec = canonical_spec(cw)
    key = content_key(sources, ENGINE_VERSION, spec)

    out = Path(out_dir)
    run_log = out / "run_log.json"
    if run_log.exists() and not force:
        prior = json.loads(run_log.read_text())
        if prior.get("cache_key") == key:
            prior["cached"] = True
            return prior

    out.mkdir(parents=True, exist_ok=True)
    # Hand R a resolved config (absolute source paths) so it makes no decisions.
    cfg = cw.model_dump(mode="json", by_alias=True)
    for s, p in zip(cfg["sources"], sources):
        s["path"] = p
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(cfg, fh)
        cfg_path = fh.name

    _rscript("apply.R", cfg_path, str(out))
    manifest = json.loads((out / "manifest.json").read_text())

    prov = build_provenance(cw)
    with open(out / "provenance.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PROVENANCE_COLUMNS)
        w.writeheader()
        w.writerows(prov)
    prov_vars = {r["analytic_var"] for r in prov}

    gates = run_gates(cw, manifest, prov_vars)
    result = {
        "cache_key": key,
        "engine_version": ENGINE_VERSION,
        "construct": cw.construct_name,
        "cached": False,
        "clean": is_clean(gates),
        "manifest": manifest,
        "gates": [g.__dict__ for g in gates],
        "exclusions": [e.model_dump(by_alias=True) for e in cw.exclusions],
        "outputs": {
            "pooled": str(out / "pooled.csv"),
            "provenance": str(out / "provenance.csv"),
        },
    }
    run_log.write_text(json.dumps(result, indent=2))
    return result
