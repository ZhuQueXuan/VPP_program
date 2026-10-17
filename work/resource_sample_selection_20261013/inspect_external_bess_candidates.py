"""Read small first-party evidence files. Never train or overwrite downloads."""
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile
import io
import argparse
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--receipt-id', required=True)
args = parser.parse_args()
if not args.receipt_id.isidentifier():
    raise ValueError('receipt-id must be a simple identifier')
DEST = ROOT / 'downloads' / 'independent_candidates_20261013'
DEST.mkdir(parents=True, exist_ok=True)
receipt = DEST / f'{args.receipt_id}.json'
if receipt.exists():
    raise FileExistsError(receipt)
SOURCES = {
    'ppl_repo.json': ('https://api.github.com/repos/PPLResearch/BESS-Analysis', 2_000_000),
    'ppl_main_commit.json': ('https://api.github.com/repos/PPLResearch/BESS-Analysis/commits/main', 2_000_000),
    'ppl_ESS_2017.csv': ('https://media.githubusercontent.com/media/PPLResearch/BESS-Analysis/refs/heads/main/ESS_2017.csv', 12_000_000),
    'rwth_home_metadata.zip': ('https://zenodo.org/api/records/12091223/files/Metadata_and_Code.zip/content', 100_000),
    'rwth_home_record.json': ('https://zenodo.org/api/records/12091223', 2_000_000),
    'schaeffer_readme.md': ('https://zenodo.org/api/records/13715694/files/README.md/content', 100_000),
    'schaeffer_record.json': ('https://zenodo.org/api/records/13715694', 2_000_000),
}
receipts = []
for name, (url, cap) in SOURCES.items():
    path = DEST / name
    record = {'file': name, 'requested_url': url, 'utc': datetime.now(timezone.utc).isoformat()}
    try:
        if path.exists():
            raw = path.read_bytes()
            record['acquisition'] = 'existing file, not redownloaded'
        else:
            req = urllib.request.Request(url, headers={'User-Agent': 'VPP-research-source-audit/1.0'})
            with urllib.request.urlopen(req, timeout=20) as response:
                record.update(final_url=response.url, content_type=response.headers.get('Content-Type'))
                raw = response.read(cap + 1)
            if len(raw) > cap:
                raise ValueError('response exceeds evidence-file limit')
            if raw.lstrip().lower().startswith((b'<!doctype html', b'<html')):
                raise ValueError('HTML returned instead of evidence file')
            with path.open('xb') as handle:
                handle.write(raw)
        record.update(status='downloaded', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if name.endswith('.json'):
            payload = json.loads(raw)
            if name == 'ppl_repo.json':
                record['summary'] = {k: payload.get(k) for k in ('full_name','description','license','default_branch','pushed_at')}
            elif name == 'ppl_main_commit.json':
                record['summary'] = {'sha': payload.get('sha'), 'date': payload.get('commit', {}).get('committer', {}).get('date')}
            else:
                record['summary'] = {k: payload.get('metadata', {}).get(k) for k in ('title', 'license', 'doi', 'version')}
        elif name.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                record['members'] = [{'name': i.filename, 'bytes': i.file_size} for i in archive.infolist()]
        elif name.endswith('.csv'):
            record['header_preview'] = raw.decode('utf-8-sig').splitlines()[:4]
        else:
            record['text'] = raw.decode('utf-8-sig')
    except Exception as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    receipts.append(record)
    print(json.dumps(record, ensure_ascii=False))
with receipt.open('x', encoding='utf-8') as handle:
    json.dump(receipts, handle, ensure_ascii=False, indent=2)
