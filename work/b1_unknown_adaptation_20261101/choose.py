from common import *

def main():
    summaries=read('validation/summary.json');by={c:{r['method']:r for r in rr} for c,rr in summaries.items()};eligible=[];allchecks=[]
    for method in ['tracked_retained','dual_short']:
        a=by['main'][method];old=by['main']['old_retained'];cp=by['main']['tracked_cpop'];s=by['short'][method];so=by['short']['old_retained']
        checks=dict(main_duration10percent_better=a['primary_seconds']<=.9*old['primary_seconds'],same_tracked_cpop_noninferiority=a['primary_seconds']<=cp['primary_seconds'],
            main_whole_miss_not_increased=a['whole_miss']<=old['whole_miss'],main_short_miss_not_increased=a['short_local_miss']<=old['short_local_miss'],
            main_false_positive_not_increased=a['null_false_positive']<=old['null_false_positive'],
            short_local_miss_not_increased=s['short_local_miss']<=so['short_local_miss'],short_false_positive_not_increased=s['null_false_positive']<=so['null_false_positive'],
            short_duration_noninferiority5s=s['primary_seconds']<=so['primary_seconds']+5)
        item=dict(method=method,checks=checks,main=a,short=s);allchecks.append(item)
        if all(checks.values()):eligible.append(item)
    write('validation_decision.json',dict(all=allchecks,eligible=eligible))
    if not eligible:print(json.dumps(native(allchecks)),flush=True);return
    selected=min(eligible,key=lambda r:r['main']['primary_seconds']);write('selected.json',selected)
    paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'selected.json',HERE/read('error_tracking/selection.json')['selected']['model']]
    paths += [ROOT/'work/b1_reliability_20261031/study/generator.py',ROOT/'work/b1_ev_mainline_20261030/simulation.py',ROOT/'work/b1_reliability_20261031/study/models/reliable_reference.json']
    paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},test_not_generated=True,selected_method=selected['method']))
    print(json.dumps(native(selected)),flush=True)
if __name__=='__main__':main()
