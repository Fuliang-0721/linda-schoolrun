package com.acooldog.toolbox;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.StringRes;
import androidx.appcompat.app.AlertDialog;
import androidx.preference.EditTextPreference;
import androidx.preference.Preference;
import androidx.preference.PreferenceFragmentCompat;
import androidx.preference.SwitchPreferenceCompat;

import com.acooldog.toolbox.utils.AppLogReporter;
import com.acooldog.toolbox.utils.GoUtils;
import com.elvishew.xlog.XLog;

public class FragmentSettings extends PreferenceFragmentCompat {

    private void setupDecimalEditTextPreference(EditTextPreference preference) {
        if (preference != null) {
            preference.setSummaryProvider((Preference.SummaryProvider<EditTextPreference>) pref ->
                    getResources().getString(R.string.setting_current_value) + pref.getText());
            preference.setOnBindEditTextListener(editText -> {
                editText.setInputType(InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_CLASS_NUMBER);
                editText.setSelection(editText.length());
            });
            preference.setOnPreferenceChangeListener((pref, newValue) -> {
                if (newValue.toString().trim().isEmpty()) {
                    GoUtils.DisplayToast(this.getContext(), getResources().getString(R.string.app_error_input_null));
                    return false;
                }
                return true;
            });
        }
    }

