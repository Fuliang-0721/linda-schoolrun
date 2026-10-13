# 部署配置

使用 `docker-compose.yml` 与 `.env.production.example` 开始部署，详见 [部署与版本发布](../../docs/DEPLOYMENT.md)。

`Caddyfile` 和 `nginx/schoolrun-backend.conf` 均将下载请求转发给后端验证限时授权。不要直接公开 releases 目录。
