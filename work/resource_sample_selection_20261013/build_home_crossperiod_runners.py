"""Create separate v2 runners, preserving v1 source and algorithm verbatim where possible."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def replace(s,a,b):
    if s.count(a)!=1: raise ValueError(f'expected one source fragment: {a[:100]}')
    return s.replace(a,b)
def save(name,s):
    (ROOT/name).open('x',encoding='utf-8',newline='\n').write(s)

s=(ROOT/'prepare_home_capacity_samples.py').read_text('utf-8')
s=s.replace("home_capacity_sample_protocol_v1.json","home_capacity_crossperiod_protocol_v2.json")
s=replace(s,"source=ROOT/protocol['source']['relative_path']\nif sha(source)!=protocol['source']['sha256']: raise ValueError('source fingerprint mismatch')", """admission_file=ROOT/protocol['source']['relative_directory']/protocol['source']['admission_receipt']
admission=json.loads(admission_file.read_text('utf-8'))
if admission['status']!='admitted_frozen_history_proxy_only' or admission['protocol_sha256']!=sha(protocol_path): raise ValueError('no matching admission')
sources=admission['source_members']
for source in sources:
    if sha(ROOT/source['path'])!=source['sha256']: raise ValueError('source fingerprint mismatch')""")
s=replace(s,"frame=pd.read_csv(source,nrows=expected)","""parts=[]
for source in sources:
    for chunk in pd.read_csv(ROOT/source['path'],chunksize=250000):
        ct=pd.to_datetime(chunk['Time'],format='%d-%b-%Y %H:%M:%S',errors='raise')
        selected_chunk=chunk.loc[(ct>=start)&(ct<cutoff)]
        if len(selected_chunk): parts.append(selected_chunk)
frame=pd.concat(parts,ignore_index=True)""")
s=s.replace("'source_sha256':sha(source)","'source_members':sources,'admission_sha256':sha(admission_file)")
save('prepare_home_crossperiod_samples.py',s)

s=(ROOT/'verify_home_capacity_samples.py').read_text('utf-8')
s=replace(s,"source=ROOT/p['source']['relative_path']\nif sha(source)!=p['source']['sha256']: raise ValueError('source hash differs')", """admission=json.loads((ROOT/p['source']['relative_directory']/p['source']['admission_receipt']).read_text('utf-8'))
if admission['status']!='admitted_frozen_history_proxy_only': raise ValueError('not admitted')
sources=admission['source_members']
for source in sources:
    if sha(ROOT/source['path'])!=source['sha256']: raise ValueError('source hash differs')
def native_rows():
    for source in sources:
        with (ROOT/source['path']).open(encoding='utf-8',newline='') as handle:
            yield from csv.DictReader(handle)""")
s=replace(s,"with source.open(encoding='utf-8',newline='') as handle:\n    for row in csv.DictReader(handle):", "if True:\n    for row in native_rows():")
s=replace(s,"        if time>=cutoff: break", "        if time<start: continue\n        if time>=cutoff: break")
s=s.replace("'source_sha256':sha(source)","'source_members':sources")
# Explicitly verify source selection and cutoff even if no eligible pair exists.
s=replace(s,"f=f[0]", """f=f[0]
if f['sample_id']!=p['sample']['sample_id'] or f['history_cutoff']!=str(cutoff): raise ValueError('event/cutoff mismatch')
if not selected and any(f[k]!='' for k in ('selected_pair_id','history_net_capacity_ah','history_net_UI_energy_kwh','history_anchor_age_seconds')): raise ValueError('unavailable proxy filled')""")
save('verify_home_crossperiod_samples.py',s)

s=(ROOT/'run_home_capacity_baselines.py').read_text('utf-8')
s=replace(s,"protocol_file=ROOT/'home_capacity_baseline_protocol_v1.json'\nprotocol=json.loads(protocol_file.read_text('utf-8'))", "protocol_file=ROOT/'home_capacity_crossperiod_protocol_v2.json'\nprotocol=json.loads(protocol_file.read_text('utf-8'))['baseline']")
s=replace(s,"for role in ('source','reference'):\n    if sha(ROOT/sample_protocol[role]['relative_path'])!=sample_protocol[role]['sha256']: raise ValueError(f'{role} changed')", """admission=json.loads((ROOT/sample_protocol['source']['relative_directory']/sample_protocol['source']['admission_receipt']).read_text('utf-8'))
for item in admission['source_members']:
    if sha(ROOT/item['path'])!=item['sha256']: raise ValueError('source changed')
if sha(ROOT/sample_protocol['reference']['relative_path'])!=sample_protocol['reference']['sha256']: raise ValueError('reference changed')""")
s=s.replace("'source_sha256':sample_protocol['source']['sha256']", "'source_members':admission['source_members']")
save('run_home_crossperiod_baselines.py',s)

s=(ROOT/'verify_home_capacity_baselines.py').read_text('utf-8')
s=replace(s,"if sha(ROOT/sp['source']['relative_path'])!=sp['source']['sha256'] or sha(ROOT/sp['reference']['relative_path'])!=sp['reference']['sha256']: raise ValueError('original sources changed')", """admission=json.loads((ROOT/sp['source']['relative_directory']/sp['source']['admission_receipt']).read_text('utf-8'))
for item in admission['source_members']:
    if sha(ROOT/item['path'])!=item['sha256']: raise ValueError('original source changed')
if sha(ROOT/sp['reference']['relative_path'])!=sp['reference']['sha256']: raise ValueError('reference changed')
def native_rows():
    for item in admission['source_members']:
        with (ROOT/item['path']).open(encoding='utf-8',newline='') as handle:
            yield from csv.DictReader(handle)""")
s=replace(s,"    with (ROOT/sp['source']['relative_path']).open(encoding='utf-8',newline='') as handle:\n        for raw in csv.DictReader(handle):", "    if True:\n        for raw in native_rows():")
s=s.replace("'source_sha256':sp['source']['sha256']", "'source_members':admission['source_members']")
s=replace(s,"cap=energy=None", """if proof['source_members']!=admission['source_members']: raise ValueError('sample source binding differs')
cap=energy=None""")
save('verify_home_crossperiod_baselines.py',s)
print('Created four separate v2 runners; v1 source untouched.')
