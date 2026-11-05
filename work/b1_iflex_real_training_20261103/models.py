"""Shared feature engineering and same-budget learners for factual kWh."""
from dataclasses import dataclass
from datetime import date
import numpy as np
from sklearn.preprocessing import PolynomialFeatures,StandardScaler,OneHotEncoder,SplineTransformer
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

@dataclass
class Design:
    augmented:bool
    def raw(self,rows):
        num=[];cat=[];price=[]
        for r in rows:
            x=[np.arcsinh(float(r['pre24_kwh'])/10.),np.arcsinh(float(r['pre168_kwh'])/70.),float(r['pre24_temperature'])]
            if self.augmented:x.append(np.arcsinh(float(r['mean_peak_history_kwh'])))
            num.append(x)
            cat.append([r['Group']+'|'+r['Region'],str(date.fromisoformat(r['Date']).weekday())])
            price.append(float(r['nominal_price_level']))
        return np.asarray(num,float),np.asarray(cat),np.asarray(price,float)
    def fit(self,rows):
        x,c,_=self.raw(rows)
        self.poly=PolynomialFeatures(2,include_bias=False).fit(x)
        self.scale=StandardScaler().fit(self.poly.transform(x))
        self.categories=OneHotEncoder(handle_unknown='ignore',sparse_output=False).fit(c)
        self.spline=SplineTransformer(knots=np.linspace(2,15,6)[:,None],degree=3,
            include_bias=False,extrapolation='error').fit(np.array([[2.],[15.]]))
        return self
    def transform(self,rows,method):
        x,c,a=self.raw(rows)
        x=np.column_stack([self.scale.transform(self.poly.transform(x)),self.categories.transform(c)])
        if method in ('history_ridge','history_hgb'):return x
        b=((a-2)/13)[:,None] if method=='linear_ridge' else self.spline.transform(a[:,None])
        return np.column_stack([x,b,(x[:,:,None]*b[:,None,:]).reshape(len(x),-1)])

def fit_model(method,params,settings,x,y):
    if method.endswith('ridge'):return Ridge(alpha=params['alpha']).fit(x,y)
    return HistGradientBoostingRegressor(max_leaf_nodes=params['leaves'],l2_regularization=params['l2'],**settings).fit(x,y)
