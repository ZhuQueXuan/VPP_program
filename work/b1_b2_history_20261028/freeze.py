from io_utils import BASE,ROOT,read,write,sha

def main():
    old=read(ROOT/'work/b2_b3_integration_20261028/source_freeze.json');protected=dict(old['protected'])
    for p in (ROOT/'work/b2_b3_integration_20261028').iterdir():
        if p.is_file():protected[str(p.relative_to(ROOT)).replace('\\','/')]=sha(p)
    source={p.name:sha(p) for p in BASE.iterdir() if p.suffix in ['.py','.json'] and p.name not in ['source_freeze.json']}
    for rel,h in protected.items():assert sha(ROOT/rel)==h,rel
    write(BASE/'source_freeze.json',dict(source=source,protected=protected,main_data_not_generated=True))
    print('frozen',len(source),'new',len(protected),'old',flush=True)

if __name__=='__main__':main()
