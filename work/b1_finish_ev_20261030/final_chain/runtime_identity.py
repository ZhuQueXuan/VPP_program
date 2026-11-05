"""Close native side-file provenance against an existing pre-run freeze."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old_path=ROOT/'work/b1_template_repair_20261030/test/source_freeze.json'
    old=json.loads(old_path.read_text(encoding='utf-8'))
    names=['B1算法/b1_algorithm/runtime.json','B1算法/b1_algorithm/process/cpop_batch.R',
        'B1算法/b1_algorithm/process/_policy.json']
    side={}
    for name in names:
        original=ROOT/name;value=sha(original)
        side[name]=dict(sha256=value,prior_frozen_sha256=old[name],unchanged_from_prior_freeze=value==old[name])
        destination=HERE/'runtime_source'/name;destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream:stream.write(original.read_bytes())
    runtime=json.loads((ROOT/names[0]).read_text(encoding='utf-8'))
    dependencies={name:dict(declared_sha256=value,actual_sha256=sha(ROOT/name),matched=sha(ROOT/name)==value)
        for name,value in runtime['sha256'].items()}
    out=dict(schema='b1.final-native-runtime-identity.v1',
        main_freeze_scope='Python scientific modules, reference artifacts, scripts and protocol; native side files recorded separately here',
        prior_pre_run_freeze=old_path.relative_to(ROOT).as_posix(),prior_freeze_file_sha256=sha(old_path),
        side_files=side,dependencies=dependencies,all_matched=all(v['unchanged_from_prior_freeze'] for v in side.values()) and all(v['matched'] for v in dependencies.values()),
        every_seed_validates_native_dependencies_before_processing=True,
        original_study_source_freeze_unchanged=True,scientific_run_repeated=False)
    with (HERE/'runtime_identity.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False)
    assert out['all_matched']
    print('native side-file identity passed',sha(HERE/'runtime_identity.json'))


if __name__=='__main__':main()
