from pathlib import Path
import urllib.request,json,time,hashlib
HERE=Path(__file__).resolve().parent
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'VPP-public-data-research','Accept':'application/json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=45) as r:return r.read()
        except Exception as ex:
            if attempt==2:raise
            print('retry',attempt+1,type(ex).__name__,url.split('?')[0][-65:],flush=True);time.sleep(attempt+1)
def save(name,url):
    p=HERE/name
    if p.exists():return json.loads(p.read_text(encoding='utf-8'))
    raw=get(url);obj=json.loads(raw);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');print(name,len(raw),flush=True);return obj
if __name__=='__main__':
    repo=json.loads((HERE/'acn_repository.json').read_text(encoding='utf-8'))
    branch=save('acn_branch.json','https://api.github.com/repos/tongxin-li/ACN-Data-Static/branches/'+repo['default_branch'])
    tree=save('acn_tree.json','https://api.github.com/repos/tongxin-li/ACN-Data-Static/git/trees/'+branch['commit']['sha']+'?recursive=1')
    files=[x for x in tree['tree'] if x['type']=='blob' and x['path'].endswith('.csv.gz')]
    print('ACN actual tree',dict(truncated=tree.get('truncated'),files=len(files),bytes=sum(x.get('size',0) for x in files)),flush=True)
    for name,url in [('osf_node.json','https://api.osf.io/v2/nodes/94gkc/'),('osf_files.json','https://api.osf.io/v2/nodes/94gkc/files/osfstorage/?page[size]=100')]:
        try:save(name,url)
        except Exception as ex:(HERE/(name+'.error.json')).write_text(json.dumps(dict(url=url,error=str(ex))),encoding='utf-8');print(name,type(ex).__name__,flush=True)
