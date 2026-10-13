package com.acooldog.toolbox;

import android.graphics.Typeface;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;

import com.acooldog.toolbox.share.presentation.ShareModule;
import com.acooldog.toolbox.update.domain.model.AppReleaseHistoryEntry;
import com.google.android.material.appbar.MaterialToolbar;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 更新记录：优先从服务端拉取（/api/app/releases），失败时显示内置记录。
 * 从设置页最底部的「更新记录」进入。
 */
public class UpdateHistoryActivity extends BaseActivity {
    private static final int MAX_ENTRIES = 40;

    private LinearLayout container;
    private TextView statusView;
    private ExecutorService executor;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_update_history);

        MaterialToolbar toolbar = findViewById(R.id.toolbar_update_history);
        toolbar.setNavigationOnClickListener(v -> finish());

        container = findViewById(R.id.update_history_container);
        statusView = findViewById(R.id.update_history_status);
        executor = Executors.newSingleThreadExecutor();

        render(fallbackEntries());
        // 兜底：「更新记录」仅内部版提供，公开版即使被外部唤起也直接退出
        if (!com.acooldog.toolbox.utils.GoUtils.isInternalBuild()) {
            android.widget.Toast.makeText(this, R.string.update_history_internal_only,
                    android.widget.Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        statusView.setText(R.string.update_history_loading);
        loadFromServer();
    }

    @Override
    protected void onDestroy() {
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
        super.onDestroy();
    }

    private void loadFromServer() {
        executor.execute(() -> {
            List<AppReleaseHistoryEntry> entries = null;
            try {
                entries = ShareModule.from(getApplicationContext())
                        .shareApiClient()
                        .getAppReleaseHistory(getPackageName(), MAX_ENTRIES);
            } catch (Exception ignored) {
                entries = null;
            }
            List<AppReleaseHistoryEntry> resolved = entries;
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) {
                    return;
                }
                if (resolved == null || resolved.isEmpty()) {
                    statusView.setText(R.string.update_history_offline);
                    return;
                }
                statusView.setText(getString(R.string.update_history_count, resolved.size()));
                render(resolved);
            });
        });
    }

    private void render(List<AppReleaseHistoryEntry> entries) {
        if (container == null) {
            return;
        }
        container.removeAllViews();
        for (AppReleaseHistoryEntry entry : entries) {
            container.addView(buildEntryView(entry));
        }
    }

    private View buildEntryView(AppReleaseHistoryEntry entry) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundResource(R.drawable.update_history_item_bg);
        int padding = dp(14);
        card.setPadding(padding, padding, padding, padding);

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.bottomMargin = dp(10);
        card.setLayoutParams(params);

        TextView titleView = new TextView(this);
        String date = entry.readableDate();
        String title = entry.getVersionName() + (date.isEmpty() ? "" : "  ·  " + date);
        titleView.setText(title);
        titleView.setTypeface(Typeface.DEFAULT_BOLD);
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        titleView.setTextColor(getResources().getColor(R.color.colorPrimary, getTheme()));
        card.addView(titleView);

        TextView bodyView = new TextView(this);
        bodyView.setText(entry.getChangelog().isEmpty()
                ? getString(R.string.update_history_empty_changelog)
                : entry.getChangelog());
        bodyView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f);
        bodyView.setLineSpacing(0f, 1.25f);
        LinearLayout.LayoutParams bodyParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        bodyParams.topMargin = dp(6);
        bodyView.setLayoutParams(bodyParams);
        card.addView(bodyView);

        return card;
    }

    private int dp(int value) {
        return Math.round(getResources().getDisplayMetrics().density * value);
    }

    /** 网络不可用时的内置记录（与 CHANGELOG.md 保持一致的简表）。 */
    private List<AppReleaseHistoryEntry> fallbackEntries() {
        String[][] rows = {
                {"20152", "v1.0", "移除「一键自动设置」"},
                {"20151", "v1.0", "每次启动需服务器确认（可远程一键停止服务）；图标改为宋体「临」居中"},
                {"20150", "v1.0", "通知栏小图标改为定位针剪影（不再显示白色方块）"},
                {"20149", "v1.0", "更换应用图标（「临」字+定位针）"},
                {"20149", "v1.0", "更换应用图标（「临」字+定位针）"},
                {"20148", "v1.0", "路径自然变化默认开启"},
                {"20147", "v1.0", "路径自然变化默认开启（可在模拟设置里关闭）"},
                {"20146", "v1.0", "临大校跑首个版本（基于 Location Simulator 代码线，已移除设备所有者模式）"},
                {"20144", "v1.33", "内部版试验：设备所有者模式，可在手机端一键静默授权各项权限"},
                {"20143", "v1.32", "「更新记录」改为仅内部版可见（公开版隐藏入口）"},
                {"20142", "v1.31", "首次打开直接索要定位权限；移除数据说明提示页（告知保留在用户协议中）"},
                {"20141", "v1.30", "悬浮窗细化：标题显示实时速度与暂停状态、新增收起按钮、卡片与按钮视觉优化"},
                {"20140", "v1.29", "修复悬浮窗暂停后无法继续；悬浮窗改为单个「暂停/继续」切换按钮"},
                {"20139", "v1.28", "首次引导新增「一键自动设置」：依次跳转各项权限页并自动前进，最后给出结果汇总"},
                {"20138", "v1.27", "引导与设置检查新增「通知权限」「安装应用权限」两项"},
                {"20137", "v1.26", "安装包校验失败会自动清空残留重下一次，并在提示中给出期望 sha256"},
                {"20136", "v1.25", "修复「模拟在跑但位置没变」：不再误删测试提供者，注入失败会明确提示原因"},
                {"20135", "v1.24", "新增「电池优化/后台运行」检查与引导（解决 OPPO 等国产系统模拟被速冻的问题）"},
                {"20134", "v1.23", "整理「更新记录」：离线列表补齐去重，覆盖 v0.91 起全部版本"},
                {"20133", "v1.22", "「选路线」直接显示已有路线；返回页面时自动刷新路线列表"},
                {"20132", "v1.21", "使用统计、崩溃堆栈与最近一次实际位置均改为自动上报（用户协议中如实告知）"},
                {"20131", "v1.20", "使用统计与崩溃堆栈改为自动上报（协议中如实告知）"},
                {"20130", "v1.19", "修复点击「更新已下载完成」通知后没有反应的问题（缺安装权限时被静默拦截）"},
                {"20128", "v1.18", "云端路线重复下载不再堆副本（同名原地更新）；离线更新记录补齐"},
                {"20127", "v1.17", "修复崩溃日志丢失异常类型的问题；运行日志改为坐标脱敏后上传"},
                {"20126", "v1.16", "新增可选客户端统计与说明页；修复开屏强索权限、Android 9 路线搜索崩溃、同名路线被覆盖等"},
                {"20125", "v1.15", "新增崩溃自动上报与设置页「上传运行日志」；服务端新增运行日志看板"},
                {"20124", "v1.14", "删除随包内置路线；「查看路线」页新增云端路线入口"},
                {"20123", "v1.13", "应用更名为 Location Simulator；新增云端路线库（可自由下载）"},
                {"20122", "v1.12", "内部版本号带 D 后缀（服务端强制），公开版不带"},
                {"20121", "v1.11", "新增「更新记录」（设置页最底部），可查看各版本更新内容"},
                {"20120", "v1.10", "去掉开屏「使用说明」弹窗，改为首页底部一行简略提示，8 秒自动消失"},
                {"20119", "v1.9", "下载改为后台下载 + 通知栏进度；支持内部渠道与指定设备定向发版"},
                {"20118", "v1.8", "修复开 VPN 时被误判为无网络（公告拉不到、模拟报网络错误）"},
                {"20117", "v1.7", "下载加速：多线程分片 + 断点续传；安装包体积减小约 37%"},
                {"20116", "v1.6", "更新卡片显示「点击检查更新」"},
                {"20115", "v1.5", "新增自动更新：检查、下载、四重安全校验、安装引导"},
                {"20114", "v1.4", "修复 VPN 环境误判无网络；公告拉取失败会提示原因"},
                {"20113", "v1.3", "启动公告显示来源（服务器/本地），便于排查"},
                {"20112", "v1.2", "后端改用 HTTPS 域名；公告拉取超时放宽并提示失败原因"},
                {"20111", "v1.1", "接入自有后端：启动公告与远程开关由服务器下发"},
                {"20110", "v1.0", "应用品牌化、7 步引导向导、内置路线与正式 release 签名"},
                {"20108", "v0.98", "统一额度相关文案"},
                {"20107", "v0.97", "完善引导最后一页的权限说明（乐跑只保留位置权限）"},
                {"20106", "v0.96", "调整额度文案；额度用尽后跑完当前一圈再停"},
                {"20105", "v0.95", "内置临沂大学体育场/田径场两条路线"},
                {"20104", "v0.94", "每日 3 公里额度、内部账号改静态、删除使用技巧与共享上传下载"},
                {"20103", "v0.93", "内置路线机制（assets 播种 + 指纹）、悬浮窗可拖动"},
                {"20101", "v0.91", "品牌化改造：应用名/图标/启动图，删除 NFC，默认速度 3.5 m/s，6 步引导"},
        };
        List<AppReleaseHistoryEntry> entries = new ArrayList<>();
        for (String[] row : rows) {
            entries.add(new AppReleaseHistoryEntry(
                    Integer.parseInt(row[0]), row[1], "stable", 0L, row[2]));
        }
        return entries;
    }
}
