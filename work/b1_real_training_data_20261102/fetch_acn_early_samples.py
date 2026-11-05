from fetch_metadata import HERE,get
import json,hashlib,urllib.parse
from pathlib import Path
tree=json.loads((HERE/'acn_tree.json').read_text(encoding='utf-8'));commit=json.loads((HERE/'acn_branch.json').read_text(encoding='utf-8'))['commit']['sha'];files=[r for r in tree['tree'] if r['path'].endswith('.csv.gz')];selected=[]
for location in sorted({Path(r['path']).parent.as_posix() for r in files}):
    block=sorted([r for r in files if Path(r['path']).parent.as_posix()==location],key=lambda r:hashlib.sha256(r['path'].encode()).hexdigest());selected+=block[:2]
manifest=[]
for item in selected:
    url='https://raw.githubusercontent.com/tongxin-li/ACN-Data-Static/'+commit+'/'+urllib.parse.quote(item['path']);dest=HERE/'early_screening_acn'/Path(item['path']).relative_to('time series data');dest.parent.mkdir(parents=True,exist_ok=True);raw=dest.read_bytes() if dest.exists() else get(url)
    if not dest.exists():dest.write_bytes(raw)
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['sha']
    manifest.append(dict(path=item['path'],local=str(dest.relative_to(HERE)),sha256=hashlib.sha256(raw).hexdigest(),git_blob_sha=item['sha'],screening_seen_exclude_final_blind=True))
(HERE/'acn_early_screening_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print('early screened',len(manifest),flush=True)
