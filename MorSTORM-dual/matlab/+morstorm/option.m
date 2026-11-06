function value = option(config, name, fallback)
% Read a field without substituting for an explicitly empty value.
if isfield(config, name), value = config.(name); else, value = fallback; end
end
