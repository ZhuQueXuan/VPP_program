"""Independent neighboring-mode counts and native context checks for residual audit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(audit_run,verification_id):
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',v) for v in [audit_run,verification_id]):
        raise ValueError('Invalid ID')
    directory=BASE/'apr2023_response_residual_runs'/audit_run
    output=directory/(verification_id+'.json')
    if output.exists():raise FileExistsError(output)
    p=json.loads((BASE/'apr2023_response_sample_protocol_v1.json').read_text(encoding='utf-8'))
    src=json.loads((BASE/'apr2023_lmo1_field_protocol_v1.json').read_text(encoding='utf-8'))
    receipt=json.loads((directory/'audit_receipt.json').read_text(encoding='utf-8'))
    source_path=BASE/src['csv_relative_path']
    if sha(source_path)!=src['csv_sha256']:raise ValueError('Source changed')
    if any(sha(directory/name)!=value for name,value in receipt['output_sha256'].items()):
        raise ValueError('Audit artifact changed')
    f=pd.read_csv(source_path,sep=';')
    pq=f.Mode_PQ.to_numpy()==1;setting=f.P_AC_Set.to_numpy();ac=f.P_AC.to_numpy()
    clock=pd.to_datetime(f.DateAndTime)
    groups=pd.read_csv(directory/'age_group_metrics.csv')
    checks=[]
    for block in p['partitions']:
        lo=clock.searchsorted(pd.Timestamp(block['start_inclusive']))
        hi=clock.searchsorted(pd.Timestamp(block['end_exclusive']))
        i=np.arange(lo+1,hi-1);i=i[pq[i]]
        first=~pq[i-1]
        second=pq[i-1]&~pq[np.maximum(i-2,0)]
        third=~first&~second
        residual=np.abs(setting[i].astype(float)-ac[i+1])
        for name,mask in zip(['first_logged_PQ_row','second_logged_PQ_row','third_or_later_logged_PQ_row'],[first,second,third]):
            saved=groups[(groups.partition==block['name'])&(groups.age_group==name)].iloc[0]
            if int(mask.sum())!=int(saved['n']) or float(residual[mask].sum())!=float(saved.absolute_residual_sum_kw):
                raise ValueError('Independent counts/sums differ')
            if int((residual[mask]>50).sum())!=int(saved.large_residual_n):
                raise ValueError('Independent large-residual counts differ')
            checks.append(block['name']+':'+name)
    cases=pd.read_csv(directory/'top20_native_cases.csv')
    for row in cases.itertuples():
        i=row.native_origin_row
        if row.signed_residual_kw!=setting[i]-ac[i+1] or row.command_difference_term_kw+row.contemporaneous_difference_term_kw!=row.signed_residual_kw:
            raise ValueError('Top-case signed differences differ')
    context=pd.read_csv(directory/'top20_native_contexts.csv')
    for row in context.itertuples():
        i=row.selected_origin_row+row.relative_to_origin_s
        if row.P_AC_Set!=setting[i] or row.P_AC!=ac[i] or row.I_DC_Batt!=f.I_DC_Batt.iloc[i] or row.Mode_PQ!=f.Mode_PQ.iloc[i]:
            raise ValueError('Exported native context differs')
    baseline=BASE/'apr2023_response_baseline_runs'/receipt['baseline_run']
    br=json.loads((baseline/'run_receipt.json').read_text(encoding='utf-8'))
    if any(sha(baseline/name)!=value for name,value in br['output_sha256'].items()):
        raise ValueError('Original baseline altered')
    first_two=groups[(groups.partition=='evaluation')&groups.age_group.isin(['first_logged_PQ_row','second_logged_PQ_row'])]
    evaluation=groups[groups.partition=='evaluation']
    result={'verification_id':verification_id,'audit_run':audit_run,
            'status':'independent_neighbor_based_phase_counts_sums_and_large_counts_pass',
            'group_checks':checks,'top_cases_and_exported_ac_set_current_pq_match_native':True,
            'original_ten_baseline_artifacts_unchanged':True,
            'evaluation_first_two_sample_share':float(first_two.n.sum()/evaluation.n.sum()),
            'evaluation_first_two_abs_sum_share':float(first_two.absolute_residual_sum_kw.sum()/evaluation.absolute_residual_sum_kw.sum()),
            'source_csv_sha256':src['csv_sha256'],'verification_code_sha256':sha(Path(__file__)),
            'limits':'posthoc observed-phase association; no causal or physical timing validation. Exported contexts numerically checked for AC/set/current/PQ fields only.'}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (directory/(verification_id+'_code_snapshot.py')).write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-run',required=True)
    parser.add_argument('--verification-id',required=True)
    args=parser.parse_args()
    verify(args.audit_run,args.verification_id)
