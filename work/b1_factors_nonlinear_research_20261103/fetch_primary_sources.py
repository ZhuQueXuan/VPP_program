"""Download public author source files for static research inspection only."""
from pathlib import Path
import json
import hashlib
import urllib.request

OUT = Path(__file__).resolve().parent / 'primary_sources'
OUT.mkdir(parents=True, exist_ok=True)


def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'VPP-method-research', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


repo = 'zhangyk8/npDoseResponse'
commit = json.loads(get(f'https://api.github.com/repos/{repo}/commits?until=2026-11-03T15:59:59Z&per_page=1'))[0]
revision = commit['sha']
tree = json.loads(get(f'https://api.github.com/repos/{repo}/git/trees/{revision}?recursive=1'))
assert not tree.get('truncated')
selected = [r['path'] for r in tree['tree'] if r['type'] == 'blob' and
            (r['path'] in ['LICENSE', 'README.md', 'setup.py'] or
             (r['path'].startswith('npDoseResponse/') and r['path'].endswith('.py')))]
files = []
for name in selected:
    url = f'https://raw.githubusercontent.com/{repo}/{revision}/{name}'
    data = get(url)
    target = OUT / 'npDoseResponse' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(data)
    files.append(dict(path=str(target.relative_to(OUT)), url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
manifest = dict(repository=repo, revision=revision, date=commit['commit']['committer']['date'],
                activity_checked_through='2026-11-03', files=files, downloaded_code_executed=False)
with (OUT / 'source_receipt.json').open('x', encoding='utf-8') as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
print(json.dumps(dict(repository=repo, revision=revision, date=manifest['date'], downloaded_files=len(files),
                      bytes=sum(r['bytes'] for r in files))))
