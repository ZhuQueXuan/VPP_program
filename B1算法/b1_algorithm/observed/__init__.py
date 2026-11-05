"""Inference-only access to the retained real-EV observation adapter."""
import json
from pathlib import Path
from ._recovery import infer


def analyze_observed_event(record, fitted_power_kw):
    """Use original observations and a supplied matching CPOP power curve.

    record['model_input'] contains relative_seconds, power_kw, current_a,
    and pilot_a. Time zero is the observed limit-change anchor.
    Outputs describe observed change/recovery, not physical curtailment duration.
    """
    models = Path(__file__).resolve().parent / 'models'
    event = json.loads((models / 'event.json').read_text(encoding='utf-8'))
    recovery = json.loads((models / 'recovery.json').read_text(encoding='utf-8'))
    return infer(record, fitted_power_kw, event, recovery)


__all__ = ['analyze_observed_event']
