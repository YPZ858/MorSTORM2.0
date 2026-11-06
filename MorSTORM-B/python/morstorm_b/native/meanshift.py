"""Port of VeatchLab Mean-Shift-Drift-Correction b04d42f0.

Derived from Frank Fazekas, Thomas Shaw and Sarah Veatch (2021), GPL-3.0-or-later.
Upstream source and notices are listed in THIRD_PARTY.md. This module
preserves all-pair windows, original stopping rule, auto precision estimation,
error-derived weights, rank-guarded outlier handling and author interpolation.
MATLAB's proprietary fit engine is replaced by explicitly configured SciPy
bounded least squares; agreement is validated numerically, not bitwise.
"""
import numpy as np
from numba import njit
from scipy.optimize import least_squares
from scipy.linalg import lstsq,svd
from scipy.stats import t as student
from .common import mround,colon,interpolate,prepare,finite_curve,ParityDomainError

DEFAULTS={'nTimeBin':20,'rmax':500.,'maxiter':200,'calc_error':1,'broadsweep':0,
          'delta_broad':100.,'delta_narrow_ratio':3.,'interp_method':'linear','outlier_error':50.}


@njit(cache=True)
def _pair_kernel(a,b,radius,tmin,tmax,limit):
    dim=a.shape[1]-1;r2=radius*radius;left=0;count=0
    for i in range(len(a)):
        while left+1<len(b) and b[left,0]<a[i,0]-radius:left+=1
        for j in range(left,len(b)):
            dx=b[j,0]-a[i,0];distance=dx*dx
            if distance>r2:break
            for k in range(1,dim):distance+=(b[j,k]-a[i,k])**2
            dt=b[j,dim]-a[i,dim]
            if distance<=r2 and tmin<=dt<=tmax:count+=1
            if count>=limit:break
        if count>=limit:break
    out=np.empty((count,dim));left=0;p=0
    for i in range(len(a)):
        while left+1<len(b) and b[left,0]<a[i,0]-radius:left+=1
        for j in range(left,len(b)):
            dx=b[j,0]-a[i,0];distance=dx*dx
            if distance>r2:break
            for k in range(1,dim):distance+=(b[j,k]-a[i,k])**2
            dt=b[j,dim]-a[i,dim]
            if distance<=r2 and tmin<=dt<=tmax:
                if p>=count:return out
                for k in range(dim):out[p,k]=b[j,k]-a[i,k]
                p+=1
    return out


def _pairs(a,b,radius,tmin,tmax,limit):
    if not len(a) or not len(b):return np.empty((0,a.shape[1]-1))
    aa=np.ascontiguousarray(a[np.argsort(a[:,0],kind='stable')]);bb=np.ascontiguousarray(b[np.argsort(b[:,0],kind='stable')])
    return _pair_kernel(aa,bb,float(radius),float(tmin),float(tmax),int(limit))


def _iterate(d,start,delta,maxiter):
    shift=np.asarray(start,dtype=float).copy();change=np.ones(len(shift));iterations=0
    discount=np.sqrt(2.0)**2
    while np.all(change!=0) and iterations<maxiter and not np.isnan(shift[0]):
        residual=d-shift;squared=residual[:,0]**2+residual[:,1]**2
        if d.shape[1]==3:squared+=residual[:,2]**2/discount
        selection=np.sqrt(squared)<delta
        selected=d[selection]
        new=np.array([np.mean(selected[:,j].copy()) for j in range(len(shift))]) if len(selected) else np.full(len(shift),np.nan)
        change=new-shift;shift=new;iterations+=1
    return shift,iterations


def _fit_width(x,y,start,upper):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
    if len(x)<3 or not np.isfinite(y).all():raise ValueError('Insufficient finite data for author Gaussian error fit')
    tiny=np.finfo(float).tiny
    def model(p):return p[0]*np.exp(-x*x/(2*max(p[1],tiny)**2))+p[2]
    def jac(p):
        s=max(p[1],tiny);e=np.exp(-x*x/(2*s*s))
        return np.column_stack((e,p[0]*e*x*x/(s**3),np.ones(len(x))))
    # Some vendor SciPy builds do not move bound-valued x0 into the interior.
    # Apply that standard TRF feasibility adjustment explicitly.
    bound_resolution=1e-10
    initial=np.maximum(np.asarray(start,float),bound_resolution)
    initial[1]=min(initial[1],upper-bound_resolution*max(1,upper))
    result=least_squares(lambda p:model(p)-y,initial,jac=jac,
                         bounds=([0.,0.,0.],[np.inf,upper,np.inf]),method='trf',
                         ftol=1e-7,xtol=1e-7,gtol=1e-7,max_nfev=600,x_scale='jac')
    if not result.success:raise ValueError('Author Gaussian fit did not converge in native backend')
    # Treat coefficients within the bound feasibility adjustment as fixed.
    # The solver's termination tolerance is too coarse for deciding the
    # degrees of freedom of the author's confidence interval near zero.
    active=result.x<=bound_resolution
    active[1] |= upper-result.x[1]<=bound_resolution*max(1,upper)
    free=~active;dof=len(y)-int(free.sum());half=np.nan
    if not active[1] and dof>0:
        jj=jac(result.x)[:,free]
        u,s,vh=np.linalg.svd(jj,full_matrices=False)
        if len(s) and (s>np.finfo(float).eps*max(jj.shape)*s[0]).all():
            cov=(vh.T/(s*s))@vh
            se=np.sqrt(np.maximum(np.diag(cov),0)*np.dot(result.fun,result.fun)/dof)
            pos=int(np.flatnonzero(np.flatnonzero(free)==1)[0])
            half=student.ppf(.84,dof)*se[pos]
    return float(result.x[1]),float(half),result.x


