#!/usr/bin/env bash
set -euo pipefail
umask 077
tools=/sdk/build-tools
platform=/sdk/platform/android.jar
rm -rf build/classes build/dex build/assets
mkdir -p build/classes build/dex build/assets/web
cp -R web/. build/assets/web/
cp state/private/tv-config.json build/assets/private-config.json
"$tools/aapt" package -f -M android/AndroidManifest.xml -S android/res -A build/assets -I "$platform" -F build/unsigned.apk
javac -source 8 -target 8 -Xlint:-options -classpath "$platform" -d build/classes android/src/dev/tvlivedashboard/*.java
jar cf build/classes.jar -C build/classes .
"$tools/d8" --lib "$platform" --min-api 26 --output build/dex build/classes.jar
jar uf build/unsigned.apk -C build/dex classes.dex
"$tools/zipalign" -f 4 build/unsigned.apk build/aligned.apk
if [ ! -f state/private/signing.keystore ]; then
  keytool -genkeypair -keystore state/private/signing.keystore \
    -storepass:file state/private/signing_password -keypass:file state/private/signing_password \
    -alias tv-live-dashboard -keyalg RSA -keysize 3072 -validity 10000 \
    -dname 'CN=TV Live Dashboard, OU=Personal TV, O=Local'
fi
"$tools/apksigner" sign --ks state/private/signing.keystore \
  --ks-pass file:state/private/signing_password --ks-key-alias tv-live-dashboard \
  --out build/tv-live-dashboard.apk build/aligned.apk
"$tools/apksigner" verify --verbose build/tv-live-dashboard.apk
"$tools/aapt" dump badging build/tv-live-dashboard.apk
