from common import *
from candidate import refine,features

def main():
    n=360;s=np.arange(n)*10.-900;u=np.where((s>=0)&(s<1800),-1.5,0.);y=np.zeros(n);controls=[]
    for width in [1,3,6]:
        z=y.copy();z[130:130+width]=1.
        a,info=refine(z,s,u,.05,4.)
        if width>=3:assert np.array_equal(a,z)
        else:assert a[130]==0.
        controls.append(dict(true_response_bins=width,retained=bool(a[130]!=0),same_input_fault_ambiguity=width==1))
    z=y.copy();z[130:136]=1.;z[133]=0.;a,_=refine(z,s,u,.05,4.)
    assert a[133]==1. # genuine one-fine-bin gap also cannot be identified
    z=y.copy();z[90]=1.;a,_=refine(z,s,u,.05,4.);assert a[90]==1.
    coarse=np.arange(60)*60.-900;z=np.zeros(60);z[20]=1.
    a,info=refine(z,coarse,np.where((coarse>=0)&(coarse<1800),-1.5,0.),.05,4.);assert np.array_equal(a,z)
    mask=np.zeros(360);mask[100:106]=1.;f=features(mask,s,1800,.15);assert f['cumulative_seconds']==f['longest_seconds']==60.
    write('controls_receipt.json',dict(passed=True,cases=controls,known_failure='True single10s action and single10s gap can be mistaken for anomalies. Mandatory adoption safety gates retain these cases.',coarse_passthrough=True,command_edge_protected=True))
    print('controls passed, including documented10s ambiguity',flush=True)
if __name__=='__main__':main()
