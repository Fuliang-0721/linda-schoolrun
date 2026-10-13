package com.acooldog.toolbox;

import android.graphics.Typeface;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;

import com.acooldog.toolbox.route.data.FileRouteRepository;
import com.acooldog.toolbox.route.domain.model.CloudRouteInfo;
import com.acooldog.toolbox.route.domain.model.RouteDefinition;
import com.acooldog.toolbox.route.domain.model.RoutePoint;
import com.acooldog.toolbox.share.presentation.ShareModule;
import com.acooldog.toolbox.utils.GoUtils;
import com.google.android.material.appbar.MaterialToolbar;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 云端路线库：从服务器下载路线到本地（本地路线文件格式与内置路线一致，
 * 下载后即可在「选择路线」里直接使用）。
 */
public class CloudRouteActivity extends BaseActivity {
    private LinearLayout container;
    private TextView statusView;
    private ExecutorService executor;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_cloud_route);

        MaterialToolbar toolbar = findViewById(R.id.toolbar_cloud_route);
        toolbar.setNavigationOnClickListener(v -> finish());

        container = findViewById(R.id.cloud_route_container);
        statusView = findViewById(R.id.cloud_route_status);
        executor = Executors.newSingleThreadExecutor();

        statusView.setText(R.string.cloud_route_loading);
        loadRoutes();
    }

    @Override
    protected void onDestroy() {
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
        super.onDestroy();
    }

    private void loadRoutes() {
        executor.execute(() -> {
            List<CloudRouteInfo> routes = null;
            String error = null;
            try {
                routes = ShareModule.from(getApplicationContext())
                        .shareApiClient()
                        .getCloudRoutes();
            } catch (Exception exception) {
                error = exception.getClass().getSimpleName();
            }
            List<CloudRouteInfo> resolved = routes;
            String finalError = error;
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) {
                    return;
                }
                if (resolved == null || resolved.isEmpty()) {
                    statusView.setText(getString(R.string.cloud_route_empty,
                            finalError == null ? "" : finalError));
                    return;
                }
                statusView.setText(getString(R.string.cloud_route_count, resolved.size()));
                render(resolved);
            });
        });
    }

    private void render(List<CloudRouteInfo> routes) {
        if (container == null) {
            return;
        }
        container.removeAllViews();
        for (CloudRouteInfo info : routes) {
            container.addView(buildRouteView(info));
        }
    }

    private View buildRouteView(CloudRouteInfo info) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundResource(R.drawable.update_history_item_bg);
        int padding = dp(14);
        card.setPadding(padding, padding, padding, padding);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(10);
        card.setLayoutParams(params);

        TextView titleView = new TextView(this);
        titleView.setText(info.getName());
        titleView.setTypeface(Typeface.DEFAULT_BOLD);
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        titleView.setTextColor(getResources().getColor(R.color.colorPrimary, getTheme()));
        card.addView(titleView);

        String date = info.readableCreatedAt();
        TextView summaryView = new TextView(this);
        summaryView.setText(date.isEmpty()
                ? getString(R.string.cloud_route_points, info.getPointCount())
                : getString(R.string.cloud_route_points_with_date, info.getPointCount(), date));
        summaryView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f);
        LinearLayout.LayoutParams summaryParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        summaryParams.topMargin = dp(4);
        summaryView.setLayoutParams(summaryParams);
        card.addView(summaryView);

        Button downloadButton = new Button(this);
        downloadButton.setText(R.string.cloud_route_download);
        downloadButton.setAllCaps(false);
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        buttonParams.topMargin = dp(8);
        buttonParams.gravity = Gravity.END;
        downloadButton.setLayoutParams(buttonParams);
        downloadButton.setOnClickListener(v -> downloadRoute(info, downloadButton));
        card.addView(downloadButton);

        return card;
    }

    private void downloadRoute(CloudRouteInfo info, Button button) {
        button.setEnabled(false);
        button.setText(R.string.cloud_route_downloading);
        executor.execute(() -> {
            String error = null;
            try {
                List<RoutePoint> points = ShareModule.from(getApplicationContext())
                        .shareApiClient()
                        .getCloudRoutePoints(info.getId());
                if (points.size() < 2) {
                    throw new IllegalStateException("路线点位不足");
                }
                FileRouteRepository repository = new FileRouteRepository(getApplicationContext());
                RouteDefinition existing = findLocalRouteByName(repository, info.getName());
                if (existing != null) {
                    // 本地已有同名路线：原地更新该路线（保留路线 ID），避免每次下载都堆一份副本
                    repository.updateRoute(existing.getId(), info.getName(), points, existing.getShareInfo());
                } else {
                    String routeJson = buildRouteJson(info.getName(), points);
                    repository.importRoute(
                            info.getName(),
                            new ByteArrayInputStream(routeJson.getBytes(StandardCharsets.UTF_8))
                    );
                }
            } catch (Exception exception) {
                String message = exception.getMessage();
                error = exception.getClass().getSimpleName()
                        + (message == null || message.isEmpty() ? "" : ": " + message);
            }
            String finalError = error;
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) {
                    return;
                }
                if (finalError == null) {
                    button.setText(R.string.cloud_route_downloaded);
                    GoUtils.DisplayToast(this, getString(R.string.cloud_route_success, info.getName()));
                } else {
                    button.setEnabled(true);
                    button.setText(R.string.cloud_route_download);
                    GoUtils.DisplayToast(this, getString(R.string.cloud_route_failed, finalError));
                }
            });
        });
    }

    /** 按名字查本地已有路线（用于「重新下载」时原地更新而不是新增副本）。 */
    private RouteDefinition findLocalRouteByName(FileRouteRepository repository, String name) {
        if (name == null || name.isEmpty()) {
            return null;
        }
        try {
            for (RouteDefinition route : repository.getRoutes()) {
                if (name.equals(route.getName())) {
                    return route;
                }
            }
        } catch (IOException ignored) {
            // 读取失败按"没有同名路线"处理，走新增分支
        }
        return null;
    }

    /** 生成与本地路线文件一致的 JSON，交给 FileRouteRepository 导入。 */
    private String buildRouteJson(String name, List<RoutePoint> points) throws JSONException {
        long now = System.currentTimeMillis();
        JSONObject root = new JSONObject();
        root.put("version", 1);
        root.put("name", name);
        root.put("createdAt", now);
        root.put("updatedAt", now);

        JSONArray array = new JSONArray();
        for (RoutePoint point : points) {
            JSONObject item = new JSONObject();
            item.put("bdLongitude", point.getBdLongitude());
            item.put("bdLatitude", point.getBdLatitude());
            item.put("wgsLongitude", point.getWgsLongitude());
            item.put("wgsLatitude", point.getWgsLatitude());
            item.put("altitude", point.getAltitude());
            array.put(item);
        }
        root.put("points", array);
        return root.toString();
    }

    private int dp(int value) {
        return Math.round(getResources().getDisplayMetrics().density * value);
    }
}
