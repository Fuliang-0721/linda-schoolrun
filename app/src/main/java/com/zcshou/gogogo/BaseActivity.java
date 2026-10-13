package com.acooldog.toolbox;

import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import androidx.appcompat.app.AppCompatActivity;
import com.acooldog.toolbox.config.RemoteAccessGate;
import com.acooldog.toolbox.config.AppUpdateStore;

public class BaseActivity extends AppCompatActivity {
    private View blocker;
    private boolean resumed;
    private long generation;
    private final Handler gateHandler = new Handler(Looper.getMainLooper());
    private final Runnable check = this::checkAccess;
    @Override protected void onResume() {
        super.onResume(); resumed = true;
        if (!(this instanceof GuideActivity) && !(this instanceof InternalLoginActivity)) checkAccess();
    }
    @Override protected void onPause() {
        resumed = false; generation++; gateHandler.removeCallbacks(check); super.onPause();
    }
    private void blockInput() {
        if (blocker != null) return;
        blocker = new View(this); blocker.setClickable(true); blocker.setFocusable(true);
        ((ViewGroup)getWindow().getDecorView()).addView(blocker, new ViewGroup.LayoutParams(-1,-1));
    }
    private void unblockInput() {
        if (blocker != null) { ((ViewGroup)blocker.getParent()).removeView(blocker); blocker = null; }
    }
    private void checkAccess() {
        if (!resumed || isFinishing()) return;
        blockInput(); long ticket = ++generation;
        RemoteAccessGate.confirm(this, (allowed, message) -> {
            if (!resumed || generation != ticket || isDestroyed()) return;
            if (!allowed) { RemoteAccessGate.showBlockedDialog(this, message, this::checkAccess); return; }
            if (new AppUpdateStore(this).isForceBlocked()) {
                RemoteAccessGate.stop(this);
                com.acooldog.toolbox.update.presentation.AppUpdateController.checkAndPrompt(this, true);
            } else unblockInput();
            gateHandler.postDelayed(check, RemoteAccessGate.RENEW_MILLIS);
        });
    }
}
