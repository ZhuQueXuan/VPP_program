from common import *
from assess import audit
checks={}
for stage in ['main_confirmation','weak_confirmation']:
    rows,details=audit(stage);checks[stage]=details
write('confirmation_scalar_audit.json',checks)
print('Confirmation independently recomputed duration truth and errors',sum(v['checks'] for v in checks.values()),flush=True)
