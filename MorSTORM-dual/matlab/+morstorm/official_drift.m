function [curve,diagnostics]=official_drift(t,cfg)
% Direct calls to pinned author MATLAB releases, with format/unit conversion.
% Algorithm bodies, interpolation, weights and returned drift zero points are
% unchanged. Python delegates to this same function through a MATLAB batch job.
method=lower(cfg.method); sourceName=method;
if strcmp(method,'rrnpcloud'), sourceName='npcloud'; end
assert(any(strcmp(sourceName,{'meanshift','npcloud','aim'})),'Unknown author algorithm');
[folder,diagnostics]=morstorm.official_source(sourceName,cfg);
old=path; restore=onCleanup(@()path(old));
axes=intersect({'x_nm','y_nm','z_nm'},t.Properties.VariableNames,'stable');
sorted=sortrows(t,'frame'); frames=double(sorted.frame); xyz=double(sorted{:,axes});
nf=max(frames); first=min(frames); dim=numel(axes);
assert(first==1,'morstorm:FrameOrigin','Author adapters require the first localized frame to be 1; reindex frames explicitly before calling.');
assert(nf<=double(intmax('int32')),'Frames exceed the NP-Cloud author int32 representation');
segment=morstorm.option(cfg,'segment_frames',100);
assert(isscalar(segment)&&isfinite(segment)&&segment>=1&&segment==floor(segment),'segment_frames must be a positive integer');
parameters=morstorm.option(cfg,'parameters',struct()); opts=morstorm.option(parameters,sourceName,struct());
if strcmp(method,'meanshift')
    addpath(folder,'-begin');
    clear compute_drift_2D compute_drift_3D drift_default_meanshift Fcrosspairs Fcrosspairs_3D
    specs=drift_default_meanshift();
    legacy=morstorm.option(cfg,'official_options',struct()); fields=fieldnames(legacy);
    for k=1:numel(fields), opts.(fields{k})=legacy.(fields{k}); end
    if isfield(cfg,'nTimeBin'), opts.nTimeBin=cfg.nTimeBin; end
    fields=fieldnames(opts);
    for k=1:numel(fields)
        assert(isfield(specs,fields{k}),'Unknown author MeanShift option: %s',fields{k});
        specs.(fields{k})=opts.(fields{k});
    end
    nb=specs.nTimeBin;
    assert(isscalar(nb)&&nb>=2&&nb==floor(nb)&&nb<=nf,'MeanShift nTimeBin must be an integer in 2..max_frame');
    starts=round(1+(0:nb-1)*(nf-floor(nf/nb))/(nb-1)); ends=min(nf,starts+floor(nf/nb)-1);
    for k=1:nb, assert(any(frames>=starts(k)&frames<=ends(k)),'MeanShift author alignment bin is empty'); end
    if dim==2, entry='compute_drift_2D'; mexEntry='Fcrosspairs'; else, entry='compute_drift_3D'; mexEntry='Fcrosspairs_3D'; end
    verify_entry(entry,fullfile(folder,[entry,'.m']));
    assert(exist(mexEntry,'file')==3,'morstorm:MissingMex',...
        'Author %s.%s is required. Compile the original C file using MATLAB mex or install the author platform binary.',mexEntry,mexext);
    data=[xyz,frames];
    [~,info]=feval(entry,data,specs);
    curve=[double(info.xinterp(:)),double(info.yinterp(:))];
    if dim==3, curve(:,3)=double(info.zinterp(:)); end
    diagnostics.parameters=specs; diagnostics.entry_point=entry;
    diagnostics.binwidth_frames=info.binwidth;
