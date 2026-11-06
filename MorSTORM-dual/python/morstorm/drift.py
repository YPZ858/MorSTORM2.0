"""Selectable original-author engines shared by the MATLAB and Python frontends."""
import numpy as np
import pandas as pd
from .official import estimate_author

_PLUGINS = {}
AUTHOR_METHODS = {'meanshift','npcloud','rrnpcloud','aim'}


def register_drift(name, function):
    name = name.lower()
    if name in AUTHOR_METHODS | {'none','external_csv'}:
        raise ValueError('Cannot replace a built-in author engine')
    _PLUGINS[name] = function


def estimate(table, config):
    cfg = {'method':'none', **config}
    if not {'frame','x_nm','y_nm'}.issubset(table):
        raise ValueError('Canonical frame, x_nm and y_nm columns are required')
    axes = [a for a in ('x_nm','y_nm','z_nm') if a in table]
    data = table[['frame'] + axes].to_numpy(dtype=float)
    if table.empty or len(axes) < 2 or not np.isfinite(data).all():
        raise ValueError('Finite nonempty canonical localizations required')
    frames = data[:,0]
    if (frames < 1).any() or (frames != np.floor(frames)).any():
        raise ValueError('Canonical frames must be positive integers')
    nf, dim = int(frames.max()), len(axes)
    method = str(cfg['method']).lower(); cfg['method'] = method
    if method in AUTHOR_METHODS:
        curve, diag = estimate_author(table, cfg)
    elif method == 'none':
        curve, diag = np.zeros((nf,dim)), {'implementation':'identity'}
    elif method == 'external_csv':
        d = pd.read_csv(cfg['path'])
        columns = ['dx_nm','dy_nm'] + (['dz_nm'] if dim == 3 else [])
        if not {'frame',*columns}.issubset(d): raise ValueError('External drift columns missing')
        ff = d.frame.to_numpy(dtype=float)
        if len(ff)<2 or not np.isfinite(d[['frame']+columns].to_numpy()).all() or (np.diff(ff)<=0).any() or (ff!=np.floor(ff)).any():
            raise ValueError('External drift frames must be finite, integral, unique and increasing')
        if ff[0]>1 or ff[-1]<nf: raise ValueError('External drift must cover 1..max_frame')
        curve = np.column_stack([np.interp(np.arange(1,nf+1),ff,d[c]) for c in columns])
        diag = {'implementation':'external-curve','sign':'corrected=observed-drift'}
    elif method in _PLUGINS:
        curve, diag = _PLUGINS[method](table.copy(deep=True),cfg)
    else:
        raise ValueError(f'Unknown author drift engine {method!r}')
    curve = np.asarray(curve,dtype=float)
    if curve.shape != (nf,dim) or not np.isfinite(curve).all():
        raise ValueError('Drift engine returned an invalid max_frame x D array')
    diag['method'] = method
    return curve,diag
