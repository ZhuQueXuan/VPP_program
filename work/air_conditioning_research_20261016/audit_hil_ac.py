"""Full five-file AC source audit; no model fitting or prediction errors."""
from common import *
from datetime import datetime
import math,statistics
src=BASE/'downloads/HIL_AC_SOURCE_01';out=BASE/'runs/HIL_AC_QA_01';out.mkdir(parents=True,exist_ok=False)
receipt=load(src/'receipt.json');entries=[r for r in receipt['files'] if r['name'].startswith('AC_')]
assert len(entries)==5 and all(r['status']=='downloaded' for r in entries)
summary=[];core=['T_Return (C)','T_Supply (C)','T_Outdoor (C)','Outdoor Unit Power (W)','Indoor Unit Power (W)','Evaporator Airflow Rate (CFM)','Cooling Capacity (kW)']
for entry in entries:
    p=src/entry['name'];assert sha(p)==entry['sha256']
    assert entry['etag'].strip('"')==entry['md5']
    records=read(p);assert len(records)>100
    values={k:[float(r[k]) for r in records] for k in records[0] if k!='TimeStamp'}
    times=[datetime.fromisoformat(r['TimeStamp']) for r in records];dt=[(b-a).total_seconds() for a,b in zip(times,times[1:])]
    thermostat=values['T_SP_Thermostat (C)'];changes=[b-a for a,b in zip(thermostat,thermostat[1:])]
    info={'file':p.name,'rows':len(records),'bytes':p.stat().st_size,'SHA256':sha(p),'MD5_matches_response_singlepart_ETag':True,
      'header':list(records[0]),'first_timestamp':records[0]['TimeStamp'],'last_timestamp':records[-1]['TimeStamp'],
      'clock':{'timezone':'not encoded; do not assert UTC','backwards':sum(x<0 for x in dt),'duplicate_steps':sum(x==0 for x in dt),
       'non1s_steps':sum(x!=1 for x in dt),'minimum_step_s':min(dt),'maximum_step_s':max(dt),'median_step_s':statistics.median(dt)},
      'fields':{k:{'nonfinite':sum(not math.isfinite(x) for x in v),'minimum':min(x for x in v if math.isfinite(x)),
                   'maximum':max(x for x in v if math.isfinite(x))} for k,v in values.items()},
      'core_nonfinite_rows':sum(not all(math.isfinite(values[k][i]) for k in core) for i in range(len(records))),
      'thermostat_setpoint_unique_values':len(set(thermostat)),'thermostat_nonzero_adjacent_changes':sum(x!=0 for x in changes),
      'negative_published_outdoor_power_rows':sum(x<0 for x in values['Outdoor Unit Power (W)']),
      'negative_published_indoor_power_rows':sum(x<0 for x in values['Indoor Unit Power (W)']),
      'negative_published_capacity_rows':sum(x<0 for x in values['Cooling Capacity (kW)'])}
    summary.append(info)
    print(json.dumps({k:v for k,v in info.items() if k not in ('fields','header')},ensure_ascii=False),flush=True)
dump(out/'file_quality.json',summary)
notes={'date':'2026-10-16','source':'NLR catalog246, DOI10.7799/2440214, original2024files current2026catalog',
 'license':'NREL dataset license, retain entire notice and credit DOE/NREL/ALLIANCE; not CC-BY by assumption.',
 'five_files':len(summary),'raw_rows':sum(r['rows'] for r in summary),'equipment':'One two-stage SEER21 2-ton central AC in cooling mode, five chamber-temperature tests. No HP tests/space-heating mixing.',
 'direct_measured':'Published indoor/outdoor equipment electrical power, chamber/duct temperature and airflow per catalog; not occupied-house measurements.',
 'calculated_or_emulated':'Cooling capacity derived from air-side measures, used in EnergyPlus. Return/indoor chamber setpoints and building thermal response are HIL-driven. No claim of field-room temperature dynamics.',
 'time':'Raw TimeStamp naive; within-record relative time only. Physical lab measures nominal1s. Thermostat5min observations resampled to1s: interpolated changes cannot define true1s commands or dispatch latency.',
 'matrix':'14AC conditions reference5filenames; approximate start times, some text times, not exact command truth. Matched filenames/Excel dates checked separately in document evidence.',
 'paper_scope':'82562 describes platform/validates a3ton heat pump on field comparison; not exact validation of these2024two-stageAC tests. No transferred quoted accuracy.',
 'FLEXLAB_candidate_limit':'Paper109149 p11 explicitly uses common chiller and boiler, calculates cooling/heating electrical power assuming COP3.0/efficiency0.95. Do not validate compressor electricity with those estimated channels. No six-buildings raw download/admission.',
 'status':'source/fields/time/use-boundary QA only; sample/split/model not yet frozen'}
dump(out/'summary.json',notes)
dump(out/'receipt.json',{'date':'2026-10-16','status':'source_audit_completed','script_sha256':sha(Path(__file__)),
 'outputs':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
print(json.dumps(notes,ensure_ascii=False,indent=2))
