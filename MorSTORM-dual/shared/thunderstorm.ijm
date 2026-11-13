// MorSTORM isolated ImageJ batch process. Four UTF-8 lines:
// input TIFF, output CSV, recorder camera options, recorder Run analysis options.
settings = split(File.openAsString(getArgument()), "\n");
if (settings.length < 4) exit("Expected four settings lines");
setBatchMode(true);
open(settings[0]);
run("Camera setup", settings[2]);
run("Run analysis", settings[3]);
run("Export results", "filepath=[" + settings[1] + "] fileformat=[CSV (comma separated)] sigma=true sigma1=true sigma2=true intensity=true chi2=true offset=true saveprotocol=true x=true y=true z=true bkgstd=true id=true uncertainty=true uncertainty_z=true frame=true detections=true");
close("*");
// The enclosing JVM is dedicated to this one job.
eval("script", "java.lang.System.exit(0);");
