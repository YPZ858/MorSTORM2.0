function manifest = run(config,method,outputDir)
% RUN(config struct or JSON filename). Relative paths are beside the JSON file.
base=pwd;
if ischar(config)||isstring(config)
    configPath=char(java.io.File(char(config)).getCanonicalPath());
    base=fileparts(configPath); cfg=jsondecode(fileread(configPath));
else
    cfg=config;
end
if nargin>=2 && ~isempty(method), cfg.drift.method=char(method); end
if nargin>=3 && ~isempty(outputDir), cfg.output_dir=char(outputDir); end
assert(morstorm.option(cfg,'schema_version',1)==1,'Unsupported schema_version');
for item={{'input','path'},{'drift','path'},{'morphology','fiji_dir'},{'localization','fiji_dir'}}
    s=item{1};
    if isfield(cfg,s{1})&&isfield(cfg.(s{1}),s{2})
        cfg.(s{1}).(s{2})=absolute(base,cfg.(s{1}).(s{2}));
    end
end
if isfield(cfg,'drift')&&isfield(cfg.drift,'official')
    for key={'root','meanshift_dir','npcloud_dir','aim_dir','lock_file','work_dir'}
        if isfield(cfg.drift.official,key{1}), cfg.drift.official.(key{1})=absolute(base,cfg.drift.official.(key{1})); end
    end
end
folder=absolute(base,morstorm.option(cfg,'output_dir',fullfile('results','run')));
assert(~isfolder(folder)&&~isfile(folder),'Output directory already exists; choose a new run directory');
mkdir(folder);
safeConfig=cfg;
if isfield(safeConfig,'drift')&&isfield(safeConfig.drift,'function')
    safeConfig.drift.function=func2str(safeConfig.drift.function);
end
manifest=struct('schema_version',1,'morstorm_version','0.5.0rc1','language','matlab',...
    'started_utc',utcnow(),'status','running','config',safeConfig,'matlab_version',version);
save_json(fullfile(folder,'manifest.json'),manifest);
try
    inp=cfg.input; manifest.input_sha256=sha256(inp.path);
    kind=morstorm.option(inp,'kind','localizations');
    assert(any(strcmp(kind,{'localizations','movie'})),'input.kind must be localizations or movie');
    if strcmp(kind,'movie')
        loc=cfg.localization; backend=morstorm.option(loc,'backend','');
        assert(any(strcmp(backend,{'picasso','thunderstorm','custom'})),'Unknown localization backend');
        if ~isfield(loc,'command')
            result=morstorm.localize(inp,loc,folder);
            fields=fieldnames(result);
            for k=1:numel(fields), inp.(fields{k})=result.(fields{k}); end
        else
        name=morstorm.option(loc,'output_filename','localized.csv');
        assert(~contains(name,{'/','\'}) && ~any(strcmp(name,{'.','..'})),'output_filename must be a filename');
        localized=fullfile(folder,name); args=cellstr(string(loc.command));
        args=cellfun(@(a)strrep(strrep(a,'{input}',inp.path),'{output}',localized),args,'UniformOutput',false);
        morstorm.process(args,fullfile(folder,'localization.log'),morstorm.option(loc,'timeout_seconds',3600));
        assert(isfile(localized),'Localization command did not produce {output}');
        result=morstorm.option(loc,'result',struct()); fields=fieldnames(result);
        for k=1:numel(fields), inp.(fields{k})=result.(fields{k}); end
        inp.path=localized;
        end
    end
    [t,metadata]=morstorm.read_localizations(inp.path,inp);
    driftCfg=morstorm.option(cfg,'drift',struct());
    if ~isfield(driftCfg,'pixel_size_nm'), driftCfg.pixel_size_nm=morstorm.option(metadata,'pixel_size_nm',[]); end
    [curve,diagnostics]=morstorm.estimate_drift(t,driftCfg);
    axes=intersect({'x_nm','y_nm','z_nm'},t.Properties.VariableNames,'stable');
    t{:,axes}=double(t{:,axes})-curve(t.frame,:);
    writetable(t,fullfile(folder,'corrected.csv'));
    thunder=t(:,[{'frame'},axes]);
    thunder.Properties.VariableNames=[{'frame'},cellfun(@(a)[a(1),' [nm]'],axes,'UniformOutput',false)];
    writetable(thunder,fullfile(folder,'thunderstorm.csv'));
    if strcmp(metadata.format,'picasso'), morstorm.write_picasso(t,metadata,folder); end
    d=array2table([(1:size(curve,1))',curve],'VariableNames',[{'frame'},strcat('d',axes)]);
    writetable(d,fullfile(folder,'drift.csv'));
    [image,rendering]=morstorm.render(t,morstorm.option(cfg,'render',struct()));
    morstorm.write_tiff(fullfile(folder,'density.tif'),image);
    writetable(t(:,{'x_nm','y_nm'}),fullfile(folder,'coordinates.csv'));
    save_json(fullfile(folder,'render.json'),rendering);
    manifest.localizations=height(t); manifest.input_metadata=metadata;
    manifest.drift=diagnostics; manifest.render=rendering;
    morphCfg=morstorm.option(cfg,'morphology',struct());
    if morstorm.option(morphCfg,'enabled',true)
        manifest.morphology=morstorm.morphology(folder,rendering,morphCfg); manifest.status='complete';
    else
        manifest.status='preprocessing_only';
    end
    files=[dir(fullfile(folder,'*.csv'));dir(fullfile(folder,'*.tif'))]; hashes=struct();
    for k=1:numel(files), hashes.(matlab.lang.makeValidName(files(k).name))=sha256(fullfile(folder,files(k).name)); end
    manifest.output_sha256=hashes;
catch err
    manifest.status='failed'; manifest.error=err.message; manifest.finished_utc=utcnow();
    save_json(fullfile(folder,'manifest.json'),manifest); rethrow(err);
end
manifest.finished_utc=utcnow(); save_json(fullfile(folder,'manifest.json'),manifest);
end

function p=absolute(base,p)
p=char(p); if ~java.io.File(p).isAbsolute(), p=fullfile(base,p); end
p=char(java.io.File(p).getCanonicalPath());
end
function value=utcnow()
value=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss''Z'''));
end
function save_json(path,value)
f=fopen(path,'w','n','UTF-8'); assert(f>=0,'Could not write manifest'); cleanup=onCleanup(@()fclose(f));
fprintf(f,'%s',jsonencode(value));
end
function value=sha256(path)
digest=java.security.MessageDigest.getInstance('SHA-256');
f=fopen(path,'rb'); assert(f>=0,'Could not read input'); cleanup=onCleanup(@()fclose(f));
while ~feof(f), digest.update(fread(f,1024*1024,'*uint8')); end
raw=typecast(digest.digest(),'uint8'); value=lower(reshape(dec2hex(raw,2)',1,[]));
end
