"""Read saved new-study graphs and score observed skeletons; never refit.

For these explicitly generated SCMs, hidden H is common to A and Y and their
adjacency is already present. Only skeleton and negative-control truths are
scored; discovered endpoints are described, not scored against the full DAG.
"""
from pathlib import Path
import json
import hashlib
from collections import defaultdict
from statistics import mean

HERE = Path(__file__).resolve().parent
LABELS = {'deadline_slack': '期限余量', 'demand_urgency': '需求紧迫度',
          'negative_control': '无关对照因素', 'offered_incentive': '事前补偿',
          'cumulative_response_seconds': '累计响应时长'}
L, U, N, A, Y = LABELS


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def edge_set(edges):
    return {frozenset(e) for e in edges}


def expected_skeleton(kind):
    if kind not in {'randomized', 'zero_effect', 'observed_confounding',
                    'hidden_confounding', 'nonmonotone'}:
        raise ValueError('Unknown SCM: require explicit observed-skeleton oracle: '+kind)
    edges = [(L, Y), (U, Y)]
    if kind != 'randomized':
        edges += [(L, A), (U, A)]
    if kind != 'zero_effect':
        edges += [(A, Y)]
    return edge_set(edges)


def evaluate(graph, kind):
    if graph.get('status') != 'ok':
        return dict(status='unavailable', graph_status=graph.get('status'))
    edges = graph['edges']
    pred = edge_set((e['node1'], e['node2']) for e in edges)
    truth = expected_skeleton(kind)
    tp, fp, fn = len(pred & truth), len(pred-truth), len(truth-pred)
    names = graph['nodes']
    total_pairs = len(names)*(len(names)-1)//2
    endpoint_pairs = [(e['endpoint1'], e['endpoint2']) for e in edges]
    circle = sum(a == 'circle' for pair in endpoint_pairs for a in pair)
    undirected = sum(pair == ('tail', 'tail') for pair in endpoint_pairs)
    ambiguous = sum('circle' in pair or pair == ('tail', 'tail') for pair in endpoint_pairs)
    # N is independent of every other node in the generator, not merely null
    # conditional on an arbitrary fitted adjustment set.
    negative_edges = [e for e in edges if N in (e['node1'], e['node2'])]
    return dict(status='ok', graph_type=graph['graph_type'],
        true_adjacencies=tp, false_adjacencies=fp, missed_adjacencies=fn,
        true_nonedges=total_pairs-len(truth)-fp,
        predicted_adjacencies=len(pred), oracle_adjacencies=len(truth),
        adjacency_precision=tp/len(pred) if pred else None,
        adjacency_recall=tp/len(truth),
        negative_control_false_edges=len(negative_edges),
        negative_control_edge_opportunities=len(names)-1,
        circle_endpoints=circle, undirected_tail_tail_edges=undirected,
        unresolved_edge_count=ambiguous,
        fully_directed_edges=sum(set(pair) == {'tail', 'arrow'} for pair in endpoint_pairs),
        bidirected_edges=sum(pair == ('arrow', 'arrow') for pair in endpoint_pairs),
        endpoint_accuracy=None, hidden_confounder_detection_accuracy=None,
        endpoint_scoring_reason='No complete equivalence-class endpoint oracle asserted; no comparison to directed full SCM',
        display_edges=[dict(left=LABELS[e['node1']], right=LABELS[e['node2']],
                            left_endpoint=e['endpoint1'], right_endpoint=e['endpoint2']) for e in edges])


def main():
    rows = []
    hashes = {}
    skipped = []
    for stage in ['development', 'final']:
        folder = HERE/stage
        summary = folder/'summary.json'
        if not summary.exists():
            skipped.append(stage)
            continue
        stage_summary = read(summary)
        for entry in stage_summary['rows']:
            kind, seed = entry['mechanism'], entry['seed']
            path = folder/f'{seed}-{kind}'/'model.json'
            envelope = read(path)
            model = envelope.get('payload', envelope)
            hashes[str(path.relative_to(HERE)).replace('\\', '/')] = hashlib.sha256(path.read_bytes()).hexdigest()
            for method, graph in model['structure'].items():
                assert graph['automatic_adjustment_selection'] is False
                assert graph['temporal_constraints_applied'] is False
                assert len(graph['selected_event_indices']) == graph['selected_users']
                assert len(set(graph['selected_event_indices'])) == graph['selected_users']
                rows.append(dict(stage=stage, seed=seed, mechanism=kind, method=method,
                    independent_users=graph['independent_users'], selected_users=graph['selected_users'],
                    metrics=evaluate(graph, kind)))
    buckets = defaultdict(list)
    for row in rows:
        buckets[(row['stage'], row['method'])].append(row)
    aggregate = []
    for (stage, method), entries in sorted(buckets.items()):
        scores = [r['metrics'] for r in entries if r['metrics']['status'] == 'ok']
        tp = sum(m['true_adjacencies'] for m in scores)
        fp = sum(m['false_adjacencies'] for m in scores)
        fn = sum(m['missed_adjacencies'] for m in scores)
        aggregate.append(dict(stage=stage, method=method, cohort_count=len(entries),
            output_count=len(scores), micro_adjacency_precision=tp/(tp+fp) if tp+fp else None,
            micro_adjacency_recall=tp/(tp+fn) if tp+fn else None,
            true_adjacencies=tp, false_adjacencies=fp, missed_adjacencies=fn,
            negative_control_false_edges=sum(m['negative_control_false_edges'] for m in scores),
            negative_control_opportunities=sum(m['negative_control_edge_opportunities'] for m in scores),
            unresolved_edges=sum(m['unresolved_edge_count'] for m in scores),
            total_predicted_edges=sum(m['predicted_adjacencies'] for m in scores)))
    output = dict(status='saved_graphs_evaluated_no_fit', rows=rows, aggregate=aggregate,
        skipped_incomplete_stages=skipped, local_labels=LABELS,
        scoring_scope='observed-skeleton adjacency and known-independent N only; endpoints described not assigned DAG accuracy',
        scm_evidence='data.py mean_parts and generate; normalized L/U affect both participation and positive-time mean; no N outcome/assignment dependence',
        interpretation='Mediating mixture components do not make graph attribution separately identified willingness or causal contribution fractions',
        temporal_knowledge_note='tiers shown beside graph; not imposed through strong forbidden-edge background knowledge',
        source_models_sha256=hashes,
        evaluator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (HERE/'structure_evaluation.json').open('x', encoding='utf-8') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(status=output['status'], rows=len(rows), aggregate=aggregate,
                          skipped=skipped), ensure_ascii=False))


if __name__ == '__main__':
    main()
