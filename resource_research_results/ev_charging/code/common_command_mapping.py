"""Static common-command EVTEC grid-power research baseline; units kW.

The fitted breakpoint is a statistical mapping parameter. It is not a physical
maximum, a lower confidence bound, a capacity offer or a control instruction.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Calibration:
    fitted_breakpoint_kW: float
    minimum_training_command_kW: float
    maximum_training_command_kW: float

    def __post_init__(self):
        vals=(self.fitted_breakpoint_kW,self.minimum_training_command_kW,self.maximum_training_command_kW)
        if not all(math.isfinite(v) and v>=0 for v in vals):raise ValueError('Finite nonnegative calibration values required.')
        if self.minimum_training_command_kW>self.maximum_training_command_kW or self.fitted_breakpoint_kW>self.maximum_training_command_kW:
            raise ValueError('Calibration range or breakpoint inconsistent.')

def map_common_command(command_id2_kW,command_id3_kW,command_id4_kW,calibration):
    """Map equal current commands to a same-row grid-power estimate.

    Source chronology/continuity and complete-row availability are caller
    preconditions. State/connector codes are not interpreted or inferred.
    """
    commands=(command_id2_kW,command_id3_kW,command_id4_kW)
    if not all(math.isfinite(v) and v>=0 for v in commands):raise ValueError('Finite nonnegative commands required.')
    if not command_id2_kW==command_id3_kW==command_id4_kW:raise ValueError('Only exactly equal commands were admitted; no interface is guessed.')
    u=command_id2_kW
    return {'baseline_grid_kW':u,'estimated_grid_kW':min(u,calibration.fitted_breakpoint_kW),
            'outside_training_command_range':not calibration.minimum_training_command_kW<=u<=calibration.maximum_training_command_kW}
