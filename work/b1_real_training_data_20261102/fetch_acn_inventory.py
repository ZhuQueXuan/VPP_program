from fetch_metadata import HERE,get,save
from pathlib import Path
import json,hashlib,urllib.parse,concurrent.futures
repo='https://api.github.com/repos/tongxin-li/ACN-Data-Static/git/trees/'
branch=json.loads((HERE/'acn_branch.json').read_text(encoding='utf-8'));commit=branch['commit']['sha']
root=save('acn_root_tree.json',repo+commit);ts=next(r for r in root['tree'] if r['path']=='time series data')
sites=save('acn_sites_tree.json',repo+ts['sha']);files=[];ledger=[]
for site in sites['tree']:
    if site['type']!='tree':continue
    locations=save('acn_'+site['path']+'_locations.json',repo+site['sha'])
    for location in locations['tree']:
        if location['type']!='tree':continue
        tree=save('acn_'+site['path']+'_'+location['path']+'_tree.json',repo+location['sha']+'?recursive=1');assert not tree.get('truncated')
        block=[]
        for r in tree['tree']:
            if r['type']!='blob' or not r['path'].endswith('.csv.gz'):continue
            path='time series data/'+site['path']+'/'+location['path']+'/'+r['path'];item=dict(path=path,git_blob_sha=r['sha'],bytes=r.get('size',0),site=site['path'],location=location['path']);files.append(item);block.append(item)
        ledger.append(dict(site=site['path'],location=location['path'],files=len(block),bytes=sum(r['bytes'] for r in block)))
(HERE/'acn_complete_inventory.json').write_text(json.dumps(dict(commit=commit,files=files,locations=ledger,total_files=len(files),bytes=sum(r['bytes'] for r in files)),ensure_ascii=False),encoding='utf-8')
samples=[]
for location in sorted({r['location'] for r in files}):
    block=sorted([r for r in files if r['location']==location],key=lambda r:hashlib.sha256(r['path'].encode()).hexdigest());samples+=block[:3]
def fetch(item):
    url='https://raw.githubusercontent.com/tongxin-li/ACN-Data-Static/'+commit+'/'+urllib.parse.quote(item['path'])
    dest=HERE/'screening_acn'/item['site']/item['location']/Path(item['path']).name;dest.parent.mkdir(parents=True,exist_ok=True)
    raw=dest.read_bytes() if dest.exists() else get(url)
    if not dest.exists():dest.write_bytes(raw)
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();assert blob==item['git_blob_sha']
    return dict(item,url=url,local=str(dest.relative_to(HERE)),sha256=hashlib.sha256(raw).hexdigest(),screening_seen_exclude_final_blind=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:samples=list(pool.map(fetch,samples))
(HERE/'acn_screening_manifest.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(total_files=len(files),total_compressed_bytes=sum(r['bytes'] for r in files),locations=ledger,sample_files=len(samples))),flush=True)
