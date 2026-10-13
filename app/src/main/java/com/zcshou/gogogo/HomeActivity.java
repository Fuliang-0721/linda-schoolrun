package com.acooldog.toolbox;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.widget.TextView;

import androidx.annotation.IdRes;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;

import com.acooldog.toolbox.home.HomeMineFragment;
import com.acooldog.toolbox.home.HomeStartFragment;
import com.acooldog.toolbox.update.presentation.AppUpdateController;
import com.acooldog.toolbox.update.service.AppUpdateDownloadService;
import com.acooldog.toolbox.utils.GoUtils;
import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.bottomnavigation.BottomNavigationView;

public class HomeActivity extends BaseActivity implements HomeMineFragment.Actions {
    private static final String KEY_SELECTED_TAB = "selected_tab";

    /** 从更新完成通知点进来时置为 true，进入后直接拉起安装。 */
    public static final String EXTRA_INSTALL_PENDING_UPDATE = "extra_install_pending_update";

    /** 开屏公告文本：进入首页后在底部短提示条展示（不再弹窗）。 */
    public static final String EXTRA_ENTRY_NOTICE = "extra_entry_notice";

    private static final long NOTICE_BANNER_VISIBLE_MILLIS = 8000L;

    private BroadcastReceiver updateFinishedReceiver;
    private final Handler uiHandler = new Handler(Looper.getMainLooper());
    private TextView noticeBannerView;
    private String fullNoticeText = "";
    private final Runnable hideNoticeBannerRunnable = this::hideNoticeBanner;

    private MaterialToolbar toolbar;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        toolbar = findViewById(R.id.toolbar_main);
        setSupportActionBar(toolbar);

        BottomNavigationView bottomNavigationView = findViewById(R.id.home_bottom_nav);
        bottomNavigationView.setOnItemSelectedListener(item -> {
            switchTab(item.getItemId());
            return true;
        });

        int selectedTab = savedInstanceState == null
                ? R.id.nav_home_start
                : savedInstanceState.getInt(KEY_SELECTED_TAB, R.id.nav_home_start);
        bottomNavigationView.setSelectedItemId(selectedTab);

        noticeBannerView = findViewById(R.id.tv_notice_banner);
        if (noticeBannerView != null) {
            noticeBannerView.setOnClickListener(v -> showFullNoticeDialog());
        }
        showNoticeBannerIfNeeded();

        // 进入主界面 3 秒后静默检查更新（24 小时冷却，不阻塞使用）
        uiHandler.postDelayed(
                () -> AppUpdateController.checkAndPrompt(HomeActivity.this, false), 3000L);

        // 从「更新已下载完成」通知点进来 → 直接安装（应用已在运行时只会走 onNewIntent，必须也处理）
        handleInstallPendingIntent(getIntent());

