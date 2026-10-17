"""Bounded read-only retrieval of public author repository metadata."""
from pathlib import Path
import datetime
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/resource_sample_selection_20261013/downloads/blyth_ecm_20261015'
OUT.mkdir(parents=True, exist_ok=True)

def fetch(url, name, limit=5_000_000):
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    req = urllib.request.Request(url, headers={'User-Agent': 'VPP-research-source-check'})
    with urllib.request.urlopen(req, timeout=40) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Download exceeds declared byte limit')
    path.write_bytes(data)
    return data

commit = json.loads(fetch('https://api.github.com/repos/MarkBlyth/parameterisation_methodsx/commits/main', 'commit.json'))
sha = commit['sha']
tree = json.loads(fetch(f'https://api.github.com/repos/MarkBlyth/parameterisation_methodsx/git/trees/{sha}?recursive=1', 'tree.json'))
interesting = [x for x in tree['tree'] if any(s in x['path'].lower() for s in ['wltp', 'model.py', 'model_demo', 'mlp001_params', 'mlp001_ocv', 'readme', 'license', 'preprocess', 'convert'])]
receipt = {'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'commit': sha,
           'commit_date': commit['commit']['committer']['date'], 'truncated': tree['truncated'], 'selected_tree': interesting}
(OUT / 'source_selection.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2))
