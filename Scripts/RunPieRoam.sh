#!/usr/bin/env bash
# Launches the editor, drives a long rendered PIE roam (Scripts/PieRoam.py)
# past the opening sequence, then stops the editor.
#
# Usage: bash Scripts/RunPieRoam.sh [roam-observe-seconds] [tag]
set -u

EDITOR="C:/Program Files/Epic Games/UE_5.4/Engine/Binaries/Win64/UnrealEditor.exe"
UPROJ="C:/Users/Admin/Downloads/SILID-main/ue5/SILID.uproject"

cd "$(dirname "$0")/.." || exit 1

OBSERVE=300
TAG="pie_roam"
for arg in "$@"; do
  case "$arg" in
    ''|*[!0-9]*) TAG="$arg" ;;
    *) OBSERVE="$arg" ;;
  esac
done

if tasklist | grep -qi "UnrealEditor.exe"; then
  echo "REFUSING TO LAUNCH: an UnrealEditor.exe is already running"
  exit 3
fi

mkdir -p BuildLogs
rm -f Saved/pie_roam_report.txt Saved/pie_roam_probe.txt
STDOUT="BuildLogs/${TAG}_stdout.txt"
DRIVER="BuildLogs/${TAG}_driver.log"
: > "$STDOUT"
: > "$DRIVER"

"$EDITOR" "$UPROJ" -windowed -ResX=960 -ResY=540 -nosplash -nop4 -log -stdout -SILIDAUTODRIVE \
  > "$STDOUT" 2>&1 &
echo "launched editor, tag=$TAG observe=${OBSERVE}s"

python Scripts/PieRoam.py "$OBSERVE" > "$DRIVER" 2>&1
DRIVER_STATUS=$?
tail -60 "$DRIVER"

sleep 2
taskkill //F //IM UnrealEditor.exe >/dev/null 2>&1 || true

echo "---- report ----"
cat Saved/pie_roam_report.txt 2>/dev/null || echo "NO REPORT"
exit "$DRIVER_STATUS"
