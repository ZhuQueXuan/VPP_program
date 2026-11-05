from fetch_metadata import HERE,get
import json,hashlib
sources={
    'acn_snapshot_README.md':'https://raw.githubusercontent.com/tongxin-li/ACN-Data-Static/abb7cf15cc7108913e965d4375cc7270d532b65f/README.md',
    'dortmund_parameters.csv':'https://zenodo.org/records/14065331/files/parameters.csv?download=1',
    'dortmund_measurements.csv':'https://zenodo.org/records/14065331/files/measurements.csv?download=1',
    'osf_README.md':'https://osf.io/download/b6h8u/'
}
out=[]
for name,url in sources.items():
    try:
        p=HERE/'source_documents'/name;p.parent.mkdir(parents=True,exist_ok=True);raw=p.read_bytes() if p.exists() else get(url)
        if not p.exists():p.write_bytes(raw)
        out.append(dict(file=str(p.relative_to(HERE)),url=url,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()));print(name,len(raw),flush=True)
    except Exception as ex:out.append(dict(file=name,url=url,error=str(ex)))
(HERE/'supporting_sources.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
