from pathlib import Path
from html.parser import HTMLParser
import requests,json,hashlib,time
HERE=Path(__file__).resolve().parent
class Form(HTMLParser):
    def __init__(self):super().__init__();self.token=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input' and a.get('name')=='csrf_token':self.token=a.get('value')
out=[]
for site in ['Caltech','Office 1']:
  for year in [2018,2019,2020]:
    p=HERE/'source_documents'/('acn_official_'+site.replace(' ','_')+'_'+str(year)+'.json')
    try:
        if p.exists():raw=p.read_bytes();value=json.loads(raw)
        else:
            session=requests.Session();page=session.get('https://ev.caltech.edu/dataset.html',timeout=(10,20));page.raise_for_status();form=Form();form.feed(page.text);assert form.token
            query=dict(csrf_token=form.token,site=site,start=f'01/01/{year} 12:00 AM',end=f'01/01/{year+1} 12:00 AM',min_kWh='0',submit='Download')
            response=session.post('https://ev.caltech.edu/dataset.html',data=query,timeout=(15,60));response.raise_for_status();value=response.json();raw=response.content;p.write_bytes(raw)
        rows=value.get('_items',[]) if isinstance(value,dict) else value;assert isinstance(rows,list)
        assert not any('chargingCurrent' in r or 'pilotSignal' in r for r in rows),'metadata only; no heldout observation access'
        out.append(dict(site=site,year=year,path=p.relative_to(HERE).as_posix(),records=len(rows),users=sum(bool(r.get('userID')) for r in rows),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),status='downloaded'))
        print(site,year,len(rows),'metadata sessions',flush=True)
    except Exception as ex:out.append(dict(site=site,year=year,status='failed',error=str(ex)));print(site,year,type(ex).__name__,flush=True)
(HERE/'official_metadata_manifest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
