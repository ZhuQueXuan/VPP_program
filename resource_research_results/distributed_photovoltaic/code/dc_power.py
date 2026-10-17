"""Fixed-parameter module DC power reconstruction using a back-temperature proxy.

This is a component calculation. It does not forecast future weather, model an
inverter, identify an available AC limit, or determine controllable reserve.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class ModuleParameters:
    p0_W: float
    gamma_per_C: float
    reference_C: float = 25.0

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.p0_W,self.gamma_per_C,self.reference_C)) or self.p0_W<=0:
            raise ValueError('Module parameters must be finite and p0_W positive.')

def reconstruct_module_dc(poa_W_m2, back_temperature_C, parameters, deltaT_C_at_1000=0.0):
    """Return irradiance-only baseline and temperature-proxy corrected power (W).

    The default DeltaT=0 uses measured back temperature as a cell-temperature
    approximation. DeltaT=3 is only a published representative sensitivity.
    Parameters apply to the characterized module; supply measured parameters
    before transferring to another module. Total POA approximates effective
    irradiance. The function neither clips power to nameplate nor estimates
    angle, spectrum, soiling, sensor timing, or AC conversion losses.
    """
    if not all(math.isfinite(x) for x in (poa_W_m2,back_temperature_C,deltaT_C_at_1000)):
        raise ValueError('Inputs must be finite; no missing-value substitution.')
    if poa_W_m2<0 or deltaT_C_at_1000<0:
        raise ValueError('Irradiance and assumed cell/back gradient must be nonnegative.')
    cell_proxy_C=back_temperature_C+deltaT_C_at_1000*poa_W_m2/1000
    factor=1+parameters.gamma_per_C*(cell_proxy_C-parameters.reference_C)
    if factor<=0:
        raise ValueError('Temperature factor is outside the positive linear model domain.')
    baseline_W=parameters.p0_W*poa_W_m2/1000
    corrected_W=baseline_W*factor
    if not all(math.isfinite(x) for x in (cell_proxy_C,factor,baseline_W,corrected_W)):
        raise ValueError('Nonfinite model output; do not silently clip or replace it.')
    return {'irradiance_only_W':baseline_W,'temperature_corrected_W':corrected_W,
            'cell_temperature_proxy_C':cell_proxy_C,
            'outside_lab_GT_matrix_range':poa_W_m2<100 or poa_W_m2>1100 or back_temperature_C<15 or back_temperature_C>75,
            'status':'computed_with_back_temperature_proxy'}
