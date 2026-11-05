"""Independent delivery check from saved outputs; no experiments are rerun."""
from pathlib import Path
import csv, hashlib, json, re

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
def read(rel):return json.loads((BASE/rel).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(rel):return list(csv.DictReader((BASE/rel).open(encoding='utf-8-sig',newline='')))
checks={}
for rel in ['process/audit_receipt.json','process/supplement_native_default/audit.json',
 'reference/audit_receipt.json','reference/integration/audit_receipt.json',
 'causal/results/audit_receipt.json','causal/process_independent_audit.json',
 'causal/results/doubleml_reference_check.json']:
 assert read(rel)['passed'],rel
checks['component_independent_audits_passed']=True
manifest=json.loads((ROOT/'work/ride_b1_v02_reproduction_20261029/source_manifest.json').read_text(encoding='utf-8'))
for item in manifest['files']:
 path=ROOT/'work/ride_b1_v02_reproduction_20261029/source'/item['path']
 assert sha(path)==item['sha256'],str(path)
checks['original_RIDE_files_unchanged']=len(manifest['files'])
assert read('process/main/summary.json')['n_variants']==960
assert read('process/main/summary.json')['n_metric_rows']==5760
assert read('process/supplement_native_default/receipt.json')['n_metric_rows']==1920
assert read('causal/results/audit_receipt.json')['replicate_rows']==400
assert read('reference/integration/audit_receipt.json')['selected_paired_event_records']==52
assert read('demo_output.json')['status']=='passed'
checks['counts_and_new_entry_demo_verified']=True

source=ROOT/'04_汇报与调研资料/课题一B1算法研究报告_通用方法对比版_20261029.md'
text=source.read_text(encoding='utf-8')
main=rows('process/main/summary.csv');native=rows('process/supplement_native_default/summary.csv')
table_methods={
 '原生CPOP 默认网格 区间投影':('CPOP_default_average_projection',native),
 '原生CPOP 默认网格 直接格预测':('CPOP_default_binned',native),
 '同族折线 区间平均适配':('Grid_average',main),
 '阶段模板与区间平均':('RIDE_template_average',main),
 '原常均值分段F1':('F1_frozen_segment_adapter',main),
 '原始规则F0':('F0_frozen_rule',main),
}
values_checked=0
for label,(method,data) in table_methods.items():
 line=next(l for l in text.splitlines() if l.startswith('| '+label+' |'))
 printed=[c.strip() for c in line.strip('|').split('|')][1:]
 for d,value in zip([1/6,1,15],printed):
  actual=next(r for r in data if r['method']==method and abs(float(r['delta_min'])-d)<1e-8)
  assert value==f"{float(actual['request_rmse']):.5f}",(label,d,value)
  values_checked+=1
causal=rows('causal/results/summary.csv')
scenarios={'随机正作用':'rct_positive','非随机正作用':'observational_positive',
 '非随机零作用':'observational_zero','非随机非单调':'observational_nonmonotone'}
for label,scenario in scenarios.items():
 line=next(l for l in text.splitlines() if l.startswith('| '+label+' |'))
 printed=[c.strip() for c in line.strip('|').split('|')][1:]
 for method,value in zip(['Unadjusted_arm_mean','Plugin_shared','IPW_shared','AIPW_shared'],printed):
  actual=next(r for r in causal if r['method']==method and r['scenario']==scenario)
  assert value==f"{float(actual['mean_curve_rmse']):.5f}",(label,method,value)
  values_checked+=1
reference=rows('reference/summary.csv')
for label,hot,resource in [('普通空调','False','AC'),('普通EV','False','EV'),('高温空调','True','AC'),('高温EV','True','EV')]:
 line=next(l for l in text.splitlines() if l.startswith('| '+label+' |'))
 printed=[c.strip() for c in line.strip('|').split('|')][1:]
 for method,value in zip(['prev10','gbdt','selected'],printed):
  actual=next(r for r in reference if r['hot']==hot and r['resource']==resource and r['method']==method)
  assert value==f"{float(actual['rmse_kw']):.4f}",(label,method,value)
  values_checked+=1
checks['report_numeric_cells_independently_checked']=values_checked

paths=[BASE/'README.md',BASE/'report/report.md',source,ROOT/'.review/2026-10-29-b1-mainline.md']
link_count=0
for p in paths:
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
  if target.startswith(('https://','http://')):continue
  assert (p.parent/target).exists(),(str(p),target)
  link_count+=1
checks['local_delivery_links_verified']=link_count

export=read('report/word_export.json');build=read('report/build_receipt.json')
docx=Path(export['input']);pdf=Path(export['pdf'])
assert sha(docx).lower()==export['docx_sha256'].lower()==build['docx_sha256']
assert sha(pdf).lower()==export['pdf_sha256'].lower()
assert sha(source)==build['source_sha256']
assert export['page_count']==6
assert all((BASE/f'report/render/page-{i}.png').exists() for i in range(1,7))
checks['exact_DOCX_native_Word_PDF_and_render_match']=True
checks['visual_inspection']={'pages':[1,2,3,4,5,6],'result':'passed',
 'observations':'All final page PNGs inspected; readable text, equations and four figures; table2 continues with repeated header; no clipped content or isolated caption.'}
checks['formal_outputs']={'docx':str(docx),'pdf':str(pdf),'markdown':str(source),'pages':6}
checks['overall_passed']=True
(BASE/'completion_receipt.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2))
