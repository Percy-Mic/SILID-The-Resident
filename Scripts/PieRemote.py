"""Drives a real PIE session in an already-running SILID editor.

Connects over the Python remote-execution channel, waits until the editor's
world is actually the mansion, presses Play through the level editor API, then
reads the session log for the gameplay receipts.

Three hard-won details:
- `-ExecutePythonScript` closes the editor as soon as the startup script
  returns, so PIE has to be driven from outside the editor.
- The editor rotates SILID.log on start, so a log marker can still describe the
  previous session. PIE is gated on a live world probe (below) and receipts are
  read only past the offset recorded at Play time.
- PythonScriptPlugin 5.4 discards `print` output from the remote reply, so the
  probe reports through a small receipt file instead of stdout.

Usage: python Scripts/PieRemote.py [seconds-to-observe]
Receipt: Saved/pie_run_report.txt
"""

import os
import sys
import threading
import time

REPO = r"C:\Users\Admin\Downloads\SILID-main\ue5"
LOG = os.path.join(REPO, "Saved", "Logs", "SILID.log")
OUT = os.path.join(REPO, "Saved", "pie_run_report.txt")
WORLD_FILE = os.path.join(REPO, "Saved", "pie_world_probe.txt")
PYTHON_PLUGIN = (r"C:\Program Files\Epic Games\UE_5.4\Engine\Plugins"
                 r"\Experimental\PythonScriptPlugin\Content\Python")

PROBE_SNIPPET = """
import time
import unreal
try:
    w = unreal.EditorLevelLibrary.get_editor_world()
    name = w.get_name() if w else ''
except Exception as exc:
    name = 'ERR:%s' % exc
with open(r'__WORLD_FILE__', 'w') as fh:
    fh.write('%s|%.3f' % (name, time.time()))
""".replace("__WORLD_FILE__", WORLD_FILE)

START_SNIPPET = """
import unreal
sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
used = 'NONE'
for name in ('editor_request_begin_play', 'editor_play_simulate', 'play_simulate'):
    fn = getattr(sub, name, None)
    if fn is None:
        continue
    try:
        fn()
        used = name
        break
    except Exception as exc:
        used = 'ERR:%s:%s' % (name, exc)
if used == 'NONE':
    try:
        unreal.EditorLevelLibrary.editor_play_simulate()
        used = 'EditorLevelLibrary.editor_play_simulate'
    except Exception as exc:
        used = 'ERR:library:%s' % exc
print('PIESTART used=%s' % used)
"""

END_SNIPPET = """
import unreal
sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
for name in ('editor_request_end_play', 'editor_end_play'):
    fn = getattr(sub, name, None)
    if fn is not None:
        try:
            fn()
            print('PIEEND via %s' % name)
            break
        except Exception as exc:
            print('PIEEND error %s: %s' % (name, exc))
"""


def read_log():
    try:
        with open(LOG, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def connect(total_timeout_s=900, attempt_s=120):
    sys.path.insert(0, PYTHON_PLUGIN)
    import remote_execution

    remote_execution.DEFAULT_RECEIVE_BUFFER_SIZE = 4 * 1024 * 1024
    deadline = time.time() + total_timeout_s
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        rex = remote_execution.RemoteExecution()
        rex.multicast_bind_address = "127.0.0.1"
        rex.start()
        stop_at = min(deadline, time.time() + attempt_s)
        while time.time() < stop_at:
            nodes = rex.remote_nodes
            if nodes:
                node_id = list(nodes.keys())[0] if isinstance(nodes, dict) else nodes[0]
                rex.open_command_connection(node_id)
                print("connected (attempt %d)" % attempt, flush=True)
                return rex
            time.sleep(1)
        print("discovery attempt %d found no node; retrying" % attempt, flush=True)
        try:
            rex.stop()
        except Exception:
            pass
    return None


def run(rex, code):
    result = rex.run_command(code, unattended=True, raise_on_failure=False)
    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


def fire(rex, code, label):
    """Runs a remote command without waiting for its reply.

    Pressing Play tears down and rebuilds the PIE world, and the editor never
    sends the command result for that call, so a blocking run would hang here
    forever. Fire-and-forget keeps the driver free to read the log instead.
    """

    def worker():
        try:
            print("%s -> %s" % (label, run(rex, code)[-300:]), flush=True)
        except Exception as exc:
            print("%s reply lost: %s" % (label, exc), flush=True)

    threading.Thread(target=worker, daemon=True).start()


def probe_world(rex, wait_s=15):
    """Returns the editor world name, or '' if the probe did not answer."""
    try:
        os.remove(WORLD_FILE)
    except OSError:
        pass
    fire(rex, PROBE_SNIPPET, "PROBE")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        try:
            with open(WORLD_FILE, encoding="utf-8") as fh:
                name, stamp = fh.read().rsplit("|", 1)
            if time.time() - float(stamp) < 10:
                return name
        except (OSError, ValueError):
            pass
        time.sleep(1)
    return ""


def main():
    observe_s = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    lines = ["PIE run - live editor via remote execution"]
    fails = []

    def check(name, ok, detail=""):
        lines.append("%-34s %s %s" % (name, "OK" if ok else "FAIL", detail))
        if not ok:
            fails.append(name)

    def finish():
        lines.append("RESULT: " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("\n".join(lines), flush=True)
        return 0 if not fails else 2

    rex = connect()
    if rex is None:
        check("remote execution connected", False, "no node discovered")
        return finish()
    check("remote execution connected", True)

    world = ""
    deadline = time.time() + 900
    while time.time() < deadline:
        world = probe_world(rex)
        if world == "LM_SILID_GroundFloor":
            break
        time.sleep(2)
    check("editor world loaded", world == "LM_SILID_GroundFloor", world[-40:])
    if world != "LM_SILID_GroundFloor":
        return finish()

    time.sleep(3)
    baseline = len(read_log())
    fire(rex, START_SNIPPET, "PIESTART")

    started = False
    deadline = time.time() + 600
    while time.time() < deadline:
        if "PIE: Play in editor total start time" in read_log()[baseline:]:
            started = True
            break
        time.sleep(2)
    check("pie session started", started)
    if started:
        time.sleep(observe_s)

    fire(rex, END_SNIPPET, "PIEEND")
    time.sleep(6)

    text = read_log()[baseline:]
    check("pie world created", "UEDPIE_0_LM_SILID_GroundFloor" in text)
    check("game mode took over", "LogLoad: Game class is 'SILIDGameMode'" in text)
    check("world live for play", "up for play" in text)
    check("run state initialized", "LogSILID: RunState phase=" in text)
    check("resident spawned", "LogSILID: Resident auto-spawned" in text)
    check("opening began", "SILID opening: drive begun" in text)
    check("opening entered Driving", "SILID opening: phase -> Driving" in text)

    receipts = [line.strip() for line in text.splitlines()
                if "SILID opening: drive pos=" in line]
    moved = any("travelled=0 " not in line + " " for line in receipts)
    check("drive receipts emitted", bool(receipts), "%d receipt(s)" % len(receipts))
    check("car actually moved", moved, receipts[-1][-86:] if receipts else "none")
    check("opening reached Failing", "SILID opening: phase -> Failing" in text)
    check("opening reached Stopped", "SILID opening: phase -> Stopped" in text)

    hung = any(marker in text for marker in (
        "DXGI_ERROR_DEVICE_REMOVED", "DXGI_ERROR_DEVICE_HUNG",
        "D3D device being lost", "appError called", "Fatal error"))
    check("no device hang", not hung, "DXGI/appError present" if hung else "")

    return finish()


raise SystemExit(main())
