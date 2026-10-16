"""Load and canonicalize a crosswalk config (YAML or JSON)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .schema import Crosswalk


def load_crosswalk(path: str | Path) -> Crosswalk:
    text = Path(path).read_text()
    raw = yaml.safe_load(text)
    return Crosswalk.model_validate(raw)


def canonical_spec(crosswalk: Crosswalk) -> str:
    """Stable JSON serialization for content-addressed caching.

    Sorted keys + no whitespace => identical spec always yields the same hash.
    """
    return json.dumps(
        crosswalk.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
    )
