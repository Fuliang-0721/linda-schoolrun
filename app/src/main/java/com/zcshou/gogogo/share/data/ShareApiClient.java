package com.acooldog.toolbox.share.data;

import android.text.TextUtils;

import androidx.annotation.NonNull;

import com.acooldog.toolbox.BuildConfig;
import com.acooldog.toolbox.share.domain.model.AppClientConfig;
import com.acooldog.toolbox.route.domain.model.CloudRouteInfo;
import com.acooldog.toolbox.route.domain.model.RoutePoint;
import com.acooldog.toolbox.update.domain.model.AppReleaseHistoryEntry;
import com.acooldog.toolbox.update.domain.model.AppVersionInfo;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * 仅保留「客户端配置」这一条接口：启动时拉取使用说明文案与**远程关闭开关**。
 * v0.94 起共享路线 / 使用技巧 / 上传下载等接口已全部移除。
 */
public final class ShareApiClient {
    private static final MediaType MEDIA_TYPE_JSON = MediaType.parse("application/json; charset=utf-8");

    private final OkHttpClient okHttpClient;
    private final HttpUrl baseUrl;
    private android.content.Context context;

    public ShareApiClient(android.content.Context context) throws IOException {
        this();
        this.context = context;
    }

    public void login(String username, String password) throws IOException {
        try {
            JSONObject payload = new JSONObject().put("username", username).put("password", password)
                    .put("deviceId", new com.acooldog.toolbox.config.AppUpdateStore(context).getInstallId())
                    .put("deviceName", "").put("appVariant", "internal");
            JSONObject result = executeObject(new Request.Builder().url(buildUrl("api/auth/login"))
                    .post(RequestBody.create(MEDIA_TYPE_JSON, payload.toString())).build());
            JSONObject a = result.getJSONObject("account");
            String token = result.getString("token");
            if (token.isEmpty() || !"active".equals(a.getString("status"))) throw new IOException("无效登录响应");
            new com.acooldog.toolbox.config.InternalAuthStore(context).saveSession(token,
                    new com.acooldog.toolbox.share.domain.model.InternalAccountProfile(a.getString("id"),
                            a.getString("username"), a.optString("remark"), a.optString("testerType"),
                            a.optString("testerTypeLabel"), a.getString("status")));
            com.acooldog.toolbox.config.RemoteAccessGate.invalidate(context);
        } catch (JSONException e) { throw new IOException("登录响应无效", e); }
    }


    public ShareApiClient() throws IOException {
        this(BuildConfig.SHARE_API_BASE_URL);
    }

    ShareApiClient(String configuredBaseUrl) throws IOException {
        okHttpClient = new OkHttpClient.Builder()
                .followRedirects(false)
                .followSslRedirects(false)
                .callTimeout(8L, TimeUnit.SECONDS)
                .connectTimeout(5L, TimeUnit.SECONDS)
                .readTimeout(20L, TimeUnit.SECONDS)
                .writeTimeout(20L, TimeUnit.SECONDS)
                .build();
        baseUrl = parseBaseUrl(configuredBaseUrl);
    }

    public void eraseDeviceLogs(JSONObject identity) throws IOException {
        if (baseUrl == null || !baseUrl.isHttps()) throw new IOException("日志清除仅支持 HTTPS");
        executeRequest(new Request.Builder().url(buildUrl("api/app-logs/device/erase"))
                .post(RequestBody.create(MEDIA_TYPE_JSON, identity.toString())).build());
    }
    public void sendTelemetry(JSONObject payload, boolean erase) throws IOException {
        if (baseUrl == null || !baseUrl.isHttps()) throw new IOException("客户端统计仅支持 HTTPS");
        Request request = new Request.Builder().url(buildUrl(erase ? "api/client-telemetry/erase" : "api/client-telemetry"))
                .post(RequestBody.create(MEDIA_TYPE_JSON, payload.toString())).build();
        try (Response response = okHttpClient.newBuilder().followRedirects(false)
                .followSslRedirects(false).callTimeout(15, TimeUnit.SECONDS).build().newCall(request).execute()) {
            if (!response.isSuccessful()) throw new IOException("统计请求失败：HTTP " + response.code());
        }
    }

    public AppClientConfig getAppClientConfig() throws IOException {
        return getAppClientConfig("");
    }

