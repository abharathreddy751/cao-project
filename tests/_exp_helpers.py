"""Shared helpers for experiment/analysis tests (synthetic data lives only in tests)."""
import json

ENV = {"machine_id": "M1", "environment_hash": "E1", "git": {"commit": "abc", "dirty": False},
       "software": {"src_sha256": "f" * 64}}


def make_design(tmp_path, n_blocks=12, warmup=1, conds=("A", "B"), instances=("i1", "i2", "i3"), ram=2.0, name="d.json", **kw):
    d = {"name": "t", "evidence_label": "real", "seed": 7, "n_blocks": n_blocks, "warmup_blocks": warmup,
         "instances": list(instances), "min_free_ram_gb": ram, "reference": conds[0],
         "conditions": [{"name": c, "policy": "pol_" + c} for c in conds], **kw}
    p = tmp_path / name
    p.write_text(json.dumps(d))
    return p
