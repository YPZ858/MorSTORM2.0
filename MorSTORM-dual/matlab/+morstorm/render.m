function [image, meta] = render(t,cfg)
pixel=morstorm.option(cfg,'pixel_size_nm',10);
assert(isscalar(pixel)&&isfinite(pixel)&&pixel>0,'render.pixel_size_nm must be positive');
xy=t{:,{'x_nm','y_nm'}}; origin=floor(min(xy,[],1)/pixel)*pixel-pixel;
indices=floor((xy-origin)/pixel); dims=max(indices,[],1)+2;
assert(prod(dims)<=morstorm.option(cfg,'max_pixels',100000000),'Rendered image exceeds max_pixels; check units');
image=single(accumarray(indices(:,[2,1])+1,1,[dims(2),dims(1)]));
meta=struct('pixel_size_nm',pixel,'origin_nm',origin,'shape_yx',dims([2,1]),...
    'method','localization-count histogram','dimensions','2D XY projection',...
    'cell_convention','half-open edges; y increases with row');
end
