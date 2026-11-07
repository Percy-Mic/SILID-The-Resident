"""Profiles rendered PIE frame cost on the current (low-end) recipe.

Starts PIE, waits past the opening, teleports into mansion viewpoints, runs
ProfileGPU, and extracts the GPU timing hierarchy from the session log. The
goal is to show what still dominates frame cost on this GPU (Intel HD 4600)
without guessing.

Uses the same remote-execution / file-probe pattern as PieRoam.py (UE 5.4
discards remote print output).

Usage: python Scripts/PieProfile.py
Receipt: Saved/pie_profile_report.txt
"""

import os
import re
import sys
import threading
import time

REPO = r"C:\Users\Admin\Downloads\SILID-main\ue5"
LOG = os.path.join(REPO, "Saved", "Logs", "SILID.log")
OUT = os.path.join(REPO, "Saved", "pie_profile_report.txt")
WORLD_FILE = os.path.join(REPO, "Saved", "pie_world_probe.txt")
PROBE_FILE = os.path.join(REPO, "Saved", "pie_profile_probe.txt")
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
for name in ('editor_request_begin_play', 'editor_play_simulate', 'play_simulate'):
    fn = getattr(sub, name, None)
    if fn is None:
        continue
    try:
        fn(); break
    except Exception:
        pass
else:
    try:
        unreal.EditorLevelLibrary.editor_play_simulate()
    except Exception:
        pass
"""

END_SNIPPET = """
import unreal
sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
for name in ('editor_request_end_play', 'editor_end_play'):
    fn = getattr(sub, name, None)
    if fn is not None:
        try:
            fn(); break
        except Exception:
            pass
"""

PROFILE_SNIPPET = r"""
import time
import unreal

OUT = r'__PROBE_FILE__'
lines = []

def log(msg):
    lines.append(msg)
    try:
        with open(OUT, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines))
    except Exception:
        pass

def find_pie_world():
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if ues:
            for name in ('get_game_world', 'get_pie_world', 'get_play_world'):
                fn = getattr(ues, name, None)
                if fn:
                    w = fn()
                    if w and 'UEDPIE' in w.get_path_name():
                        return w
    except Exception as exc:
        log('ues: %s' % exc)
    try:
        fn = getattr(unreal.EditorLevelLibrary, 'get_pie_worlds', None)
        if fn:
            ws = fn()
            if ws:
                return ws[0]
    except Exception:
        pass
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return None

def find_pawn(world):
    for path in ('/Script/SILID.SILIDCharacter', '/Script/SILID.SILIDResident'):
        try:
            cls = unreal.load_class(None, path)
            if cls:
                actors = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
                if actors:
                    return actors[0]
        except Exception:
            pass
    try:
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        if pc and pc.get_pawn():
            return pc.get_pawn()
    except Exception:
        pass
    try:
        actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Pawn)
        return actors[0] if actors else None
    except Exception:
        return None

def interior_points(world):
    pts = []
    base = (0.0, 0.0, 180.0)
    try:
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for a in (eas.get_all_level_actors() if eas else []):
            try:
                if isinstance(a, unreal.PlayerStart):
                    loc = a.get_actor_location()
                    base = (loc.x, loc.y, loc.z + 88.0)
                    pts.append(('PlayerStart',) + base)
                    break
            except Exception:
                pass
    except Exception:
        pass
    bx, by, bz = base
    for label, dx, dy in (('interior-a', 0, 0), ('interior-b', 700, 300),
                          ('interior-c', -600, 500), ('interior-d', 400, -700)):
        pts.append((label, bx + dx, by + dy, bz))
    return pts

def exec_cmd(world, cmd):
    # Try world-context execution first, then global.
    try:
        unreal.SystemLibrary.execute_console_command(world, cmd)
        return True
    except Exception:
        pass
    try:
        unreal.SystemLibrary.execute_console_command(None, cmd)
        return True
    except Exception as exc:
        log('cmd fail %s: %s' % (cmd, exc))
        return False

log('profile start')
world = find_pie_world()
if not world:
    log('NO_WORLD'); raise SystemExit
log('world=%s' % world.get_path_name())
pawn = find_pawn(world)
log('pawn=%s' % (('%s %s' % (pawn.get_name(), pawn.get_class().get_name())) if pawn else 'NONE'))

