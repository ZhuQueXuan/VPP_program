"""Reuse HTTPS connections for the remaining public small-file downloads."""
from pathlib import Path
import json,hashlib,urllib.parse,concurrent.futures,threading,time
import requests
HERE=Path(__file__).resolve().parent;local=threading.local();plan=json.loads((HERE/'acn_split_plan.json').read_text(encoding='utf-8'));selected=json.loads((HERE/'acn_download_selection.json').read_text(encoding='utf-8'))[200:]
def fetch(r):
    dest=HERE/'acn_raw'/r['split']/r['site']/r['location']/Path(r['path']).name;dest.parent.mkdir(parents=True,exist_ok=True)
    url='https://raw.githubusercontent.com/tongxin-li/ACN-Data-Static/'+plan['commit']+'/'+urllib.parse.quote(r['path'])
    try:
        if dest.exists():
            raw=dest.read_bytes()
            if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob_sha']:return dict(path=r['path'],status='already_verified')
        if not hasattr(local,'session'):
            local.session=requests.Session();local.session.headers.update({'User-Agent':'VPP-public-data-research'})
        for attempt in range(3):
            try:
                response=local.session.get(url,timeout=(15,40));response.raise_for_status();raw=response.content
                assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob_sha'];break
            except Exception:
                if attempt==2:raise
        if not dest.exists():dest.write_bytes(raw)
        return dict(path=r['path'],status='downloaded')
    except Exception as ex:return dict(path=r['path'],status='failed',error=str(ex))
results=[];start=time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for r in pool.map(fetch,selected):
        results.append(r)
        if len(results)%100==0:print('remaining ACN',len(results),'/',len(selected),flush=True)
(HERE/'acn_accelerated_download.json').write_text(json.dumps(dict(results=results,seconds=time.perf_counter()-start)),encoding='utf-8')
print('Remaining downloads complete',len(results),sum(r['status']=='failed' for r in results),flush=True)
