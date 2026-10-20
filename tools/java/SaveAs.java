import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;

/** Round-trip a .circ through Logisim itself: load, then save as. */
public class SaveAs {
    public static void main(String[] args) throws Exception {
        Loader loader = new Loader(null);
        LogisimFile f = loader.openLogisimFile(new java.io.File(args[0]));
        boolean ok = loader.save(f, new java.io.File(args[1]));
        System.out.println("saved=" + ok);
    }
}
