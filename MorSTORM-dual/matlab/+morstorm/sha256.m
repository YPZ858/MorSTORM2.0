function value=sha256(filename)
digest=java.security.MessageDigest.getInstance('SHA-256');
f=fopen(filename,'rb'); assert(f>=0,'Cannot read source: %s',filename); cleanup=onCleanup(@()fclose(f));
while ~feof(f), digest.update(fread(f,1024*1024,'*uint8')); end
raw=typecast(digest.digest(),'uint8'); value=lower(reshape(dec2hex(raw,2)',1,[]));
end
