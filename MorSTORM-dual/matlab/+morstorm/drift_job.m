function drift_job(folder)
% File protocol for Python -> the exact same MATLAB author-code dispatcher.
try
    cfg=jsondecode(fileread(fullfile(folder,'config.json')));
    input=load(fullfile(folder,'input.mat'),'localizations'); data=double(input.localizations);
    names={'frame','x_nm','y_nm'}; if size(data,2)==4, names{end+1}='z_nm'; end
    assert(any(size(data,2)==[3,4]),'Expected frame,x_nm,y_nm[,z_nm]');
    t=array2table(data,'VariableNames',names);
    [curve,diagnostics]=morstorm.estimate_drift(t,cfg);
    save(fullfile(folder,'output.mat'),'curve','-v7');
    write_json(fullfile(folder,'diagnostics.json'),diagnostics);
catch err
    write_json(fullfile(folder,'error.json'),struct('identifier',err.identifier,'message',err.message));
    rethrow(err);
end
end
function write_json(path,value)
f=fopen(path,'w','n','UTF-8'); assert(f>=0,'Cannot write drift job status'); cleanup=onCleanup(@()fclose(f));
fprintf(f,'%s',jsonencode(value));
end
