from common import *
import re,zipfile,io

def main():
    base=ROOT/'data/六类资源研究数据/03_电动汽车充电设施'
    files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(base.rglob('*')) if p.is_file()]
    header=read(ROOT/'work/ev_exante_admission_20261021/epfl_header_inventory.json')
    epfl=[]
    for item in header:
        for sheet in item['sheets']:
            first=sheet['first_three_rows_only'][0]
            epfl.append(dict(path=item['path'],xml_member=sheet['xml_member'],headers=[x['value'] for x in first['cells'] if x['value'] is not None]))
    catalog=read(EV/'downloads/EV_NEXT_SOURCE_01/kit_zenodo_record.json')
    with zipfile.ZipFile(ARCHIVE) as z:
        members=z.namelist();non_tables=[n for n in members if not n.endswith('/') and not n.lower().endswith('.csv')]
    out=dict(local_ev_files=files,kit_published_files=[dict(name=r['key'],bytes=r['size']) for r in catalog['files']],
        local_ev_filenames_suggesting_execution_or_fault_logs=[r['path'] for r in files if re.search(r'(?i)(ocpp|fault|acknow|execution|error.?code|device.?log)',Path(r['path']).name)],
        dortmund_archive_files=len(members),dortmund_non_csv_payloads=non_tables,
        epfl_headers=epfl,epfl_scope='1minute samples. Ctrl_t means Pset<Preq, Ctrl_s repeats session-level occurrence; neither is a fault label or command ACK. Session fields are not execution logs.',
        acn_scope='Local official docs/author code only, no registered/downloaded live session time series or OCPP execution/error logs.',
        urbanev_scope='Region-level price/occupancy, not the same vehicle/device and no per-event fine fault labels.',
        no_cross_source_identity_join=True,scope='Inventory only; absence claim limited to local files and inspected publisher field/file descriptions.')
    write('local_source_inventory.json',out)
    print(json.dumps({k:v for k,v in out.items() if k not in ['local_ev_files','epfl_headers','kit_published_files']}))
if __name__=='__main__':main()
