"""No fitting: verify M2 can express a terminal idle gap before rebound."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process import _ride_template as tpl

def main():
    target=HERE/'template_math_receipt.json'
    if target.exists():raise RuntimeError('receipt already exists')
    W=30.;q=1.5;s=np.arange(-15.,45.);e=s+1
    theta=np.array([1.,0.,.8,29.,0.,.9,5.,14.,15.])
    predicted=q*tpl.interval_average(theta,W,s,e)
    expected=np.where((s>=1)&(s<15),1.2,np.where((s>=30)&(s<35),-1.35,0.))
    assert np.max(abs(predicted-expected))<1e-12
    assert np.max(abs(predicted[(s>=15)&(s<30)]))<1e-12
    result=dict(passed=True,numerical_max_error=float(np.max(abs(predicted-expected))),
        no_model_fitting=True,production_modified=False,
        conclusion='M2 can exactly represent one terminal idle gap and later rebound within default amplitude bounds; a blanket impossibility claim would be wrong.',
        template_sha256=hashlib.sha256((ROOT/'B1算法/b1_algorithm/process/_ride_template.py').read_bytes()).hexdigest())
    with target.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result))
if __name__=='__main__':main()
