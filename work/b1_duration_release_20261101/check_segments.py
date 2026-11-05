"""Small exhaustive least-squares partition check, independent of prefix DP."""
from common import *
from candidates import fit_segments
from itertools import product

def main():
    rng=np.random.default_rng(7709901);checks=0
    for n in [3,5,8]:
      for trial in range(8):
        y=rng.normal(size=n)*.1;sigma=.05;beta=3*np.log(n);best=float('inf')
        for edges in product([False,True],repeat=n-1):
            bounds=[0]+[i+1 for i,yes in enumerate(edges) if yes]+[n];cost=beta*(len(bounds)-2)
            for a,b in zip(bounds[:-1],bounds[1:]):
                segment=y[a:b];rss=np.sum((segment-segment.mean())**2)
                if b-a>=3:
                    x=np.column_stack([np.ones(b-a),np.arange(b-a)]);r=segment-x@np.linalg.lstsq(x,segment,rcond=None)[0];rss=min(rss,float(r@r))
                cost+=rss/sigma**2
            best=min(best,cost)
        fitted=fit_segments(y,sigma,3.,0.)
        assert abs(fitted['objective']-best)<1e-8,(n,trial,best,fitted['objective'])
        assert len(fitted['prediction'])==n;checks+=1
    write('segment_checks.json',dict(exhaustive_cases=checks,all_passed=True))
    print('exhaustive partition checks',checks)
if __name__=='__main__':main()
