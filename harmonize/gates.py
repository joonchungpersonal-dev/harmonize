"""Validation gates as pure predicates over the R engine's manifest.

Each gate is a deterministic, unit-testable function. A failing HALT gate means
the run is NOT clean — the engine refuses to label the output as validated.
These are the harmonize invariants made checkable (not prose).
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import Crosswalk


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    halt: bool  # a failed halt gate blocks "clean" status
    detail: str


def gate_row_integrity(manifest: dict) -> GateResult:
    rin, rout = manifest["rows_in_total"], manifest["rows_out"]
    return GateResult(
        "row_integrity",
        rin == rout,
        True,
        f"rows_in={rin} rows_out={rout}",
    )


def gate_key_uniqueness(manifest: dict) -> GateResult:
    dups = manifest["key_duplicates"]
    return GateResult(
        "key_uniqueness", dups == 0, True, f"duplicate composite keys={dups}"
    )


def gate_sentinels_mapped(manifest: dict) -> GateResult:
    # R reports any configured sentinel value still present in item columns.
    residual = manifest["residual_sentinels"]
    return GateResult(
        "sentinels_mapped",
        residual == 0,
        True,
        f"unmapped sentinel values remaining in item columns={residual}",
    )


def gate_provenance_complete(crosswalk: Crosswalk, prov_vars: set[str]) -> GateResult:
    required = {it.name for it in crosswalk.items} | {crosswalk.composite.name}
    missing = required - prov_vars
    return GateResult(
        "provenance_complete",
        not missing,
        True,
        f"analytic vars missing lineage={sorted(missing)}",
    )


def run_gates(
    crosswalk: Crosswalk, manifest: dict, prov_vars: set[str]
) -> list[GateResult]:
    return [
        gate_row_integrity(manifest),
        gate_key_uniqueness(manifest),
        gate_sentinels_mapped(manifest),
        gate_provenance_complete(crosswalk, prov_vars),
    ]


def is_clean(results: list[GateResult]) -> bool:
    return all(r.passed for r in results if r.halt)
