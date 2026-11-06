function [curve,diagnostics]=official_meanshift(t,cfg)
% Compatibility alias: uses the same pinned author dispatcher as method=meanshift.
cfg.method='meanshift'; [curve,diagnostics]=morstorm.official_drift(t,cfg);
end