    private void setupLinkPreference(String key, int urlStringResId) {
        Preference preference = findPreference(key);
        if (preference == null) {
            return;
        }
        preference.setOnPreferenceClickListener(pref -> {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(getString(urlStringResId)));
            startActivity(intent);
            return true;
        });
    }

    private void setupDocumentPreference(String key, @StringRes int titleResId, @StringRes int contentResId) {
        Preference preference = findPreference(key);
        if (preference == null) {
            return;
        }
        preference.setOnPreferenceClickListener(pref -> {
            showDocumentDialog(titleResId, contentResId);
            return true;
        });
    }

    private void showDocumentDialog(@StringRes int titleResId, @StringRes int contentResId) {
        if (getContext() == null) {
            return;
        }
        ScrollView scrollView = new ScrollView(getContext());
        int padding = Math.round(getResources().getDisplayMetrics().density * 20f);
        TextView contentView = new TextView(getContext());
        contentView.setPadding(padding, padding, padding, padding);
        contentView.setLineSpacing(0f, 1.25f);
        contentView.setText(getString(contentResId));
        scrollView.addView(contentView);

        new AlertDialog.Builder(requireContext())
                .setTitle(titleResId)
                .setView(scrollView)
                .setPositiveButton(R.string.legal_document_close, null)
                .show();
    }

    /** 上传运行日志：先确认，再后台打包上传（不含任何硬件标识）。 */
    private void confirmUploadLog() {
        if (getContext() == null) {
            return;
        }
        new AlertDialog.Builder(requireContext())
                .setTitle(R.string.upload_log_confirm_title)
                .setMessage(getString(R.string.upload_log_confirm_message,
                        AppLogReporter.describeReportSize(requireContext())))
                .setNegativeButton(R.string.legal_document_close, null)
                .setPositiveButton(R.string.upload_log_confirm_action, (dialog, which) -> {
                    GoUtils.DisplayToast(getContext(), getString(R.string.upload_log_sending));
                    AppLogReporter.uploadAsync(requireContext(), AppLogReporter.REASON_MANUAL,
                            (success, message) -> {
                                if (getContext() == null) {
                                    return;
                                }
                                GoUtils.DisplayToast(getContext(), success
                                        ? getString(R.string.upload_log_success, message)
                                        : getString(R.string.upload_log_failed, message));
                            });
                })
                .show();
    }

    private void showTelemetryChoices() {
        com.acooldog.toolbox.config.TelemetryStore store = new com.acooldog.toolbox.config.TelemetryStore(requireContext());
        android.widget.LinearLayout content = new android.widget.LinearLayout(requireContext());
        content.setOrientation(android.widget.LinearLayout.VERTICAL);
        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        content.setPadding(pad, pad, pad, pad);
        TextView description = new TextView(requireContext());
        description.setText(R.string.telemetry_description);
        content.addView(description);
        android.widget.CheckBox usage = new android.widget.CheckBox(requireContext());
        usage.setText(R.string.telemetry_usage);
        usage.setChecked(store.enabled());
        content.addView(usage);
        android.widget.CheckBox location = new android.widget.CheckBox(requireContext());
        location.setText(R.string.telemetry_location);
        location.setChecked(store.locationEnabled());
        content.addView(location);
        android.widget.CheckBox crash = new android.widget.CheckBox(requireContext());
        crash.setText(R.string.telemetry_crash); crash.setChecked(store.crashEnabled()); content.addView(crash);
        ScrollView scroll = new ScrollView(requireContext()); scroll.addView(content);
        new AlertDialog.Builder(requireContext()).setTitle(R.string.telemetry_title).setView(scroll)
                .setNeutralButton(R.string.telemetry_erase, (dialog, which) -> {
                    store.saveConsent(false, false, false); store.requestErase();
                    com.acooldog.toolbox.utils.CrashLogger.clearPending(requireContext());
                    com.acooldog.toolbox.utils.ClientTelemetry.consentChanged();
                    GoUtils.DisplayToast(requireContext(), getString(R.string.telemetry_saved));
                })
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.telemetry_save, (dialog, which) -> {
                    store.saveConsent(usage.isChecked(), location.isChecked(), crash.isChecked());
                    if (!crash.isChecked()) com.acooldog.toolbox.utils.CrashLogger.clearPending(requireContext());
                    com.acooldog.toolbox.utils.ClientTelemetry.consentChanged();
                    if (location.isChecked() && !com.acooldog.toolbox.config.SetupChecklist.isSatisfied(requireContext(),
                            com.acooldog.toolbox.config.SetupChecklist.STEP_LOCATION)) {
                        com.acooldog.toolbox.config.SetupChecklist.performFix(requireActivity(),
                                com.acooldog.toolbox.config.SetupChecklist.STEP_LOCATION);
                    }
                    GoUtils.DisplayToast(requireContext(), getString(R.string.telemetry_saved));
                }).show();
    }

    @Override
    public void onCreatePreferences(Bundle savedInstanceState, String rootKey) {
        addPreferencesFromResource(R.xml.preferences_main);

        Preference telemetryPreference = findPreference("setting_telemetry");
        if (telemetryPreference != null) telemetryPreference.setOnPreferenceClickListener(pref -> {
            showTelemetryChoices(); return true;
        });

        String verName = GoUtils.getVersionName(FragmentSettings.this.getContext());
        Preference pfVersion = findPreference("setting_version");
        if (pfVersion != null) {
            pfVersion.setSummary(verName);
        }

        EditTextPreference pfWalk = findPreference("setting_walk");
        setupDecimalEditTextPreference(pfWalk);

        EditTextPreference pfRun = findPreference("setting_run");
        setupDecimalEditTextPreference(pfRun);

        EditTextPreference pfBike = findPreference("setting_bike");
        setupDecimalEditTextPreference(pfBike);

        SwitchPreferenceCompat pLog = findPreference("setting_log_off");
        if (pLog != null) {
            pLog.setOnPreferenceChangeListener((preference, newValue) -> {
                if (((SwitchPreferenceCompat) preference).isChecked() != (Boolean) newValue) {
                    XLog.d(preference.getKey() + newValue);

                    if (Boolean.parseBoolean(newValue.toString())) {
                        XLog.d("on");
                    } else {
                        XLog.d("off");
                    }
                    return true;
                } else {
                    return false;
                }
            });
        }

        EditTextPreference pfPosHisValid = findPreference("setting_pos_history");
        setupDecimalEditTextPreference(pfPosHisValid);

        EditTextPreference pfLatOffset = findPreference("setting_lat_max_offset");
        setupDecimalEditTextPreference(pfLatOffset);

        EditTextPreference pfLonOffset = findPreference("setting_lon_max_offset");
        setupDecimalEditTextPreference(pfLonOffset);

        setupDocumentPreference("setting_user_agreement", R.string.app_agreement, R.string.app_agreement_content);
        setupDocumentPreference("setting_disclaimer", R.string.app_privacy, R.string.app_privacy_content);

        Preference pfUploadLog = findPreference("setting_upload_log");
        if (pfUploadLog != null) {
            pfUploadLog.setOnPreferenceClickListener(pref -> {
                confirmUploadLog();
                return true;
            });
        }

        Preference pfUpdateHistory = findPreference("setting_update_history");
        if (pfUpdateHistory != null) {
            // 「更新记录」仅内部版可见（版本名带 D 的内部构建）
            boolean internalBuild = GoUtils.isInternalBuild();
            pfUpdateHistory.setVisible(internalBuild);
            if (internalBuild) {
                pfUpdateHistory.setOnPreferenceClickListener(pref -> {
                    startActivity(new Intent(requireContext(), UpdateHistoryActivity.class));
                    return true;
                });
            }
        }
    }
}
