package com.acooldog.toolbox.update.data;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Build;
import android.text.TextUtils;

import androidx.annotation.Nullable;

import com.acooldog.toolbox.update.domain.model.AppVersionInfo;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Set;

/**
 * 安装前四重校验：文件 sha256、包名、版本号、**签名指纹必须与当前应用完全一致**。
 * 签名校验是防"被替换成其它包"的关键；同时也能提前发现"换了签名"这类无法覆盖安装的情况。
 */
public final class ApkVerifier {

    private ApkVerifier() {
    }

    /** @return null 表示校验通过；否则返回失败原因。 */
    @Nullable
    public static String verify(Context context, File apk, AppVersionInfo expected) {
        if (apk == null || !apk.exists() || apk.length() <= 0) {
            return "安装包不存在或为空";
        }
        if (TextUtils.isEmpty(expected.getSha256()) || !expected.getSha256().matches("[a-fA-F0-9]{64}")) {
            return "缺少有效的 sha256 校验信息";
        }
        if (expected.getSizeBytes() > 0 && apk.length() != expected.getSizeBytes()) return "安装包大小不一致";
        if (!TextUtils.isEmpty(expected.getSha256())) {
            String actual = sha256(apk);
            if (!expected.getSha256().equalsIgnoreCase(actual)) {
                return "sha256 校验不一致";
            }
        }

        PackageManager manager = context.getPackageManager();
        PackageInfo archive = manager.getPackageArchiveInfo(
                apk.getAbsolutePath(),
                PackageManager.GET_SIGNING_CERTIFICATES
        );
        if (archive == null) {
            return "无法解析安装包";
        }
        if (!context.getPackageName().equals(archive.packageName)) {
            return "包名不一致：" + archive.packageName;
        }
        if (archive.getLongVersionCode() <= com.acooldog.toolbox.BuildConfig.VERSION_CODE) return "安装包版本必须高于当前版本";
        if (expected.getVersionCode() > 0 && archive.getLongVersionCode() != expected.getVersionCode()) {
            return "版本号不一致：" + archive.getLongVersionCode();
        }
        if (!sameSignatures(context, manager, archive)) {
            return "签名不一致（安装包可能被替换）";
        }
        return null;
    }

    private static boolean sameSignatures(Context context, PackageManager manager, PackageInfo archive) {
        Set<String> archiveDigests = signatureDigests(archive);
        if (archiveDigests.isEmpty()) {
            return false;
        }
        try {
            PackageInfo installed = manager.getPackageInfo(
                    context.getPackageName(),
                    PackageManager.GET_SIGNING_CERTIFICATES
            );
            Set<String> installedDigests = signatureDigests(installed);
            return !installedDigests.isEmpty() && installedDigests.equals(archiveDigests);
        } catch (PackageManager.NameNotFoundException exception) {
            return false;
        }
    }

    private static Set<String> signatureDigests(PackageInfo info) {
        Set<String> digests = new HashSet<>();
        Signature[] signatures = null;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && info.signingInfo != null) {
            signatures = info.signingInfo.hasMultipleSigners()
                    ? info.signingInfo.getApkContentsSigners()
                    : info.signingInfo.getSigningCertificateHistory();
        } else if (info.signatures != null) {
            signatures = info.signatures;
        }
        if (signatures == null) {
            return digests;
        }
        for (Signature signature : signatures) {
            try {
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                digests.add(toHex(digest.digest(signature.toByteArray())));
            } catch (Exception ignored) {
                // 单个签名计算失败不影响其它签名
            }
        }
        return digests;
    }

    /** 供下载服务写日志与提示：文件的 sha256，失败返回空串。 */
    public static String sha256Of(File file) {
        return sha256(file);
    }

    /** 取前 8 位，便于日志与用户提示里对比。 */
    public static String shortSha(String sha256) {
        if (sha256 == null) {
            return "";
        }
        return sha256.length() > 8 ? sha256.substring(0, 8) : sha256;
    }

    private static String sha256(File file) {
        try (InputStream input = new FileInputStream(file)) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                digest.update(buffer, 0, count);
            }
            return toHex(digest.digest());
        } catch (Exception exception) {
            return "";
        }
    }

    private static String toHex(byte[] bytes) {
        StringBuilder builder = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            builder.append(Character.forDigit((value >> 4) & 0xF, 16));
            builder.append(Character.forDigit(value & 0xF, 16));
        }
        return builder.toString();
    }
}
