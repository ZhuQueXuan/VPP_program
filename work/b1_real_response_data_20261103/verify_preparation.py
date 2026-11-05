"""Source-integrity audit, not a model/test-performance evaluation."""
from pathlib import Path
import json,hashlib,csv
from datetime import datetime,timedelta,timezone
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
RAW=ROOT/'data/public_datasets/挪威_iFlex_动态电价试验'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
P=read(HERE/'real_data_protocol.json');checks=[];issues=[];maximum_errors={}
def claim(name,ok,detail=None):
    checks.append(dict(check=name,passed=bool(ok),detail=detail))
    if not bool(ok):issues.append(dict(check=name,detail=detail))
def close(name,a,b,tol=1e-8):
    if pd.isna(a) and pd.isna(b):claim(name,True);return
    e=float(abs(a-b));maximum_errors[name]=max(e,maximum_errors.get(name,0.))
    claim(name,np.isfinite(e) and e<=tol,e)

design=pd.read_csv(HERE/'selected_design.csv');days=pd.read_csv(RAW/'experiment_days.csv');prices=pd.read_csv(RAW/'price_signals.csv');people=pd.read_csv(RAW/'participants.csv')
selected=days[(days.Participation_Phase=='Phase_2')&days.Group.isin(P['pure_P_groups'])].copy()
keys=lambda f,cols:set(map(tuple,f[cols].astype(str).to_numpy()))
claim('exact_metadata_selected59_groupdays',len(design)==59 and not design.duplicated(['Date','Group']).any() and keys(design,['Participation_Phase','Price_signal','Date','Group'])==keys(selected,['Participation_Phase','Price_signal','Date','Group']))
claim('metadata_only4_discrete_paths',set(design.Price_signal)==set(P['observed_price_signals']) and P['continuous_eligibility'] is False)
claim('metadata30_dates_and_chronological_split',design.Date.nunique()==30 and all(r.split==P['splits_by_whole_date'][r.Date] for r in design.itertuples()))
for part,n in [('train',20),('validation',5),('test',5)]:claim('whole_dates_'+part,design.loc[design.split==part,'Date'].nunique()==n)
claim('chronological_no_split_overlap',max(design.loc[design.split=='train','Date'])<min(design.loc[design.split=='validation','Date']) and max(design.loc[design.split=='validation','Date'])<min(design.loc[design.split=='test','Date']))

groups=people[people.Group_Phase2.isin(P['pure_P_groups'])].copy()
expected=groups[['ID','Group_Phase2','Region']].merge(design,left_on='Group_Phase2',right_on='Group',how='inner',validate='many_to_many')
numeric_fields={'actual_day_kwh','actual_peak_2h_kwh','pre24_kwh','pre24_temperature','pre168_kwh'}
header=list(pd.read_csv(HERE/'prepared_P_events.csv',nrows=0))
# Never parse test outcome/history numeric values; only metadata and quality flags.
m=pd.read_csv(HERE/'prepared_P_events.csv',usecols=[c for c in header if c not in numeric_fields])
claim('all718_assigned_households',len(groups)==groups.ID.nunique()==m.ID.nunique()==718)
claim('all14213_designed_household_events',len(expected)==len(m)==14213 and not m.duplicated(['ID','Date']).any() and keys(expected,['ID','Date'])==keys(m,['ID','Date']))
joined=m.merge(expected[['ID','Group','Region','Date','split','Price_signal']],on=['ID','Date'],suffixes=('','_expected'),validate='one_to_one')
claim('household_group_region_split_signal_exact',all(joined.Group==joined.Group_expected) and all(joined.Region==joined.Region_expected) and all(joined.split==joined.split_expected) and all(joined.assigned_signal==joined.Price_signal))
registry=pd.read_csv(HERE/'P_household_registry.csv')
claim('household_registry_complete',len(registry)==718 and set(registry.ID)==set(groups.ID))
repair=read(HERE/'encoding_repair.json')
claim('encoding_repair_official_metadata_hash',repair['official_metadata_sha256']==sha(RAW/'participants.csv'))
claim('encoding_repair_scope_only_Region',repair['changed_columns']==['Region'] and not repair['source_data_or_numeric_values_changed'])
official_region=dict(zip(people.ID.astype(str),people.Region.astype(str)))
repair_counts={}
for canonical,receipt in repair['files'].items():
    native=HERE/receipt['preserved_original']
    with native.open(encoding='utf-8-sig',newline='') as f:old_rows=list(csv.DictReader(f))
    with (HERE/canonical).open(encoding='utf-8-sig',newline='') as f:new_rows=list(csv.DictReader(f))
    claim('encoding_repair_preserved_original_sha',sha(native)==receipt['preserved_sha256'])
    claim('encoding_repair_canonical_sha',sha(HERE/canonical)==receipt['canonical_sha256'])
    claim('encoding_repair_rows_and_columns',len(old_rows)==len(new_rows)==receipt['rows'] and list(old_rows[0])==list(new_rows[0]))
    # String identity is an integrity check, not analysis of heldout outcomes.
    same=all(all(old[k]==new[k] for k in old if k!='Region') for old,new in zip(old_rows,new_rows))
    claim('encoding_repair_all_other_fields_exact_strings',same)
    claim('canonical_Region_matches_official_ID',all(row['Region']==official_region[row['ID']] for row in new_rows))
    changed=sum(old['Region']!=new['Region'] for old,new in zip(old_rows,new_rows))
    claim('encoding_repair_count',changed==receipt['region_rows_repaired'])
    repair_counts[canonical]=dict(rows=len(new_rows),Region_changed=changed,all_other_fields_exact_strings=same)
