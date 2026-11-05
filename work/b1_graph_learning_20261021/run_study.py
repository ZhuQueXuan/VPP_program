from pathlib import Path
import json,hashlib,time
from itertools import permutations
import numpy as np
from generate import generate
from graph_learner import learn
BASE=Path(__file__).resolve().parent
PROJECT=BASE.parent.parent


def main():
    protocol=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
    for name in ('learned.json','evaluation.json'):
        if (BASE/name).exists():
            raise RuntimeError('study output already exists; do not overwrite frozen study')
    frozen={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest()
        for name in ('protocol.json','graph_learner.py','generate.py','run_study.py','evaluate_graph.py')}
    (BASE/'source_freeze.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    start=time.time()
    generated=generate(protocol,PROJECT/protocol['raw_root'],BASE)
    cov=np.load(BASE/'oracle_covariance.npy')
    names=protocol['nodes']
    oracle=[]
    for order in permutations(range(5)):
        result=learn(cov[np.ix_(order,order)],[names[i] for i in order],tiers=protocol['tiers'])
        oracle.append(dict(order=list(order),result=result))
    (BASE/'oracle_learned.json').write_text(json.dumps(oracle,indent=2),encoding='utf-8')
    observed=np.load(PROJECT/protocol['raw_root']/'observations.npz')
    outputs=[]
    for n in protocol['sample_sizes']:
        for seed in protocol['replicate_seeds']:
            x=observed[f'n{n}_seed{seed}']
            sample_cov=np.cov(x,rowvar=False)
            for order in protocol['permutations']['sample']:
                result=learn(sample_cov[np.ix_(order,order)],[names[i] for i in order],n=n,
                    alpha=protocol['alpha'],tiers=protocol['tiers'])
                outputs.append(dict(n=n,seed=seed,order=order,result=result))
    (BASE/'learned.json').write_text(json.dumps(outputs,indent=2),encoding='utf-8')
    receipt=dict(seconds=time.time()-start,generated=generated,
        learned_sha256=hashlib.sha256((BASE/'learned.json').read_bytes()).hexdigest(),
        truth_graph_loaded_by_learner=False,finite_runs=len(outputs),oracle_orders=len(oracle))
    (BASE/'run_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))

if __name__=='__main__':main()
