"""Frozen crosswalk config — the contract the LLM proposes and the engine replays.

This pydantic model IS the determinism boundary: a valid crosswalk fully
specifies a harmonization run. The engine never makes a judgment the config
doesn't encode. Validation here is fail-closed (grill remediations live as
required structure, not prose).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# The canonical provenance-codebook columns. Pinned here and consumed by
# /yardstick — this is the cross-skill contract (grill finding #13).
PROVENANCE_COLUMNS = [
    "analytic_var",
    "sources",
    "rule",
    "coding",
    "reverse",
    "sentinels_mapped",
    "min_items_present",
    "derivation",
]


class SourceRef(BaseModel):
    id: str  # also the value of the cycle/wave key column
    path: str


class ItemMap(BaseModel):
    name: str
    source_vars: dict[str, str]  # source id -> raw variable name
    coding: str = "ordinal"
    reverse: bool = False


class Composite(BaseModel):
    name: str
    rule: Literal["sum", "mean"] = "sum"
    # Proration policy (grill #4): a row scores only if >= this many items present.
    min_items_present: int = Field(ge=0)


class Exclusion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    construct_name: str = Field(alias="construct")
    source_vars: dict[str, str] = {}
    reason: str


class Sentinels(BaseModel):
    # Codebook-driven, not a hardcoded spike heuristic (grill #9).
    default: list[float] = []
    by_item: dict[str, list[float]] = {}

    def for_item(self, item: str) -> list[float]:
        return self.by_item.get(item, self.default)


class Crosswalk(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: int
    construct_name: str = Field(alias="construct")
    key: list[str]  # composite analytic key, e.g. [SEQN, cycle] (grill #8)
    sources: list[SourceRef]
    sentinels: Sentinels = Sentinels()
    items: list[ItemMap]
    composite: Composite
    exclusions: list[Exclusion] = []

    @model_validator(mode="after")
    def _check(self) -> "Crosswalk":
        if not self.key:
            raise ValueError("key must be non-empty (declare the analytic key)")
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError(f"source ids must be unique: {ids}")
        if not self.items:
            raise ValueError("at least one item is required")
        names = [it.name for it in self.items]
        if len(names) != len(set(names)):
            raise ValueError(f"item names must be unique: {names}")
        id_set = set(ids)
        for it in self.items:
            missing = id_set - set(it.source_vars)
            if missing:
                raise ValueError(
                    f"item {it.name!r} is missing a source_var for source(s) {sorted(missing)}"
                )
            # rlib/apply.R does not reverse-code, and ItemMap carries no scale
            # bounds to reverse against. Accepting the flag would emit un-reversed
            # data alongside a provenance row attesting it WAS reversed.
            if it.reverse:
                raise ValueError(
                    f"item {it.name!r} sets reverse=True, but the engine does not "
                    "implement reverse-coding. Reverse-code in the source data, or "
                    "add scale bounds to ItemMap and implement it in rlib/apply.R "
                    "before setting this flag."
                )
        if self.composite.min_items_present > len(self.items):
            raise ValueError(
                f"min_items_present ({self.composite.min_items_present}) exceeds "
                f"item count ({len(self.items)})"
            )
        return self
