from common import *
from scipy.special import expit,logit
from scipy.stats import norm
from sklearn.preprocessing import PolynomialFeatures,StandardScaler,SplineTransformer
from sklearn.linear_model import Ridge,LogisticRegression

class Outcome:
    def __init__(self,kind):self.kind=kind
    def fit(self,x,d,y):
        degree,knots=(3,8) if self.kind=='capacity' else (2,6)
        self.poly=PolynomialFeatures(degree,include_bias=False);z=self.poly.fit_transform(x);self.scaler=StandardScaler().fit(z);z=self.scaler.transform(z)
        self.spline=SplineTransformer(knots=np.linspace(*DOMAIN,knots)[:,None],degree=3,include_bias=False,extrapolation='error').fit(np.array([[0.],[2.4]]))
        features=self.design(z,d);self.parameter_columns=features.shape[1];self.xmean=z.mean(0);self.xtrain=x.copy()
        if self.kind=='hurdle':
            positive=y>0;assert positive.any() and (~positive).any()
            self.prob=LogisticRegression(C=1.,max_iter=1500,random_state=0).fit(features,positive.astype(int));self.reg=Ridge(alpha=.1).fit(features[positive],y[positive])
        elif self.kind=='capacity':
            # Fractional-logit likelihood via duplicate1/0 rows with y and1-y
            # weights, including exact0 and1 without logit transforms.
            self.prob=LogisticRegression(C=1.,max_iter=1500,random_state=0).fit(np.r_[features,features],np.r_[np.ones(len(y)),np.zeros(len(y))],sample_weight=np.r_[y,1-y])
        else:self.reg=Ridge(alpha=.1).fit(features,y)
        return self
    def design(self,z,d):return CT._design(z,self.spline.transform(np.asarray(d)[:,None]))
    def predict(self,x,d):
        f=self.design(self.scaler.transform(self.poly.transform(x)),d)
        if self.kind=='capacity':return self.prob.predict_proba(f)[:,1]
        v=self.reg.predict(f)
        if self.kind in ['bounded','hurdle']:v=np.clip(v,0,1)
        return self.prob.predict_proba(f)[:,1]*v if self.kind=='hurdle' else v
    def marginal(self,d):
        d=np.asarray(d)
        if self.kind=='single':return self.reg.predict(CT._design(np.broadcast_to(self.xmean,(len(d),len(self.xmean))),self.spline.transform(d[:,None])))
        out=np.empty(len(d));n=len(self.xtrain)
        for j in range(0,len(d),16):
            amounts=d[j:j+16];xx=np.tile(self.xtrain,(len(amounts),1));dd=np.repeat(amounts,n);out[j:j+16]=self.predict(xx,dd).reshape(len(amounts),n).mean(1)
        return out

def nuisance(data,kind,fold_seed,points=GRID):
    x=np.asarray(data['X']);d=np.asarray(data['offered_incentive']);y=np.asarray(data['outcome_seconds'])/T;groups=np.asarray(data['users']);cfg=CT.ContinuousEffectConfig(seed=fold_seed,n_boot=99,return_audit=True);folds=CT.group_folds(groups,3,fold_seed);items=[];mu=np.zeros(len(y));mm=np.zeros(len(y));pdf=np.zeros(len(y));margpdf=np.zeros(len(y))
    for fold in np.unique(folds):
        tr=folds!=fold;va=~tr;model=Outcome(kind).fit(x[tr],d[tr],y[tr]);mu[va]=model.predict(x[va],d[va]);mm[va]=model.marginal(d[va])
        xp=PolynomialFeatures(2,include_bias=False);xt=xp.fit_transform(x[tr]);xe=xp.transform(x[va]);scale=StandardScaler().fit(xt);xt=scale.transform(xt);xe=scale.transform(xe);density_model=None;sd=None
        if data['known_density'] is not None:pdf[va]=1/2.4;margpdf[va]=1/2.4
        else:
            z=logit(d[tr]/2.4);inner=CT.group_folds(groups[tr],2,fold_seed+int(fold)+130);res=np.zeros(len(z))
            for k in (0,1):dm=Ridge(alpha=.1).fit(xt[inner!=k],z[inner!=k]);res[inner==k]=z[inner==k]-dm.predict(xt[inner==k])
            sd=float(np.sqrt(np.mean(res**2)))
            if sd<.05:raise ValueError('assignment nearly deterministic; shared GPS unsupported')
            density_model=Ridge(alpha=.1).fit(xt,z);u=d[va]/2.4;pdf[va]=norm.pdf(logit(u),density_model.predict(xe),sd)/(2.4*u*(1-u));margpdf[va]=CT._marginal_logit_density(d[va],density_model.predict(xt),sd,0,2.4)
        items.append(dict(train=tr,test=va,model=model,gps=density_model,gps_poly=xp,gps_scale=scale,gps_sd=sd,held_x=xe))
    assert len({id(r['model']) for r in items})==3
    weights=margpdf/pdf
    if not np.isfinite(weights).all() or weights.max()>30:raise ValueError('shared extreme stabilized densityweights')
    h=1.06*np.std(d)*len(set(groups))**(-.2);diag,failed=CT._local_support(x,d,groups,points,h,weights,cfg)
    if failed:raise ValueError('shared localsupport unavailable on predefinedquerygrid')
    return dict(x=x,d=d,y=y,groups=groups,cfg=cfg,folds=folds,items=items,mu=mu,marginal_mu=mm,pdf=pdf,marginal_pdf=margpdf,h=h,diagnostics=diag)