def _error(d,shift,delta,rmax,rho,ndata1,ndata2,frameson=None,prec=None,zprec=None):
    dim=d.shape[1]
    radial_input=d if dim==2 else d[np.abs(d[:,2]-shift[2])<delta]
    residual=radial_input[:,:2]-shift[:2]
    r=np.sqrt(residual[:,0]**2+residual[:,1]**2)
    binsize=delta/(10 if (r<delta).sum()<100 else 20)
    edges=colon(0,binsize,rmax)
    count=np.histogram(r,edges)[0].astype(float);mid=(edges[:-1]+edges[1:])*.5
    expected=rho*np.pi*(edges[1:]**2-edges[:-1]**2)
    normalized=count/expected;nb=int(np.floor(delta/binsize))
    baseline=np.median(normalized)
    true=np.sum(count[:nb]-baseline*expected[:nb]);false=np.sum(count[:nb])-true
    if true<0:true=1.
    if false<0:false=0.
    fitstart=[normalized[:nb].max(),delta/2,normalized[:nb].min()]
    width,half,_=_fit_width(mid[:nb],normalized[:nb],fitstart,rmax)
    if np.isnan(half) or half>delta/2:width=delta
    if prec is not None:width=max(width,np.sqrt(2)*prec)
    if len(d)==1:width=np.nan
    on=1. if frameson is None else frameson
    total=true+false
    with np.errstate(divide='ignore',invalid='ignore'):
        if dim==2:
            error=(np.sqrt(2*width*width*true+delta*delta/2*false*on*on)/np.sqrt(2)/total)*(1+false/total)
            return error,width,true,false,np.nan
        false_se=delta/np.sqrt(2)/np.sqrt(false/(on*on)) if false>0 else 0.
        err=np.sqrt((true*width/np.sqrt(true))**2+(false*false_se)**2/2)/true
    # Preserve the author's original index convention: these are indices into
    # r after the axial filter, then applied directly to the original dz array.
    ix=np.flatnonzero(r<delta);zz=np.abs(d[ix,2]-shift[2])
    zstep=20 if len(ix)<100 else (10 if len(ix)<1000 else 5)
    ze=colon(0,zstep,rmax);zc=np.histogram(zz,ze)[0].astype(float);zm=(ze[:-1]+ze[1:])*.5
    depth=d[:,2].max()-d[:,2].min();zrho=ndata1*ndata2/depth if depth else np.inf
    zexpected=zrho*zstep/len(ze);zn=zc/zexpected;zb=int(np.floor(2*delta/zstep))
    if zrho==0 or zb>len(zc):return err,width,true,false,delta
    ztrue=np.sum(zc[:zb]-np.median(zn)*zexpected)
    if ztrue<=0:return err,width,true,false,delta
    zw,zh,_=_fit_width(zm[:zb],zn[:zb],[zn[:zb].max(),delta,np.median(zn)],2*delta)
    if np.isnan(zh) or zh>delta/2:zw=delta
    if zprec is not None:zw=max(zw,np.sqrt(2)*zprec)
    if len(d)==1:zw=np.nan
    return err,width,true,false,zw


def _weighted_solve(a,b,w):
    scale=np.sqrt(w)
    if not np.isfinite(scale).all() or not np.any(scale>0):raise ValueError('Invalid author-derived least-squares weights')
    return lstsq(a*scale[:,None],b*scale[:,None],lapack_driver='gelsy')[0]


