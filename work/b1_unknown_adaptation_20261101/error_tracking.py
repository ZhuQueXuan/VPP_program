"""Retrospective conditional reference-error tracking from pre-actuation meters.

The pre-notice reference is unchanged. This is a process-layer nuisance model,
conditioned on observed task-relative[-15,0) powers, not a notice-time forecast.
"""
from common import *
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from b1_algorithm.reference.core import ReferenceWindow
from b1_algorithm.reference.reliable import load_ev_reliable_reference_model,predict_ev_reliable_reference

def forecasts(facts):
    m=load_ev_reliable_reference_model(ROOT/'work/b1_reliability_20261031/study/models/reliable_reference.json')
    return np.array([predict_ev_reliable_reference(m,ReferenceWindow(**f['reference_window'])).reference_kw for f in facts])

def prepare():
    train=read('reference/train_facts.json');val=read('reference/validation_facts.json')
    a=forecasts(train)-np.array([f['power_kw'] for f in train]);b=forecasts(val)-np.array([f['power_kw'] for f in val]);results=[]
    for alpha in [.1,1.,10.,100.]:
        scaler=StandardScaler().fit(a[:,:15]);model=Ridge(alpha=alpha,solver='cholesky').fit(scaler.transform(a[:,:15]),a)
        payload=dict(schema='b1.pre-actuation-reference-error.v1',alpha=alpha,mean=scaler.mean_,scale=scaler.scale_,coef=model.coef_,intercept=model.intercept_,
            fit_cutoff=max(f['availability']['power_records_available_at_min'] for f in train),training_users=sorted({f['task']['user_id'] for f in train}),
            input='Observed residuals in[-15,0) task minutes only, no response-period or rebound measurements',
            output='Conditional mean forecast error on60 interval grid; reference-at-notice artifact and raw accounting unchanged',
            model_role='Retrospective process nuisance correction, conditional on pre-actuation interval being before the commanded action')
        p=predict(payload,b);name=f'error_tracking/model_a{alpha:g}.json';write(name,payload)
        results.append(dict(model=name,alpha=alpha,baseline_RMSE=float(np.sqrt(np.mean(b[:,15:]**2))),corrected_RMSE=float(np.sqrt(np.mean((b[:,15:]-p[:,15:])**2)))))
    chosen=min(results,key=lambda r:r['corrected_RMSE']);write('error_tracking/selection.json',dict(candidates=results,selected=chosen,train_n=len(train),validation_n=len(val),truth_read=False))
    print(json.dumps(chosen),flush=True)

def predict(model,y):
    y=np.atleast_2d(y);return (y[:,:15]-model['mean'])/model['scale']@np.asarray(model['coef']).T+model['intercept']
if __name__=='__main__':prepare()
