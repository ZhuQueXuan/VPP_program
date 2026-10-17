"""Bounded acquisition of public PVDAQ index/metadata listing; no model fitting."""
from pathlib import Path
import argparse
import csv
import datetime
import hashlib
import io
import json
import urllib.request
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parent
OUT=BASE/'downloads'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    args=parser.parse_args()
    target=OUT/args.attempt
    target.mkdir(parents=True,exist_ok=False)
    urls={
        'systems.csv':'https://oedi-data-lake.s3.amazonaws.com/pvdaq/csv/systems_20250729.csv',
        'metadata_listing.xml':'https://oedi-data-lake.s3.amazonaws.com/?list-type=2&prefix=pvdaq%2Fcsv%2F&max-keys=100',
        'official_documentation.md':'https://raw.githubusercontent.com/openEDI/documentation/main/pvdaq.md'
    }
    receipt={'attempt':args.attempt,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':[]}
    for name,url in urls.items():
        record={'file':name,'url':url}
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'VPP-PV-research-source-check'})
            with urllib.request.urlopen(req,timeout=35) as response:
                data=response.read(5_000_001)
                record.update(http_status=response.status,content_type=response.headers.get('Content-Type'))
            if len(data)>5_000_000:raise ValueError('Declared 5 MB limit exceeded')
            (target/name).write_bytes(data)
            record.update(status='downloaded',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
            if name=='systems.csv':
                rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
                record['columns']=list(rows[0]) if rows else []
                record['rows']=len(rows)
                (target/'system_records.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
            if name=='metadata_listing.xml':
                ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
                xml=ET.fromstring(data)
                record['objects']=[{'key':x.findtext('s:Key',namespaces=ns),'bytes':int(x.findtext('s:Size',namespaces=ns))} for x in xml.findall('s:Contents',ns)]
                record['is_truncated']=xml.findtext('s:IsTruncated',namespaces=ns)
        except Exception as error:
            record.update(status='failed',error=repr(error))
        receipt['files'].append(record)
    (target/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(receipt,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
