"""Same-observation real descriptors and fixed perturbation checks, no truth labels."""
from common import *
from candidate import propose_edges,cache_blocks,choose_partition
from collections import defaultdict,Counter
def main():
    frozen=read('validation_freeze.json');ratio=frozen['selected_ratio'];method=frozen['selected_method']
    for p,h in frozen['source_sha256'].items():assert sha(ROOT/p)==h
    path=PREVIOUS/'real_cases.json';allcases=json.loads(path.read_text(encoding='utf-8'));groups=defaultdict(list)
    for c in allcases:groups[(c['recording'],c['direction'])].append(c)
    cases=[]
    for key,rr in sorted(groups.items()):
        rr.sort(key=lambda c:(c['edge_index'],c['event_id']));cases.extend([rr[0],rr[-1]])
    assert len(cases)==72 and len({c['event_id'] for c in cases})==72
    write('real_selection.json',{'rule':read('protocol.json')['real_auxiliary']['selection'],
        'selected_ids':[c['event_id'] for c in cases],'source_sha256':sha(path),'selected_before_fitting':True,
        'directions':dict(Counter(c['direction'] for c in cases))})
    spec=read('protocol.json')['real_auxiliary'];rng=np.random.default_rng(spec['seed'])
    items=[];cp=[];blocks=[];proposals={};ptimes={}
    for c in cases:
        y=np.asarray(c['progress']);g=rng.normal(0,.03,len(y));sp=g.copy()
        ix=rng.choice(np.flatnonzero(np.asarray(c['starts_s'])>=0),2,replace=False);sp[ix]+=rng.choice([-1.,1.],2)*.30
        s=np.asarray(c['starts_s']);e=np.asarray(c['ends_s']);x=(s+e)/2
        command=np.where(s<0,c['previous_command_A'],c['new_command_A'])
        for condition in spec['conditions']:
            value=y if condition=='original' else y+(g if condition=='gaussian' else sp)
            sigma=c['noise_sigma_progress'] if condition=='original' else float(np.hypot(c['noise_sigma_progress'],.03))
            i=len(items);tic=time.perf_counter();proposal=propose_edges(value,x,sigma,command);ptimes[i]=time.perf_counter()-tic;proposals[i]=proposal
            items.append({'case':c,'event_id':c['event_id'],'condition':condition,'y':value,'sigma':sigma,'command':command})
            cp.append({'case_id':i,'starts':s,'ends':e,'y':value,'sigma':sigma,'train':np.ones(len(y),bool)})
            blocks.append({'case_id':i,'x':x,'y':value,'sigma':sigma,'proposal':proposal})
    write('real_inputs.json',[{k:v for k,v in r.items() if k!='case'} for r in items])
    write('real_proposals.json',proposals)
    original,ometa=fit_cases(cp,runtime('native/real_original'));assert ometa['status']=='ok'
    caches,bmeta=cache_blocks(blocks,'native/real_blocks',chunk_size=36)
    labs,lmeta=labs_batch([c['y'] for c in cp],'labs/real')
    desc=load_module(PREVIOUS/'run_real.py','_previous_real_descriptors').descriptors
    outputs=[];metrics=[]
    for i,item in enumerate(items):
        c=item['case'];fit=choose_partition(proposals[i],caches[i],item['sigma'],len(item['y']),ratio)
        fit['seconds']=ptimes[i]+sum(r.get('seconds',0.) for r in caches[i].values())
        results={'cpop':original[i],method:fit,'labs':labs[i]}
        full=caches[i][f"0:{len(item['y'])}"]
        if original[i]['status']==full['status']=='ok':assert np.max(np.abs(np.asarray(original[i]['prediction'])-np.asarray(full['prediction'])))<1e-7
        outputs.append({'event_id':item['event_id'],'condition':item['condition'],'results':results})
        reference=desc(c,c['progress'])
        for m,r in results.items():
            d={'event_id':c['event_id'],'recording':c['recording'],'condition':item['condition'],'method':m,
               'status':r['status'],'seconds':r.get('seconds',0.),'jump_count':len(r.get('jump_boundaries',[]))}
            if r['status']=='ok':
                feat=desc(c,r['prediction']);d.update(features=feat,original_observed_features=reference)
                for key in ['target_duration_seconds','longest_target_seconds','steady_error_progress']:
                    d[key+'_difference']=abs(feat[key]-reference[key])
                for key in ['t10_seconds','t90_seconds']:
                    a,b=feat[key],reference[key];d[key+'_status_difference']=(a is None)!=(b is None)
                    d[key+'_difference']=abs(a-b) if a is not None and b is not None else None
            else:d['reason']=r.get('reason',r.get('error'))
            metrics.append(d)
    summary=[];pairs=[]
    for m in ['cpop',method,'labs']:
      for condition in spec['conditions']:
        rr=[r for r in metrics if r['method']==m and r['condition']==condition];v=[r for r in rr if r['status']=='ok']
        d={'method':m,'condition':condition,'n':len(rr),'available':len(v)}
        if v:
            for key in ['target_duration_seconds_difference','longest_target_seconds_difference','steady_error_progress_difference','jump_count','seconds']:d[key]=float(np.mean([r[key] for r in v]))
            for key in ['t10_seconds','t90_seconds']:
                d[key+'_status_difference']=sum(r[key+'_status_difference'] for r in v)
                vs=[r[key+'_difference'] for r in v if r[key+'_difference'] is not None]
                d[key+'_difference']=float(np.mean(vs)) if vs else None;d[key+'_paired_present_n']=len(vs)
        summary.append(d)
      lookup={(r['event_id'],r['condition']):r for r in metrics if r['method']==m}
      paired=[(lookup[(c['event_id'],'gaussian')],lookup[(c['event_id'],'gaussian_plus_spikes')]) for c in cases]
      good=[(a,b) for a,b in paired if a['status']==b['status']=='ok']
      d={'method':m,'n':len(paired),'available_pairs':len(good)}
      for key in ['target_duration_seconds','longest_target_seconds','steady_error_progress']:
        d[key+'_change']=float(np.mean([abs(a['features'][key]-b['features'][key]) for a,b in good])) if good else None
      d['t90_status_flips']=sum((a['features']['t90_seconds'] is None)!=(b['features']['t90_seconds'] is None) for a,b in good)
      pairs.append(d)
    write('real_block_cache.json',[{'event_id':r['event_id'],'condition':r['condition'],'blocks':caches[i]} for i,r in enumerate(items)])
    write('real_curves.json',outputs);write('real_metrics.json',metrics);write('real_summary.json',summary);write('real_paired_stability.json',pairs)
    write('real_receipt.json',{'status':'complete','original_events':72,'recordings':18,'input_variants':216,'outputs':len(metrics),
       'available':sum(r['status']=='ok' for r in metrics),'known_latent_clean_truth':False,'new_real_holdout':False,
       'source_original_unchanged':sha(path)==read('real_selection.json')['source_sha256'],
       'runtime':{'original':ometa,'blocks':bmeta,'labs':lmeta},
       'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [HERE/'run_real.py',HERE/'candidate.py',path]}})
    print(json.dumps({'pairs':pairs,'summary':summary},ensure_ascii=False))
if __name__=='__main__':main()
