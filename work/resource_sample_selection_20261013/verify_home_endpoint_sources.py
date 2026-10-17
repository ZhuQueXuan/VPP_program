"""Cross-check source inventory with an independent workbook reader; do not edit sources."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import io
import json
import zipfile
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--audit-run',required=True);pa.add_argument('--verification-id',required=True);a=pa.parse_args()
if not a.audit_run.isidentifier() or not a.verification_id.isidentifier():raise ValueError('simple IDs required')
BASE=ROOT/'downloads/rwth_home_endpoint_evidence_20261015';folder=BASE/a.audit_run;out=BASE/(a.verification_id+'.json')
if out.exists():raise FileExistsError(out)
read=lambda p:json.loads(p.read_text('utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
summary=read(folder/'summary.json');inventory=read(folder/'workbook_inventory.json');receipt=read(folder/'receipt.json')
for name,h in receipt['artifacts'].items():assert sha(folder/name)==h,name
for name,h in summary['source_files'].items():assert sha(ROOT/name)==h,name
meta=ROOT/'downloads/independent_candidates_20261013/rwth_home_metadata.zip'
assert sha(meta)==summary['metadata_zip_sha256']
worksheets_checked=0;headers_checked=0;event_tables={};examples={}
with zipfile.ZipFile(meta) as zipmeta:
    for entry in inventory:
        name=entry['identity']
        if name.startswith('00_Data/'):
            raw=zipmeta.read(name);assert hashlib.sha256(raw).hexdigest()==entry['sha256'];path_or_buffer=io.BytesIO(raw)
        else:path_or_buffer=ROOT/next(k for k in summary['source_files'] if Path(k).name==name)
        wb=load_workbook(path_or_buffer,read_only=True,data_only=False)
        assert wb.sheetnames==[s['name'] for s in entry['worksheets']]
        for s in entry['worksheets']:
            ws=wb[s['name']];assert ws.sheet_state==s['state']
            cells=next(ws.iter_rows(min_row=1,max_row=1))
            headers={c.column_letter:str(c.value) if c.value is not None else '' for c in cells if c.value is not None}
            expected={k:v for k,v in s['first_three_rows'][0].items() if v!=''}
            expected={''.join(c for c in k if c.isalpha()):v for k,v in expected.items()}
            assert headers==expected,(name,s['name'],headers,expected)
            headers_checked+=len(headers);worksheets_checked+=1
            if name=='00_Data/00_Metadata/Capacity_Tests.xlsx' or (name=='publisher_source_03.xlsx' and s['name']=='a)-c)'):
                rows=list(ws.iter_rows(min_row=2,values_only=True)); assert len(rows)==60
                records=[]
                for row in rows:
                    date=row[0] if isinstance(row[0],dt.datetime) else dt.datetime(1899,12,30)+dt.timedelta(days=float(row[0]))
                    records.append((date.replace(microsecond=0).isoformat(sep=' '),int(row[1])))
                event_tables[name]=records
            if name=='publisher_source_04.xlsx':
                col=s['columns']['A'];assert col['numeric_min']==42903 and col['numeric_max']==42905
                # Read actual first/last data cells using the second reader, not just inventory labels.
                first=ws.cell(row=2,column=1).value;last=ws.cell(row=s['rows'],column=1).value
                serial=lambda value:(value-wb.epoch).total_seconds()/86400 if isinstance(value,dt.datetime) else float(value)
                assert serial(first)==42903 and serial(last)==42905,(first,last)
                examples[s['name']]={'time_min_serial':serial(first),'time_max_serial':serial(last),'rows':s['rows']}
        wb.close()
assert len(event_tables)==2
assert event_tables['00_Data/00_Metadata/Capacity_Tests.xlsx']==event_tables['publisher_source_03.xlsx']
assert sum(t=='2019-07-01 13:55:06' and identity==1 for t,identity in event_tables['publisher_source_03.xlsx'])==1
pdf=ROOT/'downloads/rwth_home_capacity_20261014/supplementary_information.pdf';assert sha(pdf)==summary['supplementary_pdf_sha256']
result={'status':'passed','verification_id':a.verification_id,'audit_run':a.audit_run,
        'workbooks_checked':len(inventory),'worksheet_names_headers_checked':worksheets_checked,'header_cells_checked':headers_checked,
        'two_source_test_keys_equal':True,'test_keys_checked_each':60,'target_test_key_unique':True,
        'main_fig3_example_ranges_checked':examples,'publisher_sources_unmodified':True,
        'new_capacity_integrals_predictions':False,'code_sha256':sha(Path(__file__)),
        'scope':'independent openpyxl sheet names/states/headers for all 40 sheets; all 60 event keys in both tables; first/last example times; source/artifact hashes; no physical endpoint confirmation'}
out.open('x',encoding='utf-8').write(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
