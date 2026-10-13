package com.acooldog.toolbox.home;

import android.content.Context;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.acooldog.toolbox.BuildConfig;
import com.acooldog.toolbox.R;
import com.acooldog.toolbox.config.InternalAuthStore;
import com.acooldog.toolbox.share.domain.model.InternalAccountProfile;

import android.widget.TextView;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class HomeMineFragment extends Fragment {
    private ExecutorService ioExecutor;
    private InternalAuthStore authStore;
    private TextView internalLoginSummaryView;

    public interface Actions {
        void onUpdateClicked();

        void onSettingsCheckClicked();

        void onSettingsClicked();

        void onInternalLoginClicked();

        void onDeveloperOptionsClicked();
    }

    public static HomeMineFragment newInstance() {
        return new HomeMineFragment();
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_home_mine, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        ioExecutor = Executors.newSingleThreadExecutor();
        if (getContext() != null) {
            authStore = new InternalAuthStore(getContext().getApplicationContext());
        }
        bindInternalLoginState(view);
        bindUpdateSummary(view);
        Actions actions = getActions();
        if (actions == null) {
            return;
        }
        view.findViewById(R.id.card_update).setOnClickListener(v -> actions.onUpdateClicked());
        view.findViewById(R.id.card_settings_check).setOnClickListener(v -> actions.onSettingsCheckClicked());
        view.findViewById(R.id.card_settings).setOnClickListener(v -> actions.onSettingsClicked());
        view.findViewById(R.id.card_internal_login).setOnClickListener(v -> actions.onInternalLoginClicked());
        view.findViewById(R.id.card_dev).setOnClickListener(v -> actions.onDeveloperOptionsClicked());
    }

    @Override
    public void onResume() {
        super.onResume();
        bindInternalLoginState(getView());
    }

    @Override
    public void onDestroyView() {
        if (ioExecutor != null) {
            ioExecutor.shutdownNow();
            ioExecutor = null;
        }
        internalLoginSummaryView = null;
        super.onDestroyView();
    }

    @Nullable
    private Actions getActions() {
        if (getActivity() instanceof Actions) {
            return (Actions) getActivity();
        }
        return null;
    }

    private void bindUpdateSummary(@Nullable View root) {
        if (root == null) {
            return;
        }
        TextView summary = root.findViewById(R.id.tv_home_update_summary);
        if (summary != null) {
            String text = getString(R.string.update_card_summary, BuildConfig.VERSION_NAME);
            if (authStore != null && authStore.isLoggedIn()) {
                text = text + getString(R.string.update_card_channel_internal);
            }
            summary.setText(text);
        }
    }

    private void bindInternalLoginState(@Nullable View root) {
        if (root == null) {
            return;
        }
        internalLoginSummaryView = root.findViewById(R.id.home_internal_login_summary);
        renderInternalLoginState();
    }

    private void renderInternalLoginState() {
        if (internalLoginSummaryView == null || authStore == null) {
            return;
        }
        InternalAccountProfile profile = authStore.getProfile();
        if (profile != null && !profile.getUsername().isEmpty()) {
            internalLoginSummaryView.setText(getString(
                    R.string.home_internal_login_logged_in,
                    profile.getUsername(),
                    profile.getTesterTypeLabel()
            ));
        } else {
            internalLoginSummaryView.setText(R.string.home_internal_login_summary);
        }
    }

}
