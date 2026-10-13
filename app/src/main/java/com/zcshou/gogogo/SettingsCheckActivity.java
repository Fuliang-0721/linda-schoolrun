package com.acooldog.toolbox;

import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;

import com.acooldog.toolbox.config.SetupChecklist;
import com.google.android.material.appbar.MaterialToolbar;

/**
 * 设置检查：随时查看使用前的必要设置是否已完成，并可直接跳去设置。
 */
public class SettingsCheckActivity extends BaseActivity {
    private static final int COLOR_DONE = 0xFF2E7D32;
    private static final int COLOR_PENDING = 0xFFD97706;

    private LinearLayout itemsContainer;
    private TextView summaryView;
    private TextView hintView;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings_check);

        MaterialToolbar toolbar = findViewById(R.id.toolbar_settings_check);
        toolbar.setNavigationOnClickListener(v -> finish());

        itemsContainer = findViewById(R.id.layout_settings_check_items);
        summaryView = findViewById(R.id.tv_settings_check_summary);
        hintView = findViewById(R.id.tv_settings_check_hint);
    }

    @Override
    protected void onResume() {
        super.onResume();
        render();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        render();
    }

    private void render() {
        int doneCount = SetupChecklist.satisfiedCount(this);
        summaryView.setText(getString(
                R.string.settings_check_summary_format,
                doneCount,
                SetupChecklist.STEP_COUNT
        ));
        hintView.setText(doneCount >= SetupChecklist.STEP_COUNT
                ? R.string.settings_check_all_done
                : R.string.settings_check_hint);

        itemsContainer.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(this);
        for (int step = 0; step < SetupChecklist.STEP_COUNT; step++) {
            itemsContainer.addView(buildRow(inflater, step));
        }
    }

    private View buildRow(@NonNull LayoutInflater inflater, int step) {
        View row = inflater.inflate(R.layout.item_settings_check_row, itemsContainer, false);
        TextView statusView = row.findViewById(R.id.tv_check_status);
        TextView titleView = row.findViewById(R.id.tv_check_title);
        TextView descView = row.findViewById(R.id.tv_check_desc);
        Button actionButton = row.findViewById(R.id.btn_check_action);

        boolean satisfied = SetupChecklist.isSatisfied(this, step);
        statusView.setText(satisfied ? "✓" : "!");
        statusView.setTextColor(satisfied ? COLOR_DONE : COLOR_PENDING);
        titleView.setText(SetupChecklist.titleRes(step));
        descView.setText(statusTextRes(step, satisfied));
        descView.setTextColor(satisfied ? COLOR_DONE : COLOR_PENDING);

        if (step == SetupChecklist.STEP_CONSENT) {
            actionButton.setVisibility(View.VISIBLE);
            actionButton.setText(R.string.settings_check_action_docs);
            actionButton.setOnClickListener(v -> showConsentDocuments());
            return row;
        }

        if (satisfied) {
            actionButton.setVisibility(View.GONE);
            return row;
        }

        actionButton.setVisibility(View.VISIBLE);
        actionButton.setText(actionTextRes(step));
        actionButton.setOnClickListener(v -> SetupChecklist.performFix(this, step));
        return row;
    }

    private int statusTextRes(int step, boolean satisfied) {
        if (satisfied) {
            return R.string.settings_check_status_done;
        }
        return SetupChecklist.isCritical(step)
                ? R.string.settings_check_status_critical
                : R.string.settings_check_status_pending;
    }

    private int actionTextRes(int step) {
        switch (step) {
            case SetupChecklist.STEP_LOCATION:
            case SetupChecklist.STEP_ACTIVITY:
            case SetupChecklist.STEP_NOTIFICATION:
                return R.string.settings_check_action_grant;
            default:
                return R.string.settings_check_action_fix;
        }
    }

    private void showConsentDocuments() {
        new AlertDialog.Builder(this)
                .setTitle(R.string.setting_user_agreement)
                .setPositiveButton(R.string.app_agreement,
                        (dialog, which) -> showDocument(R.string.app_agreement, R.string.app_agreement_content))
                .setNegativeButton(R.string.app_privacy,
                        (dialog, which) -> showDocument(R.string.app_privacy, R.string.app_privacy_content))
                .setNeutralButton(R.string.legal_document_close, null)
                .show();
    }

    private void showDocument(int titleResId, int contentResId) {
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
