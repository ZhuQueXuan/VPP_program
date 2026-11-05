"""Direct multi-horizon ridge from the complete legal observed prefix."""
from common import *
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from b1_algorithm.reference.core import ReferenceWindow,_validated

def features(fact,history):
    w=ReferenceWindow(**fact['reference_window']);a=_validated(w)
    pre=np.asarray(w.pre_power_kw,float);s=np.asarray(w.pre_starts_min);e=np.asarray(w.pre_ends_min)
    use=(s>=a['notice']-60-1e-8)&(e<=a['notice']+1e-8);p=pre[use]
    assert len(p)==60 and max(e[use])<=a['notice']
    anchor=float(p.mean());x=p-anchor
    if history:
        prior=np.asarray(w.prior_mean_kw,float);x=np.r_[x,prior-prior.mean()]
    return x,anchor

def fit(facts,alpha,history):
    assert all(f['non_event'] and not f['task_dispatched'] for f in facts)
    X=[];Y=[]
    for f in facts:
        x,anchor=features(f,history);X.append(x);Y.append(np.asarray(f['power_kw'])-anchor)
    scaler=StandardScaler().fit(X);reg=Ridge(alpha=alpha,solver='cholesky').fit(scaler.transform(X),Y)
    return dict(schema='b1.prefix60-multioutput-ridge.v1',alpha=alpha,history=history,mean=scaler.mean_,scale=scaler.scale_,coef=reg.coef_,intercept=reg.intercept_,
        fit_cutoff=max(f['availability']['power_records_available_at_min'] for f in facts),training_users=sorted({f['task']['user_id'] for f in facts}),
        training_tasks=[f['task']['task_id'] for f in facts],features='All60 observed pre-notice intervals, centered by their mean; optional centered historical60 curve',
        source='Completed explicitly non-dispatched non-event observed powers, no evaluator truth')

def predict(model,facts):
    X=[];anchors=[]
    for f in facts:
        assert f['task']['notice_min']>model['fit_cutoff'] and f['task']['user_id'] not in model['training_users']
        x,anchor=features(f,model['history']);X.append(x);anchors.append(anchor)
    z=(np.asarray(X)-model['mean'])/model['scale'];prediction=z@np.asarray(model['coef']).T+model['intercept']+np.asarray(anchors)[:,None]
    assert np.isfinite(prediction).all() and prediction.min()>=0
    return prediction

def prepare():
    gen=load(ROOT/'work/b1_reliability_20261031/study/generator.py','non_event_training_source')
    train=[]
    for seed in [7730000,7730001]:train+=gen.generate_reliability(seed,256,variants=('non_event',),clock_shift_min=14011200)['non_event'][0]
    val=gen.generate_reliability(7730100,64,variants=('non_event',),clock_shift_min=16027200)['non_event'][0]
    write('reference/train_facts.json',train);write('reference/validation_facts.json',val);results=[]
    for history in [False,True]:
      for alpha in [.1,1.,10.,100.]:
        model=fit(train,alpha,history);p=predict(model,val);target=np.array([f['power_kw'] for f in val]);loss=float(np.mean((p-target)**2))
        name=f'reference/model_h{int(history)}_a{alpha:g}.json';write(name,model);results.append(dict(model=name,rmse=float(np.sqrt(loss)),alpha=alpha,history=history))
    chosen=min(results,key=lambda r:r['rmse']);write('reference/selection.json',dict(candidates=results,selected=chosen,training_n=len(train),validation_n=len(val)))
    print(json.dumps(chosen),flush=True)
if __name__=='__main__':prepare()
