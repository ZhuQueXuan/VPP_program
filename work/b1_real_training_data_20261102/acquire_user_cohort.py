from pathlib import Path
import requests,threading,concurrent.futures,json,hashlib,urllib.parse,time,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DEST=ROOT/'data/ACN_real_user_benchmark_v1_20261102';local=threading.local()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
for name,h in read(DEST/'split_freeze.json')['files'].items():assert hashlib.sha256((DEST/name).read_bytes()).hexdigest()==h
records=read(DEST/'session_manifest.json');commit=read(DEST/'split_protocol.json')['source_snapshot_commit'];existing={}
for r in read(HERE/'acn_download_manifest.json'):
    if r['status']=='downloaded':existing[r['path']]=HERE/r['local']
for fn in ['acn_early_screening_manifest.json','acn_screening_manifest.json']:
    for r in read(HERE/fn):existing[r['path']]=HERE/r['local']
def acquire(r):
    p=ROOT/r['local'];p.parent.mkdir(parents=True,exist_ok=True)
    try:
        if p.exists():raw=p.read_bytes();source='canonical_existing'
        elif r['path'] in existing:raw=existing[r['path']].read_bytes();source='verified_local_copy'
        else:
            if not hasattr(local,'session'):local.session=requests.Session();local.session.headers.update({'User-Agent':'VPP-public-data-research'})
            url='https://raw.githubusercontent.com/tongxin-li/ACN-Data-Static/'+commit+'/'+urllib.parse.quote(r['path'])
            for attempt in range(3):
                try:
                    response=local.session.get(url,timeout=(15,40));response.raise_for_status();raw=response.content;break
                except Exception:
                    if attempt==2:raise
            source='public_pinned_download'
        assert len(raw)==r['bytes'] and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob_sha']
        if not p.exists():p.write_bytes(raw)
        return dict(r,status='downloaded',sha256=hashlib.sha256(raw).hexdigest(),acquisition=source)
    except Exception as ex:return dict(r,status='failed',error=str(ex))
out=[];start=time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for r in pool.map(acquire,records):
        out.append(r)
        if len(out)%150==0:print('User-group corpus',len(out),'/',len(records),flush=True)
(DEST/'download_manifest.json').write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
print(json.dumps(dict(records=len(out),successful=sum(r['status']=='downloaded' for r in out),bytes=sum(r['bytes'] for r in out if r['status']=='downloaded'),elapsed_seconds=time.perf_counter()-start)),flush=True)
