function morstorm_gui_stages(path)
% Invoke the released A MATLAB functions for only the requested modules.
cfg = jsondecode(fileread(path));
folder = cfg.output_dir;
inp = cfg.input;
loaded = false;
result = struct();
for k = 1:numel(cfg.modules)
    module = cfg.modules{k};
    fprintf('::morstorm-stage::%s\n', module);
    if strcmp(module, 'localize')
        if isfield(cfg, 'crop_applied'), inp.path = cfg.crop_applied.working_tiff; end
        localized = morstorm.localize(inp, cfg.localization, folder);
        if isfield(cfg, 'crop_applied')
            morstorm.process({cfg.table_python,fullfile(fileparts(mfilename('fullpath')),'raw_crop.py'), ...
                path,localized.path},fullfile(folder,'crop-coordinates.log'),600);
        end
        fields = fieldnames(localized);
        for i = 1:numel(fields)
            name = fields{i};
            inp.(name) = localized.(name);
        end
        [~,name,extension] = fileparts(inp.path);
        result.localization = struct('backend',cfg.localization.backend,'output',[name extension]);
    end
    if any(strcmp(module, {'postfit','reconstruct'}))
        inputFile = fullfile(folder,[module '-source.json']);
        save_json(inputFile,inp);
        morstorm.process({cfg.table_python,fullfile(fileparts(mfilename('fullpath')),'table_stages.py'), ...
            module,inputFile,path,folder},fullfile(folder,[module '-worker.log']),3700);
        stage = jsondecode(fileread(fullfile(folder,[module '-result.json'])));
        inp = stage.input;
        result.(module) = stage.metadata;
        if strcmp(module, 'postfit'), loaded = false; end
    end
    if ~loaded
        [t, metadata] = morstorm.read_localizations(inp.path, inp);
        axes = intersect({'x_nm','y_nm','z_nm'}, t.Properties.VariableNames, 'stable');
        loaded = true;
    end
    if strcmp(module, 'drift')
        [curve, result.drift] = morstorm.estimate_drift(t, cfg.drift);
        t{:,axes} = double(t{:,axes}) - curve(t.frame,:);
        writetable(t, fullfile(folder,'corrected.csv'));
        thunder = t(:,[{'frame'},axes]);
        thunder.Properties.VariableNames = [{'frame'},cellfun(@(a)[a(1),' [nm]'],axes,'UniformOutput',false)];
        writetable(thunder, fullfile(folder,'thunderstorm.csv'));
        if strcmp(metadata.format,'picasso')
            morstorm.write_picasso(t,metadata,folder);
            inp = struct('path',fullfile(folder,'picasso_corrected.hdf5'),'format','picasso', ...
                'pixel_size_nm',cfg.drift.pixel_size_nm);
        else
            inp = struct('path',fullfile(folder,'corrected.csv'),'format','csv', ...
                'pixel_size_nm',cfg.drift.pixel_size_nm);
        end
        drift = array2table([(1:size(curve,1))',curve], 'VariableNames',[{'frame'},strcat('d',axes)]);
        writetable(drift,fullfile(folder,'drift.csv'));
    elseif strcmp(module, 'morphology')
        [image, rendering] = morstorm.render(t,cfg.render);
        morstorm.write_tiff(fullfile(folder,'density.tif'),image);
        writetable(t(:,{'x_nm','y_nm'}),fullfile(folder,'coordinates.csv'));
        save_json(fullfile(folder,'render.json'),rendering);
        result.render = rendering;
        result.morphology = morstorm.morphology(folder,rendering,cfg.morphology);
    end
end
result.localizations = height(t);
result.last_frame = max(t.frame);
save_json(fullfile(folder,'stage-result.json'),result);
end

function save_json(path,value)
f = fopen(path,'w','n','UTF-8');
assert(f>=0,'Could not open %s',path);
close_file = onCleanup(@()fclose(f));
fprintf(f,'%s',jsonencode(value));
end
