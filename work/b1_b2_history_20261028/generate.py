"""Fresh paired synthetic histories. Truth stays outside public observations."""
import time
import numpy as np
from scipy.special import expit,softmax
from io_utils import BASE,RAW,read,write,sha
from features import physical
from legacy import loader,templates,b1_event

def one(rep,p):
    rng=np.random.default_rng(p['data']['seed_start']+rep);U=p['data']['users'];K=p['data']['events'];shape=(U,K)
    b=rng.uniform(.6,7,shape);T=rng.choice([60.,90.,120.],shape);q=rng.choice([1.5,3.],shape)
    o=dict(b=b,T=T,q=q,E=b*T/60,low=rng.uniform(-2,0,shape),high=rng.uniform(.5,4,shape),prob=rng.uniform(.1,.9,shape),
      reference=rng.uniform(-.4,1.8,shape),green_preference=np.repeat(rng.random(U)[:,None],K,axis=1),green_attribute=rng.integers(0,2,shape),risk=rng.random(shape),permission=rng.random(shape)<.85)
    o=physical(o);order=rng.permutation(U);split=np.empty(U,int);split[order[:240]]=0;split[order[240:320]]=1;split[order[320:]]=2
    stable=.8*rng.normal(size=U);drift=np.empty(shape);drift[:,0]=stable
    for j in range(1,K):drift[:,j]=.7*drift[:,j-1]+np.sqrt(1-.49)*.8*rng.normal(size=U)
    latent=np.stack([np.zeros(shape),np.repeat(stable[:,None],K,axis=1),drift]);ua=rng.random(shape);us=rng.random(shape)
    flat={k:v.ravel() for k,v in o.items()}
    with loader.legacy('b2') as old:
        z=-.4+.9*old.predict.__globals__['difference'](flat['low'],flat['high'],flat['prob'],flat['reference'],2.,.7)-1.1*flat['discomfort']+.6*flat['green_preference']*flat['green_attribute']
    # Independent coefficients, never fitted probabilities.
    risk=o['risk'];m=o['margin'];logits=np.stack([1.1-1.2*risk+1.5*m,.4+.4*risk,-.4+1.2*risk-.8*m,-.7+1.6*risk-1.2*m,-.5+.8*risk],axis=-1)
    pa=expit(z.reshape(shape)[None]+.7*latent);pe=softmax(logits[None]+latent[:,:,:,None]*np.array([.9,.1,-.2,-.7,-.1]),axis=-1)
    A=np.where(o['eligible'][None],(ua[None]<pa).astype(int),-1);state=np.minimum(np.sum(us[None,:,:,None]>pe.cumsum(axis=-1),axis=-1),4)
    label=np.where(A==1,state+1,0);reduction=o['q'][None,:,:,None]*templates()[state]*(A==1)[:,:,:,None]
    ref=o['b'][:,:,None]*(np.arange(120)[None,None,:]<o['T'][:,:,None]);power=np.repeat(ref[None],3,axis=0)
    power[:,:,:,:30]-=reduction
    post=o['b'][None]+reduction.sum(axis=-1)/60/(o['T'][None]/60-.5)
    for s in range(3):
        for minute in range(30,120):power[s,:,:,minute]=post[s]*(minute<o['T'])
    assert power.min()>-1e-9 and power.max()<7.2+1e-9
    assert abs(power.sum(axis=-1)/60-o['E'][None]).max()<1e-9
    return o,split,A,np.where(A==1,state,-1),label,power,dict(latent=latent,pa=pa,pe=pe)

def main():
    p=read(BASE/'protocol.json');RAW.mkdir(exist_ok=True,parents=True);start=time.perf_counter();obs=[];splits=[];aa=[];ss=[];yy=[];powers=[];truth=[];b1=[]
    if (RAW/'observations.npz').exists():raise RuntimeError('raw already exists')
    for r in range(p['data']['repetitions']):
        o,sp,a,s,y,power,t=one(r,p);ref=o['b'][:,:,None]*(np.arange(120)<o['T'][:,:,None]);f=np.empty((3,400,12,4))
        for scene in range(3):
            for u in range(400):
                for j in range(12):f[scene,u,j]=b1_event(ref[u,j],power[scene,u,j],o['q'][u,j])
        obs.append(o);splits.append(sp);aa.append(a);ss.append(s);yy.append(y);powers.append(power);truth.append(t);b1.append(f)
        print('generated and native B1 extracted',r+1,flush=True)
    with (RAW/'observations.npz').open('xb') as f:np.savez_compressed(f,**{k:np.stack([o[k] for o in obs]) for k in obs[0]},split=splits,A=aa,state=ss,label=yy,power=powers)
    with (BASE/'truth.npz').open('xb') as f:np.savez_compressed(f,**{k:np.stack([t[k] for t in truth]) for k in truth[0]})
    with (BASE/'b1_features.npz').open('xb') as f:np.savez_compressed(f,features=b1)
    write(BASE/'generation.json',dict(variants=288000,base_events=96000,native_B1_calls=288000,seconds=time.perf_counter()-start,raw_sha=sha(RAW/'observations.npz'),features_sha=sha(BASE/'b1_features.npz')))

if __name__=='__main__':main()
