"""Observed-only estimators. No simulator or evaluator imports."""
import numpy as np
from scipy.special import expit
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold


def outcome_model():
    return HistGradientBoostingRegressor(max_iter=60, max_leaf_nodes=7,
        min_samples_leaf=25, l2_regularization=1., learning_rate=.05,
        early_stopping=False, random_state=71)


def fit_aux(x, d, y, randomized):
    if min(np.sum(d == 0), np.sum(d == 1)) < 20:
        raise ValueError('insufficient training-arm support')
    models = [outcome_model().fit(x[d == k], y[d == k]) for k in (0,1)]
    e_model = None if randomized else LogisticRegression(C=1).fit(x,d)
    return dict(mu=models, propensity=e_model, randomized=randomized)


def predict_aux(models, x):
    mu0, mu1 = [m.predict(x) for m in models['mu']]
    e = np.full(len(x), .5) if models['randomized'] else models['propensity'].predict_proba(x)[:,1]
    return mu0, mu1, e


def aipw(y, d, mu0, mu1, e):
    if not np.isfinite(e).all() or e.min() < .05 or e.max() > .95:
        raise ValueError('propensity support gate failed; no clipping')
    return mu1-mu0 + d*(y-mu1)/e - (1-d)*(y-mu0)/(1-e)


class EffectStudy:
    def fit(self, x, d, y, users, randomized):
        self.columns = ('x','w')
        self.bounds = (x.min(axis=0),x.max(axis=0))
        self.fold_models = []
        self.folds = []
        self.oof = np.full((len(x),3),np.nan)
        seen = np.zeros(len(x),int)
        for tr, va in GroupKFold(3).split(x, d, users):
            assert not set(users[tr]).intersection(users[va])
            m = fit_aux(x[tr],d[tr],y[tr],randomized)
            self.oof[va] = np.column_stack(predict_aux(m,x[va]))
            seen[va] += 1
            self.fold_models.append(m)
            self.folds.append(dict(train_users=np.unique(users[tr]).tolist(),
                                   heldout_users=np.unique(users[va]).tolist(),
                                   arm_counts=[int(np.sum(d[tr]==k)) for k in (0,1)]))
        assert np.all(seen == 1)
        self.oof_scores = aipw(y,d,*self.oof.T)
        self.full = fit_aux(x,d,y,randomized)
        self.ridge = [make_pipeline(PolynomialFeatures(2,include_bias=False),Ridge(alpha=1.))
                      .fit(x[d==k],y[d==k]) for k in (0,1)]
        self.randomized = randomized
        return self

    def predict_observed(self, x):
        # Physical synthetic domain is [-1,1]^2, not empirical min/max support.
        if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all() or np.any(abs(x)>1):
            raise ValueError('invalid or out-of-declared-domain new X')
        mu0,mu1,e = predict_aux(self.full,x)
        ridge_effect=self.ridge[1].predict(x)-self.ridge[0].predict(x)
        return dict(mu0=mu0,mu1=mu1,e=e,ridge_effect=ridge_effect)

    def effect(self,x):
        p=self.predict_observed(x)
        return p['mu1']-p['mu0']
