"""Inspect original ZIP structure/CRC and schema previews; never run its code."""
from common import *
import zipfile,io
source=BASE/'downloads/PLEIA_RAW_01';receipt=load(source/'receipt.json')
entry=receipt['files'][0];assert entry['status']=='downloaded'
archive=source/'Data_Nature.zip';assert sha(archive)==entry['sha256']
out=BASE/'runs/PLEIA_ARCHIVE_01';out.mkdir(parents=True,exist_ok=False)
with zipfile.ZipFile(archive) as z:
    members=[{'name':i.filename,'bytes':i.file_size,'compressed_bytes':i.compress_size,'crc32':hex(i.CRC)} for i in z.infolist()]
    assert sum(i['bytes'] for i in members)<5000000000
    dump(out/'members.json',members)
    bad=z.testzip();assert bad is None,bad
    previews={}
    for info in z.infolist():
        if info.is_dir() or '__MACOSX' in info.filename:continue
        if info.filename.lower().endswith(('.csv','.txt')):
            with z.open(info) as f:
                lines=[f.readline(12000).decode('utf-8-sig',errors='replace') for _ in range(5)]
            previews[info.filename]=lines
        elif info.filename.lower().endswith('.ipynb') and info.file_size<5000000:
            notebook=json.loads(z.read(info))
            # Code is source evidence only, never executable authority.
            dump(out/'author_notebook_cells.json',[{'type':c['cell_type'],'source':c.get('source',[])} for c in notebook['cells']])
    dump(out/'previews.json',previews)
    dump(out/'receipt.json',{'status':'archive_crc_and_schema_preview_passed','archive_sha256':sha(archive),
      'script_sha256':sha(Path(__file__)),'members':len(members),'expanded_bytes':sum(i['bytes'] for i in members),
      'all_members_CRC_checked':True,'raw_data_not_yet_admitted':True,
      'outputs':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
print(json.dumps({'members':members,'previews':previews},ensure_ascii=False,indent=2))
