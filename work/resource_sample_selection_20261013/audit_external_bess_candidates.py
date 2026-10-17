"""Purpose-specific source audit, no model fitting or target-derived filtering."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import urllib.request
import zipfile
from datetime import datetime

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'downloads' / 'independent_candidates_20261013'
receipt = DEST / 'field_audit_01.json'
if receipt.exists():
    raise FileExistsError(receipt)
source = DEST / 'ppl_ESS_2017.csv'
commit = json.loads((DEST / 'ppl_main_commit.json').read_text('utf-8'))['sha']
repo = json.loads((DEST / 'ppl_repo.json').read_text('utf-8'))
result = {'commit': commit, 'repo_license_api': repo.get('license'), 'raw_file_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
timestamps = []
modes = Counter()
missing = Counter()
with source.open('r', encoding='utf-8-sig', newline='') as handle:
    reader = csv.DictReader(handle)
    result['columns'] = reader.fieldnames
    for row in reader:
        timestamps.append(datetime.fromisoformat(row['Timestamp']))
        modes[row['Mode']] += 1
        missing.update(k for k, v in row.items() if v is None or v.strip().lower() in ('', 'na', 'nan', 'null'))
result.update(rows=len(timestamps), start=str(min(timestamps)), end=str(max(timestamps)),
              modes=dict(modes), missing_cells=dict(missing),
              duplicate_timestamps=len(timestamps)-len(set(timestamps)),
              adjacent_intervals_seconds=dict(Counter(int((b-a).total_seconds()) for a,b in zip(timestamps,timestamps[1:]))))
# Immutable Git LFS pointer establishes whether the downloaded main file matches the fixed commit.
for label, url, cap, partial in [
    ('ppl_2017_pointer', f'https://raw.githubusercontent.com/PPLResearch/BESS-Analysis/{commit}/ESS_2017.csv', 4096, False),
    ('ppl_2025_header', f'https://media.githubusercontent.com/media/PPLResearch/BESS-Analysis/{commit}/ESS_2025.csv', 8192, True),
]:
    entry = {'url': url, 'partial': partial}
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'VPP-research-source-audit/1.0'})
        if partial:
            request.add_header('Range', f'bytes=0-{cap-1}')
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(cap if partial else cap+1)
            entry.update(status=response.status, final_url=response.url, content_range=response.headers.get('Content-Range'))
        if raw.lstrip().lower().startswith((b'<html', b'<!doctype html')):
            raise ValueError('HTML challenge, not evidence')
        if not partial and len(raw)>cap:
            raise ValueError('pointer exceeds expected size')
        text = raw.decode('utf-8-sig')
        entry.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), lines=text.splitlines()[:4])
        with (DEST / (label + ('.partial.txt' if partial else '.txt'))).open('xb') as handle:
            handle.write(raw)
        if label.endswith('pointer'):
            oid = [line.split('sha256:',1)[1] for line in text.splitlines() if line.startswith('oid sha256:')]
            entry['download_matches_commit_lfs_oid'] = oid == [result['raw_file_sha256']]
    except Exception as exc:
        entry['error'] = f'{type(exc).__name__}: {exc}'
    result[label] = entry
for name in ('rwth_home_record.json', 'schaeffer_record.json'):
    path = DEST / name
    if path.exists():
        record = json.loads(path.read_text('utf-8'))
        result[name] = {'license': record.get('metadata', {}).get('license'), 'files': [(f['key'], f['size']) for f in record.get('files', [])]}
path = DEST / 'rwth_home_metadata.zip'
if path.exists():
    with zipfile.ZipFile(path) as archive:
        result['rwth_zip_crc_failure'] = archive.testzip()
        result['rwth_metadata_texts'] = {i.filename: archive.read(i).decode('utf-8', errors='replace') for i in archive.infolist() if i.filename.endswith(('.m','.txt','.csv')) and i.file_size<100000}
with receipt.open('x', encoding='utf-8') as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='rwth_metadata_texts'}, ensure_ascii=False))
