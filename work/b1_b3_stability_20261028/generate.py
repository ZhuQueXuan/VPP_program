"""Public declarations and private paired executions, no new learning."""
from datetime import datetime,timedelta
import numpy as np
from scipy.special import expit,softmax
from core_io import BASE,RAW,read,write,integrity,sha
from controller import LOW

def probabilities(c,arrivals):
    pa=[];ps=[]
    for task in arrivals:
        aa=[];ss=[]
        for ev in c['evs']:
            o=ev['declaration'];b=o['b'];T=120-task['start_min'];q=o['q'];qm=min(b,(7.2-b)*(T/60-.5)/.5);margin=(qm-q)/7.2;discomfort=q/7.2+q*.5/(b*T/60)
            lo=o['low']-o['reference'];hi=o['high']-o['reference'];p=o['prob'];g=.7;lam=2.;wp=p**g/(p**g+(1-p)**g)**(1/g);wq=(1-p)**g/((1-p)**g+p**g)**(1/g)
            value=(1-wp)*lo+wp*hi if lo>=0 else lam*(wq*lo+(1-wq)*hi) if hi<=0 else lam*wq*lo+wp*hi;outside=-o['reference'] if -o['reference']>=0 else -lam*o['reference']
            aa.append(expit(-.4+.9*(value-outside)-1.1*discomfort+.6*o['green_preference']*o['green_attribute']))
            r=o['risk'];ss.append(softmax([1.1-1.2*r+1.5*margin,.4+.4*r,-.4+1.2*r-.8*margin,-.7+1.6*r-1.2*margin,-.5+.8*r]))
        pa.append(aa);ps.append(ss)
    return np.array(pa),np.array(ps)

def build(rep,seed):
    rng=np.random.default_rng(seed+rep);b=rng.uniform(3,4.6,2);initial=float(rng.uniform(3,5));scale=float(rng.uniform(3.5,4.5));forecast=scale*(.95+.05*np.cos(np.arange(180)*2*np.pi/180));evs=[]
    for i in range(2):
        q=float(rng.choice([1.5,3.]));declaration=dict(b=float(b[i]),T=120.,E=float(2*b[i]),q=q,low=float(rng.uniform(-2,0)),high=float(rng.uniform(.5,4)),prob=float(rng.uniform(.1,.9)),reference=float(rng.uniform(-.4,1.8)),green_preference=float(rng.random()),green_attribute=int(rng.integers(2)),risk=float(rng.random()),permission=not (rep%6==0 and i==1))
        evs.append(dict(resource_id=f'ev-{rep}-{i}',declaration=declaration,recovery_control_authorized=True))
    common=rng.random((180,1));ind=rng.random((180,4));bounded=LOW+(.55*common+.45*ind)*(1-LOW);stress=bounded.copy();stress[10:]=[.12,.12,.62,.12];ua=rng.random((2,2));us=rng.random((2,2));out=[];factors=[];aa=[];ss=[];pas=[];pss=[]
    start=datetime.fromisoformat('2026-10-28T00:00:00+08:00')
    for level,grid,evhead in [('tight',1.2,1.2),('loose',3.6,3.2)]:
        for second in [60,90]:
            for regime,g in [('nominal',np.ones((180,4))),('bounded',bounded),('stress',stress)]:
                c=dict(site_id=f'site-{rep}',evidence='hypothetical_ac',units='AC_kW_kWh_min',start=start.isoformat(),information_cutoff=start.isoformat(),ev_deadline_min=120,horizon_min=180,evs=evs,
                  pv=dict(resource_id=f'pv-{rep}',permission=True,accepted=rep%5!=0),battery=dict(resource_id=f'bat-{rep}',permission=True,accepted=rep%7!=0),pv_forecast_kw=forecast.tolist(),initial_kwh=initial,fixed_kw=5.,grid_headroom_kw=grid,ev_headroom_kw=evhead)
                tasks=[]
                for j,t in enumerate([0,second]):
                    tid=f'task-{rep}-{j}';known=(start+timedelta(minutes=t)).isoformat();records=[dict(resource_id=e['resource_id'],task_id=tid,offer_id=f'offer-{rep}-{j}-{i}',granted=e['declaration']['permission'],known_at=known) for i,e in enumerate(evs)]
                    tasks.append(dict(task_id=tid,start_min=t,duration_min=30,q_kw=1.8,known_at=known,permission_records=records))
                pa,ps=probabilities(c,tasks);out.append(dict(id=f'r{rep:02d}_{level}_{second}_{regime}',replicate=rep,headroom=level,second_start=second,regime=regime,public=c,arrival_stream=tasks));factors.append(g);aa.append(ua);ss.append(us);pas.append(pa);pss.append(ps)
    return out,dict(factors=np.array(factors),ua=np.array(aa),us=np.array(ss),pa=np.array(pas),ps=np.array(pss))

def main():
    integrity();p=read(BASE/'protocol.json');cases=[];private=[]
    for rep in range(p['new_panel']['seed_blocks']):
        cs,a=build(rep,p['new_panel']['seed_start']);cases.extend(cs);private.append(a)
    RAW.mkdir(parents=True,exist_ok=True);write(RAW/'cases.json',cases)
    with (RAW/'executor_private.npz').open('xb') as f:np.savez_compressed(f,**{k:np.concatenate([a[k] for a in private]) for k in private[0]})
    write(BASE/'generation.json',dict(cases=len(cases),independent_blocks=20,raw_sha=sha(RAW/'cases.json'),private_sha=sha(RAW/'executor_private.npz')));print('generated',len(cases),flush=True)

if __name__=='__main__':main()
