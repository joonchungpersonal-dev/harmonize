"""End-to-end smoke test on tiny synthetic two-wave CSV data.

Requires Rscript (the data engine). Skipped if R is unavailable so the pure
Python suite still runs anywhere.
"""

import shutil

import pytest
import yaml

from harmonize import engine

pytestmark = pytest.mark.skipif(
    shutil.which("Rscript") is None, reason="Rscript not available"
)

CROSSWALK = {
    "version": 1,
    "construct": "dep",
    "key": ["SEQN", "cycle"],
    "sources": [
        {"id": "w1", "path": "w1.csv"},
        {"id": "w2", "path": "w2.csv"},
    ],
    "sentinels": {"default": [9]},
    "items": [
        {"name": "q1", "source_vars": {"w1": "Q1", "w2": "Q1"}},
        {"name": "q2", "source_vars": {"w1": "Q2", "w2": "Q2"}},
    ],
    "composite": {"name": "total", "rule": "sum", "min_items_present": 2},
}


@pytest.fixture
def project(tmp_path):
    # w1: 2 rows, one has sentinel 9 in q2 -> total NA (proration, min 2 present)
    (tmp_path / "w1.csv").write_text("SEQN,Q1,Q2\n1,1,2\n2,3,9\n")
    (tmp_path / "w2.csv").write_text("SEQN,Q1,Q2\n1,0,1\n2,2,2\n")
    cw = tmp_path / "cw.yaml"
    cw.write_text(yaml.safe_dump(CROSSWALK))
    return tmp_path, cw


def test_apply_is_clean_and_correct(project):
    data_dir, cw = project
    out = data_dir / "out"
    res = engine.apply(cw, out, data_dir=data_dir)
    assert res["clean"] is True
    m = res["manifest"]
    assert m["rows_in_total"] == 4
    assert m["rows_out"] == 4
    assert m["key_duplicates"] == 0  # SEQN reused across cycles, key=(SEQN,cycle)
    assert m["residual_sentinels"] == 0  # 9 mapped to NA
    assert m["composite_missing"] == 1  # the sentinel row fails proration
    assert (out / "pooled.csv").exists()
    assert (out / "provenance.csv").exists()


def test_rerun_hits_cache_identical_key(project):
    data_dir, cw = project
    out = data_dir / "out"
    r1 = engine.apply(cw, out, data_dir=data_dir)
    r2 = engine.apply(cw, out, data_dir=data_dir)
    assert r2["cached"] is True
    assert r1["cache_key"] == r2["cache_key"]
