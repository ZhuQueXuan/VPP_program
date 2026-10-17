"""Fetch selected author files at the recorded immutable commit; no execution."""
from pathlib import Path
import datetime
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/resource_sample_selection_20261013/downloads/blyth_ecm_20261015'
selection = json.loads((OUT / 'source_selection.json').read_text(encoding='utf-8'))
sha = selection['commit']
tree = json.loads((OUT / 'tree.json').read_text(encoding='utf-8'))
records = {x['path']: x for x in tree['tree']}
paths = ['LICENSE', 'README.md', 'research/scripts/model.py', 'try_me/model_demo.py',
         'research/scripts/plot_wltp_validation.py', 'research/processed_data/MLP001_params.csv',
         'research/processed_data/MLP001_ocv.csv', 'try_me/wltp.csv']
receipt = {'commit': sha, 'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': []}
for relative in paths:
    target = OUT / 'author' / relative
    if target.exists():
        raise FileExistsError(target)
    url = f'https://raw.githubusercontent.com/MarkBlyth/parameterisation_methodsx/{sha}/{relative}'
    req = urllib.request.Request(url, headers={'User-Agent': 'VPP-research-source-check'})
    with urllib.request.urlopen(req, timeout=40) as response:
        data = response.read(3_000_001)
    if len(data) > 3_000_000:
        raise ValueError('File exceeds 3 MB')
    blob_sha = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
    assert blob_sha == records[relative]['sha'], relative
    assert len(data) == records[relative]['size'], relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    receipt['files'].append({'path': relative, 'bytes': len(data), 'git_blob_sha1': blob_sha,
                             'sha256': hashlib.sha256(data).hexdigest(), 'url': url})
(OUT / 'download_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps({'commit': sha, 'files': len(paths), 'total_bytes': sum(x['bytes'] for x in receipt['files'])}))
