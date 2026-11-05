"""Read-only frozen-model queries. Creates only a new review receipt, exclusively."""
import sys
sys.dont_write_bytecode = True
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT / "work/b2_completion_20261027"
protected = [PACKAGE / p for p in ["api.py", "common.py", "dynamic/models.joblib", "dynamic/selection.json"]]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = {str(p): sha(p) for p in protected}
sys.path.insert(0, str(PACKAGE))
from api import evaluate

case = json.loads((PACKAGE / "example_output.json").read_text(encoding="utf-8"))["input"]
rows = []
for permission in [0, False, 1, True, "0", "0.0"]:
    query = copy.deepcopy(case)
    query["permission"] = permission
    result = evaluate(query)
    rows.append({"input": query, "permission_input_type": type(permission).__name__,
                 "output": {k: result.get(k) for k in ["status", "existing_permission", "eligible", "expected_delivery_kw", "control_requires_actual_acceptance", "committed_kw"]},
                 "dynamic_scenario_count": len(result.get("dynamic_scenarios", []))})
after = {str(p): sha(p) for p in protected}
assert before == after
receipt = {"scope": "read-only queries of existing frozen models; no generation/training/old-output write", "full_base_input": case,
           "source_and_model_sha_before": before, "source_and_model_sha_after": after,
           "source_and_models_unchanged": before == after, "queries": rows,
           "finding": "permission numeric 0/False is blocked, but convertible nonempty strings '0'/'0.0' pass numeric validation then bool(raw string) incorrectly marks permission true"}
with (HERE / "b2_api_probe_results.json").open("x", encoding="utf-8") as f:
    json.dump(receipt, f, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps({"receipt": str(HERE / "b2_api_probe_results.json"), "unchanged": before == after,
                  "queries": [{"permission": q["input"]["permission"], "type": q["permission_input_type"], **q["output"], "scenarios": q["dynamic_scenario_count"]} for q in rows]}, ensure_ascii=False, indent=2))
