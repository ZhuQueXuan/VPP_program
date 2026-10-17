"""Adapt independent project tasks to the colleague's unchanged DML core."""
from __future__ import annotations
import os
for _var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_var] = '2'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
import traceback
import warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
warnings.filterwarnings('ignore', message='X does not have valid feature names')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / 'data/驱动因素解耦模拟数据集_v2'
CORE = ROOT / 'work/vpp_dml_review_20261017/vpp_dml_framework'
sys.path.insert(0, str(CORE))
from vpp_dml.pipeline import DMLSpec, VPPResponseDML, make_final
from vpp_dml.nuisance import crossfit, default_learner
from vpp_dml.diagnostics import identification_report

ARMS = [0.8, 1.2, 1.6]
PHI = ['price_08_vs_04', 'price_12_vs_04', 'price_16_vs_04']
NUMERIC = ['rated_power_mw', 'scenario_difficulty', 'required_duration_minutes',
           'predecision_state_index_pct', 'prior_accepted_tasks_7d',
           'ambient_temperature_c', 'production_factor', 'execution_authorized']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p, x): p.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
def csv(p, x): x.to_csv(p, index=False, encoding='utf-8-sig', float_format='%.15g')

class TaskDML(VPPResponseDML):
    """Only replace panel splitting/clock groups; retain colleague estimators."""
    def fit_tasks(self, df, features, folds, aggregation_groups, nuisance=None):
        X = df[features].to_numpy(float)
        self.nuis = nuisance if nuisance is not None else crossfit(
            X, df['completion_ratio'].to_numpy(float), df[PHI].to_numpy(float), folds,
            learner_factory=lambda: default_learner(300, 2026), phi_names=PHI)
        self.gate = identification_report(self.nuis)
        if not self.gate['ok']:
            raise ValueError('Identification gate failed before final fit: '+str(self.gate))
        self.Z = X
        self.groups = aggregation_groups
        self.final = make_final(self.spec, features)
        self.final.fit(X, self.nuis.y_res, self.nuis.phi_res, groups=aggregation_groups, time=None)
        self.theta = self.final.effect(X)
        self._df_index = df.index
        return self

    def predict_effects(self, df, features):
        return self.final.effect(df[features].to_numpy(float))

def prepare(out):
    a = pd.read_csv(DATA/'01_predecision_inputs.csv')
    y = pd.read_csv(DATA/'02_observed_responses.csv', usecols=['case_id','entity_id','split','completion_ratio'])
    entities = pd.read_csv(DATA/'01_entities.csv')
    assert len(a)==3456 and a.case_id.is_unique and len(entities)==96
    assert a.assignment_design.eq('entity_blocked_random_permutation_of_full_factorial').all()
    assert np.allclose(a.assignment_probability, .25)
    assert np.all(pd.to_datetime(a.observed_at) <= pd.to_datetime(a.decision_at))
    assert np.all(pd.to_datetime(a.decision_at) < pd.to_datetime(a.start_at))
    assert len(a)==len(y) and y.case_id.is_unique
    d = a[['case_id','entity_id','aggregation_id','resource_type_id','model_family','split',
           'incentive_yuan_per_kwh']+NUMERIC].merge(y, on=['case_id','entity_id','split'], validate='one_to_one')
    assert len(d)==3456 and d.completion_ratio.between(0,1).all()
    expected={'train':{'SYN-AGG-01','SYN-AGG-02','SYN-AGG-03'},'validation':{'SYN-AGG-04'},'test':{'SYN-AGG-05','SYN-AGG-06'}}
    for s,groups in expected.items(): assert set(d.loc[d.split==s,'aggregation_id'])==groups
    assert d.groupby('entity_id')['split'].nunique().max()==1
    for _,g in d.groupby('entity_id'):
        assert len(g)==36
        assert g.groupby('incentive_yuan_per_kwh').size().to_dict()=={.4:9,.8:9,1.2:9,1.6:9}
    d['execution_authorized']=d.execution_authorized.astype(float)
    assert np.isfinite(d[NUMERIC].to_numpy(float)).all()
    train=d[d.split=='train'].copy()
    levels=sorted(train.resource_type_id.unique().tolist())
    assert len(levels)==16 and set(d.resource_type_id)<=set(levels)
    feature_cols=list(NUMERIC)
    for k,name in enumerate(levels[1:],1):
        col=f'type_{k:02d}'
        d[col]=(d.resource_type_id==name).astype(float)
        feature_cols.append(col)
    # Scaling is frozen using outer training only. No labels or latent truth used.
    mu=d.loc[d.split=='train',feature_cols].mean()
    sd=d.loc[d.split=='train',feature_cols].std(ddof=0)
    sd=sd.where(sd>1e-12,1)
    d[feature_cols]=(d[feature_cols]-mu)/sd
    for arm,col in zip(ARMS,PHI): d[col]=np.isclose(d.incentive_yuan_per_kwh,arm).astype(float)
    sets={s:d[d.split==s].reset_index(drop=True) for s in expected}
    tr=sets['train']
    groups=tr.aggregation_id.to_numpy()
    folds=list(GroupKFold(3).split(tr,groups=groups))
    fold_rows=[]
    for i,(ftr,fte) in enumerate(folds):
        assert not(set(groups[ftr])&set(groups[fte]))
        for side,idx in [('fit',ftr),('residual',fte)]:
            for j in idx: fold_rows.append({'fold':i,'role':side,'case_id':tr.case_id.iloc[j],'aggregation_id':groups[j]})
    csv(out/'fold_membership.csv',pd.DataFrame(fold_rows))
    csv(out/'prepared_model_rows.csv',d)
    dump(out/'encoding.json',{'features':feature_cols,'numeric':NUMERIC,'type_levels':levels,
         'onehot_drop_reference':levels[0],'train_mean':mu.to_dict(),'train_sd':sd.to_dict(),'treatment_features':PHI})
    qa={'rows':{s:len(v) for s,v in sets.items()},'entities':{s:int(v.entity_id.nunique()) for s,v in sets.items()},
        'aggregations':{s:sorted(v.aggregation_id.unique().tolist()) for s,v in sets.items()},
        'types':16,'finite_inputs':True,'all_outcomes_kept':True,
        'learner_predictor_columns':feature_cols+PHI,'postdecision_predictors':[],
        'source_truth_read_for_training':False,'input_only_rows_all_3456':True}
    dump(out/'admission.json',qa)
    return sets,feature_cols,folds,groups

