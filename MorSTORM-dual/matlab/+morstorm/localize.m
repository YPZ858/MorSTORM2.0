function result = localize(inp, settings, folder)
% Raw TIFF adapters. ThunderSTORM uses an isolated ImageJ JVM; Picasso uses
% the Python upstream adapter in the selected Python environment.
backend=settings.backend; root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
if strcmp(backend,'picasso')
    output=fullfile(folder,'localized.hdf5'); settings.input=inp.path; settings.output=output;
    f=fopen(fullfile(folder,'localization-settings.json'),'w','n','UTF-8');
    assert(f>=0,'Could not write localization settings'); fprintf(f,'%s',jsonencode(settings)); fclose(f);
    assert(isfield(settings,'python_executable'),'Picasso raw localization needs localization.python_executable');
    morstorm.process({settings.python_executable,'-m','morstorm.localize',fullfile(folder,'localization-settings.json')},...
        fullfile(folder,'localization.log'),morstorm.option(settings,'timeout_seconds',3600));
    result=struct('format','picasso','path',output,'pixel_size_nm',settings.pixel_size_nm);
elseif strcmp(backend,'thunderstorm')
    output=fullfile(folder,'localized.csv'); fiji=settings.fiji_dir;
    ij=dir(fullfile(fiji,'jars','ij-*.jar')); thunder=dir(fullfile(fiji,'plugins','*Thunder*STORM*.jar'));
    assert(~isempty(ij)&&~isempty(thunder),'Fiji with Thunder_STORM.jar required');
    % All jars are local to this isolated JVM; the installed ImageJ registers plugins.
    cp=strjoin({fullfile(root,'shared','morstorm-morphology.jar'),fullfile(fiji,'jars','*'),fullfile(thunder(1).folder,thunder(1).name)},pathsep);
    java=morstorm.option(settings,'java_executable','');
    if isempty(java)
        candidates=[dir(fullfile(fiji,'java','**','bin','java.exe'));dir(fullfile(fiji,'java','**','bin','java'))];
        assert(~isempty(candidates),'Set localization.java_executable'); java=fullfile(candidates(end).folder,candidates(end).name);
    end
    lines={strrep(inp.path,'\','/'),strrep(output,'\','/'),settings.camera_options,settings.analysis_options};
    assert(~any(cellfun(@(s)any(contains(s,{newline,char(13)})),lines)),'Macro parameters cannot contain newlines');
    path=fullfile(folder,'thunderstorm-settings.txt'); f=fopen(path,'w','n','UTF-8');
    assert(f>=0,'Could not write ThunderSTORM settings'); fprintf(f,'%s\n',lines{:}); fclose(f);
    encoded=morstorm.base64args({fullfile(root,'shared','thunderstorm.ijm'),path});
    morstorm.process({java,'-Djava.awt.headless=false','-Dfile.encoding=UTF-8',['-Dplugins.dir=',fiji],'-cp',cp,...
        'MorstormThunderstorm','--base64',encoded{:}},...
        fullfile(folder,'localization.log'),morstorm.option(settings,'timeout_seconds',3600));
    result=struct('format','thunderstorm','path',output,'coordinate_unit','nm','frame_base',1);
else
    error('morstorm:Localization','Built-in backend must be picasso or thunderstorm');
end
assert(isfile(result.path),'Localization adapter produced no output; inspect localization.log');
end