    /** 启动配置；channel=internal 时服务端只对公开渠道生效的停止策略不会命中。 */
    public AppClientConfig getAppClientConfig(String channel) throws IOException {
        HttpUrl.Builder builder = buildUrl("api/client-config").newBuilder();
        if (channel != null && !channel.trim().isEmpty()) {
            builder.addQueryParameter("channel", channel.trim());
        }
        Request request = new Request.Builder()
                .url(builder.build())
                .get()
                .build();
        return parseAppClientConfig(executeObject(request));
    }

    /** 自动更新：查询服务端版本。 */
    public AppVersionInfo getAppVersionInfo(
            String packageName,
            String channel,
            int versionCode,
            String abi,
            String installId
    ) throws IOException {
        HttpUrl.Builder builder = buildUrl("api/app/version").newBuilder()
                .addQueryParameter("package", packageName)
                .addQueryParameter("channel", channel)
                .addQueryParameter("versionCode", String.valueOf(versionCode));
        if (!TextUtils.isEmpty(abi)) {
            builder.addQueryParameter("abi", abi);
        }
        if (!TextUtils.isEmpty(installId)) {
            builder.addQueryParameter("installId", installId);
        }

        Request request = new Request.Builder().url(builder.build()).get().build();
        JSONObject jsonObject = executeObject(request);
        return new AppVersionInfo(
                optBoolean(jsonObject, "update"),
                optBoolean(jsonObject, "force"),
                optInt(jsonObject, "versionCode"),
                optString(jsonObject, "versionName"),
                optInt(jsonObject, "minSupportedVersionCode"),
                optLong(jsonObject, "sizeBytes"),
                optString(jsonObject, "sha256"),
                optString(jsonObject, "downloadUrl"),
                optStringList(jsonObject, "mirrorUrls"),
                optString(jsonObject, "changelog"),
                optString(jsonObject, "packageName"),
                optString(jsonObject, "abi"),
                optInt(jsonObject, "rolloutPercent"),
                optLong(jsonObject, "publishedAt")
        );
    }

    /** 云端路线列表（公开接口 /api/shared/routes）。 */
    public java.util.List<CloudRouteInfo> getCloudRoutes() throws IOException {
        Request request = new Request.Builder().url(buildUrl("api/shared/routes")).get().build();
        java.util.List<CloudRouteInfo> routes = new java.util.ArrayList<>();
        try {
            JSONArray items = new JSONObject(executeRequest(request)).optJSONArray("items");
            if (items == null) {
                return routes;
            }
            for (int index = 0; index < items.length(); index++) {
                JSONObject item = items.optJSONObject(index);
                if (item == null) {
                    continue;
                }
                routes.add(new CloudRouteInfo(
                        optString(item, "id"),
                        optString(item, "name"),
                        optInt(item, "pointCount"),
                        optLong(item, "createdAt")
                ));
            }
        } catch (JSONException exception) {
            throw new IOException("云端路线解析失败", exception);
        }
        return routes;
    }

    /** 云端路线点位（公开接口 /api/shared/routes/{id}）。 */
    public java.util.List<RoutePoint> getCloudRoutePoints(String routeId) throws IOException {
        HttpUrl url = buildUrl("api/shared/routes").newBuilder().addPathSegment(routeId).build();
        Request request = new Request.Builder().url(url).get().build();
        java.util.List<RoutePoint> points = new java.util.ArrayList<>();
        try {
            JSONObject root = new JSONObject(executeRequest(request));
            JSONObject data = root.optJSONObject("data");
            JSONArray items = data == null ? null : data.optJSONArray("points");
            if (items == null) {
                return points;
            }
            for (int index = 0; index < items.length(); index++) {
                JSONObject item = items.optJSONObject(index);
                if (item == null) {
                    continue;
                }
                points.add(new RoutePoint(
                        optDouble(item, "bdLongitude"),
                        optDouble(item, "bdLatitude"),
                        optDouble(item, "wgsLongitude"),
                        optDouble(item, "wgsLatitude"),
                        optDouble(item, "altitude")
                ));
            }
        } catch (JSONException exception) {
            throw new IOException("云端路线点位解析失败", exception);
        }
        return points;
    }

