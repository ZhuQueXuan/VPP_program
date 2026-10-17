"""Acquire first-party method evidence and list one system's remote ZIP members."""
from pathlib import Path
import urllib.request
import json, hashlib, re, zipfile, io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'downloads' / 'independent_candidates_20261013'
DEST = ROOT / 'downloads' / 'rwth_home_capacity_20261014'
DEST.mkdir(parents=True, exist_ok=True)
RECEIPT = DEST / 'method_acquisition_01.json'
if RECEIPT.exists():
    raise FileExistsError(RECEIPT)
report = {}
def fetch(url, limit, byte_range=None):
    headers = {'User-Agent': 'VPP-research-source-audit/1.0'}
    if byte_range is not None:
        headers['Range'] = f'bytes={byte_range[0]}-{byte_range[1]}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as response:
        if byte_range is not None and response.status != 206:
            raise ValueError(f'Range unsupported: status {response.status}')
        raw = response.read(limit+1)
        metadata = {'url':url, 'final_url':response.url, 'status':response.status, 'content_range':response.headers.get('Content-Range')}
    if len(raw)>limit:
        raise ValueError('response size exceeds explicit cap')
    if byte_range is not None and len(raw)!=byte_range[1]-byte_range[0]+1:
        raise ValueError('Range response length mismatch')
    metadata.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    return raw, metadata
def download(name, url, cap):
    path=DEST/name
    try:
        if path.exists():
            raw=path.read_bytes()
            info={'url':url,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'reuse':True}
        else:
            raw,info=fetch(url,cap)
            if name.endswith(('.pdf','.xlsx')) and not raw.startswith(b'%PDF' if name.endswith('.pdf') else b'PK'):
                raise ValueError('invalid PDF/XLSX signature')
            path.open('xb').write(raw)
        report[name]=info
        print(name,info,flush=True)
        return raw
    except Exception as exc:
        report[name]={'url':url,'error':str(exc)}
        print(name, report[name],flush=True)
        return None

html=download('article_page.html','https://www.nature.com/articles/s41560-024-01620-9',3_000_000)
pdf_url='https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41560-024-01620-9/MediaObjects/41560_2024_1620_MOESM1_ESM.pdf'
download('supplementary_information.pdf',pdf_url,8_000_000)
if html:
    decoded=html.decode('utf-8')
    links=sorted(set(re.findall(r'href="(https://media\.springernature\.com/[^"]+\.xlsx)"',decoded)))
    report['xlsx_urls']=links
    for index,url in enumerate(links):
        download(f'publisher_source_{index+1:02}.xlsx',url.replace('&amp;','&'),5_000_000)

def workbook_rows(raw):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    output={}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        ss=[]
        if 'xl/sharedStrings.xml' in archive.namelist():
            ss=[''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        for name in archive.namelist():
            if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
                rows=[]
                for row in ET.fromstring(archive.read(name)).findall('.//s:row',ns):
                    cells={}
                    for cell in row.findall('s:c',ns):
                        value=cell.find('s:v',ns)
                        raw='' if value is None else value.text
                        if cell.attrib.get('t')=='s' and raw:
                            raw=ss[int(raw)]
                        elif cell.attrib.get('t')=='inlineStr':
                            raw=''.join(cell.find('s:is',ns).itertext())
                        cells[cell.attrib['r']]=raw
                    rows.append(cells)
                output[name]=rows
    return output
with zipfile.ZipFile(SOURCE/'rwth_home_metadata.zip') as archive:
    tests=workbook_rows(archive.read('00_Data/00_Metadata/Capacity_Tests.xlsx'))
    metadata=workbook_rows(archive.read('00_Data/00_Metadata/Metadata_Systems.xlsx'))
records=[]
for row in tests['xl/worksheets/sheet1.xml'][1:]:
    start=next(v for k,v in row.items() if k.startswith('A'))
    system=next(v for k,v in row.items() if k.startswith('B'))
    records.append({'system_id':system,'excel_serial':start,'start_local_unspecified':str(datetime(1899,12,30)+timedelta(days=float(start)))})
report['capacity_test_index']=records
report['system_01_metadata']=metadata['xl/worksheets/sheet1.xml'][1]
print('system_01_tests',[r for r in records if r['system_id']=='1'],flush=True)
for path in DEST.glob('publisher_source_*.xlsx'):
    report[path.name]['workbook']=workbook_rows(path.read_bytes())

class RemoteZip(io.RawIOBase):
    def __init__(self,url,size): self.url,self.size,self.pos,self.requests=url,size,0,[]
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self,n=-1):
        if n<0: n=self.size-self.pos
        n=min(n,self.size-self.pos)
        if n==0: return b''
        if n>2_000_000: raise ValueError('central-directory read unexpectedly large')
        start=self.pos; end=start+n-1
        raw,info=fetch(self.url,n,(start,end))
        if info['content_range']!=f'bytes {start}-{end}/{self.size}':
            raise ValueError('Range header mismatch')
        self.requests.append(info); self.pos+=len(raw)
        return raw
record=json.loads((SOURCE/'rwth_home_record.json').read_text('utf-8'))
file=next(f for f in record['files'] if f['key']=='Data_ID_01.zip')
remote=RemoteZip(file['links']['self'],file['size'])
try:
    with zipfile.ZipFile(remote) as archive:
        report['system_01_zip_members']=[{'name':i.filename,'compression':i.compress_type,'crc32':f'{i.CRC:08x}','compressed_bytes':i.compress_size,'bytes':i.file_size,'header_offset':i.header_offset} for i in archive.infolist()]
    report['remote_archive']={'url':file['links']['self'],'bytes':file['size'],'publisher_checksum':file['checksum'],'full_archive_checksum_verified':False,'range_requests':remote.requests}
    print('system_01_member_count',len(report['system_01_zip_members']),flush=True)
except Exception as exc:
    report['remote_archive']={'url':file['links']['self'],'error':str(exc),'range_requests':remote.requests}
    print('remote_archive',report['remote_archive'],flush=True)
RECEIPT.open('x',encoding='utf-8').write(json.dumps(report,ensure_ascii=False,indent=2))
