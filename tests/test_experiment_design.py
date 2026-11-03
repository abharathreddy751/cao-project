import collections

import pytest

from _exp_helpers import make_design
from caosched.experiment.design import load_design, plan_blocks


def test_plan_deterministic_and_seed_dependent(tmp_path):
    d = load_design(make_design(tmp_path, conds=("A", "B", "C", "D")))
    key = lambda p: [(b["instance"], [(c.name, s) for c, s in b["runs"]]) for b in p]
    assert key(plan_blocks(d)) == key(plan_blocks(load_design(d.path)))
    d2 = load_design(make_design(tmp_path, conds=("A", "B", "C", "D"), name="d2.json", seed=8))
    assert key(plan_blocks(d)) != key(plan_blocks(d2))


def test_interleaving_each_block_has_each_condition_once(tmp_path):
    d = load_design(make_design(tmp_path, conds=("A", "B", "C", "D"), n_blocks=9))
    blocks = plan_blocks(d)
    assert len(blocks) == 9
    for b in blocks:
        assert sorted(c.name for c, _ in b["runs"]) == ["A", "B", "C", "D"]
        assert all(c.instance == b["instance"] for c, _ in b["runs"])
    assert len({tuple(c.name for c, _ in b["runs"]) for b in blocks}) > 1  # orders actually vary
    counts = collections.Counter(b["instance"] for b in blocks)
    assert set(counts.values()) == {3}  # 3 instances x 3 cycles: each cycle uses each instance once


def test_warmup_flags_and_validation(tmp_path):
    blocks = plan_blocks(load_design(make_design(tmp_path, warmup=2)))
    assert [b["warmup"] for b in blocks[:4]] == [True, True, False, False]
    with pytest.raises(ValueError):
        load_design(make_design(tmp_path, name="x.json", evidence_label="bogus"))
    with pytest.raises(ValueError):
        load_design(make_design(tmp_path, name="y.json", warmup=12))
