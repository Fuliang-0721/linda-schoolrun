package com.acooldog.toolbox;

import android.os.Bundle;
import android.text.TextUtils;
import android.widget.TextView;

import androidx.annotation.Nullable;

import com.acooldog.toolbox.config.InternalAuthStore;
import com.acooldog.toolbox.share.domain.model.InternalAccountProfile;
import com.acooldog.toolbox.utils.GoUtils;
import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.textfield.TextInputEditText;

/** Internal account login. */
public class InternalLoginActivity extends BaseActivity {
    private InternalAuthStore authStore;
    private TextView statusView;
    private TextInputEditText usernameInput;
    private TextInputEditText passwordInput;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_internal_login);

        authStore = new InternalAuthStore(getApplicationContext());

        MaterialToolbar toolbar = findViewById(R.id.toolbar_internal_login);
        toolbar.setNavigationOnClickListener(v -> finish());

        statusView = findViewById(R.id.internal_login_status);
        usernameInput = findViewById(R.id.internal_login_username_input);
        passwordInput = findViewById(R.id.internal_login_password_input);

        findViewById(R.id.internal_login_button).setOnClickListener(v -> login());
        findViewById(R.id.internal_logout_button).setOnClickListener(v -> logout());

        refreshSessionState();
    }

    private void refreshSessionState() {
        InternalAccountProfile profile = authStore.getProfile();
        if (profile == null) {
            statusView.setText(getString(R.string.internal_login_status_logged_out));
            return;
        }
        statusView.setText(getString(
                R.string.internal_login_status_logged_in,
                profile.getUsername(),
                profile.getTesterTypeLabel()
        ));
        if (usernameInput != null && TextUtils.isEmpty(usernameInput.getText())) {
            usernameInput.setText(profile.getUsername());
        }
    }

    private void login() {
        String username = text(usernameInput);
        String password = text(passwordInput);
        if (TextUtils.isEmpty(username)) {
            GoUtils.DisplayToast(this, getString(R.string.internal_login_need_username));
            return;
        }
        if (TextUtils.isEmpty(password)) {
            GoUtils.DisplayToast(this, getString(R.string.internal_login_need_password));
            return;
        }
        findViewById(R.id.internal_login_button).setEnabled(false);
        new Thread(() -> {
            String error = null;
            try { com.acooldog.toolbox.share.presentation.ShareModule.from(this).shareApiClient().login(username, password); }
            catch (Exception e) { error = e.getMessage(); }
            final String result = error;
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                findViewById(R.id.internal_login_button).setEnabled(true);
                passwordInput.setText("");
                if (result != null) { GoUtils.DisplayToast(this, result); return; }
                refreshSessionState();
                GoUtils.DisplayToast(this, getString(R.string.internal_login_success));
                finish();
            });
        }, "internal-login").start();
    }

    private void logout() {
        authStore.clear();
        com.acooldog.toolbox.config.RemoteAccessGate.invalidate(this);
        if (passwordInput != null) {
            passwordInput.setText("");
        }
        refreshSessionState();
        GoUtils.DisplayToast(this, getString(R.string.internal_logout_success));
    }

    private String text(@Nullable TextInputEditText input) {
        if (input == null || input.getText() == null) {
            return "";
        }
        return input.getText().toString().trim();
    }
}
