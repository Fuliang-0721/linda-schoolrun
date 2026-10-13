package com.acooldog.toolbox.config;
import android.content.Context;
import android.content.SharedPreferences;
import java.util.UUID;

/** User-controlled reporting preferences, enabled by default. */
public final class TelemetryStore {
    private final SharedPreferences prefs;
    public TelemetryStore(Context context) { prefs = context.getApplicationContext().getSharedPreferences("client_telemetry", Context.MODE_PRIVATE); }
    public boolean reviewed() { return prefs.getBoolean("reviewed", false); }
    public boolean enabled() { return prefs.getBoolean("enabled", true); }
    public boolean locationEnabled() { return prefs.getBoolean("location", true); }
    public boolean crashEnabled() { return prefs.getBoolean("crash", true); }
    public boolean reportingEnabled() { return enabled() || locationEnabled(); }
    public boolean erasePending() { return prefs.getBoolean("erase_pending", false); }
    public boolean logsErasePending() { return prefs.getBoolean("logs_erase_pending", false); }
    public long consentVersion() { return prefs.getLong("consent_version", 0); }
    public void saveConsent(boolean enabled, boolean location) { saveConsent(enabled, location, crashEnabled()); }
    public void saveConsent(boolean enabled, boolean location, boolean crash) {
        synchronized (TelemetryStore.class) {
            SharedPreferences.Editor e = prefs.edit().putBoolean("reviewed", true)
                    .putBoolean("enabled", enabled).putBoolean("location", location).putBoolean("crash", crash)
                    .putLong("consent_version", consentVersion()+1);
            if (!enabled || !location) e.putBoolean("erase_pending", true);
            if (!crash) e.putBoolean("logs_erase_pending", true);
            e.apply();
        }
    }
    public void requestErase() { synchronized (TelemetryStore.class) {
        prefs.edit().putBoolean("erase_pending", true).putBoolean("logs_erase_pending", true)
                .putLong("consent_version", consentVersion()+1).apply();
    } }
    public boolean beginSending() { synchronized (TelemetryStore.class) {
        if (!reportingEnabled()) return false;
        prefs.edit().putBoolean("ever_sent", true).apply(); return true;
    } }
    public void erased(long version) { synchronized (TelemetryStore.class) {
        if (version == consentVersion()) prefs.edit().putBoolean("erase_pending", false).apply();
    } }
    public void logsErased(long version) { synchronized (TelemetryStore.class) {
        if (version == consentVersion()) prefs.edit().putBoolean("logs_erase_pending", false).apply();
    } }
    public String token() { synchronized (TelemetryStore.class) {
        String token = prefs.getString("token", "");
        if (token.isEmpty()) { token = (UUID.randomUUID().toString()+UUID.randomUUID()).replace("-", ""); prefs.edit().putString("token", token).apply(); }
        return token;
    } }
    public long value(String key) { return prefs.getLong(key, 0); }
    public long increment(String key, long amount) { synchronized (TelemetryStore.class) {
        long value = value(key)+Math.max(0, amount); prefs.edit().putLong(key, value).apply(); return value;
    } }
}
