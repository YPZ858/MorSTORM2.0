// First six lines: input, CSV output or -, TIFF output or -, camera options,
// export options, renderer options or -. Remaining lines are table operations.
settings = split(File.openAsString(getArgument()), "\n");
setBatchMode(true);
run("Camera setup", settings[3]);
run("Import results", "filepath=[" + settings[0] + "] fileformat=[CSV (comma separated)] startingframe=1 append=false livepreview=false");
for (i = 6; i < settings.length; i++) {
    run("Show results table", settings[i]);
}
if (settings[1] != "-") {
    run("Export results", "filepath=[" + settings[1] + "] fileformat=[CSV (comma separated)] saveprotocol=false " + settings[4]);
}
if (settings[2] != "-") {
    run("Visualization", settings[5]);
    saveAs("Tiff", settings[2]);
}
close("*");
File.saveString("complete", getArgument() + ".done");
eval("script", "java.lang.System.exit(0);");
