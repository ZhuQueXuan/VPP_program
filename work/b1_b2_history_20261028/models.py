"""Small fixed encoders and identical multinomial heads; no test selection."""
import warnings
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.neural_network import MLPRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from legacy import templates

NAMES=['C0','C1','C2','C3']
def latent(ae,z):
    for i in range(2):z=np.tanh(z@ae.coefs_[i]+ae.intercepts_[i])
    return z

def fit(X,S,H,y,eligible,train,rep):
    mask=train&eligible;counts=np.bincount(y[mask],minlength=6)
    if counts.min()<20:raise RuntimeError('insufficient training class support; experiment unavailable')
    scale=StandardScaler().fit(H[train]);z=scale.transform(H);pca=PCA(6,svd_solver='full').fit(z[train])
    ae=MLPRegressor(hidden_layer_sizes=(24,6,24),activation='tanh',solver='adam',alpha=.001,learning_rate_init=.003,batch_size=128,max_iter=60,tol=0,n_iter_no_change=61,early_stopping=False,random_state=810+rep)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always');ae.fit(z[train],z[train])
    designs=[X,np.c_[X,S],np.c_[X,pca.transform(z)],np.c_[X,latent(ae,z)]];heads=[];probs=[];messages=[str(w.message) for w in caught]
    for v in designs:
        head=make_pipeline(StandardScaler(),LogisticRegression(C=1,solver='lbfgs',max_iter=1000,tol=1e-8))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always');head.fit(v[mask],y[mask])
        messages.extend(str(w.message) for w in caught);assert np.array_equal(head[-1].classes_,np.arange(6))
        p=head.predict_proba(v);p[~eligible]=[1,0,0,0,0,0];heads.append(head);probs.append(p)
    return dict(scale=scale,pca=pca,ae=ae,heads=heads),np.array(probs),dict(class_counts=counts,warnings=messages,ae_epochs=ae.n_iter_,ae_loss_curve=ae.loss_curve_,ae_parameters=sum(x.size for x in ae.coefs_+ae.intercepts_),head_iterations=[int(h[-1].n_iter_.max()) for h in heads])

def predict(m,X,S,H,method):
    if method==0:v=X
    elif method==1:v=np.c_[X,S]
    else:
        z=m['scale'].transform(H);v=np.c_[X,m['pca'].transform(z) if method==2 else latent(m['ae'],z)]
    return m['heads'][method].predict_proba(v)

def metrics(p,y,q):
    mean=templates().mean(axis=1);expected=q*(p[:,1:]@mean);actual=q*np.r_[0,mean][y];service=np.isin(y,[1,2]).astype(float);ps=p[:,1:3].sum(axis=1)
    return dict(mse=float(np.mean((expected-actual)**2)),rmse=float(np.sqrt(np.mean((expected-actual)**2))),mae=float(np.mean(abs(expected-actual))),brier=float(np.mean((ps-service)**2)),n=len(y))

def select(probs,y,q,valid):
    scores=[metrics(p[valid],y[valid],q[valid]) for p in probs];base=scores[0]
    allowed=[i for i in range(1,4) if scores[i]['mse']<base['mse'] and scores[i]['brier']<=base['brier']]
    return min(allowed,key=lambda i:(scores[i]['mse'],i)) if allowed else 0,scores
