"""Aggregate research evidence and verify preserved file identities; no fits."""
from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


structure = read(HERE/'structure_sources.json')
derivative = read(HERE/'derivative_sources.json')
feasibility = read(HERE/'data_feasibility.json')
micro = read(HERE/'method_microcheck.json')
design = read(HERE/'research_design.json')
primary = read(HERE/'primary_sources/source_receipt.json')
sources = dict(review_local_date='2026-11-03', coverage='targeted primary-source review, not exhaustive',
               structure=structure['sources'], derivative=derivative['sources'],
               data_primary_sources=feasibility['datasets'],
               frozen_author_source=primary)
with (HERE/'sources.json').open('x', encoding='utf-8') as stream:
    json.dump(sources, stream, ensure_ascii=False, indent=2)

for record in primary['files']:
    assert sha(HERE/'primary_sources'/record['path']) == record['sha256'], record['path']
assert sha(HERE/'method_microcheck.py') == micro['script_sha256']
old = read(ROOT/'work/b1_continuous_dml_pilot_20261103/freeze.json')['files']
changed = [name for name, expected in old.items() if sha(ROOT/name) != expected]
assert not changed, changed
for name in ['structure_sources.json', 'derivative_sources.json', 'data_feasibility.json',
             'method_microcheck.json', 'research_design.json', 'sources.json']:
    read(HERE/name)

receipt = dict(
    completed_utc=datetime.now(timezone.utc).isoformat(),
    status='literature_code_data_review_and_mathematical_feasibility_complete',
    research_scope='factors, nonlinear marginal effects, sensitivity and target crossings within B1 research point1',
    source_groups=dict(structure=len(structure['sources']), derivative=len(derivative['sources']),
                       data=len(feasibility['datasets'])),
    original_author_files_verified=len(primary['files']),
    old_frozen_files_unchanged=len(old),
    old_formal_B1_files_unchanged=sum(name.startswith('B1算法/') for name in old),
    main_research_fits=0, mathematical_random_check_arrays=97,
    main_evaluation_cohorts_generated=0, consumed_tests_reopened=False,
    independent_formula_review='derivative_threshold_research: verified Eq8, kernel support, integral outside-window beta contribution and observational-equivalence example',
    microcheck_status=micro['status'],
    microcheck_clarifications=[
        '97 random check arrays use uniform density; nonuniform density is verified in the analytic quadrature block',
        'experimental_sample_generation=false in the microcheck means no research evaluation cohort; random numerical arrays are present',
        'exact recovery with a flat misspecified mean is a quadratic special-case identity, not generic finite-sample DR performance',
    ],
    chosen_research_route=design['method_decisions'],
    adoption='current continuous DR retained; no production method or parameters changed',
    full_graph_and_derivative_experiment_executed=False,
    real_data_effects_validated=False, full_uniform_coverage_validated=False,
    dependencies_installed=False, downloaded_code_training_executed=False,
    no_files_deleted=True, no_upload_or_commit=True,
    local_failed_operations=[
        'Initial public GitHub socket download denied by sandbox10013; auto-reviewed escalated public-source download succeeded',
        'First multi-file documentation patch context failed atomically; corrected exact headings then applied; no deletion or algorithm edit',
    ],
    documentation_updated=[
        'AGENTS.md', 'docs/DECISION_LOG.md', 'docs/DATA_CARD.md', 'docs/EXPERIMENT_LOG.md',
        'outputs/ROADMAP_v2.md', 'outputs/第一阶段两周执行计划_v2_20261013.md', '项目文件索引.md',
        '.review/2026-11-03-factors-nonlinearity.md',
    ],
    artifacts_sha256={str(path.relative_to(HERE)).replace('\\','/'): sha(path)
                      for path in HERE.rglob('*') if path.is_file() and path.name != 'completion_receipt.json'},
)
with (HERE/'completion_receipt.json').open('x', encoding='utf-8') as stream:
    json.dump(receipt, stream, ensure_ascii=False, indent=2)
print(json.dumps(dict(status=receipt['status'], source_groups=receipt['source_groups'],
                      prior_frozen_verified=len(old), formal_verified=receipt['old_formal_B1_files_unchanged'],
                      fits=0, mathematical_microcheck=receipt['microcheck_status']), ensure_ascii=False))
