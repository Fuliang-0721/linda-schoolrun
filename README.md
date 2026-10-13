# 临大校跑 · Linyi Campus Run

面向 Android 定位功能开发与测试的路线模拟工具。把地图选点、路线管理和模拟控制放在同一个应用中，并提供可自行部署的管理后端。

## 能做什么

- **路线管理**：地图绘制、地点搜索、本地保存、导入与云端路线浏览。
- **模拟控制**：按速度或步频配置路线，支持多圈、暂停、继续及悬浮控制。
- **更新管理**：版本检查、灰度下发、后台下载，以及安装前的文件哈希、包名、版本和签名校验。
- **管理后台**：公告、服务状态、内部账号、版本记录和诊断数据管理。
- **上报设置**：统计、崩溃和最近一次真实位置默认开启，可分别关闭或全部关闭并请求删除。

## 运行要求

| 项目 | 要求 |
|---|---|
| Android | 9.0 / API 28 起，arm64-v8a |
| 客户端构建 | JDK 21、Android SDK 36、Build Tools 36.1.0 |
| 后端 | Python 3.12；生产使用 MySQL 8，开发测试支持 SQLite |
| 网络 | 自行配置 HTTPS 后端与百度地图 Android AK |

应用使用 Android 的模拟位置机制，需要在开发者选项中选择本应用。系统仍会标记模拟位置；本项目不保证第三方应用接受模拟数据，也不提供规避检测的承诺。

## 快速开始

1. 安装 JDK 与 Android SDK，设置 `JAVA_HOME`、`ANDROID_HOME`。
2. 参考 `local.properties.example` 创建本机 `local.properties`，配置地图 AK、签名指纹及自己的后端地址。
3. 构建 debug 包并运行测试：

```bash
./gradlew :app:assembleDebug :app:testDebugUnitTest
```

Windows 使用 `gradlew.bat`。Debug 构建不需要维护者的正式签名；正式发布需要配置你自己的 keystore。

后端开发：

```bash
cd backend
python -m venv .venv
# 激活虚拟环境后：
python -m pip install -r requirements-dev.txt
# 创建 .env，设置 APP_ENV=development、DATABASE_URL=sqlite:///./dev.db
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

正式 App 仅连接 HTTPS。未配置地图 AK 或后端时，源码可以构建，但地图或服务确认不可正常工作。

## 使用与数据说明

服务端确认是使用模拟功能的前提。客户端使用最长两分钟的服务授权有效期，在到期前预留网络确认时间；服务端明确停用或有效期届满未获确认时停止模拟。运行状态使用单调时钟，系统日期调整不延长授权。

内部账号由后台创建并通过服务端验证，没有通用内置账号或密码。安装标识随机生成，不读取 IMEI 等硬件身份。数据上报设置及删除限制见 [隐私与数据](docs/PRIVACY.md)。

## 文档

- [开发与测试](docs/DEVELOPMENT.md)
- [部署与版本发布](docs/DEPLOYMENT.md)
- [隐私与数据](docs/PRIVACY.md)
- [更新记录](CHANGELOG.md)
- [安全问题反馈](SECURITY.md)

## 贡献

欢迎通过 Issue 提供可复现的问题场景，通过 Pull Request 提交修复。请说明 Android 版本、设备型号、预期与实际行为，并移除日志中的账号、凭据、位置和个人信息。提交代码前运行相关测试，不要提交本地配置、密钥、数据库或安装包。

本项目用于获得授权的开发、调试和研究场景，请勿用于作弊、冒充真实位置、侵犯隐私或其他不当用途。
