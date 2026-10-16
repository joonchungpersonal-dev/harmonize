"""Build the provenance codebook from the frozen config.

One row per analytic variable, in the pinned PROVENANCE_COLUMNS order — the
schema /yardstick consumes directly (no re-cleaning).
"""

from __future__ import annotations

from .schema import PROVENANCE_COLUMNS, Crosswalk


def build_provenance(crosswalk: Crosswalk) -> list[dict]:
    rows: list[dict] = []
    for it in crosswalk.items:
        srcs = "; ".join(f"{sid}:{var}" for sid, var in sorted(it.source_vars.items()))
        sentinels = crosswalk.sentinels.for_item(it.name)
        rows.append(
            {
                "analytic_var": it.name,
                "sources": srcs,
                "rule": "map 1:1",
                "coding": it.coding,
                "reverse": it.reverse,
                "sentinels_mapped": ",".join(str(s) for s in sentinels),
                "min_items_present": "",
                "derivation": "renamed from source var; sentinel->NA; reverse-coded"
                if it.reverse
                else "renamed from source var; sentinel->NA",
            }
        )
    comp = crosswalk.composite
    rows.append(
        {
            "analytic_var": comp.name,
            "sources": "; ".join(it.name for it in crosswalk.items),
            "rule": comp.rule,
            "coding": "composite",
            "reverse": False,
            "sentinels_mapped": "",
            "min_items_present": comp.min_items_present,
            "derivation": f"{comp.rule} of {len(crosswalk.items)} items, "
            f"scored if >= {comp.min_items_present} present",
        }
    )
    # Assert pinned column contract.
    for r in rows:
        assert set(r) == set(PROVENANCE_COLUMNS), "provenance row violates pinned schema"
    return rows