    private double optDouble(@NonNull JSONObject jsonObject, String... keys) {
        for (String key : keys) {
            if (jsonObject.has(key) && !jsonObject.isNull(key)) {
                return jsonObject.optDouble(key, 0d);
            }
        }
        return 0d;
    }

    /** 上报运行日志（崩溃现场 / 手动反馈），返回服务端日志编号。 */
    public String uploadDeviceLog(
            String installId,
            String versionName,
            int versionCode,
            String deviceModel,
            int androidSdk,
            String reason,
            String logText
    ) throws IOException {
        JSONObject payload = new JSONObject();
        try {
            payload.put("installId", installId == null ? "" : installId);
            payload.put("token", new com.acooldog.toolbox.config.TelemetryStore(context).token());
            payload.put("versionName", versionName == null ? "" : versionName);
            payload.put("versionCode", versionCode);
            payload.put("deviceModel", deviceModel == null ? "" : deviceModel);
            payload.put("androidSdk", androidSdk);
            payload.put("reason", reason == null || reason.isEmpty() ? "manual" : reason);
            payload.put("logText", logText == null ? "" : logText);
        } catch (JSONException exception) {
            throw new IOException("日志打包失败", exception);
        }

        Request request = new Request.Builder()
                .url(buildUrl("api/app-logs/device"))
                .post(RequestBody.create(payload.toString(), MEDIA_TYPE_JSON))
                .build();
        try {
            JSONObject data = new JSONObject(executeRequest(request)).optJSONObject("data");
            return data == null ? "" : optString(data, "id");
        } catch (JSONException exception) {
            throw new IOException("日志上传响应解析失败", exception);
        }
    }

    /** 更新记录（公开接口 /api/app/releases）。 */
    public java.util.List<AppReleaseHistoryEntry> getAppReleaseHistory(String packageName, int limit)
            throws IOException {
        HttpUrl url = buildUrl("api/app/releases").newBuilder()
                .addQueryParameter("package", packageName)
                .addQueryParameter("limit", String.valueOf(limit))
                .build();
        Request request = new Request.Builder().url(url).get().build();

        java.util.List<AppReleaseHistoryEntry> entries = new java.util.ArrayList<>();
        try {
            JSONObject root = new JSONObject(executeRequest(request));
            JSONArray items = root.optJSONArray("items");
            if (items == null) {
                JSONObject data = root.optJSONObject("data");
                if (data != null) {
                    items = data.optJSONArray("items");
                }
            }
            if (items == null) {
                return entries;
            }
            for (int index = 0; index < items.length(); index++) {
                JSONObject item = items.optJSONObject(index);
                if (item == null) {
                    continue;
                }
                entries.add(new AppReleaseHistoryEntry(
                        optInt(item, "versionCode"),
                        optString(item, "versionName"),
                        optString(item, "channel"),
                        optLong(item, "publishedAt"),
                        optString(item, "changelog")
                ));
            }
        } catch (JSONException exception) {
            throw new IOException("更新记录解析失败", exception);
        }
        return entries;
    }

    private HttpUrl parseBaseUrl(String configuredBaseUrl) throws IOException {
        if (configuredBaseUrl == null || configuredBaseUrl.trim().isEmpty()) {
            return null;
        }
        String normalized = configuredBaseUrl.trim();
        if (!normalized.endsWith("/")) {
            normalized = normalized + "/";
        }
        try {
            return HttpUrl.get(normalized);
        } catch (IllegalArgumentException exception) {
            throw new IOException("Invalid SHARE_API_BASE_URL", exception);
        }
    }

    private HttpUrl buildUrl(String relativePath) throws IOException {
        if (baseUrl == null) {
            throw new IOException("请先配置 SHARE_API_BASE_URL");
        }
        HttpUrl url = baseUrl.resolve(relativePath);
        if (url == null) {
            throw new IOException("Unable to resolve share API path: " + relativePath);
        }
        return url;
    }

    private JSONObject executeObject(Request request) throws IOException {
        String responseText = executeRequest(request);
        try {
            JSONObject root = new JSONObject(responseText);
            JSONObject data = root.optJSONObject("data");
            return data != null ? data : root;
        } catch (JSONException exception) {
            throw new IOException("Unable to parse share API response", exception);
        }
    }

