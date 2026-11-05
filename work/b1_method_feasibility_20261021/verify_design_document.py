"""Check B1 design artifact and existing model identities without simulation or fitting."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOC = HERE / 'B1总体方法设计与可行性论证_待审稿.md'


def main():
    content = DOC.read_text(encoding='utf-8')
    assert '\ufffd' not in content
    for required in ['Y_obs', 'Y_star', '二档', '不能定位激励轴的阈值',
                     'PC-stable', 'PELT', '尚未开展新实验', '不移入`01_项目依据/`',
                     '禁止把精确潜在交付量直接放训练表']:
        assert required in content, required
    assert {f'S{i}' for i in range(7)} <= set(re.findall(r'\bS[0-6]\b', content))
    links = []
    for path in [DOC, ROOT / '.review/2026-10-21-b1-method-feasibility.md']:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if target.startswith(('http://', 'https://', '#')):
                continue
            assert (path.parent / target.split('#', 1)[0]).resolve().exists(), (path, target)
            links.append(target)
    manifest = json.loads((ROOT / '资源能力模型/manifest.json').read_text(encoding='utf-8'))
    actual = {p.relative_to(ROOT / '资源能力模型').as_posix()
              for p in (ROOT / '资源能力模型').rglob('*') if p.is_file()}
    assert actual == set(manifest['files']) | {'manifest.json'}
    for relative, item in manifest['files'].items():
        raw = (ROOT / '资源能力模型' / relative).read_bytes()
        assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], relative
    for relative, digest in manifest['old_113_release_hashes'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest, relative
    assert not (ROOT / '01_项目依据/课题一四算法内容与输入输出规划_v1_20261021.md').exists()
    for relative in ['AGENTS.md', 'docs/DECISION_LOG.md', '项目文件索引.md',
                     'outputs/ROADMAP_v2.md', 'outputs/第一阶段两周执行计划_v2_20261013.md']:
        assert 'D105' in (ROOT / relative).read_text(encoding='utf-8')[:1400], relative
    assert (ROOT / 'docs/DECISION_LOG.md').read_text(encoding='utf-8').count('## D105｜') == 1
    result = {
        'status': 'passed', 'scope': 'design_documents_and_existing_identity_only',
        'document_sha256': hashlib.sha256(DOC.read_bytes()).hexdigest(),
        'local_links_checked': len(links), 'published_model_files': len(actual),
        'manifest_version': manifest['version'],
        'old_release_files_unchanged': len(manifest['old_113_release_hashes']),
        'new_simulated_samples': 0, 'model_runs': 0, 'training_runs': 0,
        'dependency_installs': 0, 'migrated_to_01': False,
        'design_status': 'awaiting_user_review',
    }
    (HERE / 'document_check.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