        // 后台下载完成时若 App 正在前台，立刻接着装
        updateFinishedReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                AppUpdateController.installPendingIfPossible(HomeActivity.this);
            }
        };
        IntentFilter filter = new IntentFilter(AppUpdateDownloadService.ACTION_FINISHED);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(updateFinishedReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(updateFinishedReceiver, filter);
        }
    }

    /** 处理「从更新通知点进来」的意图：onCreate 与 onNewIntent 都要走这里。 */
    private void handleInstallPendingIntent(@Nullable Intent intent) {
        if (intent == null) {
            return;
        }
        boolean pendingInstall = intent.getBooleanExtra(EXTRA_INSTALL_PENDING_UPDATE, false);
        intent.removeExtra(EXTRA_INSTALL_PENDING_UPDATE);
        if (pendingInstall) {
            AppUpdateController.installPendingIfPossible(this);
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleInstallPendingIntent(intent);
    }

    /** 首页底部小提示：显示公告（最多两行），8 秒后自动消失。 */
    private void showNoticeBannerIfNeeded() {
        Intent intent = getIntent();
        if (intent == null || noticeBannerView == null) {
            return;
        }
        String notice = intent.getStringExtra(EXTRA_ENTRY_NOTICE);
        intent.removeExtra(EXTRA_ENTRY_NOTICE);
        if (notice == null || notice.trim().isEmpty()) {
            return;
        }
        fullNoticeText = notice.trim();
        noticeBannerView.setText(fullNoticeText);
        noticeBannerView.setVisibility(View.VISIBLE);
        noticeBannerView.setAlpha(0f);
        noticeBannerView.animate().alpha(1f).setDuration(220L).start();
        uiHandler.removeCallbacks(hideNoticeBannerRunnable);
        uiHandler.postDelayed(hideNoticeBannerRunnable, NOTICE_BANNER_VISIBLE_MILLIS);
    }

    private void hideNoticeBanner() {
        if (noticeBannerView == null || noticeBannerView.getVisibility() != View.VISIBLE) {
            return;
        }
        noticeBannerView.animate().alpha(0f).setDuration(220L)
                .withEndAction(() -> {
                    if (noticeBannerView != null) {
                        noticeBannerView.setVisibility(View.GONE);
                    }
                })
                .start();
    }

    /** 点提示条时看完整公告（可选操作，默认不打扰）。 */
    private void showFullNoticeDialog() {
        hideNoticeBanner();
        if (fullNoticeText.isEmpty()) {
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle(R.string.app_entry_notice_title)
                .setMessage(fullNoticeText)
                .setPositiveButton(R.string.app_entry_notice_known, null)
                .show();
    }

    @Override
    protected void onDestroy() {
        uiHandler.removeCallbacksAndMessages(null);
        noticeBannerView = null;
        if (updateFinishedReceiver != null) {
            try {
                unregisterReceiver(updateFinishedReceiver);
            } catch (Exception ignored) {
                // 忽略重复注销
            }
            updateFinishedReceiver = null;
        }
        super.onDestroy();
    }

    @Override
    protected void onResume() {
        super.onResume();
        // 从「安装未知应用」设置页返回后，若已授权则继续安装
        AppUpdateController.installPendingIfPossible(this);

    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        super.onSaveInstanceState(outState);
        BottomNavigationView bottomNavigationView = findViewById(R.id.home_bottom_nav);
        outState.putInt(KEY_SELECTED_TAB, bottomNavigationView.getSelectedItemId());
    }

    private void switchTab(@IdRes int itemId) {
        if (itemId == R.id.nav_home_mine) {
            toolbar.setTitle(R.string.home_tab_mine);
            getSupportFragmentManager()
                    .beginTransaction()
                    .replace(R.id.home_fragment_container, HomeMineFragment.newInstance())
                    .commit();
            return;
        }

        toolbar.setTitle(R.string.home_tab_start);
        getSupportFragmentManager()
                .beginTransaction()
                .replace(R.id.home_fragment_container, HomeStartFragment.newInstance())
                .commit();
    }

    private void open(Class<?> activityClass) {
        startActivity(new Intent(this, activityClass));
    }

    @Override
    public void onUpdateClicked() {
        AppUpdateController.checkAndPrompt(this, true);
    }

    @Override
    public void onSettingsCheckClicked() {
        open(SettingsCheckActivity.class);
    }

    @Override
    public void onSettingsClicked() {
        open(SettingsActivity.class);
    }

    @Override
    public void onInternalLoginClicked() {
        open(InternalLoginActivity.class);
    }

    @Override
    public void onDeveloperOptionsClicked() {
        openDeveloperSettings(null);
    }

    private void openDeveloperSettings(View ignored) {
        if (Settings.Global.getInt(getContentResolver(), "development_settings_enabled", 0) != 1) {
            GoUtils.DisplayToast(this, getString(R.string.app_error_dev));
            return;
        }

        try {
            startActivity(new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS));
        } catch (Exception exception) {
            GoUtils.DisplayToast(this, getString(R.string.app_error_dev));
        }
    }
}
