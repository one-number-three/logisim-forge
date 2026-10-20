import java.util.prefs.*;

public class MemPrefsFactory implements PreferencesFactory {
    public Preferences userRoot() { return MemPrefs.root(); }
    public Preferences systemRoot() { return MemPrefs.root(); }
}
