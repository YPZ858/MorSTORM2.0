"""B variant: independent Python runtime, using validated ports of pinned authors."""
import numpy as np
import pandas as pd
from .native import meanshift
from .native.providers import load_provider

_PLUGINS={}
METHODS={'meanshift','npcloud','rrnpcloud','aim'}


def register_drift(name,function):
    name=name.lower()
    if name in METHODS|{'none','external_csv'}:raise ValueError('Cannot overwrite a validated built-in method')
    _PLUGINS[name]=function


def estimate(table,config):
    cfg={'method':'none',**config};method=str(cfg['method']).lower();cfg['method']=method
    if not {'frame','x_nm','y_nm'}.issubset(table):raise ValueError('Canonical frame,x_nm,y_nm required')
    axes=[a for a in ('x_nm','y_nm','z_nm') if a in table]
    values=table[['frame']+axes].to_numpy(dtype=float)
    if not len(values) or not np.isfinite(values).all():raise ValueError('Finite nonempty input required')
    ff=values[:,0]
    if (ff<1).any() or (ff!=np.floor(ff)).any():raise ValueError('Frames must be positive integers')
    nf=int(ff.max());dim=len(axes)
    if method=='aim':curve,meta=load_provider('aim').estimate(table,cfg)
    elif method in ('npcloud','rrnpcloud'):curve,meta=load_provider('npcloud').estimate(table,cfg)
    elif method=='meanshift':curve,meta=meanshift.estimate(table,cfg)
    elif method=='none':curve,meta=np.zeros((nf,dim)),{'implementation':'identity'}
    elif method=='external_csv':
        source=pd.read_csv(cfg['path']);cols=['dx_nm','dy_nm']+(['dz_nm'] if dim==3 else [])
        if not {'frame',*cols}.issubset(source):raise ValueError('External drift columns missing')
        f=source.frame.to_numpy(dtype=float)
        if len(f)<2 or not np.isfinite(source[['frame']+cols].to_numpy()).all() or (np.diff(f)<=0).any() or (f!=np.floor(f)).any() or f[0]>1 or f[-1]<nf:
            raise ValueError('External curve must have increasing finite integral frames covering the data')
        curve=np.column_stack([np.interp(np.arange(1,nf+1),f,source[c]) for c in cols]);meta={'implementation':'external-curve'}
    elif method in _PLUGINS:curve,meta=_PLUGINS[method](table.copy(deep=True),cfg)
    else:raise ValueError(f'Unknown B method {method!r}')
    curve=np.asarray(curve,dtype=float)
    if curve.shape!=(nf,dim) or not np.isfinite(curve).all():raise ValueError('Invalid drift returned')
    meta.update(method=method,runtime='standalone-python',matlab_required=False,variant='B')
    return curve,meta
