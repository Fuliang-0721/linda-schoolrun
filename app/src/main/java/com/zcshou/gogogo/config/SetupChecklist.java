package com.acooldog.toolbox.config;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.ContextCompat;

import com.acooldog.toolbox.R;
import com.acooldog.toolbox.utils.GoUtils;

/**
 * 使用前设置的统一定义：向导（GuideActivity）与设置检查页（SettingsCheckActivity）共用，
 * 避免两处判定逻辑不一致。
 */
public final class SetupChecklist {
    public static final int STEP_COUNT = 9;
    public static final int STEP_DEVELOPER = 0;
    public static final int STEP_LOCATION = 1;
    public static final int STEP_BACKGROUND = 2;
    public static final int STEP_OVERLAY = 3;
    public static final int STEP_ACTIVITY = 4;
    /** 电池优化/后台限制：ColorOS、MIUI 等会"速冻"后台服务，导致模拟跑一会儿就停。 */
    public static final int STEP_BATTERY = 5;
    /** 通知权限（Android 13+ 需运行时授权）：下载进度与完成提醒依赖它。 */
    public static final int STEP_NOTIFICATION = 6;
    /** 安装应用权限：自更新需要"安装未知应用"授权才能拉起系统安装界面。 */
    public static final int STEP_INSTALL = 7;
    public static final int STEP_CONSENT = 8;

    public static final int REQ_LOCATION = 301;
    public static final int REQ_BACKGROUND = 302;
    public static final int REQ_ACTIVITY = 303;
    public static final int REQ_NOTIFICATION = 304;

    private static final int[] STEP_ART = new int[]{
            R.drawable.guide_step1,
            R.drawable.guide_step2,
            R.drawable.guide_step3,
            R.drawable.guide_step4,
            R.drawable.guide_step5,
            R.drawable.guide_step3,
            R.drawable.guide_step5,
            R.drawable.guide_step4,
            R.drawable.guide_step6
    };

    private static final int[] STEP_TITLE = new int[]{
            R.string.guide_step_developer_title,
            R.string.guide_step_location_title,
            R.string.guide_step_background_title,
            R.string.guide_step_overlay_title,
            R.string.guide_step_activity_title,
            R.string.guide_step_battery_title,
            R.string.guide_step_notification_title,
            R.string.guide_step_install_title,
            R.string.guide_step_consent_title
    };

    private static final int[] STEP_DESC = new int[]{
            R.string.guide_step_developer_desc,
            R.string.guide_step_location_desc,
            R.string.guide_step_background_desc,
            R.string.guide_step_overlay_desc,
            R.string.guide_step_activity_desc,
            R.string.guide_step_battery_desc,
            R.string.guide_step_notification_desc,
            R.string.guide_step_install_desc,
            R.string.guide_step_consent_desc
    };

    private SetupChecklist() {
    }

    public static int artRes(int step) {
        return STEP_ART[step];
    }

    public static int titleRes(int step) {
        return STEP_TITLE[step];
    }

    public static int descRes(int step) {
        return STEP_DESC[step];
    }

    public static String title(Context context, int step) {
        return context.getString(titleRes(step));
    }

    public static String description(Context context, int step) {
        return context.getString(descRes(step));
    }

    /** 唯一的强制项：模拟位置信息应用。 */
    public static boolean isCritical(int step) {
        return step == STEP_DEVELOPER;
    }

    public static boolean canSkip(int step) {
        return step == STEP_LOCATION
                || step == STEP_BACKGROUND
                || step == STEP_OVERLAY
                || step == STEP_ACTIVITY
                || step == STEP_BATTERY
                || step == STEP_NOTIFICATION
                || step == STEP_INSTALL;
    }

    /** 第一个未完成的步骤；全部完成返回 -1。 */
    public static int firstUnsatisfied(Context context) {
        for (int step = 0; step < STEP_COUNT; step++) {
            if (!isSatisfied(context, step)) {
                return step;
            }
        }
        return -1;
    }

    /** 未完成项名称，用「、」连接；全部完成返回空串。 */
    public static String unsatisfiedSummary(Context context) {
        StringBuilder builder = new StringBuilder();
        for (int step = 0; step < STEP_COUNT; step++) {
            if (isSatisfied(context, step)) {
                continue;
            }
            if (builder.length() > 0) {
                builder.append('、');
            }
            builder.append(title(context, step));
        }
        return builder.toString();
    }