elseif strcmp(sourceName,'npcloud')
    if dim==2, sub='Codes_2D'; entry='NPC_RRNPC_CallFunction'; else, sub='Codes_3D'; entry='NPC_RRNPC_3D_CallFunction'; end
    code=fullfile(folder,sub); addpath(code,'-begin');
    clear NPC_RRNPC_CallFunction NPC_RRNPC_3D_CallFunction NP_Cloud_NoSort NP_Cloud_NoSort_3D_Pass1 NP_Cloud_NoSort_3D_Pass2
    verify_entry(entry,fullfile(code,[entry,'.m']));
    pixel=morstorm.option(cfg,'pixel_size_nm',[]);
    assert(isscalar(pixel)&&isfinite(pixel)&&pixel>0,'NP-Cloud requires the actual camera pixel_size_nm');
    allowed={'MaxSearchRadius_Pix1','MaxSearchRadius_Pix2','ReSampleFold','TolZnm','TolZnm2'};
    assert(all(ismember(fieldnames(opts),allowed)),'Unknown NP-Cloud author option');
    r1=0.3; r2=0.225; if dim==3, r1=0.35; r2=0.28; end
    if isfield(cfg,'radius_nm'), r1=cfg.radius_nm/pixel; r2=0.75*r1; end
    r1=morstorm.option(opts,'MaxSearchRadius_Pix1',r1); r2=morstorm.option(opts,'MaxSearchRadius_Pix2',r2);
    fold=morstorm.option(opts,'ReSampleFold',12); z1=morstorm.option(opts,'TolZnm',110); z2=morstorm.option(opts,'TolZnm2',90);
    assert(all(isfinite([r1,r2,fold,z1,z2]))&&all([r1,r2,fold,z1,z2]>0),'NP-Cloud author options must be positive');
    count=double(int32((nf-first)/segment)); centers=(first+(segment-1)/2):segment:nf;
    assert(count>=2&&numel(centers)==count,'morstorm:AuthorSegmentation',...
        'This segment_frames produces incompatible segment counts in the pinned NP-Cloud release. Choose another segment size.');
    assert(round(count/fold)>=1,'morstorm:AuthorResample','Author ReSampleFold would produce a zero sample step; lower ReSampleFold or use more segments.');
    for k=1:count, assert(any(frames>=first+(k-1)*segment&frames<first+k*segment),'NP-Cloud author temporal segment is empty'); end
    x=single(xyz(:,1)/pixel); y=single(xyz(:,2)/pixel); f=int32(frames);
    if dim==2
        [~,~,x1,y1,x2,y2,time1,time2]=NPC_RRNPC_CallFunction(x,y,f,segment,r1,r2,fold);
        firstCurve=[double(x1)*pixel,double(y1)*pixel]; totalCurve=[double(x2)*pixel,double(y2)*pixel];
    else
        [~,~,~,x1,y1,zz1,x2,y2,zz2,time1,time2]=NPC_RRNPC_3D_CallFunction(x,y,single(xyz(:,3)),f,segment,r1,r2,z1,z2,fold);
        firstCurve=[double(x1)*pixel,double(y1)*pixel,double(zz1)];
        totalCurve=[double(x2)*pixel,double(y2)*pixel,double(zz2)];
    end
    if strcmp(method,'npcloud'), curve=firstCurve; selected='first_pass'; else, curve=totalCurve; selected='author_total_second_pass'; end
    diagnostics.parameters=struct('DC_SegmentSize',segment,'MaxSearchRadius_Pix1',r1,...
        'MaxSearchRadius_Pix2',r2,'ReSampleFold',fold,'TolZnm',z1,'TolZnm2',z2,'pixel_size_nm',pixel);
    diagnostics.entry_point=entry; diagnostics.selected_output=selected;
    diagnostics.author_runtime_seconds=struct('npcloud',time1,'rrnpcloud_total',time2);
else
    addpath(folder,'-begin'); clear AIM IntersectionMax IntersectionMaxZ PointIntersect1D PointIntersect2D
    verify_entry('AIM',fullfile(folder,'AIM.m'));
    assert(isempty(fieldnames(opts)),'Pinned AIM exposes only trackInterval; set segment_frames and keep parameters.aim empty');
    assert(~isfield(cfg,'intersect_nm')||cfg.intersect_nm==20,'Author AIM fixes intersection distance at 20 nm; this option cannot change the original source');
    assert(~isfield(cfg,'radius_nm')||cfg.radius_nm==60,'Author AIM fixes local search radius at 60 nm');
    assert(mod(nf,segment)==0&&nf/segment>=2,'morstorm:AuthorTail',...
        'Pinned AIM clips/reindexes incomplete tail segments. Choose segment_frames that divides max_frame, with at least 2 segments; no frames are silently changed.');
    for k=1:nf/segment, assert(any(frames>(k-1)*segment&frames<=k*segment),'AIM author temporal segment is empty'); end
    assert(exist('PointIntersect2D','file')==3,'morstorm:MissingMex','Author PointIntersect2D.%s is required for this platform',mexext);
    if dim==3, assert(exist('PointIntersect1D','file')==3,'Author PointIntersect1D platform binary is missing'); end
    [~,drift]=AIM([frames,xyz/100],segment);
    curve=double(drift)*100;
    diagnostics.entry_point='AIM'; diagnostics.parameters=struct('trackInterval',segment,...
        'author_coordinate_unit_nm',100,'IntersectD',0.2,'roiR',3);
end
assert(isequal(size(curve),[nf,dim])&&all(isfinite(curve),'all'),...
    'morstorm:AuthorOutput','Author code returned invalid/nonfinite drift; inspect data and author parameters.');
diagnostics.method=method; diagnostics.output_unit='nm';
diagnostics.zero_point='unchanged from author return value'; diagnostics.input_sorted_by_frame=true;
end

function verify_entry(name,expected)
actual=which(name);
assert(strcmp(char(java.io.File(actual).getCanonicalPath()),char(java.io.File(expected).getCanonicalPath())),...
    'morstorm:ShadowedAuthor','A different %s is shadowing the pinned author source: %s',name,actual);
end
