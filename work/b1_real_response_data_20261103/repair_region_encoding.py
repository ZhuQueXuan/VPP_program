"""Restore Region from the official UTF-8 metadata; preserve native-R exports."""
from pathlib import Path
import csv,json,hashlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
source=ROOT/'data/public_datasets/挪威_iFlex_动态电价试验/participants.csv'
with source.open(encoding='utf-8-sig',newline='') as f:
    metadata={r['ID']:r for r in csv.DictReader(f)}
receipt={}
for name in ('prepared_P_events.csv','P_household_registry.csv'):
    canonical=(HERE/name).resolve()
    preserved=(HERE/(canonical.stem+'_native_R.csv')).resolve()
    assert canonical.parent==HERE.resolve() and preserved.parent==HERE.resolve()
    assert canonical.is_file() and not preserved.exists()
    canonical.rename(preserved)  # One explicit file preserved; nothing deleted.
    with preserved.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    original=[dict(r) for r in rows]
    changed=0
    for row in rows:
        expected=metadata[row['ID']]['Region']
        changed+=row['Region']!=expected
        row['Region']=expected
    with canonical.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    with canonical.open(encoding='utf-8',newline='') as f:reloaded=list(csv.DictReader(f))
    assert len(reloaded)==len(original)
    for before,after in zip(original,reloaded):
        assert all(before[k]==after[k] for k in fields if k!='Region')
        assert after['Region']==metadata[after['ID']]['Region']
    receipt[name]=dict(rows=len(rows),region_rows_repaired=int(changed),
        other_fields_identical_as_strings=True,preserved_original=preserved.name,
        preserved_sha256=hashlib.sha256(preserved.read_bytes()).hexdigest(),
        canonical_sha256=hashlib.sha256(canonical.read_bytes()).hexdigest())
value=dict(reason='Native-R character conversion exported Tromsø as a literal Unicode escape; exact ID join to original official UTF-8 metadata restores Region.',
    official_metadata_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    changed_columns=['Region'],source_data_or_numeric_values_changed=False,files=receipt)
with (HERE/'encoding_repair.json').open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps(value,ensure_ascii=True))
