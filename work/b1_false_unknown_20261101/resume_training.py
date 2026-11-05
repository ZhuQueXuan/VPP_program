"""Reuse completed native CP artifacts after a training-only LABS mkdir error."""
from common import *
from task_model import features
import csv

def main():
    cases=read('train/all_facts.json');groups={}
    for p in (HERE/'train/native/cpop').rglob('segments.csv'):
        with p.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):groups.setdefault(int(r['case_id']),[]).append(r)
    assert len(groups)==len(cases);original=[]
    for i,c in enumerate(cases):
        rows=groups[i];assert all(r['status']=='ok' for r in rows);nonempty=[r for r in rows if float(r['x1'])>float(r['x0'])]
        mid=(np.array(c['starts_s'])+np.array(c['ends_s']))/120;pred=np.full(len(mid),np.nan)
        for j,r in enumerate(nonempty):
            a,b=float(r['x0']),float(r['x1']);mask=(mid>=a-1e-9)&(mid<=b+1e-9)
            if j==0:mask|=mid<a
            if j==len(nonempty)-1:mask|=mid>b
            pred[mask]=float(r['gradient'])*mid[mask]+float(r['intercept'])
        assert np.isfinite(pred).all();original.append(dict(status='ok',prediction=pred))
    retained=preserved_curves(cases,original)
    write('train/curves.json',[dict(task_id=c['task_id'],results=dict(cpop=o,retained=r)) for c,o,r in zip(cases,original,retained)])
    X=np.vstack([features(c,o['prediction'],r['prediction']) for c,o,r in zip(cases,original,retained)]);np.save(HERE/'train/features.npy',X)
    write('train/recovery_receipt.json',dict(native_CPOP_reused=len(original),partial_LABS_training_artifacts_retained=True,LABS_training_not_required=True,
        issue='One training-only LABS parallel directory creation failed; original CP completed, no observation or baseline changed.',recovery='Exact saved native CP segment formula replay; no fitting, no data regeneration.'))
    print('training recovered',X.shape)
if __name__=='__main__':main()
