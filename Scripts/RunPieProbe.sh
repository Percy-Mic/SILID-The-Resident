#!/usr/bin/env bash
# Launches the editor, drives a real PIE session through remote execution
# (Scripts/PieRemote.py), then stops the editor. Rendered unless --nullrhi.
#
# Usage: bash Scripts/RunPieProbe.sh [--nullrhi] [observe-seconds] [tag]
set -u

EDITOR="C:/Program Files/Epic Games/UE_5.4/Engine/Binaries/Win64/UnrealEditor.exe"
UPROJ="C:/Users/Admin/Downloads/SILID-main/ue5/SILID.uproject"

cd "$(dirname "$0")/.." || exit 1

NULLRHI=0
OBSERVE=60
TAG="pie"
for arg in "$@"; do
  case "$arg" in
    --nullrhi) NULLRHI=1 ;;
    ''|*[!0-9]*) TAG="$arg" ;;
    *) OBSERVE="$arg" ;;
  esac
done

if tasklist | grep -qi "UnrealEditor.exe"; then
  echo "REFUSING TO LAUNCH: an UnrealEditor.exe is already running"
  exit 3
fi

mkdir -p BuildLogs
rm -f Saved/pie_run_report.txt
STDOUT="BuildLogs/${TAG}_stdout.txt"
DRIVER="BuildLogs/${TAG}_driver.log"
: > "$STDOUT"
: > "$DRIVER"

FLAGS=(-nosplash -nop4 -log -stdout -SILIDAUTODRIVE)
if [ "$NULLRHI" -eq 1 ]; then
  FLAGS=(-NullRHI "${FLAGS[@]}")
else
  FLAGS=(-windowed -ResX=960 -ResY=540 "${FLAGS[@]}")
fi

"$EDITOR" "$UPROJ" "${FLAGS[@]}" > "$STDOUT" 2>&1 &
echo "launched editor, tag=$TAG nullrhi=$NULLRHI observe=${OBSERVE}s"

python Scripts/PieRemote.py "$OBSERVE" > "$DRIVER" 2>&1
DRIVER_STATUS=$?
tail -40 "$DRIVER"

sleep 2
taskkill //F //IM UnrealEditor.exe >/dev/null 2>&1 || true

echo "---- report ----"
cat Saved/pie_run_report.txt 2>/dev/null || echo "NO REPORT"
exit "$DRIVER_STATUS"
