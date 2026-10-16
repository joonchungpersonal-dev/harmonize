import pytest
from pydantic import ValidationError

from harmonize.config import canonical_spec
from harmonize.schema import Crosswalk

BASE = {
    "version": 1,
    "construct": "dep",
    "key": ["id", "cycle"],
    "sources": [{"id": "w1", "path": "a.csv"}, {"id": "w2", "path": "b.csv"}],
    "sentinels": {"default": [7, 9]},
    "items": [
        {"name": "q1", "source_vars": {"w1": "Q1", "w2": "Q1"}},
        {"name": "q2", "source_vars": {"w1": "Q2", "w2": "Q2"}},
    ],
    "composite": {"name": "total", "rule": "sum", "min_items_present": 2},
}


def test_valid_config_loads():
    cw = Crosswalk.model_validate(BASE)
    assert cw.construct_name == "dep"
    assert cw.sentinels.for_item("q1") == [7, 9]


def test_empty_key_rejected():
    bad = {**BASE, "key": []}
    with pytest.raises(ValidationError):
        Crosswalk.model_validate(bad)


def test_duplicate_source_ids_rejected():
    bad = {**BASE, "sources": [{"id": "w1", "path": "a"}, {"id": "w1", "path": "b"}]}
    with pytest.raises(ValidationError):
        Crosswalk.model_validate(bad)


def test_item_missing_a_source_var_rejected():
    bad = {**BASE, "items": [{"name": "q1", "source_vars": {"w1": "Q1"}}]}
    with pytest.raises(ValidationError):
        Crosswalk.model_validate(bad)


def test_min_items_present_exceeds_items_rejected():
    bad = {**BASE, "composite": {"name": "t", "rule": "sum", "min_items_present": 5}}
    with pytest.raises(ValidationError):
        Crosswalk.model_validate(bad)


def test_canonical_spec_is_stable():
    cw = Crosswalk.model_validate(BASE)
    assert canonical_spec(cw) == canonical_spec(Crosswalk.model_validate(BASE))
