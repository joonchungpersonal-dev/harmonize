from harmonize.gates import is_clean, run_gates
from harmonize.provenance import build_provenance
from harmonize.schema import PROVENANCE_COLUMNS, Crosswalk

CW = Crosswalk.model_validate(
    {
        "version": 1,
        "construct": "dep",
        "key": ["id", "cycle"],
        "sources": [{"id": "w1", "path": "a"}, {"id": "w2", "path": "b"}],
        "sentinels": {"default": [9]},
        "items": [
            {"name": "q1", "source_vars": {"w1": "Q1", "w2": "Q1"}},
            {"name": "q2", "source_vars": {"w1": "Q2", "w2": "Q2"}},
        ],
        "composite": {"name": "total", "rule": "sum", "min_items_present": 2},
    }
)

GOOD_MANIFEST = {
    "rows_in_total": 100,
    "rows_out": 100,
    "key_duplicates": 0,
    "residual_sentinels": 0,
}


def _prov_vars():
    return {r["analytic_var"] for r in build_provenance(CW)}


def test_clean_run_passes_all_halt_gates():
    res = run_gates(CW, GOOD_MANIFEST, _prov_vars())
    assert is_clean(res)


def test_row_multiplication_fails():
    m = {**GOOD_MANIFEST, "rows_out": 200}
    res = run_gates(CW, m, _prov_vars())
    assert not is_clean(res)
    assert any(g.name == "row_integrity" and not g.passed for g in res)


def test_unmapped_sentinel_fails():
    m = {**GOOD_MANIFEST, "residual_sentinels": 3}
    res = run_gates(CW, m, _prov_vars())
    assert not is_clean(res)


def test_duplicate_key_fails():
    m = {**GOOD_MANIFEST, "key_duplicates": 4}
    res = run_gates(CW, m, _prov_vars())
    assert not is_clean(res)


def test_missing_provenance_fails():
    res = run_gates(CW, GOOD_MANIFEST, {"q1", "total"})  # q2 lineage missing
    assert not is_clean(res)


def test_provenance_rows_match_pinned_schema():
    for row in build_provenance(CW):
        assert list(row.keys()) == PROVENANCE_COLUMNS
