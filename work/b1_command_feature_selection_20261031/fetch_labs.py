"""Download a fixed public author repository for inspection; never execute it."""
import json,urllib.request,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent/'vendor'/'LABS'
BASE.mkdir(parents=True,exist_ok=True)
URL='https://api.github.com/repos/pfryz/LABS'
def fetch(url,name):
    request=urllib.request.Request(url,headers={'User-Agent':'VPP-local-research'})
    with urllib.request.urlopen(request,timeout=25) as response:body=response.read()
    with (BASE/name).open('xb') as stream:stream.write(body)
    return body
repo=json.loads(fetch(URL,'repo_metadata.json'))
commit=json.loads(fetch(URL+'/commits/'+repo['default_branch'],'commit_metadata.json'))
sha=commit['sha'];manifest={}
for path in ['code/LABS_functions.R','LICENSE','CITATION.cff','README.md']:
    name=Path(path).name
    body=fetch('https://raw.githubusercontent.com/pfryz/LABS/'+sha+'/'+path,name)
    manifest[name]={'url':'https://raw.githubusercontent.com/pfryz/LABS/'+sha+'/'+path,
                    'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
result={'repository':URL,'default_branch':repo['default_branch'],'commit':sha,
        'commit_date':commit['commit']['committer']['date'],'pushed_at':repo['pushed_at'],
        'execution':False,'downloads':manifest}
with (BASE/'download_receipt.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='downloads'}))
