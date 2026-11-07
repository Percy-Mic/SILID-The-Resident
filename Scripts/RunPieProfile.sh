#!/usr/bin/env bash
# Launches the editor and runs PieProfile.py to capture rendered frame-cost data.
set -u
EDITOR="C:/Program Files/Epic Games/UE_5.4/Engine/Binaries/Win64/UnrealEditor.exe"
UPROJ="C:/Users/Admin/Downloads/SILID-main/ue5/SILID.uproject"
cd "$(dirname "$0")/.." || exit 1
TAG="${1:-pie_profile1}"
if tasklist | grep -qi "UnrealEditor.exe"; then echo "REFUSING: editor running"; exit 3; fi
mkdir -p BuildLogs
rm -f Saved/pie_profile_report.txt Saved/pie_profile_probe.txt Saved/pie_world_probe.txt
STDOUT="BuildLogs/${TAG}_stdout.txt"; DRIVER="BuildLogs/${TAG}_driver.log"
: > "$STDOUT"; : > "$DRIVER"
"$EDITOR" "$UPROJ" -windowed -ResX=960 -ResY=540 -nosplash -nop4 -log -stdout -SILIDAUTODRIVE > "$STDOUT" 2>&1 &
echo "launched editor, tag=$TAG"
python Scripts/PieProfile.py > "$DRIVER" 2>&1
STATUS=$?
tail -80 "$DRIVER"
sleep 2
taskkill //F //IM UnrealEditor.exe >/dev/null 2>&1 || true
echo "---- report ----"
cat Saved/pie_profile_report.txt 2>/dev/null || echo "NO REPORT"
exit $STATUS
