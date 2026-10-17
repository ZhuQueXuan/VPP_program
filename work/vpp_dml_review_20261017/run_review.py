"""Run the colleague's unchanged scripts in separate, preserved copies."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "vpp_dml_framework"

def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["quick", "full", "coverage"])
    ap.add_argument("--repair-evaluation", action="store_true")
    a = ap.parse_args()
    run_id = a.mode + ("_repaired" if a.repair_evaluation else "")
    target = HERE / ("run_" + run_id)
    if target.exists():
        raise FileExistsError(target)
    shutil.copytree(SOURCE, target)
    original = hashes(SOURCE)
    assert hashes(target) == original
    if a.repair_evaluation:
        p = target / "vpp_dml" / "evaluate.py"
        old = '    return (prof - prof.mean()) / prof.std()'
        new = '    sd = prof.std()\n    return (prof - prof.mean()) / sd.where(sd.abs() > 1e-12, 1.0)'
        text = p.read_text(encoding="utf-8")
        assert text.count(old) == 1
        p.write_text(text.replace(old, new), encoding="utf-8")
    script = "run_coverage.py" if a.mode == "coverage" else "run_benchmark.py"
    args = [sys.executable, "-X", "utf8", str(target / "experiments" / script)]
    if a.mode == "quick": args.append("--quick")
    if a.mode == "coverage": args += ["--reps", "30"]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2")
    stamp = {"mode": run_id, "command": args, "source_sha256": original,
             "run_code_sha256": hashes(target),
             "repair": "Only degenerate profile standard deviation is replaced by 1 for evaluation; no fitting/data/split changes" if a.repair_evaluation else None,
             "started_epoch": time.time(), "interpretation": "synthetic reproduction only; no project data"}
    (HERE / (run_id + "_run_receipt.json")).write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8")
    with (HERE / (run_id + ".log")).open("w", encoding="utf-8") as log:
        proc = subprocess.run(args, cwd=target, env=env, stdout=log, stderr=subprocess.STDOUT)
    stamp.update(returncode=proc.returncode, elapsed_s=time.time()-stamp["started_epoch"],
                 outputs_sha256=hashes(target / "results"), source_unchanged=hashes(SOURCE)==original)
    (HERE / (run_id + "_run_receipt.json")).write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in stamp.items() if not k.endswith("sha256")}, ensure_ascii=False), flush=True)
    return proc.returncode

if __name__ == "__main__":
    raise SystemExit(main())
