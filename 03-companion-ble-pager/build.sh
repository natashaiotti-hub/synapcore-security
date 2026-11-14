#!/usr/bin/env bash
set -e

PROJ="$HOME/AndroidStudioProjects/SynapcoreCompanion"
SDK_DIR="$HOME/Android/Sdk"
BUILD_TOOLS="$SDK_DIR/build-tools/37.0.0"
ANDROID_JAR=$(find "$SDK_DIR/platforms" -name "android.jar" | head -n 1)
KT_STDLIB=$(find /usr/share/kotlin $(dirname $(readlink -f $(which kotlinc)))/.. -name "kotlin-stdlib.jar" 2>/dev/null | head -n 1)

echo "[1/5] Compilando Kotlin..."
rm -rf "$PROJ/build_manual"
mkdir -p "$PROJ/build_manual/classes" "$PROJ/build_manual/apk_root"
kotlinc "$PROJ/app/src/main/java/com/synapcore/companion/MainActivity.kt" -cp "$ANDROID_JAR" -d "$PROJ/build_manual/classes"

echo "[2/5] Convertendo bytecode para DEX (d8)..."
"$BUILD_TOOLS/d8" "$PROJ/build_manual/classes/com/synapcore/companion/"*.class "$KT_STDLIB" --lib "$ANDROID_JAR" --output "$PROJ/build_manual/apk_root"

echo "[3/5] Empacotando e alinhando APK..."
"$BUILD_TOOLS/aapt" package -f -M "$PROJ/app/src/main/AndroidManifest.xml" -I "$ANDROID_JAR" -F "$PROJ/build_manual/unaligned.apk" "$PROJ/build_manual/apk_root"
"$BUILD_TOOLS/zipalign" -f 4 "$PROJ/build_manual/unaligned.apk" "$PROJ/build_manual/synapcore.apk"

echo "[4/5] Assinando APK..."
"$BUILD_TOOLS/apksigner" sign --min-sdk-version 26 --ks ~/.android/debug.keystore --ks-pass pass:android --key-pass pass:android "$PROJ/build_manual/synapcore.apk"

echo "[5/5] Instalando e reiniciando no tablet..."
DEVICE=$(adb devices | awk 'NR>1 && $2=="device" {print $1; exit}')
if [ -n "$DEVICE" ]; then
    adb -s "$DEVICE" install -r "$PROJ/build_manual/synapcore.apk"
    adb -s "$DEVICE" shell am force-stop com.synapcore.companion
    adb -s "$DEVICE" shell am start -n com.synapcore.companion/.MainActivity
    echo "[OK] App atualizado e aberto no dispositivo $DEVICE!"
else
    echo "[AVISO] APK compilado com sucesso, mas nenhum dispositivo ADB conectado no momento."
fi
