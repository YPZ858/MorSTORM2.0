function [t, metadata] = read_localizations(path, cfg)
% Canonical columns frame/x_nm/y_nm[/z_nm]; frames are 1-based, distances nm.
fmt = morstorm.option(cfg, 'format', 'auto');
[~,~,ext] = fileparts(path);
if strcmp(fmt,'auto')
    if any(strcmpi(ext,{'.hdf5','.h5'})), fmt='picasso'; else, fmt='csv'; end
end
metadata = struct('source',path,'format',fmt);
if strcmp(fmt,'picasso')
    pixel = morstorm.option(cfg,'pixel_size_nm',[]);
    assert(isscalar(pixel) && isfinite(pixel) && pixel>0, 'MATLAB Picasso import requires explicit pixel_size_nm');
    raw = h5read(path,'/locs');
    assert(all(isfield(raw,{'frame','x','y'})), 'Picasso /locs needs frame, x, y');
    t = table(double(raw.frame(:))+1, double(raw.x(:))*pixel, double(raw.y(:))*pixel, ...
        'VariableNames',{'frame','x_nm','y_nm'});
    if isfield(raw,'z'), t.z_nm=double(raw.z(:)); end % Picasso z is already nm
    fields=fieldnames(raw);
    for k=1:numel(fields)
        f=fields{k};
        if ~any(strcmp(f,{'frame','x','y','z'})) && numel(raw.(f))==height(t), t.(f)=raw.(f)(:); end
    end
    metadata.pixel_size_nm=pixel;
else
    assert(any(strcmp(fmt,{'csv','thunderstorm'})), 'Unsupported input format');
    t=readtable(path,'VariableNamingRule','preserve');
    names=t.Properties.VariableNames;
    normalized=regexprep(lower(string(names)),'[^a-z0-9]','');
    targets={'frame','x_nm','y_nm','z_nm'}; aliases={'frame','xnm','ynm','znm'};
    mapping=morstorm.option(cfg,'columns',struct());
    for k=1:numel(targets)
        source=morstorm.option(mapping,targets{k},'');
        if isempty(source), idx=find(normalized==aliases{k},1); else, idx=find(strcmp(names,source),1); assert(~isempty(idx),'Mapped input column missing'); end
        if ~isempty(idx), names{idx}=targets{k}; end
    end
    assert(numel(unique(names))==numel(names),'Duplicate canonical columns');
    t.Properties.VariableNames=names;
    assert(all(ismember({'frame','x_nm','y_nm'},names)), 'Ambiguous CSV: map columns to frame/x_nm/y_nm explicitly');
    unit=morstorm.option(cfg,'coordinate_unit','nm');
    assert(any(strcmp(unit,{'nm','pixel'})),'coordinate_unit must be nm or pixel');
    axes=intersect({'x_nm','y_nm','z_nm'},names,'stable');
    if strcmp(unit,'pixel')
        pixel=morstorm.option(cfg,'pixel_size_nm',[]);
        assert(isscalar(pixel)&&isfinite(pixel)&&pixel>0,'Explicit positive pixel_size_nm required');
        t{:,axes}=double(t{:,axes})*pixel;
    elseif morstorm.option(cfg,'xy_in_pixels',false)
        pixel=morstorm.option(cfg,'pixel_size_nm',[]);
        assert(isscalar(pixel)&&isfinite(pixel)&&pixel>0,'Explicit positive pixel_size_nm required');
        t{:,{'x_nm','y_nm'}}=double(t{:,{'x_nm','y_nm'}})*pixel;
    end
    base=morstorm.option(cfg,'frame_base',1); assert(any(base==[0,1]),'frame_base must be 0 or 1');
    t.frame=double(t.frame)+1-base;
    metadata.pixel_size_nm=morstorm.option(cfg,'pixel_size_nm',[]);
end
axes=intersect({'x_nm','y_nm','z_nm'},t.Properties.VariableNames,'stable');
offset=morstorm.option(cfg,'coordinate_offset_nm',zeros(1,numel(axes)));
assert(numel(offset)==numel(axes)&&all(isfinite(offset)),'coordinate_offset_nm must have one finite value per axis');
t{:,axes}=double(t{:,axes})+reshape(offset,1,[]); metadata.coordinate_offset_nm=reshape(offset,1,[]);
assert(height(t)>0 && all(isfinite(t{:,[{'frame'},axes]}),'all'), 'Empty/nonfinite localizations');
assert(all(t.frame>=1 & t.frame==floor(t.frame)), 'Frames must be positive integers');
ordered=[{'frame'},axes]; t=t(:,[ordered,setdiff(t.Properties.VariableNames,ordered,'stable')]);
end
