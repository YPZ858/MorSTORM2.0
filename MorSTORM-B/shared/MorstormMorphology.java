import ij.IJ;
import ij.ImagePlus;
import ij.measure.Calibration;
import ij.measure.ResultsTable;
import ij.plugin.filter.GaussianBlur;
import ij.process.ByteProcessor;
import ij.process.FloatProcessor;
import ij.process.ImageProcessor;
import inra.ijpb.binary.BinaryImages;
import inra.ijpb.measure.region2d.MorphometricFeatures2D;
import inra.ijpb.measure.region2d.MorphometricFeatures2D.Feature;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Shared, headless MorphoLibJ engine. All input/output distances use nm.
 * Usage: density.tif output_dir pixel_nm origin_x origin_y sigma_px threshold
 *        connectivity min_area_nm2 exclude_border coordinates.csv
 * Histogram cell (col,row) covers [origin+index*pixel, origin+(index+1)*pixel).
 */
public final class MorstormMorphology {
    private static void require(boolean ok, String message) {
        if (!ok) throw new IllegalArgumentException(message);
    }
    public static void main(String[] a) {
        // ImageJ progress listeners can start AWT helper threads even headlessly.
        // This is a dedicated CLI process, so terminate after all files are closed.
        try {
            if (a.length > 0 && "--base64".equals(a[0])) {
                String[] decoded = new String[a.length - 1];
                for (int i = 0; i < decoded.length; i++) decoded[i] = new String(Base64.getDecoder().decode(a[i+1]), StandardCharsets.UTF_8);
                a = decoded;
            }
            run(a); System.exit(0);
        }
        catch (Throwable e) { e.printStackTrace(System.err); System.exit(1); }
    }
    static void run(String[] a) throws Exception {
        require(a.length == 11, "Expected 11 arguments; see source header");
        Path out = Paths.get(a[1]); Files.createDirectories(out);
        double pixel = Double.parseDouble(a[2]), ox = Double.parseDouble(a[3]), oy = Double.parseDouble(a[4]);
        double sigma = Double.parseDouble(a[5]), threshold = Double.parseDouble(a[6]), minArea = Double.parseDouble(a[8]);
        int connectivity = Integer.parseInt(a[7]); boolean excludeBorder = Boolean.parseBoolean(a[9]);
        require(Double.isFinite(pixel) && pixel > 0 && Double.isFinite(ox) && Double.isFinite(oy), "Invalid calibration");
        require(Double.isFinite(sigma) && sigma >= 0 && Double.isFinite(threshold) && threshold > 0 && Double.isFinite(minArea) && minArea >= 0, "Invalid segmentation parameters");
        require(connectivity == 4 || connectivity == 8, "Connectivity must be 4 or 8");
        ImagePlus input = IJ.openImage(a[0]);
        require(input != null && input.getStackSize() == 1, "A single XY density image is required");
        FloatProcessor density = input.getProcessor().convertToFloatProcessor();
        int width = density.getWidth(), height = density.getHeight();
        for (int i = 0; i < width * height; i++) require(Float.isFinite(density.getf(i)) && density.getf(i) >= 0, "Invalid density pixel");
        if (sigma > 0) new GaussianBlur().blurGaussian(density, sigma, sigma, 0.0002);
        ByteProcessor mask = new ByteProcessor(width, height);
        for (int i = 0; i < width * height; i++) if (density.getf(i) >= threshold) mask.set(i, 255);
        ImageProcessor labels = BinaryImages.componentsLabeling(mask, connectivity, 32);
        int max = 0;
        for (int i = 0; i < width * height; i++) max = Math.max(max, (int)labels.getf(i));
        require(max < 16777216, "Too many labels for exact float32 label TIFF");
        int[] counts = new int[max + 1]; boolean[] border = new boolean[max + 1];
        for (int y = 0; y < height; y++) for (int x = 0; x < width; x++) {
            int id = (int)labels.getf(x,y); counts[id]++;
            if (x == 0 || y == 0 || x == width-1 || y == height-1) border[id] = true;
        }
        int[] remap = new int[max + 1]; int objects = 0;
        for (int id = 1; id <= max; id++)
            if (counts[id] * pixel * pixel >= minArea && !(excludeBorder && border[id])) remap[id] = ++objects;
        for (int i = 0; i < width * height; i++) {
            int id = remap[(int)labels.getf(i)]; labels.setf(i, id); mask.set(i, id > 0 ? 255 : 0);
        }
        Calibration cal = new Calibration(); cal.pixelWidth = pixel; cal.pixelHeight = pixel; cal.setUnit("nm");
        // TIFF/ImageJ uses origin in pixel indices. MorphoLibJ instead adds
        // xOrigin/yOrigin as physical offsets. Measure with zero origin below,
        // then translate position columns explicitly, keeping TIFF calibration valid.
        cal.xOrigin = -ox / pixel; cal.yOrigin = -oy / pixel;
        ImagePlus labelImage = new ImagePlus("MorSTORM labels", labels); labelImage.setCalibration(cal);
        ImagePlus maskImage = new ImagePlus("MorSTORM mask", mask); maskImage.setCalibration(cal);
        ImagePlus blurred = new ImagePlus("MorSTORM density", density); blurred.setCalibration(cal);
        require(IJ.saveAsTiff(labelImage, out.resolve("labels.tif").toString()), "Could not save label TIFF");
        require(IJ.saveAsTiff(maskImage, out.resolve("mask.tif").toString()), "Could not save mask TIFF");
        require(IJ.saveAsTiff(blurred, out.resolve("density_smoothed.tif").toString()), "Could not save density TIFF");
        long[] locCounts = new long[objects + 1];
        try (BufferedReader r = Files.newBufferedReader(Paths.get(a[10]), StandardCharsets.UTF_8);
             BufferedWriter w = Files.newBufferedWriter(out.resolve("assignments.csv"), StandardCharsets.UTF_8)) {
            require("x_nm,y_nm".equals(r.readLine()), "coordinates.csv needs x_nm,y_nm header");
            w.write("row_id,label\n"); String line; long row = 0;
            while ((line = r.readLine()) != null) {
                String[] xy = line.split(","); require(xy.length == 2, "Invalid coordinate row");
                double x = Double.parseDouble(xy[0]), y = Double.parseDouble(xy[1]);
                require(Double.isFinite(x) && Double.isFinite(y), "Nonfinite coordinate");
                int col = (int)Math.floor((x - ox) / pixel), rr = (int)Math.floor((y - oy) / pixel);
                int id = col >= 0 && col < width && rr >= 0 && rr < height ? (int)labels.getf(col,rr) : 0;
                locCounts[id]++; w.write((++row) + "," + id + "\n");
            }
        }
        if (objects == 0) {
            Files.write(out.resolve("morphology.csv"), "Label,Area,Perimeter,Circularity,Centroid.X,Centroid.Y,Ellipse.Center.X,Ellipse.Center.Y,Ellipse.Radius1,Ellipse.Radius2,Ellipse.Orientation,Ellipse.Elong,MaxFeretDiam,MaxFeretDiamAngle,ObjectLabel,LocalizationCount\n".getBytes(StandardCharsets.UTF_8));
        } else {
            MorphometricFeatures2D features = new MorphometricFeatures2D();
            for (Feature f : new Feature[]{Feature.AREA, Feature.PERIMETER, Feature.CIRCULARITY,
                    Feature.CENTROID, Feature.EQUIVALENT_ELLIPSE, Feature.ELLIPSE_ELONGATION,
                    Feature.MAX_FERET_DIAMETER}) features.add(f);
            ImagePlus measurementImage = new ImagePlus("Measurement labels", labels);
            Calibration local = new Calibration(); local.pixelWidth = pixel; local.pixelHeight = pixel; local.setUnit("nm");
            measurementImage.setCalibration(local);
            ResultsTable result = features.computeTable(measurementImage);
            result.setPrecision(12);
            for (int row = 0; row < result.size(); row++) {
                int id = Integer.parseInt(result.getLabel(row));
                for (String column : new String[]{"Centroid.X", "Ellipse.Center.X"})
                    result.setValue(column, row, result.getValue(column, row) + ox);
                for (String column : new String[]{"Centroid.Y", "Ellipse.Center.Y"})
                    result.setValue(column, row, result.getValue(column, row) + oy);
                result.setValue("ObjectLabel", row, id);
                result.setValue("LocalizationCount", row, locCounts[id]);
            }
            result.save(out.resolve("morphology.csv").toString());
        }
        Properties meta = new Properties();
        meta.setProperty("engine", "MorphoLibJ"); meta.setProperty("dimensions", "2; XY projection");
        meta.setProperty("objects", Integer.toString(objects)); meta.setProperty("unassigned_localizations", Long.toString(locCounts[0]));
        meta.setProperty("pixel_size_nm", Double.toString(pixel)); meta.setProperty("origin_x_nm", Double.toString(ox)); meta.setProperty("origin_y_nm", Double.toString(oy));
        meta.setProperty("area_unit", "nm^2"); meta.setProperty("length_unit", "nm");
        meta.setProperty("morpholibj_source", BinaryImages.class.getProtectionDomain().getCodeSource().getLocation().toString());
        meta.setProperty("imagej_version", IJ.getVersion());
        try (OutputStream f = Files.newOutputStream(out.resolve("morphology.properties"))) { meta.store(f, "MorSTORM shared morphology engine"); }
        System.out.println("MorSTORM: " + objects + " objects; " + locCounts[0] + " unassigned localizations");
    }
}
