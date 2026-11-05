from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];folder=ROOT/'data/public_datasets/瑞士_EPFL_三级充电站';out={}
for fn in ['Session_data.xlsx','Measurement_data.xlsx']:
    p=folder/fn;book=pd.ExcelFile(p);tables={}
    for sheet in book.sheet_names:
        df=pd.read_excel(book,sheet_name=sheet);item=dict(rows=len(df),columns=[str(v) for v in df.columns],nonnull={str(k):int(v) for k,v in df.notna().sum().items()})
        for k in df.columns:
            if str(k).lower() in ['id','session','sessionid','session_id','ctrl_s','ctrl_t','controlled','ev','ev_id']:
                item.setdefault('group_fields',{})[str(k)]=dict(unique=int(df[k].nunique()),counts={str(a):int(b) for a,b in df[k].value_counts().head(8).items()})
        tables[str(sheet)]=item
        print(fn,sheet,len(df),list(df.columns),flush=True)
    out[fn]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),sheets=tables)
(HERE/'epfl_inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
