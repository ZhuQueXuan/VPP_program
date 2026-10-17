from common import *
from datetime import datetime,timezone
f=BASE/'characteristic_protocol_v1.json';assert not f.exists()
dump(f,{'decision':'D066','created_utc':datetime.now(timezone.utc).isoformat(),
 'curve_protocol_sha256':sha(BASE/'curve_protocol_v1.json'),
 'scope':'Post-evaluation description of ALL admitted original2018 six-unit mixed-operation records and ALL held-out observations. Not new blind test or benefit. No new fits/predictions/tuning.',
 'description':'Perunit all-year wind/power mean and min/q25/median/q75/max using linear-interpolated quantiles; counts negative/zero/positive/above2050; only adjacent original admitted rows for600s deltaP/deltav descriptors, no gap bridging. No causal ramp/command/time-constant interpretation.',
 'curves':'All6panels scatter ALL69236test wind/power plus original280training nodes/line, same axis limits0to27mps/-100to2200kW covering all actual admitted test values; both PNG and same-figure SVG. No choosing best turbine/month/segment.',
 'bins':'Every nonempty0.5m/s bin in BOTH original train/test summaries kept. Test-bin means descriptive only, never replace fitted nodes.',
 'worst_context':'Original globally worst M_CURVE point already known; sameunit original±3rows(±30min) reported without causal labels or changing prediction. Entire valid subset in window, missing rows explicit if any.',
 'review':'Apply unchanged D046six bounded criteria to originalwind/power statistical component plus full descriptive evidence. Capacity/healthy/control not necessary truth for this bounded output and remain separate. Do not redefine103 or claim wholeP1 pass.'})
print(sha(f))
