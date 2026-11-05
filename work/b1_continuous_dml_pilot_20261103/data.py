from common import *
from scipy.special import expit,betaincc
from numpy.polynomial.legendre import leggauss

def components(d,x1,x2,u,kind):
    if kind=='zero_effect':p=expit(-.3+.7*x1-.6*x2+u);mu=expit(.5+.5*x1-.3*x2+.3*u);full=np.zeros_like(mu)
    elif kind=='nonmonotone':p=expit(-1.2+2.1*np.sin(np.pi*d/2.4)+.7*x1-.5*x2+u);mu=expit(-.5+1.3*np.sin(np.pi*d/2.4)+.5*x1-.3*x2+.3*u);full=np.zeros_like(mu)
    elif kind=='ceiling':p=expit(-1.6+1.7*d+.7*x1-.5*x2+u);mu=expit(.3+1.8*d+.5*x1-.3*x2+.3*u);full=expit(-2+1.6*d+.4*x1)
    else:p=expit(-2.4+1.6*d+.7*x1-.5*x2+u);mu=expit(-.8+1.15*d+.5*x1-.3*x2+.3*u);full=np.zeros_like(mu)
    return p,mu,full

def generate(seed,kind,users=240,events=2,stage='development'):
    rng=np.random.default_rng(seed);g=np.repeat(np.arange(users),events);n=len(g);x=rng.uniform(-1,1,(n,2));u=rng.uniform(-.6,.6,users)[g]
    if kind in ['confounded_hurdle','assignment_mixture']:d=2.4*expit(.7*x[:,0]-.5*x[:,1]+1.35*rng.normal(size=n))
    elif kind=='weak_support':d=2.4*expit(4*x[:,0]-.7*x[:,1])
    else:d=rng.uniform(0,2.4,n)
    if kind=='assignment_mixture':
        component=rng.random(n)<expit(.6*x[:,1]);z=.7*x[:,0]-.5*x[:,1]+np.where(component,1.05,-1.05)+.8*rng.normal(size=n);d=2.4*expit(z)
    p,mu,full=components(d,x[:,0],x[:,1],u,kind);participates=rng.random(n)<p;at_full=rng.random(n)<full;beta=rng.beta(mu*18,(1-mu)*18);fraction=np.where(participates,np.where(at_full,1.,beta),0.)
    groups=np.array([f'{stage}|{kind}|{seed}|user{v:04d}' for v in g])
    known_uniform=kind not in ['confounded_hurdle','assignment_mixture','weak_support'];density=np.full(n,1/2.4) if known_uniform else None
    return dict(seed=seed,mechanism=kind,stage=stage,X=x,offered_incentive=d,outcome_seconds=T*fraction,users=groups,known_density=density,raw_latent_fraction=fraction)

def population_curve(kind,rounded=False,nodes=21):
    z,w=leggauss(nodes);a,b,c=np.meshgrid(z,z,z,indexing='ij');wa,wb,wc=np.meshgrid(w,w,w,indexing='ij');x1=a.ravel();x2=b.ravel();u=.6*c.ravel();weight=(wa*wb*wc).ravel()/8;out=[]
    for dose in GRID:
        p,mu,full=components(dose,x1,x2,u,kind)
        if rounded:
            thresholds=(np.arange(1,181)-.5)/180
            expected=np.empty(len(mu))
            for j in range(0,len(mu),512):expected[j:j+512]=betaincc(mu[j:j+512,None]*18,(1-mu[j:j+512,None])*18,thresholds).sum(1)/180
            conditional=full+(1-full)*expected
        else:conditional=full+(1-full)*mu
        out.append(float(np.sum(weight*p*conditional)*T))
    return np.array(out)
