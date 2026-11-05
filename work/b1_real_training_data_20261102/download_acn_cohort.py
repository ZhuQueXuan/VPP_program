from fetch_metadata import HERE,get
from pathlib import Path
import json,hashlib,urllib.parse,concurrent.futures,time
freeze=json.loads((HERE/'acn_split_freeze.json').read_text(encoding='utf-8'))
for name,expected in freeze['files'].items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected
plan=json.loads((HERE/'acn_split_plan.json').read_text(encoding='utf-8'));selected=json.loads((HERE/'acn_download_selection.json').read_text(encoding='utf-8'));start=time.perf_counter()
def fetch(r):
    url='https://raw.githubusercontent.com/tongxin-li/ACN-Data-Static/'+plan['commit']+'/'+urllib.parse.quote(r['path']);dest=HERE/'acn_raw'/r['split']/r['site']/r['location']/Path(r['path']).name;dest.parent.mkdir(parents=True,exist_ok=True)
    try:
        raw=dest.read_bytes() if dest.exists() else get(url)
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();assert blob==r['git_blob_sha']
        if not dest.exists():dest.write_bytes(raw)
        return dict(r,local=dest.relative_to(HERE).as_posix(),sha256=hashlib.sha256(raw).hexdigest(),verified_git_blob=True,status='downloaded')
    except Exception as ex:return dict(r,status='download_failed',error=str(ex),url=url)
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for r in pool.map(fetch,selected):
        results.append(r)
        if len(results)%50==0:print('ACN downloaded',len(results),'/',len(selected),'failures',sum(x['status']!='downloaded' for x in results),flush=True)
(HERE/'acn_download_manifest.json').write_text(json.dumps(results,ensure_ascii=False),encoding='utf-8')
print(json.dumps(dict(files=len(results),downloaded=sum(x['status']=='downloaded' for x in results),bytes=sum(x['bytes'] for x in results if x['status']=='downloaded'),elapsed_seconds=time.perf_counter()-start)),flush=True)