def predictions(out, sets, features, folds, groups):
    tr=sets['train']; X=tr[features].to_numpy(float); A=tr[PHI].to_numpy(float); y=tr.completion_ratio.to_numpy(float)
    B=np.column_stack([np.ones(len(X)),X])
    # Same feature basis and three treatment-feature interactions as series R-learner.
    design=np.column_stack([B,(A[:,:,None]*B[:,None,:]).reshape(len(X),-1)])
    ols=np.linalg.lstsq(design,y,rcond=1e-12)[0]
    ols_effect=ols[B.shape[1]:].reshape(3,B.shape[1])
    constant=np.array([tr.loc[np.isclose(tr.incentive_yuan_per_kwh,v),'completion_ratio'].mean()
                      -tr.loc[np.isclose(tr.incentive_yuan_per_kwh,.4),'completion_ratio'].mean() for v in ARMS])
    specs=[DMLSpec(name='DML_SERIES',outcome='completion_ratio',phi_cols=PHI,z_cols=features,w_cols=[],
                   final='series',seed=2026,n_estimators=300,final_kwargs={'group_col':None,'ridge':1e-4}),
           DMLSpec(name='DML_FOREST',outcome='completion_ratio',phi_cols=PHI,z_cols=features,w_cols=[],
                   final='forest',seed=2026,n_estimators=300)]
    models={}; nuisance=None
    for spec in specs:
        start=time.perf_counter()
        est=TaskDML(spec).fit_tasks(tr,features,folds,groups,nuisance)
        nuisance=est.nuis
        models[spec.name]=est
        diag=est.gate
        csv(out/f'{spec.name}_identification.csv',diag['table'])
        dump(out/f'{spec.name}_fit.json',{'elapsed_s':time.perf_counter()-start,'gate_ok':bool(diag['ok']),
             'r2_l':diag['r2_l'],'condition':diag['cond'],'fit_rows':len(tr),'fit_aggregations':sorted(set(groups)),
             'treatment_residual_sd':est.nuis.phi_res.std(axis=0).tolist(),'confidence_intervals_reported':False})
        print(f'{spec.name} trained; identification ok={diag["ok"]}',flush=True)
    np.savez(out/'series_reconstruction.npz',Z=X,y_res=nuisance.y_res,phi_res=nuisance.phi_res,
             groups=np.unique(groups,return_inverse=True)[1],beta=models['DML_SERIES'].final.beta,
             ols_coef=ols,constant_effects=constant)
    rows=[]
    for split in ['validation','test']:
        df=sets[split]; z=df[features].to_numpy(float); basis=np.column_stack([np.ones(len(z)),z])
        values={'B_ZERO':np.zeros((len(df),3)),'B_CONSTANT':np.tile(constant,(len(df),1)),
                'B_OLS':basis@ols_effect.T}
        values.update({name:est.predict_effects(df,features) for name,est in models.items()})
        for name,pred in values.items():
            assert pred.shape==(len(df),3) and np.isfinite(pred).all()
            for j,(arm,col) in enumerate(zip(ARMS,PHI)):
                for i,rec in df.iterrows():
                    rows.append({'case_id':rec.case_id,'entity_id':rec.entity_id,'aggregation_id':rec.aggregation_id,
                        'resource_type_id':rec.resource_type_id,'model_family':rec.model_family,'split':split,
                        'model':name,'contrast_price':arm,'reference_price':.4,'estimated_effect':pred[i,j]})
    p=pd.DataFrame(rows);csv(out/'predictions.csv',p)
    # Factual held-out responses were not passed to any fit function.
    return p