claim('one_split_per_whole_date',m.groupby('Date').split.nunique().max()==1)
claim('one_assignment_per_group_date',m.groupby(['Group','Date']).assigned_signal.nunique().max()==1)

notice=pd.to_datetime(m.notice_utc,utc=True)
expected_notice=pd.to_datetime(m.Date,utc=True)-pd.Timedelta(days=1)+pd.Timedelta(hours=17)
claim('notice_previous_date17UTC',notice.equals(expected_notice))
for prefix,hours in [('pre24',24),('pre168',168)]:
    last=pd.to_datetime(m[prefix+'_last_end_utc'],utc=True)
    claim(prefix+'_all_completed_by_notice',bool((last.isna()|(last<=notice)).all()))
    claim(prefix+'_finite_counts_bounded',bool(((m[prefix+'_finite']>=0)&(m[prefix+'_finite']<=m[prefix+'_rows'])).all()))
    claim(prefix+'_hour_count_bounded',bool(((m[prefix+'_rows']>=0)&(m[prefix+'_rows']<=hours)).all()))
source_detail=pd.read_csv(HERE/'independent_metadata_checks.csv')
claim('independent_all14213_metadata_rows',len(source_detail)==len(m) and keys(source_detail,['ID','Date'])==keys(m,['ID','Date']))
claim('independent_source_prices_times_indices_match',not source_detail.metadata_failures.any() and not source_detail.metadata_NA.any())
claim('independent_source_all_day_hour_structure',bool(source_detail.day_time_complete.all() and source_detail.peak_time_complete.all()))
for prefix,hours in [('pre24',24),('pre168',168)]:
    dj=m.merge(source_detail[['ID','Date',prefix+'_time_complete']],on=['ID','Date'],validate='one_to_one')
    claimed=dj[prefix+'_rows'].eq(hours)
    claim(prefix+'_no_duplicates_gaps_count_cancellation',bool((~claimed|dj[prefix+'_time_complete']).all()))
for r in pd.read_csv(HERE/'independent_source_check_summary.csv').itertuples():claim('native_R_'+r.check,r.failures==0,int(r.failures))

quality_presence={k:0 for k in numeric_fields};quality_errors=[]
with (HERE/'prepared_P_events.csv').open(encoding='utf-8-sig',newline='') as f:
    for row in csv.DictReader(f):
        present={k:bool(row[k].strip()) for k in numeric_fields}
        for k,v in present.items():quality_presence[k]+=int(v)
        for field,flag in [('actual_day_kwh','complete_day'),('actual_peak_2h_kwh','complete_peak')]:
            if present[field]!=(row[flag]=='TRUE'):quality_errors.append([row['ID'],row['Date'],field])
        for prefix,hours in [('pre24',24),('pre168',168)]:
            ready=int(row[prefix+'_rows'])==hours and int(row[prefix+'_finite'])==hours
            if present[prefix+'_kwh']!=ready:quality_errors.append([row['ID'],row['Date'],prefix+'_kwh'])
claim('saved_numeric_presence_matches_completeness_flags',not quality_errors,quality_errors[:5])

chosen=pd.read_csv(HERE/'fixed_source_check_events.csv');source_values=pd.read_csv(HERE/'independent_fixed_source_values.csv')
ordered=m[['ID','Group','Date','split']].sort_values(['Date','Group','ID'])
first=pd.concat([ordered[ordered.split=='train'].head(3),ordered[ordered.split=='validation'].head(2)],ignore_index=True)
claim('fixed5_selection_outcome_free',chosen.equals(first) and len(chosen)==5 and not chosen.split.eq('test').any())
claim('independent_fixed5_source_values',len(source_values)==5 and keys(source_values,['ID','Date'])==keys(chosen,['ID','Date']))
# Parse actual numeric columns only after filtering keys by the predeclared five.
fixed={tuple(r):{} for r in chosen[['ID','Date']].to_numpy()}
with (HERE/'prepared_P_events.csv').open(encoding='utf-8-sig',newline='') as f:
    for row in csv.DictReader(f):
        key=(row['ID'],row['Date'])
        if key not in fixed:continue
        fixed[key]={name:float(row[name]) if row[name].strip() else np.nan for name in numeric_fields|{'pre24_finite','pre168_finite'}}
