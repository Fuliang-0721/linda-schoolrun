package com.acooldog.toolbox.share.domain.model;

public final class AppClientConfig {
    private final String noticeTitle;
    private final String noticeMessage;
    private final String qqGroupNumber;
    private final String bilibiliText;
    private final String bilibiliUrl;
    private final boolean killSwitch;
    private final String killSwitchMessage;

    public AppClientConfig(
            String noticeTitle,
            String noticeMessage,
            String qqGroupNumber,
            String bilibiliText,
            String bilibiliUrl,
            boolean killSwitch,
            String killSwitchMessage
    ) {
        this.noticeTitle = noticeTitle == null ? "" : noticeTitle.trim();
        this.noticeMessage = noticeMessage == null ? "" : noticeMessage.trim();
        this.qqGroupNumber = qqGroupNumber == null ? "" : qqGroupNumber.trim();
        this.bilibiliText = bilibiliText == null ? "" : bilibiliText.trim();
        this.bilibiliUrl = bilibiliUrl == null ? "" : bilibiliUrl.trim();
        this.killSwitch = killSwitch;
        this.killSwitchMessage = killSwitchMessage == null ? "" : killSwitchMessage.trim();
    }

    public String getNoticeTitle() {
        return noticeTitle;
    }

    public String getNoticeMessage() {
        return noticeMessage;
    }

    public String getQqGroupNumber() {
        return qqGroupNumber;
    }

    public String getBilibiliText() {
        return bilibiliText;
    }

    public String getBilibiliUrl() {
        return bilibiliUrl;
    }

    /** 远程关闭开关：true 表示维护者已关闭全部客户端。 */
    public boolean isKillSwitch() {
        return killSwitch;
    }

    public String getKillSwitchMessage() {
        return killSwitchMessage;
    }
}
