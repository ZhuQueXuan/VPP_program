"""Formal integrated B1 algorithm. Versioned reference, process and effect modules."""
from .contracts import VERSION,provided_reference
from .api import analyze_event,analyze_events,estimate_event_effects

__version__=VERSION
__all__=['__version__','provided_reference','analyze_event','analyze_events','estimate_event_effects']
