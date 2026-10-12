"""Model selection from the Stage 3 scheduling pilot [real]: paired bootstrap CI of log(makespan_simple / makespan_complex)
per (simple, complex) pair, then the rule fixed in STAGE3_FREEZE.md (analysis.model_eval.select_model, margin ln 1.02).

  python scripts/select_model_from_pilot.py <session_dir> <out_dir> [--margin 0.0198]

Models and complexity order (frozen): EFT_E1 < EFT_E3 < EFT_E1_rc < EFT_Ridge < EFT_CatBoost < EFT_MLP.
Only runs with status ok and verified output are used. Writes scheduling_pairs.json and selection_record.json (exclusive)."""
import argparse
import json
import math
from pathlib import Path

from caosched.analysis.model_eval import select_model
from caosched.analysis.stats import bootstrap_mean_ci, paired_log_ratios

ORDER = ["EFT_E1", "EFT_E3", "EFT_E1_rc", "EFT_Ridge", "EFT_CatBoost", "EFT_MLP"]


def load_blocks(session: Path) -> dict:
    blocks: dict = {}
    for m in sorted(session.glob("runs/*/run_manifest.json")):
        d = json.loads(m.read_text(encoding="utf-8"))
        cond = d["condition"]["name"] if isinstance(d.get("condition"), dict) else d["condition"]
        ok = d.get("status") == "ok" and (d.get("verification") or {}).get("passed")
        ms = (d.get("extra") or {}).get("makespan_seconds")
        if ok and ms:
            blocks.setdefault((m.parent.name[:5], 0), {})[cond] = {"makespan_s": ms}  # key: block id b0000
    return blocks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("out")
    ap.add_argument("--margin", type=float, default=math.log(1.02))
    a = ap.parse_args()
    blocks = load_blocks(Path(a.session))
    pairs = []
    for i, s in enumerate(ORDER):
        for c in ORDER[i + 1:]:
            r, strata = paired_log_ratios(blocks, s, c, "makespan_s")
            mean, lo, hi = bootstrap_mean_ci(r, strata, seed=1000 + i)
            pairs.append({"simple": s, "complex": c, "diff_mean": mean, "diff_lo": lo, "diff_hi": hi, "n_blocks": len(r)})
    models = [{"name": n, "complexity": i} for i, n in enumerate(ORDER)]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "scheduling_pairs.json").open("x") as f:
        json.dump({"models": models, "pairs": pairs, "unit": "log(makespan_simple/makespan_complex)",
                   "n_blocks": len(blocks)}, f, indent=1)
    rec = select_model(models, pairs, a.margin)
    with (out / "selection_record.json").open("x") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps({"selected": rec["selected"], "margin": rec["margin"], "n_blocks": len(blocks)}, indent=1))


if __name__ == "__main__":
    main()
