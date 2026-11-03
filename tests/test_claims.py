"""The claims registry (docs/research_redesign/claims.json) must match the stored analysis tables it cites.

A claim is a number in a file: this test re-reads that file and fails if the number or the status vocabulary changed. It skips a claim
when its evidence directory is absent (a clean checkout does not carry data/results, the Stage 0 record keeps it out of Git), so it
guards the working copy that has the evidence, which is where claims are edited.
"""
import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REG = json.loads((ROOT / "docs" / "research_redesign" / "claims.json").read_text(encoding="utf-8"))
STATUSES = {"supported", "not_supported", "not_resolved", "descriptive"}


def test_registry_is_well_formed():
    ids = [c["id"] for c in REG["claims"]]
    assert len(ids) == len(set(ids)) and ids
    for c in REG["claims"]:
        assert c["status"] in STATUSES and c["text"] and c["protocol"], c["id"]
        assert {"analysis", "cond", "effect_pct", "tol"} <= set(c), c["id"]


@pytest.mark.parametrize("claim", REG["claims"], ids=lambda c: c["id"])
def test_claim_matches_its_stored_table(claim):
    path = ROOT / REG["root"] / claim["analysis"] / "effects.csv"
    if not path.is_file():
        pytest.skip(f"evidence not present: {path}")
    rows = [r for r in csv.DictReader(path.open(encoding="utf-8")) if r["variant"] == "primary" and r["metric"] == "makespan_s"
            and r["cond"] == claim["cond"]]
    assert len(rows) == 1, f"{claim['id']}: expected one primary makespan row for {claim['cond']}, found {len(rows)}"
    assert abs(float(rows[0]["effect_pct"]) - claim["effect_pct"]) <= claim["tol"], (
        f"{claim['id']}: registry says {claim['effect_pct']}, table says {rows[0]['effect_pct']}")
