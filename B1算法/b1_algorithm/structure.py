"""Nonlinear event-level structure discovery through causal-learn PC/FCI.

Outputs equivalence-class endpoints; never selects adjustment factors or
replaces the declared scientific study graph automatically.
"""
from __future__ import annotations

import contextlib
import io
from importlib.metadata import version
import numpy as np
from .effects.validation import numeric_array, user_ids


def discover_factor_structure(X, users, names, *, method="fci_kci", alpha=.05,
                              max_users=None, seed=0, time_tiers=None):
    """Use the first supplied event per user to learn a PAG or CPDAG.

    ``time_tiers`` records scientific chronology only. It is deliberately not
    passed as forbidden edges: FCI background-knowledge orientation may impose
    stronger endpoint assumptions than chronology alone.
    """
    x = numeric_array(X, "X", 2)
    groups = user_ids(users)
    names = list(names)
    if len(groups) != len(x) or len(names) != x.shape[1]:
        raise ValueError("matching rows/users and one name per variable required")
    if len(set(names)) != len(names) or not all(isinstance(n, str) and n.strip() for n in names):
        raise ValueError("unique nonempty variable names required")
    if method not in ("fci_kci", "pc_kci"):
        raise ValueError("method must be fci_kci or pc_kci")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0,1)")
    _, first = np.unique(groups, return_index=True)
    first = np.sort(first)
    if max_users is not None:
        if not isinstance(max_users, int) or max_users < 30:
            raise ValueError("max_users must be an integer at least30")
        if len(first) > max_users:
            first = np.sort(np.random.default_rng(seed).choice(first, max_users, replace=False))
    if len(first) < 30:
        raise ValueError("at least30 independent users required for this discovery interface")
    sample = x[first]
    base = dict(schema_version="b1.structure.v1", method=method,
                requested_nodes=names, nodes=names, input_events=len(x),
                independent_users=len(set(groups)), selected_users=len(first),
                selected_event_indices=first.tolist(),
                independent_row_policy="first supplied event per user; optional fixed seeded user subset",
                conditional_independence_test="kernel KCI", alpha=float(alpha),
                time_tiers=time_tiers, temporal_constraints_applied=False,
                automatic_adjustment_selection=False,
                graph_truth_identified=False,
                causal_sufficiency_assumed=(method == "pc_kci"))
    constant = [names[j] for j in range(len(names)) if np.ptp(sample[:, j]) <= 1e-12]
    if constant:
        return dict(base, status="insufficient_variation", constant_nodes=constant,
                    graph_type=None, edges=None, endpoint_matrix=None)
    try:
        if method == "fci_kci":
            from causallearn.search.ConstraintBased.FCI import fci
        else:
            from causallearn.search.ConstraintBased.PC import pc
    except ImportError as exc:
        raise ImportError("Structure discovery requires causal-learn==0.1.4.8 and its dependencies") from exc
    # Kernel tests work on the supplied values; no jitter, positive-only filter
    # or representation of Y>0 as an unobserved willingness mediator.
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        if method == "fci_kci":
            graph, _ = fci(sample, independence_test_method="kci", alpha=alpha,
                           verbose=False, show_progress=False, background_knowledge=None)
        else:
            graph = pc(sample, alpha=alpha, indep_test="kci", stable=True,
                       show_progress=False, node_names=names).G
    lookup = {node: names[j] for j, node in enumerate(graph.get_nodes())}
    rows = []
    for edge in graph.get_graph_edges():
        a, b = edge.get_node1(), edge.get_node2()
        rows.append(dict(node1=lookup[a], node2=lookup[b],
                         endpoint1=edge.get_endpoint1().name.lower(),
                         endpoint2=edge.get_endpoint2().name.lower()))
    rows.sort(key=lambda row: (names.index(row["node1"]), names.index(row["node2"])))
    return dict(base, status="ok", graph_type="PAG" if method == "fci_kci" else "CPDAG",
                backend_version=version("causal-learn"), edges=rows,
                endpoint_matrix=np.asarray(graph.graph, int).tolist(),
                backend_log=log.getvalue(),
                interpretation="observational equivalence-class structure under CI/Markov/faithfulness assumptions; unresolved endpoints retained")


def skeleton_metrics(result, reference_edges):
    """Compare adjacency only; reference must describe the observed MAG/PAG.

    A latent DAG's direct-edge list is not generally its observed skeleton.
    Endpoints are not scored against a fully oriented DAG by this helper.
    """
    if result.get("status") != "ok":
        return dict(status="unavailable")
    predicted = {frozenset((e["node1"], e["node2"])) for e in result["edges"]}
    expected = {frozenset(edge) for edge in reference_edges}
    correct = len(predicted & expected)
    return dict(status="ok", adjacency_precision=correct/len(predicted) if predicted else None,
                adjacency_recall=correct/len(expected) if expected else None,
                true_adjacencies=correct, false_adjacencies=len(predicted-expected),
                missed_adjacencies=len(expected-predicted),
                endpoint_accuracy=None,
                comparison_scope="adjacency only; no forced orientation or DAG-to-PAG endpoint score")
