#!/usr/bin/env bash
# Launches the SILID editor, runs the real-input PIE probe
# (Scripts/PieInput.py), then stops the editor.
#
# Usage: bash Scripts/RunPieInput.sh
set -u

EDITOR="C:/Program Files/Epic Games/UE_5.4/Engine/Binaries/Win64/UnrealEditor.exe"
UPROJ="C:/Users/Admin/Downloads/SILID-main/ue5/SILID.uproject"

cd "$(dirname "$0")/.." || exit 1

if tasklist | grep -qi "UnrealEditor.exe"; then
  echo "REFUSING TO LAUNCH: an UnrealEditor.exe is already running"
  exit 3
fi

mkdir -p BuildLogs
rm -f Saved/pie_input_report.txt Saved/pie_input_state.json
STDOUT="BuildLogs/pie_input_stdout.txt"
DRIVER="BuildLogs/pie_input_driver.log"
: > "$STDOUT"
: > "$DRIVER"

"$EDITOR" "$UPROJ" -windowed -ResX=960 -ResY=540 -nosplash -nop4 -log -stdout -SILIDAUTODRIVE \
  > "$STDOUT" 2>&1 &
echo "launched editor, tag=pie_input"

python Scripts/PieInput.py > "$DRIVER" 2>&1
DRIVER_STATUS=$?
tail -100 "$DRIVER"

sleep 2
taskkill //F //IM UnrealEditor.exe >/dev/null 2>&1 || true

echo "---- report ----"
cat Saved/pie_input_report.txt 2>/dev/null || echo "NO REPORT"
exit "$DRIVER_STATUS"
