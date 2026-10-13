package com.acooldog.toolbox;

import android.Manifest;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Spannable;
import android.text.SpannableStringBuilder;
import android.text.TextPaint;
import android.text.method.LinkMovementMethod;
import android.text.style.ClickableSpan;
import android.view.View;
import android.widget.CheckBox;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.StringRes;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.preference.PreferenceManager;

import com.acooldog.toolbox.config.LegalConsentStore;
import com.acooldog.toolbox.config.RemoteControlStore;
import com.acooldog.toolbox.share.domain.model.AppClientConfig;
import com.acooldog.toolbox.share.presentation.ShareModule;
import com.acooldog.toolbox.utils.GoUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class WelcomeActivity extends AppCompatActivity {
    private static final String LEGAL_PREFS_NAME = "KEY_ACCEPT_AGREEMENT";
    private static final String KEY_ACCEPT_AGREEMENT = "KEY_ACCEPT_AGREEMENT";
    private static final String KEY_ACCEPT_PRIVACY = "KEY_ACCEPT_PRIVACY";
    private static final String KEY_ACCEPT_DISCLAIMER = "KEY_ACCEPT_DISCLAIMER";
    private static final int SDK_PERMISSION_REQUEST = 127;
    private static final int REQUEST_GUIDE = 221;
    private static final long SPLASH_DURATION_MILLIS = 1000L;
    // 跨境网络首次连接可能较慢：给足 6 秒，超时才回退本地文案
    private static final long REMOTE_NOTICE_TIMEOUT_MILLIS = 2500L;

    /** 本次启动公告是否成功从服务器获取（false=用了本地兜底文案）。 */
    private boolean entryNoticeFromServer;
    /** 拉取公告失败时的原因（用于提示与远程排查）。 */
    private String remoteNoticeError;
    /** 待交给首页底部提示条显示的公告文本。 */
    private String pendingNoticeText = "";

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private SharedPreferences preferences;
    private ExecutorService ioExecutor;
    private boolean agreementAccepted;
    private boolean disclaimerAccepted;
    private boolean startupFlowStarted;
    private View logoView;
    private View titleView;
    private View subtitleView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_welcome);

        PreferenceManager.setDefaultValues(this, R.xml.preferences_main, false);

        preferences = getSharedPreferences(LEGAL_PREFS_NAME, MODE_PRIVATE);
        ioExecutor = Executors.newSingleThreadExecutor();
        agreementAccepted = preferences.getBoolean(KEY_ACCEPT_AGREEMENT, false);
        disclaimerAccepted = preferences.getBoolean(
                KEY_ACCEPT_DISCLAIMER,
                preferences.getBoolean(KEY_ACCEPT_PRIVACY, false)
        );

        logoView = findViewById(R.id.welcome_logo);
        titleView = findViewById(R.id.welcome_title);
        subtitleView = findViewById(R.id.welcome_subtitle);

        startSplashAnimation();
        mainHandler.postDelayed(this::beginStartupFlow, SPLASH_DURATION_MILLIS);
    }

    @Override
    protected void onDestroy() {
        mainHandler.removeCallbacksAndMessages(null);
        if (ioExecutor != null) {
            ioExecutor.shutdownNow();
        }
        super.onDestroy();
    }

    private void startSplashAnimation() {
        if (logoView != null) {
            logoView.setAlpha(0f);
            logoView.setScaleX(0.82f);
            logoView.setScaleY(0.82f);
            logoView.animate()
                    .alpha(1f)
                    .scaleX(1f)
                    .scaleY(1f)
                    .setDuration(SPLASH_DURATION_MILLIS)
                    .start();
        }
        if (titleView != null) {
            titleView.setAlpha(0f);
            titleView.setTranslationY(36f);
            titleView.animate()
                    .alpha(1f)
                    .translationY(0f)
                    .setDuration(SPLASH_DURATION_MILLIS)
                    .start();
        }
        if (subtitleView != null) {
            subtitleView.setAlpha(0f);
            subtitleView.setTranslationY(48f);
            subtitleView.animate()
                    .alpha(1f)
                    .translationY(0f)
                    .setStartDelay(150L)
                    .setDuration(SPLASH_DURATION_MILLIS - 150L)
                    .start();
        }
    }

    private void beginStartupFlow() {
        if (startupFlowStarted || isFinishing() || isDestroyed()) {
            return;
        }
        startupFlowStarted = true;
        // 内部工具：第一次打开就直接弹系统定位权限，不再经过说明页
        requestLocationPermissionDirectly();
        if (!LegalConsentStore.isGuideCompleted(this)) {
            startActivityForResult(new Intent(this, GuideActivity.class), REQUEST_GUIDE);
            return;
        }
        continueAfterGuide();
    }

    /** 直接索要定位权限（不弹自定义说明页）。 */
    private void requestLocationPermissionDirectly() {
        try {
            boolean fine = androidx.core.content.ContextCompat.checkSelfPermission(
                    this, android.Manifest.permission.ACCESS_FINE_LOCATION)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED;
            boolean coarse = androidx.core.content.ContextCompat.checkSelfPermission(
                    this, android.Manifest.permission.ACCESS_COARSE_LOCATION)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED;
            if (fine || coarse) {
                return;
            }
            androidx.core.app.ActivityCompat.requestPermissions(this,
                    new String[]{
                            android.Manifest.permission.ACCESS_FINE_LOCATION,
                            android.Manifest.permission.ACCESS_COARSE_LOCATION
                    },
                    SDK_PERMISSION_REQUEST);
        } catch (Exception ignored) {
            // 个别 ROM 弹窗失败不影响后续引导
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_GUIDE) {
            return;
        }
        agreementAccepted = preferences.getBoolean(KEY_ACCEPT_AGREEMENT, false);
        disclaimerAccepted = preferences.getBoolean(
                KEY_ACCEPT_DISCLAIMER,
                preferences.getBoolean(KEY_ACCEPT_PRIVACY, false)
        );
        if (resultCode != RESULT_OK) { finish(); return; }
        continueAfterGuide();
    }

    private void continueAfterGuide() {
        if (isFinishing() || isDestroyed()) {
            return;
        }
        if (!agreementAccepted || !disclaimerAccepted) {
            showLegalConsentDialog();
            return;
        }
        showEntryNoticeThenContinue();
    }

    private void showLegalConsentDialog() {
        View dialogView = getLayoutInflater().inflate(R.layout.dialog_legal_consent, null);
        TextView linksView = dialogView.findViewById(R.id.legal_consent_links);
        CheckBox consentCheckBox = dialogView.findViewById(R.id.legal_consent_checkbox);

        linksView.setMovementMethod(LinkMovementMethod.getInstance());
        linksView.setText(buildLegalLinkText(), TextView.BufferType.SPANNABLE);

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(R.string.app_error_agreement_dialog_title)
                .setView(dialogView)
                .setCancelable(false)
                .setPositiveButton(R.string.legal_consent_confirm, null)
                .setNegativeButton(R.string.legal_consent_cancel, (ignored, which) -> finish())
                .create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            if (!consentCheckBox.isChecked()) {
                GoUtils.DisplayToast(this, getString(R.string.app_error_agreement));
                return;
            }
            saveAgreementAcceptance();
            dialog.dismiss();
            showEntryNoticeThenContinue();
        }));
        dialog.show();
    }

    private SpannableStringBuilder buildLegalLinkText() {
        String text = getString(R.string.legal_consent_link_text);
        SpannableStringBuilder builder = new SpannableStringBuilder(text);
        applyClickableSpan(builder, text, "《用户协议》", () -> showDocumentDialog(R.string.app_agreement, R.string.app_agreement_content));
        applyClickableSpan(builder, text, "《免责声明》", () -> showDocumentDialog(R.string.app_privacy, R.string.app_privacy_content));
        return builder;
    }

    private void applyClickableSpan(
            SpannableStringBuilder builder,
            String fullText,
            String target,
            Runnable action
    ) {
        int start = fullText.indexOf(target);
        if (start < 0) {
            return;
        }
        int end = start + target.length();
        builder.setSpan(new ClickableSpan() {
            @Override
            public void onClick(@NonNull View widget) {
                action.run();
            }

            @Override
            public void updateDrawState(@NonNull TextPaint ds) {
                ds.setColor(getResources().getColor(R.color.colorPrimary, getTheme()));
                ds.setUnderlineText(false);
            }
        }, start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
    }

    private void showDocumentDialog(@StringRes int titleResId, @StringRes int contentResId) {
        ScrollView scrollView = new ScrollView(this);
        int padding = Math.round(getResources().getDisplayMetrics().density * 20f);
        TextView contentView = new TextView(this);
        contentView.setPadding(padding, padding, padding, padding);
        contentView.setLineSpacing(0f, 1.25f);
        contentView.setText(getString(contentResId));
        scrollView.addView(contentView);

        new AlertDialog.Builder(this)
                .setTitle(titleResId)
                .setView(scrollView)
                .setPositiveButton(R.string.legal_document_close, null)
                .show();
    }

    private void saveAgreementAcceptance() {
        agreementAccepted = true;
        disclaimerAccepted = true;
        preferences.edit()
                .putBoolean(KEY_ACCEPT_AGREEMENT, true)
                .putBoolean(KEY_ACCEPT_PRIVACY, true)
                .putBoolean(KEY_ACCEPT_DISCLAIMER, true)
                .apply();
    }

    private void showEntryNoticeThenContinue() {
        resolveEntryNoticeContent(content -> {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            // 关键：必须拿到服务器确认才放行；未确认或已停止一律禁止使用
            com.acooldog.toolbox.config.RemoteAccessGate.confirm(this, (allowed, message) -> {
                if (isFinishing() || isDestroyed()) {
                    return;
                }
                if (!allowed) {
                    com.acooldog.toolbox.config.RemoteAccessGate.showBlockedDialog(
                            this, message, this::showEntryNoticeThenContinue);
                    return;
                }
                if (!entryNoticeFromServer) {
                    String hint = getString(R.string.app_entry_notice_offline_hint);
                    if (remoteNoticeError != null && !remoteNoticeError.isEmpty()) {
                        hint = hint + "\n" + remoteNoticeError;
                    }
                    GoUtils.DisplayToast(this, hint);
                }
                // 不再弹窗：把公告交给首页底部的小提示条显示
                pendingNoticeText = content.buildDialogMessage();
                ensurePermissionsThenEnterHome();
            });
        });
    }

    private void resolveEntryNoticeContent(@NonNull EntryNoticeCallback callback) {
        EntryNoticeContent fallback = EntryNoticeContent.local(this);
        entryNoticeFromServer = false;
        // 不再依赖「网络可用性预检查」直接跳过：VPN/部分机型会误判为无网络，
        // 这里一律尝试请求，真正失败时由 6 秒超时或异常兜底。

        AtomicBoolean delivered = new AtomicBoolean(false);
        Runnable fallbackRunnable = () -> {
            if (delivered.compareAndSet(false, true)) {
                callback.onReady(fallback);
            }
        };
        mainHandler.postDelayed(fallbackRunnable, REMOTE_NOTICE_TIMEOUT_MILLIS);

        ioExecutor.execute(() -> {
            EntryNoticeContent resolved = fallback;
            try {
                AppClientConfig config = ShareModule.from(getApplicationContext())
                        .shareApiClient()
                        .getAppClientConfig();
                RemoteControlStore.update(
                        getApplicationContext(),
                        config.isKillSwitch(),
                        config.getKillSwitchMessage()
                );
                resolved = EntryNoticeContent.fromRemote(config, fallback);
                entryNoticeFromServer = true;
            } catch (Exception exception) {
                resolved = fallback;
                remoteNoticeError = exception.getClass().getSimpleName()
                        + (exception.getMessage() == null ? "" : ": " + exception.getMessage());
            }
            EntryNoticeContent finalResolved = resolved;
            runOnUiThread(() -> {
                if (delivered.compareAndSet(false, true)) {
                    mainHandler.removeCallbacks(fallbackRunnable);
                    callback.onReady(finalResolved);
                }
            });
        });
    }

    /** 命中远程关闭开关：弹不可取消提示并退出；返回 true 表示已拦截。 */
    private boolean blockIfRemoteDisabled() {
        if (!RemoteControlStore.isDisabled(this)) {
            return false;
        }
        String message = RemoteControlStore.message(this);
        new AlertDialog.Builder(this)
                .setTitle(R.string.remote_disabled_title)
                .setMessage(message == null || message.trim().isEmpty()
                        ? getString(R.string.remote_disabled_default_message)
                        : message)
                .setCancelable(false)
                .setPositiveButton(R.string.remote_disabled_exit, (dialog, which) -> finishAffinity())
                .show();
        return true;
    }

    private void ensurePermissionsThenEnterHome() {
        enterHome();
    }

    private void enterHome() {
        // 数据上报说明页已移除，进入首页即视为已告知（告知保留在《用户协议》与设置页说明中）
        new com.acooldog.toolbox.config.TelemetryStore(this).saveConsent(true, true);
        ((GoApplication) getApplication()).initializeMapsAfterConsent();
            com.acooldog.toolbox.utils.AppLogReporter.uploadPendingCrashIfAny(this);
        Intent intent = new Intent(this, HomeActivity.class);
        if (pendingNoticeText != null && !pendingNoticeText.isEmpty()) {
            intent.putExtra(HomeActivity.EXTRA_ENTRY_NOTICE, pendingNoticeText);
        }
        startActivity(intent);
        finish();
    }

    private interface EntryNoticeCallback {
        void onReady(@NonNull EntryNoticeContent content);
    }

    private static final class EntryNoticeContent {
        private final String title;
        private final String message;
        private final String groupNumber;
        private final String bilibiliText;
        private final String bilibiliUrl;

        private EntryNoticeContent(
                String title,
                String message,
                String groupNumber,
                String bilibiliText,
                String bilibiliUrl
        ) {
            this.title = title == null ? "" : title.trim();
            this.message = message == null ? "" : message.trim();
            this.groupNumber = groupNumber == null ? "" : groupNumber.trim();
            this.bilibiliText = bilibiliText == null ? "" : bilibiliText.trim();
            this.bilibiliUrl = bilibiliUrl == null ? "" : bilibiliUrl.trim();
        }

        @NonNull
        private static EntryNoticeContent local(@NonNull WelcomeActivity activity) {
            return new EntryNoticeContent(
                    activity.getString(R.string.app_entry_notice_title),
                    activity.getString(R.string.app_entry_notice_message),
                    activity.getString(R.string.app_entry_notice_group_number),
                    activity.getString(R.string.app_bilibili_notice_text),
                    activity.getString(R.string.app_bilibili_url)
            );
        }

        @NonNull
        private static EntryNoticeContent fromRemote(@NonNull AppClientConfig remote, @NonNull EntryNoticeContent fallback) {
            return new EntryNoticeContent(
                    firstNonEmpty(remote.getNoticeTitle(), fallback.title),
                    firstNonEmpty(remote.getNoticeMessage(), fallback.message),
                    firstNonEmpty(remote.getQqGroupNumber(), fallback.groupNumber),
                    firstNonEmpty(remote.getBilibiliText(), fallback.bilibiliText),
                    firstNonEmpty(remote.getBilibiliUrl(), fallback.bilibiliUrl)
            );
        }

        @NonNull
        private String buildDialogMessage() {
            if (bilibiliText.isEmpty()) {
                return message;
            }
            return message + "\n\n" + bilibiliText;
        }

        @NonNull
        private static String firstNonEmpty(String preferred, String fallback) {
            return preferred == null || preferred.trim().isEmpty() ? fallback : preferred.trim();
        }
    }
}
