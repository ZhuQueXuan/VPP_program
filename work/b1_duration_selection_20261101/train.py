from common import *
from learned import export_model,predict_model
from sklearn.ensemble import HistGradientBoostingRegressor,HistGradientBoostingClassifier
from scipy.special import expit

def main():
    source=ROOT/'work/b1_fast_selection_20261101';data=np.load(source/'training_features.npz',allow_pickle=False);X=data['X'];y=data['y']
    write('training_protocol.json',dict(objective='Duration accuracy, not computation speed. Quantile/threshold-state losses target threshold-crossing errors more directly than squared curve error.',
        source_training_features_sha256=sha(source/'training_features.npz'),training_cases=1792,training_rows=len(y),
        models=['q40_leaves31','q50_leaves31','q60_leaves31','classifier_leaves31'],max_iter=200,min_samples_leaf=30,l2=10.,
        development='Previously seen v2/v3 data and round1 validation explicitly development only; all new validation/test seeds remain unseen.',
        allowed_features='42 observed multiscale raw/segment statistics; no truth, kind, seed, cause or execution labels at prediction.',
        inference='Degree0/1 DP plus posterior quantile or threshold-state reconciliation; raw observations and accounting retained. Strong values use original DP estimate.',
        loss_scope='Simulation-trained standard scikit-learn models, not new statistical estimator or field validation.'))
    receipt=[]
    for quantile in [.4,.5,.6]:
        tic=time.perf_counter();m=HistGradientBoostingRegressor(loss='quantile',quantile=quantile,max_iter=200,max_leaf_nodes=31,min_samples_leaf=30,l2_regularization=10.,learning_rate=.08,early_stopping=False,random_state=7670000).fit(X,y)
        p=export_model(m);p['loss']='quantile';p['quantile']=quantile;name=f'model_q{int(quantile*100)}.json';write(name,p)
        xx=X[::max(1,len(X)//3000)];error=float(np.max(abs(predict_model(p,xx)-m.predict(xx))));assert error<1e-10
        receipt.append(dict(model=name,seconds=time.perf_counter()-tic,export_error=error))
    tic=time.perf_counter();m=HistGradientBoostingClassifier(max_iter=200,max_leaf_nodes=31,min_samples_leaf=30,l2_regularization=10.,learning_rate=.08,early_stopping=False,random_state=7670000).fit(X,(y*.05>=.15).astype(int))
    p=export_model(m);p['loss']='log_loss';name='model_classifier.json';write(name,p)
    xx=X[::max(1,len(X)//3000)];error=float(np.max(abs(expit(predict_model(p,xx))-m.predict_proba(xx)[:,1])));assert error<1e-10
    receipt.append(dict(model=name,seconds=time.perf_counter()-tic,export_error=error))
    write('training_receipt.json',dict(models=receipt,source=str(source.relative_to(ROOT)),feature_sha256=sha(source/'training_features.npz'),rows=len(y)))
    print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
