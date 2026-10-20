import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.Wire;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;

public class LoadDump {
    static class DumpLoader extends Loader {
        DumpLoader() { super(null); }
        @Override public void showError(String msg) {
            System.out.println("!! LOADER ERROR: " + msg);
        }
    }

    public static void main(String[] args) throws Exception {
        Loader loader = new DumpLoader();
        LogisimFile f = loader.openLogisimFile(new java.io.File(args[0]));
        if (f == null) { System.out.println("!! null file"); return; }
        System.out.println("LOADED main=" + f.getMainCircuit().getName());
        for (Circuit c : f.getCircuits()) {
            System.out.println("CIRCUIT " + c.getName() + " bounds=" + c.getBounds());
            for (Component comp : c.getNonWires()) {
                System.out.println("  " + comp.getFactory().getName() + " loc=" + comp.getLocation()
                        + " bounds=" + comp.getBounds());
                for (EndData e : comp.getEnds()) {
                    System.out.println("     port " + e.getLocation() + " width=" + e.getWidth()
                            + " in=" + e.isInput() + " out=" + e.isOutput());
                }
                System.out.println("     attrs: " + dumpAttrs(comp.getAttributeSet()));
            }
            for (Wire w : c.getWires()) {
                System.out.println("  WIRE " + w.getEnd0() + " -> " + w.getEnd1());
            }
        }
    }

    static String dumpAttrs(AttributeSet as) {
        StringBuilder sb = new StringBuilder();
        for (Attribute<?> a : as.getAttributes()) {
            sb.append(a.getName()).append("=").append(as.getValue(a)).append("; ");
        }
        return sb.toString();
    }
}
