"""Controlled Gaussian generator; no graph truth supplied to learner."""
from pathlib import Path
import numpy as np


def structural_transform():
    # Rows are node values, columns independent exogenous noises.
    transform=np.eye(5)
    transform[2]=.8*transform[0]+.7*transform[1]+transform[2]
    transform[3]=.9*transform[2]+transform[3]
    transform[4]=.6*transform[0]+.7*transform[3]+transform[4]
    return transform


def generate(protocol,raw_root,work_root):
    raw_root.mkdir(parents=True,exist_ok=True)
    transform=structural_transform()
    observed={}
    for n in protocol['sample_sizes']:
        for seed in protocol['replicate_seeds']:
            noise=np.random.default_rng(seed+100000*n).normal(size=(n,5))
            observed[f'n{n}_seed{seed}']=noise@transform.T
    np.savez_compressed(raw_root/'observations.npz',**observed)
    np.save(work_root/'oracle_covariance.npy',transform@transform.T)
    return dict(datasets=len(observed),rows=sum(len(x) for x in observed.values()),
                features=5,identity=protocol['identity'])