    public static boolean isSatisfied(Context context, int step) {
        switch (step) {
            case STEP_DEVELOPER:
                return isDeveloperOptionsEnabled(context) && GoUtils.isAllowMockLocation(context);
            case STEP_LOCATION:
                return hasPermission(context, Manifest.permission.ACCESS_FINE_LOCATION)
                        || hasPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION);
            case STEP_BACKGROUND:
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                    return true;
                }
                return hasPermission(context, Manifest.permission.ACCESS_BACKGROUND_LOCATION);
            case STEP_OVERLAY:
                return Settings.canDrawOverlays(context);
            case STEP_ACTIVITY:
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                    return true;
                }
                return hasPermission(context, Manifest.permission.ACTIVITY_RECOGNITION);
            case STEP_BATTERY:
                return isIgnoringBatteryOptimizations(context);
            case STEP_NOTIFICATION:
                return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                        || hasPermission(context, Manifest.permission.POST_NOTIFICATIONS);
            case STEP_INSTALL:
                return Build.VERSION.SDK_INT < Build.VERSION_CODES.O
                        || context.getPackageManager().canRequestPackageInstalls();
            case STEP_CONSENT:
                return LegalConsentStore.isConsentAccepted(context);
            default:
                return false;
        }
    }

    public static int satisfiedCount(Context context) {
        int count = 0;
        for (int step = 0; step < STEP_COUNT; step++) {
            if (isSatisfied(context, step)) {
                count++;
            }
        }
        return count;
    }

    public static boolean hasPermission(Context context, String permission) {
        return ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED;
    }

    public static boolean isDeveloperOptionsEnabled(Context context) {
        try {
            return Settings.Global.getInt(context.getContentResolver(), "development_settings_enabled", 0) == 1;
        } catch (Exception exception) {
            return false;
        }
    }

    /** 跳转对应系统页面；需要运行时权限的步骤直接弹权限框。 */
    public static void performFix(Activity activity, int step) {
        switch (step) {
            case STEP_DEVELOPER:
                openDeveloperOptions(activity);
                break;
            case STEP_LOCATION:
                activity.requestPermissions(
                        new String[]{
                                Manifest.permission.ACCESS_FINE_LOCATION,
                                Manifest.permission.ACCESS_COARSE_LOCATION
                        },
                        REQ_LOCATION
                );
                break;
            case STEP_BACKGROUND:
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    openAppDetailsSettings(activity);
                } else {
                    activity.requestPermissions(
                            new String[]{Manifest.permission.ACCESS_BACKGROUND_LOCATION},
                            REQ_BACKGROUND
                    );
                }
                break;
            case STEP_OVERLAY:
                openOverlaySettings(activity);
                break;
            case STEP_ACTIVITY:
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    activity.requestPermissions(
                            new String[]{Manifest.permission.ACTIVITY_RECOGNITION},
                            REQ_ACTIVITY
                    );
                }
                break;
            case STEP_BATTERY:
                openBatteryOptimizationSettings(activity);
                break;
            case STEP_NOTIFICATION:
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    activity.requestPermissions(
                            new String[]{Manifest.permission.POST_NOTIFICATIONS},
                            REQ_NOTIFICATION
                    );
                } else {
                    openAppNotificationSettings(activity);
                }
                break;
            case STEP_INSTALL:
                openInstallPermissionSettings(activity);
                break;
            default:
                break;
        }
    }

    public static void openDeveloperOptions(Activity activity) {
        if (!isDeveloperOptionsEnabled(activity)) {
            GoUtils.DisplayToast(activity, activity.getString(R.string.guide_dev_not_enabled));
            return;
        }
        try {
            activity.startActivity(new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS));
        } catch (Exception exception) {
            GoUtils.DisplayToast(activity, activity.getString(R.string.guide_dev_not_enabled));
        }
    }

    public static void openOverlaySettings(Activity activity) {
        try {
            activity.startActivity(new Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + activity.getPackageName())
            ));
        } catch (Exception exception) {
            openAppDetailsSettings(activity);
        }
    }

    /** 允许安装未知应用（自更新安装所需）。 */
    public static void openInstallPermissionSettings(Activity activity) {
        try {
            activity.startActivity(new Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + activity.getPackageName())));
        } catch (Exception exception) {
            openAppDetailsSettings(activity);
        }
    }

    /** 应用通知设置页（低于 Android 13 时的兜底入口）。 */
    public static void openAppNotificationSettings(Activity activity) {
        try {
            Intent intent = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS);
            intent.putExtra(Settings.EXTRA_APP_PACKAGE, activity.getPackageName());
            activity.startActivity(intent);
        } catch (Exception exception) {
            openAppDetailsSettings(activity);
        }
    }

    /** 是否已豁免电池优化；读不到时按"已豁免"处理，避免误报。 */
    public static boolean isIgnoringBatteryOptimizations(Context context) {
        try {
            android.os.PowerManager powerManager =
                    (android.os.PowerManager) context.getSystemService(Context.POWER_SERVICE);
            return powerManager == null
                    || powerManager.isIgnoringBatteryOptimizations(context.getPackageName());
        } catch (Exception exception) {
            return true;
        }
    }

    /** 申请电池优化白名单；国产系统没有该页时依次回退到电池设置页、应用详情页。 */
    public static void openBatteryOptimizationSettings(Activity activity) {
        try {
            Intent request = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
            request.setData(Uri.parse("package:" + activity.getPackageName()));
            activity.startActivity(request);
            return;
        } catch (Exception ignored) {
            // 部分 ROM 无此页面
        }
        try {
            activity.startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
            return;
        } catch (Exception ignored) {
            // 继续回退
        }
        openAppDetailsSettings(activity);
    }

    public static void openAppDetailsSettings(Activity activity) {
        try {
            activity.startActivity(new Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.parse("package:" + activity.getPackageName())
            ));
        } catch (Exception exception) {
            GoUtils.DisplayToast(activity, activity.getString(R.string.app_error_permission));
        }
    }
}
