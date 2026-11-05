"""Independent contract-only review; no main-panel fit or scoring repeated."""
from pathlib import Path
import json,ast,hashlib,sys
from types import SimpleNamespace
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;WORK=HERE.parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.resources.ev import ev_config
from b1_algorithm.process import _ride_revised as revised
from b1_algorithm.process.api import prepare,resolve_policy
from b1_api import analyze_event,provided_reference
checks=[]
def check(name,value):
    if not bool(value):raise AssertionError(name)
    checks.append(name)
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def funcs(text):return {x.name:x for x in ast.parse(text).body if isinstance(x,ast.FunctionDef)}
def dump(node):return ast.dump(node,include_attributes=False)
class StripDiagnosticRecord(ast.NodeTransformer):
    def visit_Assign(self,node):
        if any(isinstance(x,ast.Name) and x.id=='record' for x in node.targets):
            node.value=ast.Constant(value='independently-reviewed-record-serialization')
        return self.generic_visit(node)
class StripFailurePropagation(ast.NodeTransformer):
    def visit_If(self,node):
        if ast.unparse(node.test)=="'solver_records' in fitted":return None
        return self.generic_visit(node)
class StripPolicyValidation(ast.NodeTransformer):
    def visit_If(self,node):
        if ast.unparse(node.test)=="name == 'revised_rebound_bound_policy'":return None
        return self.generic_visit(node)
class StripRunnerPolicy(ast.NodeTransformer):
    def visit_Call(self,node):
        if isinstance(node.func,ast.Name) and node.func.id=='dict':
            node.keywords=[x for x in node.keywords if x.arg!='revised_rebound_bound_policy']
        return self.generic_visit(node)