def estimate(table,cfg):
    xyz,frames,_=prepare(table,cfg);nf=int(frames.max());dim=xyz.shape[1]
    specs={**DEFAULTS};overrides={**cfg.get('official_options',{}),**cfg.get('parameters',{}).get('meanshift',{})}
    if 'nTimeBin' in cfg:overrides['nTimeBin']=cfg['nTimeBin']
    if set(overrides)-set(DEFAULTS):raise ValueError('Unknown original MeanShift option')
    specs.update(overrides)
    nb=int(mround(specs['nTimeBin']));width=int(np.floor(nf/nb))
    if nb<2 or width<1:raise ValueError('MeanShift requires >=2 nonempty temporal bins')
    starts=mround(1+np.arange(nb)*(nf-width)/(nb-1)).astype(int);ends=np.minimum(nf,starts+width-1)
    groups=[np.column_stack((xyz[(frames>=a)&(frames<=b)],frames[(frames>=a)&(frames<=b)])) for a,b in zip(starts,ends)]
    if any(not len(g) for g in groups):raise ValueError('An original MeanShift alignment bin is empty')
    area=np.ptp(xyz[:,0])*np.ptp(xyz[:,1]);radius=specs['rmax'];broad=specs['delta_broad'];maxiter=specs['maxiter']
    ref=groups[0];auto=_pairs(ref,ref,radius,1,ref[:,-1].max(),100_000_000)
    if not len(auto):raise ValueError('Author MeanShift auto-correlation has no pairs')
    center,_=_iterate(auto,np.zeros(dim),broad,maxiter)
    rho=len(ref)**2/area
    _,auto_width,ntrue,_,zw=_error(auto,center,broad,radius,rho,len(ref),len(ref))
    precision=auto_width/np.sqrt(2);zprecision=zw/np.sqrt(2)
    narrow=precision*specs['delta_narrow_ratio'];on=(ntrue/2)/len(ref)+1
    limit=2*len(auto);shifts=np.zeros((nb,nb,dim));errors=np.zeros((nb,nb));iters=np.zeros((nb,nb),int)
    for i in range(nb-1):
        for j in range(i+1,nb):
            offset=shifts[i,j-1].copy();target=groups[j].copy();target[:,:dim]-=offset
            tmin=groups[i][:,-1].min()-target[:,-1].max()
            pairs=_pairs(groups[i],target,radius,tmin,-tmin,limit)
            start=np.zeros(dim)
            if specs['broadsweep']:
                start,_=_iterate(pairs,start,broad,maxiter)
                if np.isnan(start[0]):start[:]=0
            found,it=_iterate(pairs,start,narrow,maxiter);iters[i,j]=it
            shifts[i,j]=found+offset
            if np.isnan(shifts[i,j,0]):shifts[i,j]=offset
            if specs['calc_error']:
                error,*_=_error(pairs,found,narrow,radius,len(groups[i])*len(target)/area,
                                len(groups[i]),len(target),on,precision,zprecision)
                errors[i,j]=radius if np.isnan(error) else error
    a=[];values=[];weights=[]
    for i in range(nb-1):
        for j in range(i+1,nb):
            row=np.zeros(nb);row[i]=-1;row[j]=1
            a.append(row[1:]);values.append(shifts[i,j]);weights.append(1/errors[i,j]**2 if specs['calc_error'] else 1.)
    a=np.array(a);values=np.array(values);weights=np.array(weights)
    initial=_weighted_solve(a,values,weights);residual=np.linalg.norm(a@initial-values,axis=1)
    # MATLAB sortrows(...,1), then flipud: reverse order also reverses ties.
    order=np.argsort(residual,kind='stable')[::-1];indices=order[residual[order]>specs['outlier_error']].copy()
    original_outliers=len(indices)
    for p in range(len(indices)):
        ix=int(indices[p]);tmp=np.delete(a,ix,axis=0)
        singular=svd(tmp,compute_uv=False,lapack_driver='gesvd')
        if len(singular)==nb-1:
            # The author uses rank(A,1). In the anchored incidence matrix, a
            # mathematically unit singular value can land one ULP either side
            # of 1 and flip an entire row deletion. A/B have exhibited this.
            margin=64*np.finfo(float).eps*max(tmp.shape)*max(1.,singular[0])
            if (singular>=1-margin).all() and np.any(np.abs(singular-1)<=margin):
                raise ParityDomainError('MeanShift rank(A,1) outlier decision is at the floating-point boundary; use A for this dataset. No alternative drift was substituted.')
        if np.count_nonzero(singular>1)==nb-1:
            a=tmp;values=np.delete(values,ix,axis=0);weights=np.delete(weights,ix)
            indices[indices>ix]-=1
    controls=np.vstack((np.zeros(dim),_weighted_solve(a,values,weights)))
    centers=(starts+ends)/2
    curve=interpolate(centers,controls,np.arange(1,nf+1),specs['interp_method'])
    return finite_curve(curve),{'implementation':'native-author-port','upstream':'VeatchLab/Mean-Shift-Drift-Correction',
        'revision':'b04d42f0d099cab9b6cd0c184eb0551a41d6664a','parameters':specs,
        'fitter':'SciPy bounded TRF; analytic Jacobian; explicit stopping tolerances',
        'stages':{'loc_prec_nm':float(precision),'loc_prec_z_nm':float(zprecision) if dim==3 else None,
            'delta_narrow_nm':float(narrow),'nframeson':float(on),'pair_shifts':shifts.tolist(),
            'pair_errors':errors.tolist(),'iterations':iters.tolist(),'control_drift_nm':controls.tolist(),
            'outlier_candidates':original_outliers,'removed_constraints':int(nb*(nb-1)/2-len(a))}}
