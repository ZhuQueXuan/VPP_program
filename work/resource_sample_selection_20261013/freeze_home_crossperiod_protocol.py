"""Recheck public test index and ZIP directory, freeze dates before new raw inspection."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib, io, json, urllib.request, zipfile, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DEST = ROOT/'downloads'/'rwth_home_crossperiod_20261014'
PROTOCOL = ROOT/'home_capacity_crossperiod_protocol_v2.json'
if PROTOCOL.exists() or (DEST/'metadata.zip').exists():
    raise FileExistsError('freeze ID already used; never overwrite')
DEST.mkdir(exist_ok=True)
def sha(b): return hashlib.sha256(b).hexdigest()
requests = []
def fetch(url, cap, byte_range=None):
    headers = {'User-Agent':'VPP-research-source-audit/1.0'}
    if byte_range: headers['Range'] = f'bytes={byte_range[0]}-{byte_range[1]}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        b = r.read(cap+1)
        if len(b)>cap: raise ValueError('size cap')
        if byte_range and (r.status!=206 or r.headers.get('Content-Range')!=f'bytes {byte_range[0]}-{byte_range[1]}/973143312' or len(b)!=byte_range[1]-byte_range[0]+1):
            raise ValueError('Range response mismatch')
        requests.append({'url':url,'status':r.status,'content_range':r.headers.get('Content-Range'),'bytes':len(b),'sha256':sha(b)})
        return b
def rows(raw):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        result=[]
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//s:row',ns):
            d={}
            for c in row.findall('s:c',ns):
                v=c.find('s:v',ns); value=None if v is None else v.text
                if c.attrib.get('t')=='s' and value is not None: value=strings[int(value)]
                d[''.join(ch for ch in c.attrib['r'] if ch.isalpha())]=value
            result.append(d)
        return result
url='https://zenodo.org/api/records/12091223/files/Metadata_and_Code.zip/content'
raw=fetch(url,100000)
if hashlib.md5(raw).hexdigest()!='23720da306f63fd2fd20fdc1a7b8f106': raise ValueError('metadata MD5 mismatch')
(DEST/'metadata.zip').open('xb').write(raw)
with zipfile.ZipFile(io.BytesIO(raw)) as z: tests=rows(z.read('00_Data/00_Metadata/Capacity_Tests.xlsx'))[1:]
old=json.loads((ROOT/'home_capacity_sample_protocol_v1.json').read_text('utf-8'))
system_tests=sorted([r for r in tests if r.get('B')=='1'], key=lambda r:float(r['A']))
future=[r for r in system_tests if float(r['A'])>float(old['reference']['excel_time_value'])]
chosen=future[0]
test=datetime(1899,12,30)+timedelta(days=float(chosen['A']))
assert str(test)=='2018-03-06 16:24:35'
cutoff=test-timedelta(hours=old['information']['preparation_embargo_hours'])
duration=datetime.fromisoformat(old['information']['history_end_exclusive'])-datetime.fromisoformat(old['information']['history_start_inclusive'])
start=cutoff-duration
evidence=json.loads((ROOT/'downloads/rwth_home_capacity_20261014/method_acquisition_01.json').read_text('utf-8'))
archive=evidence['remote_archive']
class Remote(io.RawIOBase):
    def __init__(self): self.pos=0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else archive['bytes']+offset
        return self.pos
    def read(self, n=-1):
        n=min(n if n>=0 else archive['bytes']-self.pos,archive['bytes']-self.pos)
        if not n: return b''
        if n>100000: raise ValueError('directory only')
        b=fetch(archive['url'],n,(self.pos,self.pos+n-1)); self.pos+=len(b); return b
with zipfile.ZipFile(Remote()) as z:
    selected=[]
    for name in ('01/2018_02_System_ID_01.csv','01/2018_03_System_ID_01.csv'):
        m=z.getinfo(name)
        item={'name':name,'compression':m.compress_type,'crc32':f'{m.CRC:08x}','compressed_bytes':m.compress_size,'bytes':m.file_size,'header_offset':m.header_offset}
        if item!=next(x for x in evidence['system_01_zip_members'] if x['name']==name): raise ValueError('published member changed')
        selected.append(item)
p=json.loads(json.dumps(old))
p['protocol_id']='RWTH-HOME-ID01-CAPACITY-CROSSPERIOD-v2'
p['data_card_version']='DC-20261014-05'
p['frozen_at_utc']=datetime.now(timezone.utc).isoformat()
p['source'].pop('relative_path'); p['source'].pop('sha256')
p['source'].update(archive={k:v for k,v in archive.items() if k!='range_requests'}, members=selected,
    relative_directory='downloads/rwth_home_crossperiod_20261014', admission_receipt='admission_01.json',
    monthly_files_role='February and March required for fixed lookback; full months quality-only, feature builder explicitly slices frozen history')
p['reference']['excel_time_value']=chosen['A']; p['reference']['test_start_native']=str(test)
p['information'].update(history_start_inclusive=str(start),history_end_exclusive=str(cutoff),history_duration_seconds=int(duration.total_seconds()),
    history_basis='exact duration of v1 history, translated to next chronological test; fixed before any new raw curve reading',
    left_boundary='no carry-in anchor before start; existing v1 rule; all missing-high cases retained',
    diagnostic_window_start=str(test-timedelta(hours=12)),diagnostic_window_end_exclusive=str(test+timedelta(hours=12)))
p['sample'].update(sample_id='rwth_home_id01_test_20180306T162435',split='single subsequent chronological retrospective evaluation, no fit; published reference already seen')
p['baseline']=json.loads((ROOT/'home_capacity_baseline_protocol_v1.json').read_text('utf-8'))
p['baseline']['protocol_id']='RWTH-HOME-ID01-CAPACITY-CROSSPERIOD-BL-v2'
p['baseline']['sample_protocol']=PROTOCOL.name
p['baseline']['implementation_status']='frozen before new raw acquisition, no new scoring yet'
p['changes']='v2 adds next chronological event, equal duration cross-month history and multi-file provenance; rest thresholds, embargo, pairing, net I/UI integration, models and tolerances identical to v1; old files unchanged'
p['failure_policy']='retain chosen event even if no eligible spans; never extend history or replace event after observing results; failed acquisition/admission must be recorded before retry'
ref=ROOT/p['reference']['relative_path']
assert sha(ref.read_bytes())==p['reference']['sha256']
for key in ('rest_proxy','pairing'):
    assert p[key]==old[key]
receipt={'status':'frozen_before_raw_acquisition','system01_tests':system_tests,'selected_by':'earliest listed ID01 test after v1, regardless of capacity value','requests':requests,
         'old_protocol_sha256':sha((ROOT/'home_capacity_sample_protocol_v1.json').read_bytes()),'new_protocol_sha256':sha(json.dumps(p,ensure_ascii=False,indent=2).encode()),
         'known_reference_disclosure':'all ID01 published values previously inspected; not blind or independent method confirmation'}
PROTOCOL.open('x',encoding='utf-8').write(json.dumps(p,ensure_ascii=False,indent=2))
(DEST/'freeze_receipt_01.json').open('x',encoding='utf-8').write(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps({'status':receipt['status'],'test':str(test),'history_start':str(start),'history_end_exclusive':str(cutoff),'history_seconds':int(duration.total_seconds()),'protocol_sha256':receipt['new_protocol_sha256']},ensure_ascii=False))
