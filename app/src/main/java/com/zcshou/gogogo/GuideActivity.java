package com.acooldog.toolbox;

import android.os.Bundle;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.TextPaint;
import android.text.method.LinkMovementMethod;
import android.text.style.ClickableSpan;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;

import androidx.core.content.ContextCompat;

import com.acooldog.toolbox.config.LegalConsentStore;
import com.acooldog.toolbox.config.SetupChecklist;
import com.acooldog.toolbox.utils.GoUtils;

/**
 * 使用前设置向导：进主界面之前逐步引导用户完成必要设置。
 * 步骤定义、判定与跳转见 {@link SetupChecklist}。
 */
public class GuideActivity extends BaseActivity {
    /** 最后一页提示（不属于可校验的设置项，因此单独编号）。 */
    /** 数据说明提示页已移除（内部工具，告知保留在《用户协议》中）。 */
    private static final int TIP_STEP = SetupChecklist.STEP_COUNT;
    private CheckBox usageChoice;
    private CheckBox locationChoice;
    private static final int TOTAL_STEPS = TIP_STEP + 1;

    private static final int COLOR_DONE = 0xFF2E7D32;
    private static final int COLOR_PENDING = 0xFFD97706;

    private int currentStep;

    private TextView progressView;
    private ProgressBar progressBar;
    private ImageView artView;
    private TextView titleView;
    private TextView statusView;
    private TextView descView;
    private TextView linksView;
    private TextView prevView;
    private View consentLayout;
    private CheckBox consentCheckBox;
    private Button primaryButton;
    private Button skipButton;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_guide);

        usageChoice = findViewById(R.id.cb_telemetry_usage);
        locationChoice = findViewById(R.id.cb_telemetry_location);
        com.acooldog.toolbox.config.TelemetryStore telemetry = new com.acooldog.toolbox.config.TelemetryStore(this);
        usageChoice.setChecked(telemetry.enabled());
        locationChoice.setChecked(telemetry.locationEnabled());
        android.widget.CheckBox crash = new android.widget.CheckBox(this);
        crash.setTag("crash-choice"); crash.setText(R.string.telemetry_crash); crash.setChecked(telemetry.crashEnabled());
        ((android.view.ViewGroup)findViewById(R.id.layout_telemetry)).addView(crash);
        if (savedInstanceState != null) currentStep = savedInstanceState.getInt("step", currentStep);

        progressView = findViewById(R.id.tv_guide_progress);
        progressBar = findViewById(R.id.progress_guide);
        artView = findViewById(R.id.iv_guide_art);
        titleView = findViewById(R.id.tv_guide_title);
        statusView = findViewById(R.id.tv_guide_status);
        descView = findViewById(R.id.tv_guide_desc);
        linksView = findViewById(R.id.tv_guide_doc_links);
        prevView = findViewById(R.id.btn_guide_prev);
        consentLayout = findViewById(R.id.layout_guide_consent);
        consentCheckBox = findViewById(R.id.cb_guide_consent);
        primaryButton = findViewById(R.id.btn_guide_primary);
        skipButton = findViewById(R.id.btn_guide_skip);

        linksView.setMovementMethod(LinkMovementMethod.getInstance());
        linksView.setText(buildDocumentLinkText(), TextView.BufferType.SPANNABLE);

        primaryButton.setOnClickListener(v -> onPrimaryClicked());
        skipButton.setOnClickListener(v -> {
            goNext();
        });
        prevView.setOnClickListener(v -> goPrevious());
        consentCheckBox.setOnCheckedChangeListener((buttonView, isChecked) -> render());

        render();
    }

    @Override
    protected void onResume() {
        super.onResume();
        // 从系统设置页返回后重新检测当前步骤
        render();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        render();
    }

    @Override
    public void onBackPressed() {
        if (currentStep > 0 && currentStep != SetupChecklist.STEP_CONSENT) {
            goPrevious();
            return;
        }
        if (currentStep == SetupChecklist.STEP_DEVELOPER) {
            GoUtils.DisplayToast(this, getString(R.string.guide_status_required));
            return;
        }
        super.onBackPressed();
    }

    // ---------------------------------------------------------------- 渲染

    private void render() {
        findViewById(R.id.layout_telemetry).setVisibility(currentStep == TIP_STEP ? View.VISIBLE : View.GONE);
        boolean tipStep = currentStep == TIP_STEP;
        boolean consentStep = currentStep == SetupChecklist.STEP_CONSENT;
        boolean satisfied = !tipStep && SetupChecklist.isSatisfied(this, currentStep);

        progressView.setText(getString(R.string.guide_progress_format, currentStep + 1, TOTAL_STEPS));
        progressBar.setProgress((currentStep + 1) * 100 / TOTAL_STEPS);
        artView.setImageResource(tipStep ? R.drawable.guide_step7 : SetupChecklist.artRes(currentStep));
        titleView.setText(tipStep ? R.string.guide_step_tip_title : SetupChecklist.titleRes(currentStep));
        descView.setText(tipStep ? R.string.guide_step_tip_desc : SetupChecklist.descRes(currentStep));

        if (tipStep) {
            statusView.setVisibility(View.INVISIBLE);
        } else {
            statusView.setVisibility(View.VISIBLE);
            statusView.setText(satisfied ? R.string.guide_status_done : pendingStatusRes());
            statusView.setTextColor(satisfied ? COLOR_DONE : COLOR_PENDING);
        }

        consentLayout.setVisibility(consentStep ? View.VISIBLE : View.GONE);
        skipButton.setVisibility(!tipStep && SetupChecklist.canSkip(currentStep) ? View.VISIBLE : View.GONE);
        prevView.setVisibility(currentStep > 0 ? View.VISIBLE : View.INVISIBLE);
        primaryButton.setText(primaryButtonTextRes(satisfied, consentStep, tipStep));
    }

    private int pendingStatusRes() {
        return SetupChecklist.isCritical(currentStep)
                ? R.string.guide_status_required
                : R.string.guide_status_pending;
    }

    private int primaryButtonTextRes(boolean satisfied, boolean consentStep, boolean tipStep) {
        if (tipStep) {
            return R.string.guide_action_enter;
        }
        if (consentStep) {
            return R.string.guide_action_agree_enter;
        }
        if (satisfied) {
            return R.string.guide_action_next;
        }
        switch (currentStep) {
            case SetupChecklist.STEP_LOCATION:
            case SetupChecklist.STEP_ACTIVITY:
                return R.string.guide_action_grant;
            default:
                return R.string.guide_action_settings;
        }
    }

    // ---------------------------------------------------------------- 交互

    private void onPrimaryClicked() {
        if (currentStep == TIP_STEP) {
            completeGuide();
            return;
        }
        if (currentStep == SetupChecklist.STEP_CONSENT) {
            acceptConsentAndContinue();
            return;
        }
        if (SetupChecklist.isSatisfied(this, currentStep)) {
            goNext();
            return;
        }
        SetupChecklist.performFix(this, currentStep);
    }

    @Override protected void onSaveInstanceState(@NonNull Bundle state) {
        state.putInt("step", currentStep);
        super.onSaveInstanceState(state);
    }

    private void goNext() {
        if (currentStep < TOTAL_STEPS - 1) {
            currentStep++;
            render();
        }
    }

    private void goPrevious() {
        if (currentStep > 0) {
            currentStep--;
            render();
        }
    }

    /** 协议页：勾选并保存同意状态后进入下一页（后面还有一页提示）。 */
    private void acceptConsentAndContinue() {
        if (!consentCheckBox.isChecked() && !LegalConsentStore.isConsentAccepted(this)) {
            GoUtils.DisplayToast(this, getString(R.string.guide_consent_need_check));
            return;
        }
        LegalConsentStore.saveConsentAccepted(this);
        goNext();
    }

    /** 最后一页提示：点「进入应用」后关闭向导、标记完成。 */
    private void completeGuide() {
        LegalConsentStore.saveConsentAccepted(this);
        LegalConsentStore.markGuideCompleted(this);
        // 说明页已移除：完成引导即标记已告知，使统计与位置上报自动生效
        android.widget.CheckBox crash = findViewById(R.id.layout_telemetry).findViewWithTag("crash-choice");
        new com.acooldog.toolbox.config.TelemetryStore(this).saveConsent(usageChoice.isChecked(), locationChoice.isChecked(), crash.isChecked());
        GoUtils.DisplayToast(this, getString(R.string.guide_finish_toast));
        setResult(RESULT_OK);
        finish();
    }

    // ---------------------------------------------------------------- 协议文档

    private SpannableStringBuilder buildDocumentLinkText() {
        String text = getString(R.string.legal_consent_link_text);
        SpannableStringBuilder builder = new SpannableStringBuilder(text);
        applyClickableSpan(builder, text, "《用户协议》",
                () -> showDocumentDialog(R.string.app_agreement, R.string.app_agreement_content));
        applyClickableSpan(builder, text, "《免责声明》",
                () -> showDocumentDialog(R.string.app_privacy, R.string.app_privacy_content));
        return builder;
    }

    private void applyClickableSpan(SpannableStringBuilder builder, String fullText, String target, Runnable action) {
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
                super.updateDrawState(ds);
                ds.setColor(ContextCompat.getColor(GuideActivity.this, R.color.colorPrimary));
                ds.setUnderlineText(false);
            }
        }, start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    }

    private void showDocumentDialog(int titleResId, int contentResId) {
        ScrollView scrollView = new ScrollView(this);
        int padding = Math.round(getResources().getDisplayMetrics().density * 20f);
        TextView contentView = new TextView(this);
        contentView.setPadding(padding, padding, padding, padding);
        contentView.setLineSpacing(0f, 1.25f);
        contentView.setText(contentResId);
        scrollView.addView(contentView);

        new AlertDialog.Builder(this)
                .setTitle(titleResId)
                .setView(scrollView)
                .setPositiveButton(R.string.legal_document_close, null)
                .show();
    }
}