    private String executeRequest(Request request) throws IOException {
        if (!request.url().isHttps() && !BuildConfig.DEBUG) throw new IOException("正式版仅支持 HTTPS");
        if (context != null && !request.url().encodedPath().endsWith("/auth/login")) {
            com.acooldog.toolbox.config.InternalAuthStore auth = new com.acooldog.toolbox.config.InternalAuthStore(context);
            if (auth.isLoggedIn()) request = request.newBuilder().header("Authorization", "Bearer " + auth.getToken()).build();
        }
        try (Response response = okHttpClient.newCall(request).execute()) {
            ResponseBody responseBody = response.body();
            String responseText = responseBody == null ? "" : responseBody.string();
            if (!response.isSuccessful()) {
                if (context != null && response.code() == 401) new com.acooldog.toolbox.config.InternalAuthStore(context).clear();
                throw new IOException(extractErrorMessage(response.code(), responseText));
            }
            return responseText;
        }
    }

    private String extractErrorMessage(int httpCode, String responseText) {
        String normalized = responseText == null ? "" : responseText.trim();
        if (!normalized.isEmpty()) {
            try {
                JSONObject jsonObject = new JSONObject(normalized);
                String detail = jsonObject.optString("detail", "").trim();
                if (!TextUtils.isEmpty(detail)) {
                    return detail;
                }
                JSONObject data = jsonObject.optJSONObject("data");
                if (data != null) {
                    detail = data.optString("detail", "").trim();
                    if (!TextUtils.isEmpty(detail)) {
                        return detail;
                    }
                }
            } catch (JSONException ignored) {
                // Fall back to the raw response text below.
            }
        }
        if (TextUtils.isEmpty(normalized)) {
            return "HTTP " + httpCode;
        }
        return "HTTP " + httpCode + ": " + normalized;
    }

    private AppClientConfig parseAppClientConfig(JSONObject jsonObject) throws IOException {
        if (jsonObject == null || !(jsonObject.opt("killSwitch") instanceof Boolean)) {
            throw new IOException("Client config requires an explicit boolean killSwitch");
        }
        return new AppClientConfig(
                optString(jsonObject, "noticeTitle", "title"),
                optString(jsonObject, "noticeMessage", "message"),
                optString(jsonObject, "qqGroupNumber", "groupNumber", "qqGroup"),
                optString(jsonObject, "bilibiliText", "bilibiliLabel"),
                optString(jsonObject, "bilibiliUrl", "bilibiliLink"),
                optBoolean(jsonObject, "killSwitch", "disabled", "forceClose", "closed"),
                optString(jsonObject, "killSwitchMessage", "disabledMessage", "closeMessage")
        );
    }

    private String optString(@NonNull JSONObject jsonObject, String... keys) {
        for (String key : keys) {
            if (jsonObject.has(key)) {
                String value = jsonObject.optString(key, "");
                if (!TextUtils.isEmpty(value)) {
                    return value;
                }
            }
        }
        return "";
    }

    private int optInt(@NonNull JSONObject jsonObject, String... keys) {
        for (String key : keys) {
            if (jsonObject.has(key)) {
                return jsonObject.optInt(key, 0);
            }
        }
        return 0;
    }

    private long optLong(@NonNull JSONObject jsonObject, String... keys) {
        for (String key : keys) {
            if (jsonObject.has(key)) {
                return jsonObject.optLong(key, 0L);
            }
        }
        return 0L;
    }

    private java.util.List<String> optStringList(@NonNull JSONObject jsonObject, String... keys) {
        java.util.List<String> values = new java.util.ArrayList<>();
        for (String key : keys) {
            JSONArray array = jsonObject.optJSONArray(key);
            if (array == null) {
                continue;
            }
            for (int index = 0; index < array.length(); index++) {
                String value = array.optString(index, "").trim();
                if (!value.isEmpty()) {
                    values.add(value);
                }
            }
            break;
        }
        return values;
    }

    private boolean optBoolean(@NonNull JSONObject jsonObject, String... keys) {
        for (String key : keys) {
            if (jsonObject.has(key)) {
                Object value = jsonObject.opt(key);
                if (value instanceof Boolean) {
                    return (Boolean) value;
                }
                if (value instanceof Number) {
                    return ((Number) value).intValue() != 0;
                }
                if (value instanceof String) {
                    return Boolean.parseBoolean((String) value) || "1".equals(value);
                }
            }
        }
        return false;
    }
}
