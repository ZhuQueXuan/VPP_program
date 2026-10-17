"""Download only one deflated CSV member using validated HTTP ranges."""
from pathlib import Path
import json, urllib.request, struct, zlib, hashlib

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'downloads'/'rwth_home_capacity_20261014'
RECEIPT=DEST/'selected_member_acquisition_01.json'
OUTPUT=DEST/'2017_06_System_ID_01.csv'
COMPRESSED=DEST/'2017_06_System_ID_01.deflate.bin'
if any(p.exists() for p in (RECEIPT,OUTPUT,COMPRESSED)):
    raise FileExistsError('selected member or receipt already exists; no overwrite')
evidence=json.loads((DEST/'method_acquisition_01.json').read_text('utf-8'))
member=next(i for i in evidence['system_01_zip_members'] if i['name']=='01/2017_06_System_ID_01.csv')
archive=evidence['remote_archive']
record={'selection':'lowest LMO/NMC system ID, earliest listed test; fixed before raw CSV inspection',
        'selected_test_start_local_unspecified':'2017-06-14 14:23:39','diagnostic_window':'2017-06-14 12:00:00 to 2017-06-15 12:00:00, half-open',
        'selection_not_blind':'published test values and index already inspected',
        'archive':archive,'member':member,'full_archive_checksum_verified':False}
def request_range(start,end):
    req=urllib.request.Request(archive['url'],headers={'User-Agent':'VPP-research-source-audit/1.0','Range':f'bytes={start}-{end}'})
    with urllib.request.urlopen(req,timeout=30) as response:
        if response.status!=206 or response.headers.get('Content-Range')!=f"bytes {start}-{end}/{archive['bytes']}":
            raise ValueError('range status/header mismatch; full ZIP download forbidden by this script')
        raw=response.read(end-start+2)
        if len(raw)!=end-start+1:
            raise ValueError('range size mismatch')
    return raw
try:
    header=request_range(member['header_offset'],member['header_offset']+29)
    fields=struct.unpack('<4s5H3L2H',header)
    signature,version,flags,method,mtime,mdate,crc,cs,us,fn,extra=fields
    if signature!=b'PK\x03\x04' or flags&1 or method!=8 or method!=member['compression']:
        raise ValueError('unsupported/encrypted/local header mismatch')
    names=request_range(member['header_offset']+30,member['header_offset']+29+fn+extra)
    encoding='utf-8' if flags&0x800 else 'cp437'
    if names[:fn].decode(encoding)!=member['name']:
        raise ValueError('local filename mismatch')
    if not flags&8 and (crc!=int(member['crc32'],16) or cs!=member['compressed_bytes'] or us!=member['bytes']):
        raise ValueError('local sizes/CRC do not match central directory')
    if member['compressed_bytes']>20_000_000 or member['bytes']>200_000_000:
        raise ValueError('selected member exceeds explicit size cap')
    start=member['header_offset']+30+fn+extra
    raw=request_range(start,start+member['compressed_bytes']-1)
    COMPRESSED.open('xb').write(raw)
    decoder=zlib.decompressobj(-15)
    crc_value=0; digest=hashlib.sha256(); count=0
    with OUTPUT.open('xb') as handle:
        for offset in range(0,len(raw),65536):
            decoded=decoder.decompress(raw[offset:offset+65536])
            handle.write(decoded); count+=len(decoded); crc_value=zlib.crc32(decoded,crc_value); digest.update(decoded)
        decoded=decoder.flush()
        handle.write(decoded); count+=len(decoded); crc_value=zlib.crc32(decoded,crc_value); digest.update(decoded)
    if not decoder.eof or decoder.unused_data or count!=member['bytes'] or f'{crc_value:08x}'!=member['crc32']:
        raise ValueError('decompressed length/CRC/stream end mismatch; output not admitted')
    record.update(status='member_acquired_crc_verified',csv_bytes=count,csv_sha256=digest.hexdigest(),csv_crc32=f'{crc_value:08x}',
                  compressed_sha256=hashlib.sha256(raw).hexdigest(),selected_range=f'bytes {start}-{start+len(raw)-1}',
                  downloaded_payload_bytes=30+len(names)+len(raw))
except Exception as exc:
    record.update(status='failed_not_admitted',error=f'{type(exc).__name__}: {exc}')
RECEIPT.open('x',encoding='utf-8').write(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in record.items() if k not in ('archive','member')},ensure_ascii=False))
