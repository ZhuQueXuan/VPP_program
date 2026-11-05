"""Resource-specific analysis settings. Currently only single EV charging."""
from .ev import EVAnalysisConfig, assess_ev_recovery
__all__=['EVAnalysisConfig','assess_ev_recovery']
