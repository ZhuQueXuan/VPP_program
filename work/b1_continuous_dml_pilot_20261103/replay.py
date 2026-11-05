"""Replay a saved simulation curve, or evaluate direct new query amounts."""
from methods import *
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seed',type=int,default=90312000);parser.add_argument('--scenario',default='nonmonotone');parser.add_argument('--method',choices=['existing_DR','continuous_DML','soft_two_part'],default='existing_DR');parser.add_argument('--amounts',help='Optional comma-separated continuous amounts, e.g.0.73,0.85,1.17');args=parser.parse_args()
path=HERE/'final/results'/f'{args.seed}_{args.scenario}.json'
if not args.amounts:
    result=read(path)['results'][args.method];out={k:v for k,v in result.items() if k not in ['public_result','fold_by_event']}
else:
    values=np.array([float(x) for x in args.amounts.split(',')]);assert np.all((values>=.3)&(values<=2.1)),'This pilot validated queries.3..2.1only.';points=np.unique(np.r_[.3,values]);data=read(HERE/'final/facts'/f'{args.seed}_{args.scenario}.json')
    if args.method=='existing_DR':result=public_DR(data,args.seed,points)
    else:result=estimate(data,'DML','hurdle' if args.method=='soft_two_part' else 'single',args.seed,grid=points)
    out={k:v for k,v in result.items() if k not in ['public_result','fold_by_event']}
print(json.dumps(native(dict(simulation_only=True,method=args.method,result=out)),ensure_ascii=False,indent=2),flush=True)
