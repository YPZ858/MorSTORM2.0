function encoded = base64args(args)
% Legacy Windows JVM launchers narrow command arguments to the ANSI codepage.
% Use ASCII transport and decode UTF-8 inside the bridge JVM.
encoded=cellfun(@(s)matlab.net.base64encode(unicode2native(char(s),'UTF-8')),args,'UniformOutput',false);
end
