import java.util.*;
import java.util.prefs.*;

public class MemPrefs extends AbstractPreferences {
    private final Map<String, String> values = new HashMap<>();
    private final Map<String, MemPrefs> kids = new HashMap<>();

    private MemPrefs(AbstractPreferences parent, String name) { super(parent, name); }

    public static MemPrefs root() { return Holder.ROOT; }
    private static class Holder { static final MemPrefs ROOT = new MemPrefs(null, ""); }

    protected void putSpi(String k, String v) { values.put(k, v); }
    protected String getSpi(String k) {
        if (values.containsKey(k)) return values.get(k);
        if (k != null && k.toLowerCase().contains("update")) return "false";
        return null;
    }
    protected void removeSpi(String k) { values.remove(k); }
    protected void removeNodeSpi() { values.clear(); kids.clear(); }
    protected String[] keysSpi() { return values.keySet().toArray(new String[0]); }
    protected String[] childrenNamesSpi() { return kids.keySet().toArray(new String[0]); }
    protected AbstractPreferences childSpi(String name) {
        return kids.computeIfAbsent(name, n -> new MemPrefs(this, n));
    }
    protected void syncSpi() {}
    protected void flushSpi() {}
}
