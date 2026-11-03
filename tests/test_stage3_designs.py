"""scripts/make_stage3_designs.py: the Stage 3 collection designs load, plan and name buildable policies; no overwrite."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from caosched.experiment.design import load_design, plan_blocks
from caosched.experiment.montage_adapter import build_policy

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_stage3_designs.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("make_stage3_designs", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_designs_load_plan_and_are_not_overwritten(mod, tmp_path, capsys):
    mod.main(str(tmp_path))
    printed = capsys.readouterr().out
    for inst, (n_tasks, n_blocks, _, timeout) in mod.INSTANCES.items():
        d = load_design(tmp_path / f"design_{inst}.json")
        assert d.sha256 in printed and d.instances == [inst] and d.n_blocks == n_blocks and d.run_timeout_s == timeout
        assert d.reference == "EFT_E1" and d.warmup_blocks == 0 and d.evidence_label == "real"
        blocks = plan_blocks(d)
        assert len(blocks) == n_blocks and all(b["instance"] == inst and len(b["runs"]) == 1 + len(mod.RANDOM_OCCUPANCY) for b in blocks)
        ac = json.loads((tmp_path / f"adapter_config_{inst}.json").read_text())
        assert ac == {"timeout_s": 1800, "run_timeout_s": timeout, "cleanup_work": True}
        for c in d.conditions:
            ref = Path(c.kwargs["reference_hashes"]).parent
            assert ref == (mod.STAGE1_REF if inst == mod.PRIMARY else mod.STAGE3 / "refs" / inst) and Path(c.kwargs["reference_dir"]) == ref / "work"
            if c.policy == "RandomOccupancy":
                pol = build_policy(c, 1)
                assert pol.describe()["seed"] == c.kwargs["seed"] and pol.describe()["allowed_pools"] is None
    assert hashlib.sha256((tmp_path / f"design_{next(iter(mod.INSTANCES))}.json").read_bytes()).hexdigest() in printed
    with pytest.raises(FileExistsError):
        mod.main(str(tmp_path))
