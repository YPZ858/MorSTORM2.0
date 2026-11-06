function [curve,diagnostics]=estimate_drift(t,cfg)
% All named SMLM algorithms call the original author code. No surrogate fallback.
method=lower(morstorm.option(cfg,'method','none')); cfg.method=method;
assert(all(ismember({'frame','x_nm','y_nm'},t.Properties.VariableNames)),'Canonical frame,x_nm,y_nm columns are required');
axes=intersect({'x_nm','y_nm','z_nm'},t.Properties.VariableNames,'stable');
assert(height(t)>0&&all(isfinite(t{:,[{'frame'},axes]}),'all'),'Empty/nonfinite input');
assert(all(t.frame>=1&t.frame==floor(t.frame)),'Frames must be positive integers');
nf=max(t.frame); dim=numel(axes);
if isfield(cfg,'function')&&isa(cfg.function,'function_handle')
    [curve,diagnostics]=cfg.function(t,cfg);
elseif any(strcmp(method,{'meanshift','npcloud','rrnpcloud','aim'}))
    [curve,diagnostics]=morstorm.official_drift(t,cfg);
elseif strcmp(method,'none')
    curve=zeros(nf,dim); diagnostics=struct('implementation','identity','method',method);
elseif strcmp(method,'external_csv')
    d=readtable(cfg.path); names={'dx_nm','dy_nm'}; if dim==3, names{end+1}='dz_nm'; end
    assert(all(ismember([{'frame'},names],d.Properties.VariableNames)),'External drift columns missing');
    assert(height(d)>=2&&all(isfinite(d{:, [{'frame'},names]}),'all')&&all(diff(d.frame)>0)&&all(d.frame==floor(d.frame)),'Invalid external drift');
    assert(d.frame(1)<=1&&d.frame(end)>=nf,'External drift must cover all frames');
    curve=interp1(d.frame,d{:,names},(1:nf)','linear');
    diagnostics=struct('implementation','external-curve','method',method);
else
    error('morstorm:UnknownEngine','Unknown drift method: %s',method);
end
assert(isequal(size(curve),[nf,dim])&&all(isfinite(curve),'all'),'Drift must be a finite max_frame x D array');
end
