"""Fetch original WLTP workbook and provenance instructions, fixed source version."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/resource_sample_selection_20261013/downloads/blyth_ecm_20261015'
sha = json.loads((OUT / 'source_selection.json').read_text())['commit']
tree = {x['path']: x for x in json.loads((OUT / 'tree.json').read_text())['tree']}
receipt = []
for relative in ['research/lab_data/MLP001_wltp_25degC.xlsx', 'dodo.py', 'environment.yml']:
    dest = OUT / 'author' / relative
    if dest.exists():
        raise FileExistsError(dest)
    url = f'https://raw.githubusercontent.com/MarkBlyth/parameterisation_methodsx/{sha}/{relative}'
    with urllib.request.urlopen(url, timeout=55) as response:
        data = response.read(25_000_001)
    assert len(data) <= 25_000_000
    blob = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
    assert blob == tree[relative]['sha'] and len(data) == tree[relative]['size']
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    receipt.append({'path': relative, 'url': url, 'bytes': len(data), 'git_blob_sha1': blob, 'sha256': hashlib.sha256(data).hexdigest()})
(OUT / 'validation_download_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps({'files': len(receipt), 'bytes': sum(x['bytes'] for x in receipt)}))
