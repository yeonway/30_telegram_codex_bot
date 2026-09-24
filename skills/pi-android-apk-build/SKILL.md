---
name: pi-android-apk-build
description: Build and verify Android APKs on the Raspberry Pi with the installed JDK 17, Android SDK, native ARM64 AAPT2, and serialized Gradle runner. Use for native Android or Flutter Android builds executed on this Pi; do not use for review-only work or builds on another host.
---

# Raspberry Pi Android APK Build

Use `/usr/local/bin/android-build-apk <project-relative-path> [gradle-task]` instead of calling Gradle directly. The runner confines paths to `/home/user/Raspberry_Pi`, serializes builds, fixes JDK 17 and SDK paths, limits workers, requires `/opt/android-build-tools-arm64/35.0.1/aapt2`, and restores the project's original `local.properties` on exit.

Before building, inspect the selected project and its nearest `AGENTS.md`, Git status, Gradle task, version, application ID, signing configuration, and expected output variant. Do not change a lockfile, Gradle plugin, SDK level, or dependency merely to make the Pi build pass unless the task requires that change.

After building:

- Treat each `ANDROID_BUILD_APK=` line as a candidate output. Confirm ZIP integrity, size, SHA-256, package/application ID, version, architecture, and signing status.
- Distinguish a successful Gradle build from release readiness and real-device behavior.
- If the user requested a downloadable or release artifact, invoke `$pi-drive-artifact-release` through the relay artifact outbox. Do not bypass its manifest, backup, and public hash checks.
- Never delete app data, uninstall an existing app, overwrite a prior release, or claim Jarvis device validation without actual device evidence.

If the runner reports another build is active, wait or report the queue; do not bypass the lock. If it reports missing JDK, SDK, AAPT2, or disk capacity, stop and diagnose the Pi toolchain before changing the app.

## Completion

Complete only after the requested Gradle task succeeds, every reported APK passes integrity and metadata checks, the original `local.properties` is restored, and requested publication or device validation is separately evidenced.