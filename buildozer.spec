[app]
title = MegaGrid Media
package.name = megagridmedia
package.domain = org.megagrid
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3, kivy, requests, pyjnius, opencv, numpy
orientation = portrait
fullscreen = 0

android.permissions = INTERNET,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
# (int) Minimum API your APK / AAB will support
android.minapi = 24

[buildozer]
log_level = 2
warn_on_root = 1
