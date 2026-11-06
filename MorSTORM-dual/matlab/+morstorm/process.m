function process(command, logfile, timeoutSeconds)
% Execute an argument array directly; no shell quoting/interpolation.
args = java.util.ArrayList;
for k = 1:numel(command), args.add(java.lang.String(char(command{k}))); end
builder = java.lang.ProcessBuilder(args);
builder.redirectErrorStream(true);
builder.redirectOutput(java.io.File(char(logfile)));
p = builder.start();
finished = p.waitFor(int64(timeoutSeconds), java.util.concurrent.TimeUnit.SECONDS);
if ~finished
    p.destroyForcibly(); error('morstorm:Timeout', 'External process timed out; see %s', logfile);
end
if p.exitValue() ~= 0
    error('morstorm:Process', 'External process exited %d; see %s', p.exitValue(), logfile);
end
end
