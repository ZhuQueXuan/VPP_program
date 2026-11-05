"""Read-only integrity/links QA for review deliverables; no research verification writers."""
import json,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

d120=ROOT/'work/b3_feedback_20261028';freeze=read(d120/'source_freeze.json');last=read(d120/'final_checks.json')
checks={}
checks['all238_old_protected_files_match']=all(sha(p)==expected for p,expected in freeze['protected'].items())
checks['all9_D120_scientific_files_match']=all(sha(d120/p)==expected for p,expected in freeze['source'].items())
checks['all_D120_prior_final_snapshot_match']=all(sha(d120/p)==expected for p,expected in last['all_outputs'].items())
checks['b2_query_sources_models_unchanged']=read(BASE/'b2_api_probe_results.json')['source_and_models_unchanged']
probes=read(BASE/'connection_probe_results.json')
checks['overlap_in_existing_list_counterexample_reproduced']=probes['b3_duplicate_announced_calls']['result_status']=='feasible_under_declared_model' and abs(probes['b3_duplicate_announced_calls']['service_min_kw']-2)<1e-9
checks['new_call_overlap_correctly_rejected']=probes['b3_duplicate_announced_calls']['new_call_overlap_status']=='unavailable'
checks['resampling_energy_conserved_but_task_changed']=abs(probes['template_energy_vs_service_semantics']['fine_energy_kwh']-probes['template_energy_vs_service_semantics']['coarse_energy_kwh'])<1e-12 and not probes['template_energy_vs_service_semantics']['b3_strict_constant_q_each5min']
missing=[];bad_lines=[]
report=BASE/'B1至B3完整审查报告_20261028.md'
for raw in re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8')):
    if raw.startswith(('https://','http://','#')):continue
    match=re.search(r':(\d+)$',raw);target=raw[:match.start()] if match else raw
    p=Path(target)
    if not p.is_absolute():p=report.parent/p
    if not p.exists():missing.append(raw)
    elif match and int(match.group(1))>len(p.read_text(encoding='utf-8').splitlines()):bad_lines.append(raw)
checks['report_links_and_line_numbers_resolve']=not missing and not bad_lines
assert all(checks.values()),(checks,missing,bad_lines)
receipt=dict(status='passed',date='2026-10-28',checks=checks,
    scope='review-only: no training, main experiment generation/rerun, frozen-result rewrite, deletion or formal acceptance',
    old_files_checked=len(freeze['protected'])+len(last['all_outputs']),
    review_files={p.name:sha(p) for p in BASE.iterdir() if p.is_file() and p.name!='review_receipt.json'},
    prior_B1_source_audit='agent_b1:46 frozen science entries,45 direct matches,one previously documented bool serialization-only repair')
with (BASE/'review_receipt.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
print(json.dumps(dict(status='passed',checks=checks,old_files_checked=receipt['old_files_checked']),ensure_ascii=False,indent=2))