for row in source_values.to_dict('records'):
    for field in numeric_fields|{'pre24_finite','pre168_finite'}:close('independent_numeric_'+field,fixed[(row['ID'],row['Date'])][field],row[field])

path_detail={}
path_prices=[]
for signal in P['observed_price_signals']:
    pr=prices[prices.Price_signal==signal].sort_values('Hour')
    claim('24unique_hour_prices_'+signal,len(pr)==24 and set(pr.Hour)==set(range(1,25)))
    path_prices.append(pr.Experiment_price_NOK_kWh.to_numpy())
    path_detail[signal]={str(int(r.Hour)):float(r.Experiment_price_NOK_kWh) for r in pr.itertuples()}
arr=np.asarray(path_prices);outside=[i for i in range(24) if i+1 not in (17,18)]
claim('other22_prices_identical_across_P_paths',np.max(np.ptp(arr[:,outside],axis=0))<1e-10)
claim('only4_supported_peak_intensities',len(np.unique(arr[:,16:18],axis=0))==4)
split_counts={part:dict(events=int(len(df)),households=int(df.ID.nunique()),dates=int(df.Date.nunique()),group_days=int(df[['Group','Date']].drop_duplicates().shape[0]),complete_day=int(df.complete_day.sum()),complete_peak=int(df.complete_peak.sum()),price_matches=int(df.price_matches.sum()),signal_matches=int(df.signal_matches.sum())) for part,df in m.groupby('split')}
saved_counts=pd.read_csv(HERE/'preparation_counts.csv').set_index('split')
for part,summary in split_counts.items():
    for saved,col in [('designed_events','events'),('complete_day','complete_day'),('complete_peak','complete_peak'),('matched_price','price_matches'),('matched_signal','signal_matches')]:claim('saved_preparation_summary_'+saved,int(saved_counts.loc[part,saved])==summary[col])

formal=read(HERE/'formal_before.json');current={str(p.relative_to(ROOT)):sha(p) for ext in ('*.py','*.json') for p in (ROOT/'B1算法').rglob(ext)}
formal_ok=formal==current and len(current)==61;claim('formal61_exact_inventory_hashes_unchanged',formal_ok)
sources=read(HERE/'source_before.json');source_ok=all(sha(ROOT/path)==h for path,h in sources.items());claim('all_original_source_hashes_unchanged',source_ok)
prior=ROOT/'work/b1_curve_stability_20261103/retained_before.json';old=read(prior)
old_ok=all(sha(ROOT/'work/b1_curve_spline_pilot_20261103'/name)==h for name,h in old.items());claim('previous_retained376_unchanged',old_ok and len(old)==376)
result=dict(passed=not issues,issues=issues,checks=checks,total_checks=len(checks),maximum_numeric_errors=maximum_errors,
    split_counts=split_counts,assigned_households=718,designed_household_events=14213,independent_assigned_dates=30,assignment_group_days=59,
    actual_discrete_paths=P['observed_price_signals'],full_price_paths=path_detail,continuous_eligibility=False,complete_numeric_field_presence_counts=quality_presence,
    independent_numeric_source_events=chosen.to_dict('records'),numeric_source_event_count=5,test_outcome_values_used_for_model_or_selection=False,test_numeric_source_events=0,
    native_source_audit='Original RData read in nativeR. All14213 events checked using sourceID/time/hour/price/row-index metadata; strict unique hourly continuity checked for24/168h histories. Numeric original Demand/Temperature accessed only for fixed3train+2validation events.',
    known_household_future_date_split=True,unseen_user_generalization=False,model_fit=False,causal_effect_estimated=False,no_synthetic_prices=True,
    audit_limits=['No real counterfactual curve or EV effective-duration gold','Past histories can include prior treated days and are observed state, not untreated baseline','Numeric source agreement independently tested on five fixed development events; all-event outcome completeness uses exported flags/presence and time-source metadata, not test performance','Four supported price paths require discrete/path analysis before any continuous causal claim'],
    formal61_unchanged=formal_ok,original_sources_unchanged=source_ok,old_retained376_unchanged=old_ok,
    encoding_repair=repair_counts,initial_Region_encoding_failure_preserved='verification_attempt1.json',
    source_hashes={name:sha(HERE/name) for name in ['prepare_iflex.R','real_data_protocol.json','selected_design.csv','prepared_P_events.csv','verify_iflex.R','fixed_source_check_events.csv','encoding_repair.json','repair_region_encoding.py']},
    independent_check_artifacts=['independent_expected_roster.csv','independent_metadata_checks.csv','independent_fixed_source_values.csv','independent_source_check_summary.csv'],auditor_source_sha256=sha(Path(__file__)))
encoded=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
with (HERE/'verification.json').open('w',encoding='utf-8') as f:f.write(encoded)
print(json.dumps(dict(passed=result['passed'],checks=len(checks),issues=issues,split_counts=split_counts),ensure_ascii=False))
if issues:raise SystemExit(1)
