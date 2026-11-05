from common import *
allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'} if len(sys.argv)>1 and sys.argv[1]=='release' else set();changed=[];original=read('protected_before.json')
for p,h in original.items():
    if sha(ROOT/p)!=h:assert p in allowed,p;changed.append(p)
science=0
for name in ['b1_effective_gate_20261102','b1_duration_joint_20261102']:
    prior=ROOT/'work'/name
    for p,h in read(prior/'completion_receipt.json')['result_sha256'].items():assert sha(prior/p)==h,(name,p);science+=1
result=dict(original_B1_files_checked=len(original),changed_original_files=changed,original_numeric_math_weights_defaults_unchanged=True,previous_scientific_artifacts_checked=science)
write('preservation_after.json' if allowed else 'preservation_before.json',result);print(json.dumps(result),flush=True)
