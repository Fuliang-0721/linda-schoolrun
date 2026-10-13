# Linyi Campus Run

An Android route simulation tool for authorized location development and testing, with a self-hosted FastAPI management backend.

Features include map-based route creation, local route management, speed/cadence simulation, pause/resume, floating controls, staged updates and an administration interface.

Requires Android 9+ on arm64-v8a. Build with JDK 21, Android SDK 36 and Build Tools 36.1.0:

```bash
./gradlew :app:assembleDebug :app:testDebugUnitTest
```

Configure your own map API key and HTTPS backend using `local.properties.example`. Debug builds do not require the maintainer’s release key. Release builds require your own signing configuration.

Simulation requires server confirmation. A service lease expires after two minutes without renewal; an explicit denial stops simulation. Android continues to identify locations as mock data.

Usage, crash and latest real-location reporting are enabled by default and can be disabled independently. Users can request deletion; offline requests retry when the app next connects. See the [Chinese documentation](README.md) for setup, deployment and privacy details.

Use only for authorized development, debugging and research. Do not use this project to cheat, misrepresent real location or violate privacy.
