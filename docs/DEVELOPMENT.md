# 开发与测试

## 环境

客户端使用 Java 11 语言级别；构建工具运行于 JDK 21。安装 SDK platform 36、Build Tools 36.1.0，以及构建要求的 NDK 26.2.11394342。仅生成 arm64-v8a。

`local.properties` 中的 `sdk.dir` 填本机 SDK 路径；也可使用 `ANDROID_HOME`。地图和后端配置可放入本机 properties、Gradle properties 或同名环境变量。

```properties
MAPS_API_KEY=your_android_map_key
MAPS_SAFE_CODE=YOUR_SIGNING_SHA1;com.acooldog.toolbox
SHARE_API_BASE_URL=https://app.example.com/
```

百度地图 AK 应绑定你的 applicationId 与实际签名证书。库文件由项目现有 `app/libs` 提供；更换版本时同时核对 SDK 条款和设备兼容性。

## 构建

```bash
./gradlew :app:assembleDebug :app:testDebugUnitTest
```

Windows 改用 `gradlew.bat`。正式构建配置 `RELEASE_STORE_FILE`（绝对路径）、`RELEASE_STORE_PASSWORD`、`RELEASE_KEY_ALIAS`、`RELEASE_KEY_PASSWORD`；未设置时正式构建会失败，但不影响 debug 和测试。

```bash
./gradlew :app:assembleRelease -PversionSuffix=D
```

`D` 为版本展示后缀，实际内部权限由服务端账号决定。不要降低 versionCode；发布前由维护者选择新版本号、签名和目标渠道。

## 后端测试

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

开发 `.env` 设置 `APP_ENV=development`、`DATABASE_URL=sqlite:///./dev.db`。生产使用 MySQL 8；修改模型时也要添加老库迁移，并验证重复执行。

## 目录

| 路径 | 内容 |
|---|---|
| app/src/main | Android 应用、资源和模拟/更新流程 |
| app/src/test | JVM 单元测试 |
| backend/app | HTTP API、业务服务、数据库与管理页面 |
| backend/tests | 后端与安全回归测试 |
| backend/deploy | 容器、反向代理与示例配置 |

真机验收应覆盖定位权限撤回、开发者模拟位置设置、后台/锁屏恢复、两分钟断网停止、通知拒绝、未知来源安装授权和安装取消。JVM 测试不能替代这些设备行为验证。
