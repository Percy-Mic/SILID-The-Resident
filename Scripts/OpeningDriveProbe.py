"""Opening-drive receipt probe (runs INSIDE the -game session via remote exec).

Verifies, from the session's own log, that the Act I opening drive ran for
real in the packaged-style loop. The session must be launched with
-SILIDAUTODRIVE so the car holds throttle without a human pressing W.

The probe POLLS rather than reads once: boot takes ~17 s of LoadMap on this
machine, the drive needs another ~6-10 s to cover the 45 m to the failure
point, and the coast takes ~10 s more. A single read at +30 s sees only the
first seconds of driving and would report a false FAIL.

Receipt: Saved/opening_drive_report.txt (RESULT PASS/FAIL).
"""

OUT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\opening_drive_report.txt"
LOG = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\Logs\SILID.log"

import time

lines = []
fails = []


def check(name, ok, detail=""):
    lines.append("%-40s %s %s" % (name, "OK" if ok else "FAIL", detail))
    if not ok:
        fails.append(name)


def wait_for(needle, timeout_s, already_ok):
    """Poll the log until `needle` appears or time runs out."""
    if already_ok:
        return True
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            text = open(LOG, encoding="utf-8", errors="replace").read()
        except OSError:
            time.sleep(1)
            continue
        if needle in text:
            return True
        time.sleep(2)
    return False


text = open(LOG, encoding="utf-8", errors="replace").read()

check("drive begun", "SILID opening: drive begun" in text)
check("phase Driving", "phase -> Driving" in text)
check("phase Failing", wait_for("phase -> Failing", 45, "phase -> Failing" in text),
      "poll up to 45 s for the fault to fire")
check("phase Stopped", wait_for("phase -> Stopped", 45, "phase -> Stopped" in text),
      "poll up to 45 s for the coast to end at the shoulder")

lines.append("RESULT: " + ("PASS" if (not fails) else "FAIL: " + "; ".join(fails)))
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print(lines[-1])
