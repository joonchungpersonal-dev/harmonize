# harmonize

`harmonize` takes raw survey files and one reviewed YAML crosswalk, and produces a single pooled analytic dataset plus a provenance codebook that records how every analytic variable was built.

## The problem

Pooling the same questionnaire across study waves is where analysis projects lose weeks, and it is where silent errors get introduced. A concrete case, the one in `examples/`:

NHANES asks the nine PHQ-9 depression items in `DPQ_I` (2015-2016) and `DPQ_J` (2017-2018). Three things go wrong if you merge the files by hand.

1. `SEQN` is reused across cycles, so the respondent key is not unique in the pooled file. A merge on `SEQN` alone quietly collapses or duplicates rows.
2. The response codes `7` and `9` mean "refused" and "don't know". If they survive into a `rowSums`, a respondent who refused two items scores 16 points of depression they never reported.
3. Partial responders need a stated rule. Summing available items without a threshold scores someone who answered two of nine as if they had answered all nine.

Each of those is easy to fix once. The expensive part is that the fix lives in a script nobody rereads, and six months later nobody can say which sentinel codes were mapped, which variables were dropped, or why. `harmonize` makes the rules a file you can read, and makes the run refuse to call itself clean if the rules were not honored.

## Quickstart

The example crosswalk pools PHQ-9 across the two NHANES cycles. Point `--data-dir` at a folder holding `DPQ_I.rds` and `DPQ_J.rds`, both public NHANES downloads.

```bash
python3 -m pip install -e .

python3 -m harmonize.cli validate examples/nhanes_phq9.crosswalk.yaml
# OK: depression_phq9 - 9 items, key=['SEQN', 'cycle']

python3 -m harmonize.cli apply examples/nhanes_phq9.crosswalk.yaml \
    --out ./out --data-dir /path/to/nhanes
```

Observed output on NHANES 2015-2016 plus 2017-2018:

```
[CLEAN] cache_key=926d5525045fcdf9 cached=False
  [ok] row_integrity: rows_in=11268 rows_out=11268
  [ok] key_uniqueness: duplicate composite keys=0
  [ok] sentinels_mapped: unmapped sentinel values remaining in item columns=0
  [ok] provenance_complete: analytic vars missing lineage=[]
  pooled -> ./out/pooled.csv
  provenance -> ./out/provenance.csv
```

Running the same command again does no work and reports `cached=True` with the identical `cache_key`.

The written outputs are `pooled.csv` (one row per respondent per cycle, items renamed to analytic names, sentinels mapped to `NA`, composite scored), `provenance.csv` (one row per analytic variable: sources, rule, coding, sentinels mapped, derivation), `manifest.json` (row counts, duplicate keys, residual sentinels, composite missingness) and `run_log.json` (the cache key and every gate verdict).

`pip install -e .` also installs a `harmonize` console script, so `harmonize apply ...` is equivalent to the module form above. Two more subcommands exist: `schema` prints the JSON Schema of the crosswalk contract, and `hash` prints the content key for a crosswalk plus its data without running anything.

## The frozen config

A crosswalk YAML file fully specifies a run: the analytic key, the source files and their ids, the sentinel codes per item or as a default, the variable name in each source for every analytic item, and the composite rule with its minimum-items threshold. `harmonize/schema.py` is a pydantic model of exactly that, and it is the only input the engine reads.

An LLM is useful for writing that file the first time, since reading two codebooks and lining up variable names is tedious and mechanical. Nothing in this package calls an LLM, and nothing in it needs network access. Once the YAML has been reviewed by a human and committed, `harmonize apply` is Python orchestration over an R data step, both driven entirely by the file.

What that buys:

- A run costs no tokens, so rerunning after a data refresh is free and instant.
- Two runs over the same inputs produce the same bytes. The cache key is a SHA-256 over the engine version, the canonicalized config (sorted keys, no whitespace) and the digest of each source file, so a changed data file or a changed rule changes the key, and a cache hit is a real guarantee rather than a timestamp comparison.
- The diff of a methods change is the diff of a YAML file. A reviewer can see that `min_items_present` went from 9 to 7 without reading code.
- The validator is fail-closed. An item missing a variable name for one of the declared sources is a validation error, not a column of `NA`. A `min_items_present` above the item count is a validation error. Duplicate source ids and duplicate item names are validation errors.

Four gates run after the data step, and all of them halt the clean verdict: input rows must equal output rows, the declared composite key must be unique, no configured sentinel value may remain in any item column, and every analytic variable including the composite must have a provenance row. A failed gate sets `clean: false` and exits non-zero. The gates are plain predicates in `gates.py` over the R step's manifest, so they are unit-tested against synthetic failing manifests rather than only against happy-path data.

## Tests

19 tests, all passing, observed with `python3 -m pytest` on Python 3.14 with R available:

```
19 passed in 0.47s
```

They cover the cache key (determinism, sensitivity to data, spec and engine version, source-order independence), the schema validators, the gates against deliberately broken manifests, the pinned provenance column order, and two end-to-end runs against tiny synthetic two-wave CSVs that check the sentinel mapping, the proration rule and the cache hit. The two end-to-end tests skip themselves if `Rscript` is not on the path, so the rest of the suite runs anywhere.

## Scope limits

- **R is required for any real run.** The data step is `harmonize/rlib/apply.R` and needs `Rscript` plus the `jsonlite` and `haven` packages. Without R, `apply` and `profile` raise; the schema, gate and cache layers still work.
- **No reverse-coding.** The schema rejects `reverse: true` with an error rather than accepting a flag the R step does not implement. Reverse-code upstream, or add scale bounds to `ItemMap` and implement it in `apply.R`.
- **One construct per crosswalk, one composite per construct.** Composite rules are `sum` and `mean`. There is no weighting, no survey weight handling, no imputation, and no subscale scoring.
- **Items are mapped by name, not reconciled by content.** If two waves use different response options for the same question, `harmonize` will stack them anyway. Recode upstream, or declare the construct in `exclusions` with a reason, which is what the example does for the household education variable NHANES renamed and recategorized between cycles.
- **The last element of `key` is treated as the source id.** Everything before it is carried through from the source file as a person-level key.
- **Local files only.** Sources are read from disk as `.rds`, `.sav`, `.dta`, `.xpt` or `.csv`. There is no database backend and no cloud pushdown.
- **The cache is per output directory.** `apply` compares the key in `run_log.json` inside `--out`; it does not maintain a shared store across output directories. Use `--force` to recompute.
- **Not a validity check.** `harmonize` produces items and a composite with lineage. Whether that composite behaves as a measure is a separate question, handled by [yardstick](https://github.com/joonchungpersonal-dev/yardstick), which reads the provenance columns this package pins.
- **No data ships here.** The repository contains no participant data. Source paths are supplied at runtime with `--data-dir`.

## Requirements

- Python 3.10 or newer, with `pydantic` 2 and `pyyaml` 6
- R with `Rscript` on the path, and the R packages `jsonlite` and `haven`
- `pytest` to run the test suite

Developed and tested on macOS with Python 3.14 and R 4.4.

## License

MIT. See [LICENSE](./LICENSE).
