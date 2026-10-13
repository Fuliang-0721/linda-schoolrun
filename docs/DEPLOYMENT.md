# 部署与版本发布

## Docker Compose

在有域名与 HTTPS 的服务器上，将 `backend/deploy/.env.production.example` 复制为同目录 `.env`，填写域名、证书邮箱、数据库密码、管理员密码及两个独立的随机密钥。

- `APP_ENV=production`。
- 管理密码至少 16 个字符；`ADMIN_SESSION_SECRET`、`MOBILE_AUTH_SECRET` 各至少 32 个字符且互不相同。不要使用示例值。
- `ADMIN_PUBLIC_ORIGIN=https://app.example.com` 必须与浏览器实际访问的 origin 一致。
- `RELEASE_PUBLIC_BASE_URL=https://app.example.com/dl`。
- `CORS_ALLOW_ORIGINS` 默认留空；管理写操作只接受同源浏览器请求。使用脚本管理时需提供匹配的 `Origin` 请求头。

```bash
cd backend/deploy
docker compose up -d --build
```

管理入口为 `/admin`，版本及设备工具在 `/admin/ops`。首次使用前自行配置管理员账号，不存在通用生产密码。

## 从旧版本升级

1. 备份数据库并验证能恢复。
2. 更新应用及反向代理配置，配置管理员公开 origin 和强密钥。
3. 启动时迁移补齐服务状态 scope、日志安装凭据哈希等字段。
4. 在管理后台创建内部账号。旧客户端本地登录不再授予内部权限；需要安装新客户端并重新登录。
5. 旧日志没有安装令牌哈希，无法通过新客户端证明所有权自动删除；由管理员核对后清理。

新版 `/dl/` 必须转发给 FastAPI，不能继续直接暴露 releases 静态目录。更新接口签发 30 分钟下载授权，支持 Range；过期后重新检查更新。第三方镜像不受本服务访问控制，敏感内部 APK 不应放在公开镜像上。

## 发布 APK

管理员上传到 `/api/admin/releases/upload` 后，服务端流式计算 SHA-256，按内容哈希命名文件，防止覆盖已有包。用返回的地址、大小、哈希创建草稿，验证签名与 versionCode 后再发布。

建议先内部测试，再明确发布 stable。撤销记录会停止后续版本发现；已签发的下载链接最多仍有效 30 分钟。删除记录不会自动清理其安装包文件。

## 运行要求

只有反向代理对外开放端口。数据库和 API 保持内网或回环监听。限制日志访问，设置数据库/备份保留时间并演练删除请求。当前应用限流为单进程内存实现；多进程或多实例部署需要网关或共享存储限流。

服务器更新不会自动部署到任何已有实例。先在测试环境验证数据库迁移和客户端兼容性，再安排正式升级。