def main():
    target=HERE/'contract_review.json'
    if target.exists():raise RuntimeError('preserve completed contract review')
    source_names=['B1算法/b1_algorithm/process/_ride_revised.py','B1算法/b1_algorithm/process/api.py',
                  'B1算法/b1_algorithm/resources/ev.py','work/b1_template_repair_20261030/run.py']
    old=[(WORK/'test/source'/name).read_text(encoding='utf-8') for name in source_names]
    new=[(ROOT/name).read_text(encoding='utf-8') for name in source_names]
    a,b=funcs(old[0]),funcs(new[0])
    check('function inventory revised unchanged',a.keys()==b.keys())
    for name in a:
        if name not in ('rebound_bound','fit_revised_ride'):check('unchanged revised math/start function '+name,dump(a[name])==dump(b[name]))
    check('entire revised fit body same except diagnostic record formatting',
          dump(StripDiagnosticRecord().visit(a['fit_revised_ride']))==dump(StripDiagnosticRecord().visit(b['fit_revised_ride'])))
    a,b=funcs(old[1]),funcs(new[1])
    for name in a:
        if name!='complete':check('unchanged process interface function '+name,dump(a[name])==dump(b[name]))
    check('complete only adds all-failed solver record propagation',dump(a['complete'])==dump(StripFailurePropagation().visit(b['complete'])))
    a,b=funcs(old[2]),funcs(new[2])
    for name in a:
        if name!='ev_config':check('unchanged EV function '+name,dump(a[name])==dump(b[name]))
    check('EV config validation only adds policy validation',dump(a['ev_config'])==dump(StripPolicyValidation().visit(b['ev_config'])))
    old_class=next(x for x in ast.parse(old[2]).body if isinstance(x,ast.ClassDef) and x.name=='EVAnalysisConfig')
    new_class=next(x for x in ast.parse(new[2]).body if isinstance(x,ast.ClassDef) and x.name=='EVAnalysisConfig')
    new_class.body=[x for x in new_class.body if not(isinstance(x,ast.AnnAssign) and isinstance(x.target,ast.Name) and x.target.id=='revised_rebound_bound_policy')]
    check('all old EV default fields and values preserved',dump(old_class)==dump(new_class))
    a,b=funcs(old[3]),funcs(new[3])
    for name in a:
        if name!='bind':check('unchanged runner function '+name,dump(a[name])==dump(b[name]))
    check('runner bind only adds explicit headroom mode shared by all methods',dump(a['bind'])==dump(StripRunnerPolicy().visit(b['bind'])))
    replay=read(WORK/'contract_replay_receipt.json')
    check('root replay covers declared exact predictions',replay['passed'] and replay['actual_public_prediction_replays']==48 and replay['prediction_arrays_features_and_eta_exact'])
    for group in ('raw_file_hashes','event_file_hashes'):
        for name,expected in replay[group].items():check('preserved '+name,sha(ROOT/name)==expected)
    prior=read(HERE/'evidence_review.json')
    check('original frozen main scores preserved',sha(WORK/'test/metrics.csv')==prior['metrics_sha256'])
    check('original frozen source receipt preserved',sha(WORK/'test/source_freeze.json')==prior['frozen_test_source_sha256'])
    bounds=0;min_cap=float('inf')
    for seed in read(WORK/'protocol.json')['test']['seeds']:
        for suffix in ('positive','zero','stress20','stress37'):
            prefix=f'{seed}_{suffix}';facts=read(ROOT/f'data/B1_template_repair_v1_20261030/test/{prefix}_facts.json')
            events=read(WORK/f'test/events/{prefix}_ride_revised.json');cpop=read(WORK/f'test/events/{prefix}_cpop.json')
            native=pd.read_csv(Path(cpop[0]['process']['backend']['artifact_dir'])/'input.csv')
            for i,(fact,event) in enumerate(zip(facts,events)):
                reference=np.asarray(fact['power_kw'])+native[native.case_id==i*10].y.to_numpy()
                data=dict(profile=ev_config(dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom')),reference=reference,q=fact['task']['request_kw'])
                cap,origin=revised.rebound_bound(data);frozen=event['process']['selection_evidence']['rebound_max_ratio']
                check('actual new headroom function equals frozen bound '+prefix+':'+str(i),abs(cap-frozen)<1e-12)
                check('headroom cap source transparent '+prefix+':'+str(i),origin=='declared_max_minus_max_supplied_reference')
                bounds+=1;min_cap=min(min_cap,cap)
    check('all2304frozen bounds audited',bounds==2304 and min_cap>1e-6)
    s=np.arange(-15.,45.);e=s+1.;ref=np.full(60,3.5)
    task=dict(task_id='independent-contract',user_id='u',meter_id='m',start_min=0.,end_min=30.,notice_min=-15.,request_kw=1.5,task_pre_treatment=True)
    def bound(config,reference=ref):
        d=prepare(s,e,ref,reference,task,.05,config)
        return revised.rebound_bound(d)
    check('default mode configured',ev_config().revised_rebound_bound_policy=='configured_ratio')
    check('explicit tight ratio retained with declared max',bound(dict(max_charge_kw=7.2,template_rebound_max_ratio=.02))==(.02,'configured_ratio'))
    check('headroom only when explicitly selected',bound(dict(max_charge_kw=7.2,template_rebound_max_ratio=.02,revised_rebound_bound_policy='declared_headroom'))==((7.2-3.5)/1.5,'declared_max_minus_max_supplied_reference'))
    check('missing max transparent configured fallback',bound(dict(template_rebound_max_ratio=.4,revised_rebound_bound_policy='declared_headroom'))==(.4,'configured_ratio_no_declared_max'))
    for baseline in (3.5,4.):check('zero or negative headroom exactly zero '+str(baseline),bound(dict(max_charge_kw=3.5,revised_rebound_bound_policy='declared_headroom'),np.full(60,baseline))[0]==0.)
    for invalid in (None,True,False,0,1,'auto','',[],{},np.array(['configured_ratio']),np.array(['declared_headroom'])):
        try:ev_config(dict(revised_rebound_bound_policy=invalid))
        except (ValueError,TypeError):check('invalid policy rejected '+repr(invalid),True)
        else:raise AssertionError('invalid policy accepted '+repr(invalid))
    a,b=revised.bounded_amplitudes(np.ones(60),np.ones(60),np.ones(60),1.5,1.5,0.)
    check('zero rebound cap supported by amplitude profile',b==0. and abs(a-2/3)<1e-12)
    supplied=provided_reference(task,s,e,ref,available_at_min=-15.)
    original_solver=revised.least_squares;original_components=revised.interval_components
    try:
        revised.least_squares=lambda fun,x0,**kw:SimpleNamespace(x=x0,success=False,status=0,nfev=250,optimality=np.nan)
        failed=analyze_event(task,s,e,ref,supplied,.05,process_method='ride_revised')
        records=failed['process']['selection_evidence']['solver_records']
        check('all failed starts publicly retained',failed['status']=='degraded' and records and all(not rr['accepted'] and rr['optimality'] is None for rr in records))
        revised.interval_components=lambda times,W,starts,ends,structure:(np.full(len(starts),np.nan),np.zeros(len(starts)))
        bad=analyze_event(task,s,e,ref,supplied,.05,process_method='ride_revised')
        records=bad['process']['selection_evidence']['solver_records']
        check('failed nonfinite RSS serialized as None',bad['status']=='degraded' and records and all(rr.get('rss') is None and not rr['accepted'] for rr in records))
        json.dumps(bad,allow_nan=False);check('public fallback JSON finite',True)
    finally:
        revised.least_squares=original_solver;revised.interval_components=original_components
    check('old default remains original RIDE',resolve_policy(60,delta_min=1.)=='ride_template')
    before=read(WORK/'before_manifest.json')
    for name in ('B1算法/b1_algorithm/process/_policy.json','B1算法/b1_algorithm/process/_ride_fit.py','B1算法/b1_algorithm/process/_ride_identify.py','B1算法/b1_algorithm/process/_ride_template.py','B1算法/b1_algorithm/process/_cpop.py','B1算法/b1_algorithm/process/cpop_batch.R'):
        check('original method/default unchanged '+name,sha(ROOT/name)==before['runtime'][name])
    for name,expected in before['protected'].items():check('protected '+name,sha(ROOT/name)==expected)
    result=dict(passed=True,n_technical_assertions=len(checks),frozen_headroom_equivalent_records=bounds,min_frozen_headroom_ratio=min_cap,
        root_public_replay_evidence_reviewed=48,independent_main_experiment_refits=0,main_scores_recomputed_again=False,
        objective_initialization_template_solver_BIC_detection_unchanged_except_diagnostic_serialization=True,
        default_configured_ratio_respected=True,explicit_headroom_required_for_frozen_results=True,zero_headroom_boundary_corrected=True,
        failure_diagnostics_JSON_finite_and_public=True,old_method_and_default_preserved=True,
        current_source_sha256={name:sha(ROOT/name) for name in source_names},
        equivalence_scope='All2304frozen events in explicitdeclared_headroom mode. The new defaultconfigured_ratio and exactzero headroom boundary intentionally change behavior outside this equivalent panel; no unchangedmathematics claim for arbitrary inputs.',
        no_new_performance_claim=True,findings=[])
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','n_technical_assertions','frozen_headroom_equivalent_records','min_frozen_headroom_ratio','independent_main_experiment_refits')},indent=2))
if __name__=='__main__':main()
