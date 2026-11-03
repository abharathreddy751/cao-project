"""scripts/profile_montage.py on a synthetic reference run whose commands are `python -c` scripts (no Montage)."""
import csv
import importlib.util
import json
import pathlib
import sys

import pytest

from caosched.estimators import StaticProfileEstimator

spec = importlib.util.spec_from_file_location("profile_montage", pathlib.Path(__file__).parents[1] / "scripts" / "profile_montage.py")
pm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pm)

COPY = "import sys; open(sys.argv[-1],'w').write(''.join(open(f).read() for f in sys.argv[1:-1]) + 'x')"


@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "ref"
    (d / "work").mkdir(parents=True)
    tasks = []
    for i, (name, nbytes) in enumerate([("tA", 10), ("tA", 1000), ("tB", 50), ("mProject", 5), ("mProject", 500), ("mProject", 50_000)]):
        f = f"in{i}.txt"
        (d / "work" / f).write_bytes(b"x" * nbytes)
        tasks.append({"id": f"T{i}", "name": name, "argv": [sys.executable, "-c", COPY, f, f"out{i}.txt"], "inputs": [f],
                      "outputs": [{"lfn": f"out{i}.txt", "bytes": nbytes + 1}], "wall_s": 1.0, "exit": 0, "ok": True})
    tasks.append({"id": "BAD", "name": "tB", "argv": [], "inputs": ["missing.txt"], "outputs": [], "ok": True})
    (d / "run.json").write_text(json.dumps({"tasks": tasks}))
    return d


def test_profile_format_csv_fit_and_cleanup(run_dir, tmp_path):
    before = sorted(p.name for p in (run_dir / "work").iterdir())
    out = tmp_path / "prof"
    prof = pm.profile(run_dir, out, {"P": 0, "E": 1}, tmp_path / "bin", reps=2, mproject_max=2)
    (pf,) = out.glob("*_profile.json")
    est = StaticProfileEstimator.from_file(pf)                           # the format E1 reads
    assert sorted(est.table) == sorted((w, 1, p) for w in ("tA", "tB", "mProject") for p in "PE")
    assert all(v > 0 for v in est.table.values())
    (raw,) = out.glob("*_raw.csv")
    rows = list(csv.DictReader(raw.open(encoding="utf-8")))
    assert len(rows) == (2 + 1 + 2) * 2 * 2 and all(r["ok"] == "True" for r in rows)     # mProject capped to 2 tasks; BAD skipped
    assert {int(r["input_bytes"]) for r in rows if r["transformation"] == "mProject"} == {5, 50_000}   # smallest and largest
    assert {r["logical_processor"] for r in rows if r["pool"] == "E"} == {"1"}
    fit = prof["linear_fit"]["fits"]["tA|P"]
    assert set(fit) == {"a", "b", "n", "r2"} and fit["n"] == 4 and list(out.glob("*_environment.json"))
    assert not (out / "scratch").exists() and sorted(p.name for p in (run_dir / "work").iterdir()) == before
    with pytest.raises(FileExistsError):                                  # never writes into an existing directory
        pm.profile(run_dir, out, {"P": 0}, tmp_path / "bin")


def test_refuses_low_free_ram(run_dir, tmp_path):
    with pytest.raises(SystemExit, match="free RAM"):
        pm.profile(run_dir, tmp_path / "p2", {"P": 0}, tmp_path / "bin", min_free_gb=2.0, free_fn=lambda: 0.5)
    assert not (tmp_path / "p2").exists()
    calls = iter([8.0, 8.0, 0.1])                                         # fine at start and for the first run, then low
    with pytest.raises(SystemExit, match="stopping"):
        pm.profile(run_dir, tmp_path / "p3", {"P": 0}, tmp_path / "bin", reps=2, free_fn=lambda: next(calls))
    assert not list((tmp_path / "p3").glob("*_profile.json")) and len(list((tmp_path / "p3").glob("*_raw.csv"))) == 1
