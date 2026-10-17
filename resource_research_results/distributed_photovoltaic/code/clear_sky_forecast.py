"""Clear-sky POA ratio persistence for a conditional next-label forecast.

All future covariates here are astronomy and historical climatology. Actual
measurement arrival/averaging windows must be checked before online use.
"""
from dataclasses import dataclass
from zoneinfo import ZoneInfo
import math
import numpy as np
import pandas as pd
import pvlib

MODEL_SETTINGS={'solarposition_method':'nrel_numpy','standard_temperature_C':12.0,'delta_t_seconds':67.0,
                'clear_sky_model':'ineichen','linke_turbidity':'pvlib packaged climatology, daily interpolation',
                'transposition':'isotropic','albedo':0.25}

@dataclass(frozen=True)
class SiteGeometry:
    latitude: float
    longitude: float
    altitude_m: float
    timezone: str
    tilt_deg: float
    azimuth_deg: float
    minimum_current_clear_poa_W_m2: float = 20.0

    def __post_init__(self):
        numbers=(self.latitude,self.longitude,self.altitude_m,self.tilt_deg,self.azimuth_deg,self.minimum_current_clear_poa_W_m2)
        if not all(math.isfinite(x) for x in numbers):raise ValueError('Site parameters must be finite.')
        if not -90<=self.latitude<=90 or not -180<=self.longitude<=180:raise ValueError('Invalid coordinates.')
        if not 0<=self.tilt_deg<=180 or not 0<=self.azimuth_deg<=360:raise ValueError('Invalid panel orientation.')
        if self.minimum_current_clear_poa_W_m2<=0:raise ValueError('Clear-sky denominator guard must be positive.')
        ZoneInfo(self.timezone)

def forecast_next_labels(current_power_W, origin_times, site):
    """Forecast exactly one15-minute published label ahead for each input row.

    The current row is assumed fully available. Power can be negative; no
    clipping, missing-value fill, AC limit, or new parameter fitting occurs.
    Only the published site1239 geometry and 20W/m2 guard were validated.
    """
    powers=np.asarray(current_power_W,dtype=float)
    times=pd.DatetimeIndex(origin_times)
    if powers.ndim!=1 or len(powers)!=len(times) or not len(times):raise ValueError('One finite power value per timestamp required.')
    if not np.isfinite(powers).all() or times.hasnans:raise ValueError('Missing/nonfinite inputs are not replaced.')
    if times.tz is None:times=times.tz_localize(site.timezone,ambiguous='raise',nonexistent='raise')
    else:times=times.tz_convert(site.timezone)
    target=times+pd.Timedelta(minutes=15)
    alltimes=times.append(target).unique().sort_values()
    loc=pvlib.location.Location(site.latitude,site.longitude,tz=site.timezone,altitude=site.altitude_m)
    sp=loc.get_solarposition(alltimes,method=MODEL_SETTINGS['solarposition_method'],
                             temperature=MODEL_SETTINGS['standard_temperature_C'],delta_t=MODEL_SETTINGS['delta_t_seconds'])
    tl=pvlib.clearsky.lookup_linke_turbidity(alltimes,site.latitude,site.longitude,interp_turbidity=True)
    extra=pvlib.irradiance.get_extra_radiation(alltimes,method='spencer')
    cs=loc.get_clearsky(alltimes,model=MODEL_SETTINGS['clear_sky_model'],solar_position=sp,linke_turbidity=tl,dni_extra=extra)
    poa=pvlib.irradiance.get_total_irradiance(site.tilt_deg,site.azimuth_deg,sp.apparent_zenith,sp.azimuth,
                                            cs.dni,cs.ghi,cs.dhi,albedo=MODEL_SETTINGS['albedo'],model=MODEL_SETTINGS['transposition']).poa_global
    if not np.isfinite(poa).all() or (poa<0).any():raise ValueError('Clear-sky geometry failed; do not silently drop rows.')
    now=poa.reindex(times).to_numpy();future=poa.reindex(target).to_numpy()
    scaled=now>=site.minimum_current_clear_poa_W_m2;ratio=np.ones(len(times))
    np.divide(future,now,out=ratio,where=scaled)
    prediction=powers*ratio
    if not np.isfinite(prediction).all():raise ValueError('Nonfinite forecast; no clipping or fallback replacement.')
    return pd.DataFrame({'origin_time':times,'target_time':target,'persistence_W':powers,
                         'clear_sky_persistence_W':prediction,'clear_current_W_m2':now,'clear_target_W_m2':future,
                         'ratio':ratio,'branch':np.where(scaled,'scaled','persistence_fallback')})
