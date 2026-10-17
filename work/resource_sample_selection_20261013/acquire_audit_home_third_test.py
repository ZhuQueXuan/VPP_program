"""Acquire only the two frozen ZIP members and audit native monthly records."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, struct, urllib.request, zlib
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser(); pa.add_argument('--attempt',required=True); args=pa.parse_args()
if not args.attempt.isidentifier(): raise ValueError('simple ID required')
pf=ROOT/'home_capacity_crossperiod_protocol_v3.json'; p=json.loads(pf.read_text('utf-8'))
DEST=ROOT/p['source']['relative_directory']; out=DEST/f'acquisition_{args.attempt}.json'
if out.exists(): raise FileExistsError(out)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
assert json.loads((DEST/'freeze_receipt_01.json').read_text('utf-8'))['new_protocol_sha256']==hashlib.sha256(json.dumps(p,ensure_ascii=False,indent=2).encode()).hexdigest()
report={'protocol_sha256':sha(pf),'started_at_utc':datetime.now(timezone.utc).isoformat(),'members':[],'requests':[],'full_archive_checksum_verified':False}
archive=p['source']['archive']
def fetch(a,b):
    req=urllib.request.Request(archive['url'],headers={'User-Agent':'VPP-research-source-audit/1.0','Range':f'bytes={a}-{b}'})
    with urllib.request.urlopen(req,timeout=45) as r:
        if r.status!=206 or r.headers.get('Content-Range')!=f"bytes {a}-{b}/{archive['bytes']}": raise ValueError('Range mismatch')
        raw=r.read(b-a+2)
        if len(raw)!=b-a+1: raise ValueError('Range length mismatch')
        report['requests'].append({'start':a,'end':b,'status':r.status,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        return raw
try:
    for member in p['source']['members']:
        target=DEST/Path(member['name']).name
        if target.exists(): raise FileExistsError('member already exists: no silent reuse')
        fields=struct.unpack('<4s5H3L2H',fetch(member['header_offset'],member['header_offset']+29))
        signature,version,flags,method,mtime,mdate,crc,cs,us,fn,extra=fields
        if signature!=b'PK\x03\x04' or flags&1 or method!=8: raise ValueError('unsupported local header')
        name=fetch(member['header_offset']+30,member['header_offset']+29+fn+extra)
        if name[:fn].decode('utf-8' if flags&0x800 else 'cp437')!=member['name']: raise ValueError('filename mismatch')
        if not flags&8 and (crc!=int(member['crc32'],16) or cs!=member['compressed_bytes'] or us!=member['bytes']): raise ValueError('size/CRC header mismatch')
        if member['compressed_bytes']>20000000 or member['bytes']>200000000: raise ValueError('size cap')
        offset=member['header_offset']+30+fn+extra
        raw=fetch(offset,offset+member['compressed_bytes']-1)
        decoder=zlib.decompressobj(-15); count=0; crcval=0; digest=hashlib.sha256()
        with target.open('xb') as h:
            for pos in range(0,len(raw),65536):
                b=decoder.decompress(raw[pos:pos+65536]); h.write(b); count+=len(b); crcval=zlib.crc32(b,crcval); digest.update(b)
            b=decoder.flush(); h.write(b); count+=len(b); crcval=zlib.crc32(b,crcval); digest.update(b)
        if not decoder.eof or decoder.unused_data or count!=member['bytes'] or f'{crcval:08x}'!=member['crc32']: raise ValueError('CRC/length/stream mismatch')
        report['members'].append({'path':target.relative_to(ROOT).as_posix(),'bytes':count,'crc32':f'{crcval:08x}','sha256':digest.hexdigest()})
        print(json.dumps(report['members'][-1]),flush=True)
    report['status']='acquired_crc_verified'
except Exception as e:
    report.update(status='failed_not_admitted',error=f'{type(e).__name__}: {e}')
out.open('x',encoding='utf-8').write(json.dumps(report,ensure_ascii=False,indent=2))
if report['status']!='acquired_crc_verified': raise RuntimeError(report['error'])

columns=['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C']
start=pd.Timestamp(p['information']['history_start_inclusive']); cutoff=pd.Timestamp(p['information']['history_end_exclusive'])
ds=pd.Timestamp(p['information']['diagnostic_window_start']); de=pd.Timestamp(p['information']['diagnostic_window_end_exclusive'])
quality=[]; history_count=history_bad=history_interpolated=history_invalid_flags=history_bad_steps=0; history_first=history_last=None; previous=history_previous=None
for item in report['members']:
    rows=missing=nonfinite=interpolated=bad_step=bad_flag=0; first=last=None; minimum={}; maximum={}; diagnostic_rows=diagnostic_interpolated=test_matches=0
    for f in pd.read_csv(ROOT/item['path'],chunksize=250000):
        if list(f.columns)!=['Time',*columns,'Interpolated']: raise ValueError('schema mismatch')
        t=pd.to_datetime(f['Time'],format='%d-%b-%Y %H:%M:%S',errors='raise')
        seconds=t.to_numpy(dtype='datetime64[s]').astype(np.int64)
        bad_step+=int(np.count_nonzero(np.diff(seconds)!=1))
        if previous is not None: bad_step+=int(t.iloc[0] != previous+pd.Timedelta(seconds=1))
        previous=t.iloc[-1]
        numeric=f[columns].to_numpy(dtype=float); finite=np.isfinite(numeric).all(axis=1)
        missing+=int(f.isna().sum().sum()); nonfinite+=int((~finite).sum()); interpolated+=int((f['Interpolated']==1).sum()); bad_flag+=int((~f['Interpolated'].isin([0,1])).sum())
        if first is None: first=str(t.iloc[0])
        last=str(t.iloc[-1]); rows+=len(f)
        for c in columns:
            minimum[c]=min(minimum.get(c,float('inf')),float(f[c].min())); maximum[c]=max(maximum.get(c,float('-inf')),float(f[c].max()))
        mask=(t>=start)&(t<cutoff); n=int(mask.sum()); history_count+=n
        if n:
            subset=t[mask]
            if history_first is None: history_first=str(subset.iloc[0])
            history_last=str(subset.iloc[-1])
            st=subset.to_numpy(dtype='datetime64[s]').astype(np.int64)
            history_bad_steps+=int(np.count_nonzero(np.diff(st)!=1))
            if history_previous is not None: history_bad_steps+=int(subset.iloc[0]!=history_previous+pd.Timedelta(seconds=1))
            history_previous=subset.iloc[-1]
            history_invalid_flags+=int((~f.loc[mask,'Interpolated'].isin([0,1])).sum())
            history_bad+=int((~finite[mask.to_numpy()]).sum()); history_interpolated+=int((f.loc[mask,'Interpolated']==1).sum())
        diag=(t>=ds)&(t<de); diagnostic_rows+=int(diag.sum()); diagnostic_interpolated+=int((f.loc[diag,'Interpolated']==1).sum())
        test_matches+=int((t==pd.Timestamp(p['reference']['test_start_native'])).sum())
    quality.append({'path':item['path'],'rows':rows,'first':first,'last':last,'missing_cells':missing,'nonfinite_rows':nonfinite,'interpolated_rows':interpolated,'invalid_flags':bad_flag,'nonsecond_steps_including_month_join':bad_step,'min':minimum,'max':maximum,'diagnostic_rows':diagnostic_rows,'diagnostic_interpolated':diagnostic_interpolated,'test_start_matches':test_matches})
expected=p['information']['history_duration_seconds']
admitted=history_count==expected and history_first==str(start) and history_last==str(cutoff-pd.Timedelta(seconds=1)) and history_bad==history_invalid_flags==history_bad_steps==0
admission={'status':'admitted_frozen_history_proxy_only' if admitted else 'raw_history_not_admitted','protocol_sha256':sha(pf),'source_members':report['members'],'monthly_quality':quality,
    'history_rows':history_count,'history_first':history_first,'history_last':history_last,'history_nonfinite_rows':history_bad,'history_interpolated_rows':history_interpolated,'history_nonsecond_steps':history_bad_steps,'history_invalid_flags':history_invalid_flags,
    'note':'interpolated rows retained, break rest and disqualify spans; do not reject target event for unavailable proxy','scope':'native quality and one retrospective controlled-test proxy, no SOC or VPP maximum validation','full_archive_checksum_verified':False,
    'python':__import__('sys').version,'pandas':pd.__version__,'numpy':np.__version__}
(DEST/p['source']['admission_receipt']).open('x',encoding='utf-8').write(json.dumps(admission,ensure_ascii=False,indent=2,allow_nan=False))
print(json.dumps(admission,ensure_ascii=False),flush=True)
if not admitted: print('Frozen event retained: historical proxy unavailable; evaluate metadata-only baselines without resampling.',flush=True)
