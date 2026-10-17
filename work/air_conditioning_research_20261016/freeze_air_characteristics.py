"""Explicit retrospective description after prediction outcomes were seen."""
from common import *
import datetime
pp=BASE/'air_characteristic_protocol_v1.json';assert not pp.exists()
source=load(BASE/'dual_zone_protocol_v1.json')
p={'decision':'D063','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'purpose':'Retrospective resource-characteristic summary and limited basic-package evidence review; not new blind forecasting or control-response validation. Existing D062 forecasts/scores/parameters unchanged.',
 'sources':source['sources'],'source_protocol_sha256':sha(BASE/'dual_zone_protocol_v1.json'),
 'old_predictions_sha256':sha(BASE/'runs/BL_DUAL_ZONE_01/predictions.csv'),
 'summary':'Every8original day files x2rooms: all288published temperature/power values per file; min/max/mean,positive/zero power label counts. All287within-file adjacent pairs; observed next-minus-current temperature increment and rate divided by5minutes, counts up/down/equal. No pooling missing dates/cross-file pairs or interpolation. Report quantiles with linear interpolation of sorted values at(n-1)*q, q=.05,.5,.95.',
 'power_reading_pairs':'Count zero->zero,zero->positive,positive->zero,positive->positive for adjacent published P values, retain all. Counts are measurement label patterns, not verified compressor/state/command events. No timing or causality interpretation.',
 'no_energy':'No energy integration, physical on-duration, COP, available capacity or response-delay calculation: metering averaging interval,control logs,authorisation/comfort boundary not established.',
 'figures':'Exactly all4test days x2rooms,8panels,chronological and no best-case selection. Source room-temperature curve drawn at original source timestamps(all288labels); D062 prediction at its TARGET timestamp(286labels) and original same-room published W at source timestamp. Naive source clock, no time shift. Two rooms are same test bed,not8independent devices. No smoothing or clipping. SVG+PNG plus plotted-row trace hashes. No new fits/threshold tuning.',
 'final_acceptance_basis':'Apply existing D046 six bounded basic criteria to original two-room conditional next-label component plus fair earlier failures; control/latency/available-capacity remain separately unverified research tasks. Do not turn basic-package acceptance into complete air-conditioning capability,P1or103 acceptance.',
 'SHIFDR':'Primary DataCite subset10.7302/vmwh-ek70 says fan power computed from current;2021preprocessed BAS interpolated to1min. Exact subset catalog403and author-page403 stop, no raw files/README/admission. DataCite rightsList empty, ORNL ODbL not automatically inherited; paper Crossref10.1115/1.4064348 obtained only as registry/abstract. No new performance or control label claims.'}
dump(pp,p);dump(BASE/'air_characteristic_freeze_v1.json',{'protocol_sha256':sha(pp),'created_utc':p['created_utc']});print(sha(pp))