def cluster_band(contr,scores,users,seed):
    # Conditional-on-fitted-nuisance multiplier band, not a verified completeCI.
    residual=(scores-scores[:,[0]])-contr;unique,inv=np.unique(users,return_inverse=True);n=len(users);G=len(unique);sums=np.zeros((G,len(contr)));np.add.at(sums,inv,residual/n);sums*=np.sqrt(G/(G-1));se=np.sqrt(np.sum(sums**2,axis=0));active=se>1e-14;draws=np.random.default_rng(seed+73).standard_normal((199,G))@sums;crit=float(np.quantile(np.max(abs(draws[:,active])/se[active],axis=1),.95)) if active.any() else 0.
    return dict(lower=(contr-crit*se),upper=(contr+crit*se),se=se,kind='conditional_fitted_nuisance_user_multiplier_only',complete_causal_CI_validated=False)

def estimate(data,estimator='DML',outcome_kind='single',fold_seed=0,return_bundle=False,grid=None):
    try:
        points=GRID if grid is None else np.asarray(grid,float);a=nuisance(data,outcome_kind,fold_seed,points);n=len(a['y'])
        if estimator=='DR':
            xi=(a['y']-a['mu'])*a['marginal_pdf']/a['pdf']+a['marginal_mu'];L=CT.local_linear_weights(a['d'],points,a['h']);mean=L@xi;_,band=CT._conditional_band(a['d'],xi,a['groups'],points,a['h'],a['cfg']);ci=dict(lower=np.asarray(band['lower'])*T,upper=np.asarray(band['upper'])*T,kind='conditional_fitted_nuisance_user_multiplier_only',complete_causal_CI_validated=False)
        else:
            scores=np.zeros((n,len(points)))
            for item in a['items']:
                va=item['test'];x=a['x'][va]
                for j,dose in enumerate(points):
                    query=np.full(sum(va),dose);gamma=item['model'].predict(x,query)
                    if item['gps'] is None:pdf=np.full(len(query),1/2.4)
                    else:u=dose/2.4;pdf=norm.pdf(logit(u),item['gps'].predict(item['held_x']),item['gps_sd'])/(2.4*u*(1-u))
                    if not np.isfinite(pdf).all() or np.any(pdf<=0):raise ValueError('nonpositive queryGPS')
                    kernel=norm.pdf((a['d'][va]-dose)/a['h'])/a['h'];scores[va,j]=gamma+kernel/pdf*(a['y'][va]-gamma)
            mean=scores.mean(0);ci=cluster_band((mean-mean[0])*T,scores*T,a['groups'],fold_seed)
        contrast=(mean-mean[0])*T
        result=dict(status='ok',estimator=estimator,outcome_model=outcome_kind,grid=points,mean_seconds=mean*T,contrast_seconds=contrast,inference=ci,bandwidth=float(a['h']),fold_by_event=a['folds'],outcome_parameter_columns=a['items'][0]['model'].parameter_columns,all_events_retained=True,final_curve_clipped=False)
        return (result,a) if return_bundle else result
    except (ValueError,FloatingPointError,np.linalg.LinAlgError) as ex:
        result=dict(status='unsupported',estimator=estimator,outcome_model=outcome_kind,reason=str(ex),all_events_retained=True)
        return (result,None) if return_bundle else result

def public_DR(data,fold_seed,grid=None):
    assumptions=dict(ASSUMPTIONS)
    if data['known_density'] is not None:assumptions.update(randomized_assignment=True,conditional_exchangeability=None)
    points=GRID if grid is None else np.asarray(grid,float);result=CT.fit_continuous_effects(data['X'],data['offered_incentive'],data['outcome_seconds'],data['users'],dose_domain=DOMAIN,grid=points,reference_dose=float(points[0]),incentive_unit='元/千瓦时（模拟）',task=TASK,continuous_assignment=True,assumptions=assumptions,known_density=data['known_density'],config=dict(seed=fold_seed,n_boot=99,return_audit=True))
    if result['status']!='causal':return dict(status='unsupported',estimator='existing_DR',outcome_model='single',reason=str(result['reasons']),public_result=result)
    curve=result['causal_curve'];return dict(status='ok',estimator='existing_DR',outcome_model='single',grid=points,mean_seconds=curve['mean_outcomes'],contrast_seconds=curve['contrasts'],inference=result['inference'],public_result=result)
