"""OriginalZIPfull MD5/CRC, member names and bounded header inspection, no model."""
from common import *
import zipfile,io,argparse
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
folder=BASE/'downloads/KELMARSH_2018_01';rec=load(folder/'receipt.json');assert len(rec['files'])==3 and all(r['status']=='downloaded' for r in rec['files'])
for r in rec['files']:assert sha(folder/r['name'])==r['sha256']
fp=folder/'Kelmarsh_SCADA_2018_3084.zip'
with zipfile.ZipFile(fp) as z:
    bad=z.testzip();assert bad is None
    entries=[{'name':i.filename,'bytes':i.file_size,'compressed':i.compress_size,'crc32':format(i.CRC,'08x')} for i in z.infolist()]
    previews=[]
    for i in z.infolist():
        if i.is_dir():continue
        with z.open(i) as raw:
            head=io.TextIOWrapper(raw,encoding='utf-8-sig',newline='')
            lines=[]
            for _ in range(8):
                line=head.readline()
                if not line:break
                lines.append(line.rstrip('\r\n'))
        previews.append({'member':i.filename,'first8lines':lines})
dump(out/'members.json',entries);dump(out/'previews.json',previews)
dump(out/'receipt.json',{'status':'archive_identity_and_CRC_passed_not_model_admission','archive_sha256':sha(fp),'members':len(entries),'all_CRC_passed':True,'script_sha256':sha(Path(__file__)),'outputs':{f.name:sha(f) for f in sorted(out.iterdir()) if f.is_file()}})
print(json.dumps({'members':entries,'header_previews':[{'member':r['member'],'lines':[x[:300] for x in r['first8lines']]} for r in previews]},ensure_ascii=False,indent=2))
