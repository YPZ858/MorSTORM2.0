import numpy as np
from scipy.interpolate import interp1d, CubicSpline, PchipInterpolator


class ParityDomainError(ValueError):
    """An author decision is at a discontinuous, platform-dependent threshold."""


def mround(x):
    """MATLAB round: ties away from zero, unlike NumPy's ties-to-even."""
    a=np.asarray(x)
    return np.copysign(np.floor(np.abs(a)+0.5),a)


def colon(start, step, stop):
    count=int(np.floor((stop-start)/step + 2*np.finfo(float).eps*max(1,abs((stop-start)/step))))+1
    return start+step*np.arange(max(count,0))


def interpolate(x,y,q,method='linear'):
    if method=='linear':return interp1d(x,y,axis=0,fill_value='extrapolate',bounds_error=False)(q)
    if method=='spline':return CubicSpline(x,y,axis=0,bc_type='not-a-knot')(q)
    if method=='pchip':return PchipInterpolator(x,y,axis=0,extrapolate=True)(q)
    if method=='nearest':return interp1d(x,y,axis=0,kind='nearest-up',fill_value='extrapolate')(q)
    raise ValueError(f'Unsupported interpolation method {method!r}')


def prepare(table, config):
    axes=[a for a in ('x_nm','y_nm','z_nm') if a in table]
    ordered=table.sort_values('frame',kind='stable')
    xyz=ordered[axes].to_numpy(dtype=float)
    frames=ordered.frame.to_numpy(dtype=np.int64)
    if frames.min()!=1:raise ValueError('The author-compatible profile requires first localized frame 1')
    segment=config.get('segment_frames',100)
    if isinstance(segment,bool) or not np.isfinite(segment) or segment<1 or int(segment)!=segment:
        raise ValueError('segment_frames must be a positive integer')
    return xyz,frames,int(segment)


def finite_curve(curve):
    curve=np.asarray(curve,dtype=float)
    if not np.isfinite(curve).all():raise ValueError('Algorithm returned nonfinite drift; inspect data/author parameters')
    return curve
