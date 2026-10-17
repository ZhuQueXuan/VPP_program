"""Restricted static map, not a vehicle capacity or dispatch guarantee."""
import math
def predict_grid_power_kW(common_command_kW, fitted_breakpoint_kW):
    """Return min(command, calibration breakpoint) for nonnegative finite inputs.

    Requires verified equal commands on all three EVTEC fields in the source
    use case. No interface-state inference, physical capacity or timing model.
    """
    if not all(math.isfinite(v) and v>=0 for v in (common_command_kW,fitted_breakpoint_kW)):
        raise ValueError('Command and fitted breakpoint must be finite and nonnegative.')
    return min(common_command_kW,fitted_breakpoint_kW)
