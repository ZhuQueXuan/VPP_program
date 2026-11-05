"""Strict raw-domain checks precede numeric conversion."""
import math
from numbers import Real
from datetime import datetime
import numpy as np
VERSION='B1-B3-STABLE-v1-20261028'
def number(x,name,lo=None,hi=None):
    if isinstance(x,(bool,np.bool_)) or not isinstance(x,Real) or not math.isfinite(x) or (lo is not None and x<lo) or (hi is not None and x>hi):raise ValueError(name+' requires finite in-range real numeric value')
    return float(x)
def integer(x,name,lo=0,hi=None):
    if type(x) is not int or x<lo or (hi is not None and x>hi):raise ValueError(name+' requires in-range integer')
    return x
def boolean(x,name):
    if type(x) is bool:return x
    if type(x) in (int,float) and math.isfinite(x) and x in (0,1):return bool(x)
    raise ValueError(name+' requires boolean or numeric0/1, never string')
def binary(x,name,ndim=1):
    a=np.asarray(x)
    if a.ndim!=ndim or a.size==0 or a.dtype.kind not in 'biuf' or not np.isfinite(a).all() or not np.isin(a,[0,1]).all():raise ValueError(name+' raw values must be binary0/1')
    return a.astype(int)
def vector(x,name,n,lo=None,hi=None):
    if not isinstance(x,(list,tuple)) or len(x)!=n:raise ValueError(name+' wrong length')
    return np.array([number(v,name,lo,hi) for v in x])
def identity(x,name):
    if type(x) is not str or not x.strip():raise ValueError('nonempty '+name+' required')
    return x
def stamp(x):
    identity(x,'timestamp');a=datetime.fromisoformat(x.replace('Z','+00:00'))
    if a.tzinfo is None or a.utcoffset() is None:raise ValueError('timezone-aware timestamp required')
    return a
def failed(e):return dict(status='unavailable',reason=str(e),interface_version=VERSION,committed_kw=None)
def result(kind,value,**kw):return dict(status='ok',result_type=kind,interface_version=VERSION,committed_kw=None,**kw,**value)
