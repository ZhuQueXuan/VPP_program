from common import *
import data as D
for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
for p,h in read('confirmation_freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
stage=sys.argv[1];assert stage in ['main_confirmation','weak_confirmation'];spec=read('protocol.json');spec.update(read('confirmation_plan.json'));original=D.read
D.read=lambda name:spec if name=='protocol.json' else original(name)
D.run(stage)
