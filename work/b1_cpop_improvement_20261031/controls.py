"""Meaningful controls: units, edge preservation, ambiguity, native adapter equivalence."""
from common import *
from candidate import observation_weights
def main():
    y=np.zeros(21);y[10]=1.;command=np.zeros(21);sigma=.05
    r=observation_weights(y,sigma,command,kappa=3.)
    assert [x['index'] for x in r['flagged_points']]==[10]
    assert np.array_equal(y,np.r_[np.zeros(10),1.,np.zeros(10)])
    scaled=observation_weights(y*1000,sigma*1000,command*1000,kappa=3.)
    assert np.allclose(np.asarray(r['sigma_vector'])*1000,scaled['sigma_vector'],rtol=1e-14,atol=0)
    command[10:]=1.;edge=observation_weights(y,sigma,command,kappa=3.)
    assert not edge['flagged_points'] and 10 in edge['protected_indices']
    step=np.zeros(21);step[10:]=1.
    assert not observation_weights(step,sigma,np.zeros(21),kappa=3.)['flagged_points']
    ramp=np.arange(21)*.1
    assert not observation_weights(ramp,sigma,np.zeros(21),kappa=3.)['flagged_points']
    # A real one-bin physical action and sensor spike can have identical input.
    # The algorithm correctly exposes ambiguity; it does NOT prove either label.
    real_action=observation_weights(y,sigma,np.zeros(21),kappa=3.)
    assert real_action['short_action_disambiguation_available'] is False
    assert np.array_equal(real_action['sigma_vector'],r['sigma_vector'])
    rejected=0
    for bad in [np.r_[np.zeros(20),np.nan],np.r_[np.zeros(20),np.inf]]:
        try:observation_weights(bad,sigma,np.zeros(21))
        except ValueError:rejected+=1
    assert rejected==2
    rng=np.random.default_rng(7631000);cases=[]
    for i,signal in enumerate([np.zeros(21),ramp,step,y]):
        cases.append({'case_id':i,'starts':np.arange(21.),'ends':np.arange(1,22.),
          'y':signal+rng.normal(0,sigma,21),'sigma':sigma,'sigma_vector':np.full(21,sigma),'train':np.ones(21,bool)})
    cp,b=fit_cases(cases,runtime('native/controls_original'));assert b['status']=='ok'
    vec,v=weighted_batch(cases,'native/controls_vector')
    diff=max(float(np.max(np.abs(np.asarray(cp[i]['prediction'])-np.asarray(vec[i]['prediction'])))) for i in range(4))
    assert all(cp[i]['status']==vec[i]['status']=='ok' for i in range(4)) and diff<1e-10
    write('controls_receipt.json',{'status':'passed','unit_invariance':True,'command_edge_protection':True,
         'genuine_single_point_unidentifiable_control':True,'step_and_ramp_not_screened':True,
         'nonfinite_rejected':2,'native_original_scalar_vs_uniform_vector_cases':4,'max_curve_difference':diff,
         'not_a_detection_accuracy_sample':True,'candidate_sha256':sha(HERE/'candidate.py')})
    print('controls passed; native scalar/vector max difference',diff)
if __name__=='__main__':main()
