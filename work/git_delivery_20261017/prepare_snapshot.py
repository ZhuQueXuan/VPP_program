"""Build an explicit research-only Git path list; never deletes or stages files."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
G=r'C:/Users/刘文轩/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def git(*a): return subprocess.check_output([G,*a],cwd=ROOT)
assert not git('diff','--cached','--name-only').strip(),'Existing staged work requires separate handling'
selected=['.gitattributes','.gitignore','AGENTS.md','项目文件索引.md','work/README.md',
 '01_项目依据/课题一需求分析与研究框架_整合修订版_v1_20261011.md',
 '01_项目依据/课题一技术路线与模型设计方案_v1_20261011.md',
 'docs/DECISION_LOG.md','docs/DATA_CARD.md','docs/EXPERIMENT_LOG.md',
 'outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md']
untracked=git('ls-files','--others','--exclude-standard','-z').decode('utf-8').split('\0')
selected += [p for p in untracked if p.startswith('resource_research_results/')]
workroots=['resource_sample_selection_20261013','photovoltaic_research_20261015','ev_charging_research_20261016',
 'air_conditioning_research_20261016','wind_power_research_20261016','electric_water_heating_research_20261016',
 'vpp_dml_review_20261017','vpp_dml_project_trial_20261017']
for name in workroots:
    for p in (ROOT/'work'/name).iterdir():
        if p.is_file() and (p.suffix in {'.py','.json','.md','.cmd'} or p.name.startswith('requirements')):
            selected.append(p.relative_to(ROOT).as_posix())
selected += [p.relative_to(ROOT).as_posix() for p in (ROOT/'work/process_notes').glob('*.md')]
selected += ['work/vpp_dml_project_trial_20261017/heldout_type_effects.png',
             'work/vpp_dml_project_trial_20261017/heldout_type_effects.svg',
             'work/vpp_dml_review_20261017/comparison_key_metrics.csv',
             'work/vpp_dml_review_20261017/coverage_independent.csv']
# Explicit compact D071 audit evidence; source data / raw traces remain local.
base='work/electric_water_heating_research_20261016/runs/'
forced=[base+r+'/'+f for r in ['DRAW_SOURCE_04','DRAW_SOURCE_05']
        for f in ['receipt.json','source_summary.json','dictionary_readonly.json','protocol_snapshot.json']]
forced += [base+'VERIFY_DRAW_SOURCE_01/receipt.json',base+'DELIVERY_QA_01/receipt.json']
forced += [base+'DRAW_DESCRIPTION_01/'+f for f in ['draw_observations.png','draw_observations.svg','receipt.json','visual_review.json']]
selected += forced
selected=sorted(set(selected))
for p in selected:
    q=ROOT/p; assert q.is_file(),p
    assert q.stat().st_size<20_000_000,(p,'oversize')
    assert not any(x in q.parts for x in ['downloads','env','node_modules','__pycache__'])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
entries=[{'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p),'force_selected_summary':p in forced} for p in selected]
out=Path(__file__).resolve().parent
manifest={'purpose':'Research snapshot through D071, not all historical workspace edits',
 'branch_before':git('branch','--show-current').decode().strip(),
 'head_before':git('rev-parse','HEAD').decode().strip(),
 'private_remote':'https://github.com/ZhuQueXuan/VPP_program',
 'exclusions':['unrelated historical moves/deletions','original downloaded data and raw/point-level traces','runtime environments','third-party colleague original bundle without redistribution license','103 original PDF (reviewed locally)'],
 'selected_count':len(entries),'selected_bytes':sum(x['bytes'] for x in entries),'files':entries}
(out/'snapshot_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
allpaths=selected+['work/git_delivery_20261017/prepare_snapshot.py','work/git_delivery_20261017/snapshot_manifest.json']
(out/'stage_paths.nul').write_bytes(('\0'.join(allpaths)+'\0').encode('utf-8'))
print(json.dumps({'selected_count':len(allpaths),'selected_bytes':manifest['selected_bytes'],
 'forced_summaries':len(forced),'largest':sorted(entries,key=lambda x:x['bytes'],reverse=True)[:4]},ensure_ascii=False,indent=2))
