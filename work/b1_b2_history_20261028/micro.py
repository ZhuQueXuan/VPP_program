"""Development correctness tests, no scientific test-score tuning."""
import copy
import numpy as np
from sklearn.neural_network import MLPRegressor
from io_utils import BASE,write
from legacy import b1_event,templates,base_forecast,safe_b2
from features import physical,current,extract_one,summarize,assemble
from models import latent,select
from api import histories

def main():
    checks=0
    c=dict(b=3.,T=120.,q=1.5,E=6.,low=-1.,high=2.,prob=.5,reference=.4,green_preference=.5,green_attribute=1,risk=.4,permission=True)
    o=physical({k:np.array([v]) for k,v in c.items()});p=base_forecast(o)[0];safe=safe_b2(c)
    assert safe['default_execution']=='dynamic' and abs(p[1:3].sum()-safe['service30_v1_probability'])<1e-12;checks+=1
    assert current(o,p[None]).shape==(1,17);checks+=1
    ref=np.r_[np.full(120,3.)];powers=[]
    for i,a in enumerate(templates()):
        power=np.r_[3-1.5*a,np.full(90,3+1.5*a.sum()/90)];f=b1_event(ref,power,1.5)
        assert abs(f[0]-a.mean())<1e-12 and f[3]==int(i<4);checks+=1
        assert abs(f[1]-[0,2/30,5/30,0,0][i])<1e-12;checks+=1
        powers.append(power)
    zero=b1_event(ref,ref,1.5);assert np.array_equal(zero,[0,1,1,0]);checks+=1
    h=extract_one(np.tile(ref,(3,1)),np.array(powers[:3]),[1.5]*3);assert h['raw'].shape==(90,) and h['summary'].shape==(6,);checks+=1
    wrapper=dict(resource_id='EV-A',event_id='current',start='2026-10-28T09:00:00+08:00',information_cutoff='2026-10-28T09:00:00+08:00',history=[],current=c)
    for i in range(3):
        hour=i*3;wrapper['history'].append(dict(resource_id='EV-A',event_id=str(i),start=f'2026-10-28T{hour:02d}:00:00+08:00',observation_end=f'2026-10-28T{hour+2:02d}:00:00+08:00',available_at=f'2026-10-28T{hour+2:02d}:00:00+08:00',b=3.,T=120.,q=1.5,reference_kw=ref.tolist(),measured_kw=powers[i].tolist()))
    assert np.allclose(histories(wrapper)['raw'],h['raw']);checks+=1
    for kind in ['resource','future','duplicate','order','missing_bin','naive','energy','shape','overlap','availability']:
        v=copy.deepcopy(wrapper)
        if kind=='resource':v['history'][0]['resource_id']='other'
        if kind=='future':v['information_cutoff']='2026-10-28T07:00:00+08:00'
        if kind=='duplicate':v['history'][0]['event_id']='current'
        if kind=='order':v['history'].reverse()
        if kind=='missing_bin':v['history'][0]['measured_kw'].pop()
        if kind=='naive':v['start']='2026-10-28T09:00:00'
        if kind=='energy':v['history'][0]['measured_kw'][60]+=.1
        if kind=='shape':v['history'][0]['measured_kw'][0]+=.1;v['history'][0]['measured_kw'][1]-=.1
        if kind=='overlap':v['history'][1]['start']='2026-10-28T01:00:00+08:00';v['history'][1]['observation_end']='2026-10-28T03:00:00+08:00';v['history'][1]['available_at']='2026-10-28T03:00:00+08:00'
        if kind=='availability':v['history'][2]['available_at']='2026-10-28T10:00:00+08:00'
        try:histories(v)
        except ValueError:checks+=1
        else:raise AssertionError(kind)
    for n in [0,1,2]:
        v=copy.deepcopy(wrapper);v['history']=v['history'][:n];assert histories(v) is None;checks+=1
    rng=np.random.default_rng(991);z=rng.normal(size=(8,90));ae=MLPRegressor(hidden_layer_sizes=(24,6,24),max_iter=2,random_state=4).fit(z,z)
    manual=np.array([[np.tanh(sum(np.tanh(sum(z[row,k]*ae.coefs_[0][k,i] for k in range(90))+ae.intercepts_[0][i])*ae.coefs_[1][i,j] for i in range(24))+ae.intercepts_[1][j]) for j in range(6)] for row in range(8)])
    assert np.allclose(latent(ae,z),manual,atol=1e-13);checks+=1
    changed=copy.deepcopy(wrapper);changed['current']['future_result']='ignored';assert np.array_equal(histories(changed)['raw'],h['raw']);checks+=1
    v=copy.deepcopy(wrapper);v['history']=[];write(BASE/'example_input.json',wrapper)
    write(BASE/'micro.json',dict(checks=checks,status='passed',scientific_test_data_used=False))
    print('micro passed',checks,flush=True)

if __name__=='__main__':main()
