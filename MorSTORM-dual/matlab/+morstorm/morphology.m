function metadata = morphology(folder, rendering, cfg)
% Same Java bridge/JAR and calibration as Python.
fiji=cfg.fiji_dir;
ij=dir(fullfile(fiji,'jars','ij-*.jar'));
morph=dir(fullfile(fiji,'**','MorphoLibJ_*.jar'));
assert(~isempty(ij)&&~isempty(morph),'Fiji with MorphoLibJ required');
% Version-sort numeric components, including ImageJ suffix letters.
ij=latest(ij); morph=latest(morph);
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
jar=fullfile(root,'shared','morstorm-morphology.jar'); assert(isfile(jar),'Build shared/morstorm-morphology.jar first');
cp=strjoin({jar,fullfile(ij.folder,ij.name),fullfile(morph.folder,morph.name)},pathsep);
java=morstorm.option(cfg,'java_executable','');
if isempty(java)
    candidates=[dir(fullfile(fiji,'java','**','bin','java.exe'));dir(fullfile(fiji,'java','**','bin','java'))];
    if isempty(candidates), java='java'; else, java=fullfile(candidates(end).folder,candidates(end).name); end
end
data={fullfile(folder,'density.tif'),folder,num2str(rendering.pixel_size_nm,17),...
    num2str(rendering.origin_nm(1),17),num2str(rendering.origin_nm(2),17),...
    num2str(morstorm.option(cfg,'sigma_px',1),17),num2str(morstorm.option(cfg,'threshold',0.2),17),...
    num2str(morstorm.option(cfg,'connectivity',8)),num2str(morstorm.option(cfg,'min_area_nm2',0),17),...
    lower(char(string(morstorm.option(cfg,'exclude_border',false)))),fullfile(folder,'coordinates.csv')};
encoded=morstorm.base64args(data);
args={java,'-Djava.awt.headless=true','-Dfile.encoding=UTF-8','-cp',cp,'MorstormMorphology','--base64',encoded{:}};
morstorm.process(args,fullfile(folder,'morpholibj.log'),morstorm.option(cfg,'timeout_seconds',600));
metadata=struct('engine','MorphoLibJ','jar',fullfile(morph.folder,morph.name),...
    'imagej_jar',fullfile(ij.folder,ij.name),'bridge',jar,'dimensions','2D XY projection');
end

function result=latest(items)
keys=zeros(numel(items),5); suffix=strings(numel(items),1);
for k=1:numel(items)
    values=regexp(items(k).name,'\d+','match'); values=cellfun(@str2double,values);
    keys(k,1:min(5,numel(values)))=values(1:min(5,numel(values)));
    suffix(k)=string(items(k).name);
end
tbl=table(keys,suffix,(1:numel(items))','VariableNames',{'version','suffix','index'});
tbl=sortrows(tbl,{'version','suffix'}); result=items(tbl.index(end));
end
