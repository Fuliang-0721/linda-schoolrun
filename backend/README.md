# 管理后端

基于 FastAPI、SQLAlchemy 和 MySQL 的管理服务，提供服务状态、账号、路线、版本下发及诊断数据 API。

开发：Python 3.12，安装 `requirements-dev.txt`，以 `APP_ENV=development` 和本地 SQLite 配置启动。生产配置强密码、独立随机密钥和 HTTPS。

详细步骤见 [开发指南](../docs/DEVELOPMENT.md) 与 [部署指南](../docs/DEPLOYMENT.md)。
