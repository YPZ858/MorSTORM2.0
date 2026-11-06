import ij.IJ;
import ij.ImageJ;
import java.util.Base64;
import java.nio.charset.StandardCharsets;

/** ThunderSTORM needs an ImageJ instance for its results-table window.
 * Create that instance without showing the main window, then run the batch macro.
 * A desktop-capable JVM is required; morphology uses a separate headless JVM.
 */
public final class MorstormThunderstorm {
    public static void main(String[] args) {
        try {
            if (args.length == 3 && "--base64".equals(args[0]))
                args = new String[]{new String(Base64.getDecoder().decode(args[1]),StandardCharsets.UTF_8),
                    new String(Base64.getDecoder().decode(args[2]),StandardCharsets.UTF_8)};
            if (args.length != 2) throw new IllegalArgumentException("macro_path settings_path");
            new ImageJ(ImageJ.NO_SHOW);
            IJ.runMacroFile(args[0], args[1]);
            System.exit(0);
        } catch (Throwable e) { e.printStackTrace(System.err); System.exit(1); }
    }
}
