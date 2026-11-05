from pathlib import Path
from html.parser import HTMLParser
import requests,json
HERE=Path(__file__).resolve().parent
class Form(HTMLParser):
    def __init__(self):super().__init__();self.token=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input' and a.get('name')=='csrf_token':self.token=a.get('value')
out={}
try:
    session=requests.Session();page=session.get('https://ev.caltech.edu/dataset.html',timeout=(10,20));page.raise_for_status();form=Form();form.feed(page.text);assert form.token
    query=dict(csrf_token=form.token,site='Caltech',start='10/31/2019 12:00 AM',end='11/01/2019 12:00 AM',min_kWh='0',submit='Download')
    response=session.post('https://ev.caltech.edu/dataset.html',data=query,timeout=(15,45));response.raise_for_status();kind=response.headers.get('Content-Type','')
    if 'json' in kind or 'attachment' in response.headers.get('Content-Disposition',''):
        value=response.json();(HERE/'source_documents/acn_official_metadata_sample.json').write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        rows=value.get('_items',[]) if isinstance(value,dict) else value
        out=dict(status='downloaded',records=len(rows),type=kind,first_keys=list(rows[0]) if rows else [],has_user_id=sum(bool(r.get('userID')) for r in rows),has_vehicle_id=sum(bool(r.get('vehicleID') or r.get('vehicle')) for r in rows),time_series_present=any('chargingCurrent' in r for r in rows))
    else:
        (HERE/'source_documents/acn_official_metadata_sample_response.html').write_text(response.text,encoding='utf-8');out=dict(status='not_json',http_status=response.status_code,type=kind)
except Exception as ex:out=dict(status='failed',error=str(ex))
(HERE/'official_metadata_sample_receipt.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out),flush=True)