def metrics(out, pred):
    # This is intentionally the first read of potential outcomes in this workflow.
    t=pd.read_csv(DATA/'03_counterfactual_truth_evaluation_only.csv')
    assert len(t)==13824 and not t.duplicated(['case_id','intervention_incentive_yuan_per_kwh']).any()
    wide=t.pivot(index='case_id',columns='intervention_incentive_yuan_per_kwh',values='potential_completion_ratio')
    truth=pd.concat([pd.DataFrame({'case_id':wide.index,'contrast_price':v,'true_effect':(wide[v]-wide[.4]).to_numpy()}) for v in ARMS],ignore_index=True)
    d=pred.merge(truth,on=['case_id','contrast_price'],validate='many_to_one')
    assert len(d)==len(pred)
    null=d.model_family.isin(['pv','storage'])
    assert np.max(np.abs(d.loc[null,'true_effect']))==0
    csv(out/'evaluation_rows.csv',d)
    rows=[]
    for (s,m,c),g in d.groupby(['split','model','contrast_price'],sort=True):
        subsets=[('overall','all',g)]
        subsets += [('type',str(k),v) for k,v in g.groupby('resource_type_id')]
        subsets += [('aggregation',str(k),v) for k,v in g.groupby('aggregation_id')]
        subsets += [('declared_null','pv_storage',g[g.model_family.isin(['pv','storage'])]),
                    ('other_families','non_null_design',g[~g.model_family.isin(['pv','storage'])])]
        for kind,label,v in subsets:
            err=v.estimated_effect-v.true_effect
            rows.append({'split':s,'model':m,'contrast_price':c,'group_kind':kind,'group':label,'n':len(v),
               'true_mean_pp':100*v.true_effect.mean(),'estimated_mean_pp':100*v.estimated_effect.mean(),
               'bias_pp':100*err.mean(),'mae_pp':100*err.abs().mean(),'rmse_pp':100*np.sqrt(np.mean(err**2)),
               'abs_prediction_over_5pp_fraction':np.mean(np.abs(v.estimated_effect)>.05)})
    report=pd.DataFrame(rows);csv(out/'metrics_by_group.csv',report)
    summary=[]
    for (s,m,c),g in report.groupby(['split','model','contrast_price']):
        a=g[g.group_kind=='overall'].iloc[0];n=g[g.group_kind=='declared_null'].iloc[0];ty=g[g.group_kind=='type']
        summary.append({'split':s,'model':m,'contrast_price':c,'true_mean_pp':a.true_mean_pp,
              'estimated_mean_pp':a.estimated_mean_pp,'bias_pp':a.bias_pp,'type_mean_abs_bias_pp':ty.bias_pp.abs().mean(),
              'individual_mae_pp':a.mae_pp,'individual_rmse_pp':a.rmse_pp,'null_mae_pp':n.mae_pp,
              'null_over_5pp_fraction':n.abs_prediction_over_5pp_fraction})
    summ=pd.DataFrame(summary);csv(out/'summary.csv',summ)
    print(summ[(summ.split=='test') & np.isclose(summ.contrast_price,1.6)].to_string(index=False),flush=True)
    return summ

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',default=datetime.now(timezone(timedelta(hours=8))).strftime('RUN_%Y%m%d_%H%M%S'))
    args=ap.parse_args();out=HERE/'runs'/args.run_id
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    start=time.perf_counter()
    sources=[DATA/n for n in ['manifest.json','01_entities.csv','01_predecision_inputs.csv','02_observed_responses.csv','03_counterfactual_truth_evaluation_only.csv']]
    sources+=list((CORE/'vpp_dml').glob('*.py'))+[HERE/'protocol.json',Path(__file__).resolve()]
    before={str(p.relative_to(ROOT)):sha(p) for p in sources}
    receipt={'run_id':args.run_id,'status':'running','source_sha256':before,'protocol_sha256':sha(HERE/'protocol.json'),
             'python':sys.version,'versions':{m:importlib.metadata.version(m) for m in ['numpy','pandas','scikit-learn','lightgbm','econml']},
             'method':'colleague core + project task adapter','real_data':False}
    dump(out/'receipt.json',receipt)
    try:
        sets,features,folds,groups=prepare(out)
        pred=predictions(out,sets,features,folds,groups)
        summ=metrics(out,pred)
        receipt.update(status='completed',elapsed_s=time.perf_counter()-start,prediction_rows=len(pred),
                       source_unchanged=all(sha(ROOT/p)==v for p,v in before.items()),
                       outputs_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='receipt.json'})
        assert receipt['source_unchanged']
        dump(out/'receipt.json',receipt)
        print('COMPLETED',out,flush=True)
    except Exception:
        receipt.update(status='failed',elapsed_s=time.perf_counter()-start,error=traceback.format_exc())
        dump(out/'receipt.json',receipt)
        raise

if __name__=='__main__':main()
