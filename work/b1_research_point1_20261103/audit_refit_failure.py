"""Explicit injected-failure branch test; separate from actual success receipt."""
from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects import continuous as CT
from b1_algorithm.effects.refit import refit_curve_uncertainty
model=json.loads((HERE/'audit_integrated_model.json').read_text(encoding='utf-8'))['payload']
original=CT._crossfit
calls=0
def one_injected_failure(*args,**kwargs):
    global calls
    calls+=1
    if calls==1:raise ValueError('intentional audit-only first-draw failure')
    return original(*args,**kwargs)
try:
    CT._crossfit=one_injected_failure
    result=refit_curve_uncertainty(model,[.4,.73,1.17,1.65,2.],draws=99,seed=90335993)
finally:
    CT._crossfit=original
assert result['status']=='incomplete'
assert result['failed_draws']==1 and result['success_draws']==98
assert result['draw_status'][0]['status']=='unsupported'
assert not result['band_valid_for_use'] and result['successful_draw_conditional_band']
receipt=dict(status='passed_injected_failure_branch_test',injected_failures=1,
    actual_following_refits=98,failure_retained=True,interval_marked_incomplete=True,
    note='not an empirical failure rate; the first failure was deliberately injected only in this isolated audit process')
with (HERE/'audit_refit_failure_result.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
print(json.dumps(receipt))
