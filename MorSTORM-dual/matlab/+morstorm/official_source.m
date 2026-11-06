function [folder,meta]=official_source(name,cfg)
% Select and verify an unmodified author release; never fall back to other code.
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
official=morstorm.option(cfg,'official',struct());
deps=morstorm.option(official,'root',fullfile(root,'third_party'));
folder=morstorm.option(official,[name,'_dir'],fullfile(deps,name));
if strcmp(name,'aim'), entryFolder=fullfile(folder,'AIM'); else, entryFolder=folder; end
assert(isfolder(folder),'morstorm:MissingAuthorCode',...
    'Author %s code missing at %s. Run scripts/install_official.ps1 or set drift.official.root.',name,folder);
defaultLock=fullfile(root,'shared','official_sources.lock.json');
if ~isfile(defaultLock), defaultLock=fullfile(root,'official_sources.lock.json'); end
lockFile=morstorm.option(official,'lock_file',defaultLock);
assert(isfile(lockFile),'Author source lock missing: %s',lockFile);
lock=jsondecode(fileread(lockFile)); spec=lock.sources.(name);
verified=morstorm.option(official,'verify_sources',true);
files=spec.files;
for k=1:numel(files)
    filename=fullfile(folder,strrep(files(k).path,'/',filesep));
    assert(isfile(filename),'morstorm:MissingAuthorCode','Author file missing: %s',filename);
    actual=morstorm.sha256(filename);
    if verified
        assert(strcmpi(actual,files(k).sha256),'morstorm:SourceChanged',...
            'Author source hash mismatch: %s. Restore the pinned author release; no reference fallback is available.',filename);
    end
    files(k).sha256=actual;
end
meta=struct('implementation','author-code','source',spec.url,'revision',spec.revision,...
    'source_directory',folder,'source_verified',logical(verified),'source_files',files);
folder=entryFolder;
end