# Settle on representative viewpoints and capture ProfileGPU.
for label, x, y, z in interior_points(world):
    if pawn:
        try:
            pawn.set_actor_location(unreal.Vector(x, y, z), False, False)
            log('moved %s (%.0f,%.0f,%.0f)' % (label, x, y, z))
        except Exception as exc:
            log('move %s fail: %s' % (label, exc))
    time.sleep(2.5)
    exec_cmd(world, 'stat unit')
    time.sleep(0.5)
    exec_cmd(world, 'stat scenerendering')
    time.sleep(0.5)
    exec_cmd(world, 'ProfileGPU')
    log('ProfileGPU fired at %s' % label)
    time.sleep(3.0)

exec_cmd(world, 'stat none')
log('profile done')
""".replace("__PROBE_FILE__", PROBE_FILE)


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
    return str(result.get("result", "")) if isinstance(result, dict) else str(result)


def fire(rex, code, label):
    def worker():
        try:
            run(rex, code)
        except Exception as exc:
            print("%s reply lost: %s" % (label, exc), flush=True)
    threading.Thread(target=worker, daemon=True).start()


def probe_world(rex, wait_s=15):
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


def extract_profile(text):
    """Pulls ProfileGPU / timing lines from the log; returns a bounded excerpt."""
    markers = ("ProfileGPU", "GPU Profile", "GPU Timing", "Scene ",
               "BasePass", "ShadowDepths", "Lights", "Translucency",
               "PostProcessing", "PrePass", "HZB", "Velocity", "InitViews",
               "RenderDeferredLighting", "stat unit", "StatLevels",
               "Unit time", "Frame:", "Game ", "Draw ", "GPU ")
    hits = []
    for line in text.splitlines():
        if any(m in line for m in markers):
            # keep log-renderer-ish / console / stat lines
            if any(tag in line for tag in ("LogRenderer", "LogRHI", "LogConsole",
                                           "LogProfilingDebugging", "LogStats",
                                           "GPU", "Frame", "ms")):
                hits.append(line.rstrip())
    # Deduplicate near-identical stat spam loosely by keeping first/last windows.
    if len(hits) > 220:
        hits = hits[:80] + ["  ... (%d lines omitted) ..." % (len(hits) - 160)] + hits[-80:]
    return hits


def main():
    lines = ["PIE frame-cost profile (rendered, current low-end recipe)"]
    fails = []

    def check(name, ok, detail=""):
        lines.append("%-34s %s %s" % (name, "OK" if ok else "FAIL", detail))
        if not ok:
            fails.append(name)

    def finish(extra=None):
        if extra:
            lines.extend(extra)
        lines.append("RESULT: " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("\n".join(lines), flush=True)
        return 0 if not fails else 2

    for p in (PROBE_FILE,):
        try:
            os.remove(p)
        except OSError:
            pass

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
    if not started:
        return finish()

    # Let the opening settle; profiling is more representative after Stopped.
    stop_deadline = time.time() + 180
    while time.time() < stop_deadline:
        if "SILID opening: phase -> Stopped" in read_log()[baseline:]:
            break
        time.sleep(2)
    fire(rex, PROFILE_SNIPPET, "PROFILE")

    prof_deadline = time.time() + 240
    while time.time() < prof_deadline:
        try:
            if "profile done" in open(PROBE_FILE, encoding="utf-8").read():
                break
        except OSError:
            pass
        if any(m in read_log()[baseline:] for m in ("DXGI_ERROR_DEVICE_HUNG", "appError called")):
            break
        time.sleep(3)
    time.sleep(5)

    fire(rex, END_SNIPPET, "PIEEND")
    time.sleep(6)

    text = read_log()[baseline:]
    probe = ""
    try:
        probe = open(PROBE_FILE, encoding="utf-8").read()
    except OSError:
        pass
    for pl in probe.splitlines()[-10:]:
        lines.append("  probe: " + pl)

    hung = any(m in text for m in ("DXGI_ERROR_DEVICE_REMOVED", "DXGI_ERROR_DEVICE_HUNG",
                                   "D3D device being lost", "appError called", "Fatal error"))
    check("no device hang", not hung, "DXGI/appError/Fatal present" if hung else "")
    check("profile captured", "profile done" in probe or "ProfileGPU fired" in probe)

    hits = extract_profile(text)
    lines.append("  profile/timing log lines captured: %d" % len(hits))
    extra = ["", "=== captured profile/timing lines (from SILID.log) ==="]
    extra.extend(hits if hits else ["(none captured - ProfileGPU/stat output may be viewport-only in this configuration)"])
    return finish(extra)


raise SystemExit(main())
