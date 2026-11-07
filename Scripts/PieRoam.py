"""Long rendered PIE stability run past the opening sequence.

Starts PIE via the live editor's remote-execution channel, lets the opening
drive to Stopped, then teleports the player pawn through a set of mansion
waypoints in the PIE world (free-roam traversal) while watching for a D3D11
device hang. The goal is to confirm the low-end renderer recipe holds up under
the 3,477-actor mansion, not to score gameplay.

Hard-won details carried from PieRemote.py:
- `-ExecutePythonScript` quits the editor when the startup script returns.
- SILID.log is rotated on start, so a stale marker can describe the previous
  session; this gates on a live world probe and reads only past a log offset.
- PythonScriptPlugin 5.4 discards `print` output from remote replies, so probes
  report through receipt files instead of stdout.

Usage: python Scripts/PieRoam.py [observe-seconds-after-roam-start]
Receipt: Saved/pie_roam_report.txt
"""

import os
import sys
import threading
import time

REPO = r"C:\Users\Admin\Downloads\SILID-main\ue5"
LOG = os.path.join(REPO, "Saved", "Logs", "SILID.log")
OUT = os.path.join(REPO, "Saved", "pie_roam_report.txt")
WORLD_FILE = os.path.join(REPO, "Saved", "pie_world_probe.txt")
ROAM_FILE = os.path.join(REPO, "Saved", "pie_roam_probe.txt")
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

# Runs in editor Python context. Finds the PIE world, locates a pawn, and
# teleports it through a sequence of waypoints so different mansion areas are
# rendered. Writes progress to a receipt file the outer driver can read.
ROAM_SNIPPET = r"""
import math
import time
import unreal

OUT = r'__ROAM_FILE__'
lines = []

def log(msg):
    lines.append(msg)
    try:
        with open(OUT, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines))
    except Exception:
        pass

def find_pie_world():
    # UE5.4: PIE worlds carry the UEDPIE_ prefix. Try a few access paths.
    try:
        # GameplayStatics helpers take a world context; the editor world is a
        # fallback, but PIE pawns live in the PIE world.
        for getter in ('get_editor_world',):
            pass
    except Exception:
        pass
    # Most reliable: ask UnrealEditorSubsystem for the game/PIE world.
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
        log('unrealeditor subsystem: %s' % exc)
    # Fallback: scan all worlds via the editor world outer package chain is
    # not exposed cleanly; try GameplayStatics on editor world and also check
    # common PIE naming by loading.
    try:
        ew = unreal.EditorLevelLibrary.get_editor_world()
        # get_pie_worlds is not present in all 5.4 builds; try defensively.
        fn = getattr(unreal.EditorLevelLibrary, 'get_pie_worlds', None)
        if fn:
            ws = fn()
            if ws:
                return ws[0]
    except Exception:
        pass
    return None

def find_pawn(world):
    # Prefer the project's character; fall back to any pawn the player owns.
    try:
        cls = unreal.load_class(None, '/Script/SILID.SILIDCharacter')
        if cls:
            actors = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
            if actors:
                return actors[0]
    except Exception as exc:
        log('char class lookup: %s' % exc)
    try:
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        if pc:
            p = pc.get_pawn()
            if p:
                return p
    except Exception as exc:
        log('player pawn: %s' % exc)
    try:
        actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Pawn)
        log('pawns found: %d' % len(actors))
        return actors[0] if actors else None
    except Exception as exc:
        log('pawn scan: %s' % exc)
    return None

def find_opening_car(world):
    try:
        cls = unreal.load_class(None, '/Script/SILID.SILIDOpeningCar')
        if cls:
            actors = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
            return actors[0] if actors else None
    except Exception:
        pass
    return None

def build_waypoints(world):
    # Gather candidate interior points from the editor level (same coordinate
    # space as PIE) and from a coarse grid around the player start. Deduplicate
    # roughly and keep a bounded set.
    pts = []
    try:
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actors = eas.get_all_level_actors() if eas else []
        for a in actors:
            try:
                if isinstance(a, unreal.PlayerStart):
                    loc = a.get_actor_location()
                    pts.append(('PlayerStart', loc.x, loc.y, loc.z + 88.0))
            except Exception:
                pass
        # Sample a few interior-ish actors by class name as extra anchors.
        for a in actors:
            try:
                cn = a.get_class().get_name()
                if cn in ('SILIDInspectableProp', 'SILIDDoor'):
                    loc = a.get_actor_location()
                    pts.append((cn, loc.x, loc.y, loc.z + 90.0))
                    if len(pts) > 80:
                        break
            except Exception:
                pass
    except Exception as exc:
        log('waypoint scan: %s' % exc)

    # Always include a sweep relative to PlayerStart or origin.
    base = None
    for label, x, y, z in pts:
        if label == 'PlayerStart':
            base = (x, y, z); break
    if base is None:
        base = (0.0, 0.0, 180.0)
    bx, by, bz = base
    for dx in (-1200, -600, 0, 600, 1200):
        for dy in (-1200, -600, 0, 600, 1200):
            pts.append(('grid', bx + dx, by + dy, bz))

    # Downsample to ~18 well-spaced points.
    chosen = []
    min_d2 = 350.0 * 350.0
    for label, x, y, z in pts:
        if all((x-cx)**2 + (y-cy)**2 > min_d2 for _, cx, cy, cz in chosen):
            chosen.append((label, x, y, z))
        if len(chosen) >= 18:
            break
    if not chosen:
        chosen = [('fallback', 0.0, 0.0, 180.0)]
    return chosen

log('roam start')
world = find_pie_world()
if world is None:
    # last resort: try editor world (will not move PIE pawn, but records state)
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        log('fallback world: %s' % world.get_path_name())
    except Exception as exc:
        log('no world: %s' % exc)
        world = None

if world:
    log('world=%s' % world.get_path_name())
    car = find_opening_car(world)
    if car:
        try:
            car.call_method('FinishExit')
            log('FinishExit called')
        except Exception as exc:
            log('FinishExit: %s' % exc)
    time.sleep(1.0)
    pawn = find_pawn(world)
    if pawn is None:
        log('NO_PAWN')
    else:
        log('pawn=%s class=%s' % (pawn.get_name(), pawn.get_class().get_name()))
        wps = build_waypoints(world)
        log('waypoints=%d passes=2' % len(wps))
        n = 0
        for p in (1, 2):
            for i, (label, x, y, z) in enumerate(wps):
                n += 1
                try:
                    pawn.set_actor_location(unreal.Vector(x, y, z), False, False)
                    log('p%d wp %d/%d %s (%.0f,%.0f,%.0f) ok' % (p, i + 1, len(wps), label, x, y, z))
                except Exception as exc:
                    log('p%d wp %d %s fail: %s' % (p, i + 1, label, exc))
                time.sleep(4.0)
            log('pass %d complete (%d moves)' % (p, n))
            time.sleep(5.0)
        log('roam done moves=%d' % n)
else:
    log('NO_WORLD')
""".replace("__ROAM_FILE__", ROAM_FILE)


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
    """Non-blocking remote command (Play/EndPlay replies are lost in PIE)."""

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


def read_roam():
    try:
        with open(ROAM_FILE, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def main():
    roam_observe_s = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    lines = ["Long PIE roam - rendered stability past opening"]
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

    try:
        os.remove(ROAM_FILE)
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

    # Let the opening sequence run to Stopped (usually < 40 s).
    stopped = False
    deadline = time.time() + 180
    while time.time() < deadline:
        if "SILID opening: phase -> Stopped" in read_log()[baseline:]:
            stopped = True
            break
        time.sleep(2)
    check("opening reached Stopped", stopped)

    # Fire the in-PIE roam traversal (teleports the pawn through waypoints).
    fire(rex, ROAM_SNIPPET, "ROAM")
    roam_done = False
    observe_until = time.time() + roam_observe_s
    while time.time() < observe_until:
        txt = read_log()[baseline:]
        if any(m in txt for m in ("DXGI_ERROR_DEVICE_REMOVED", "DXGI_ERROR_DEVICE_HUNG",
                                   "D3D device being lost", "appError called")):
            break
        if "roam done" in read_roam():
            roam_done = True
        time.sleep(5)

    # A little extra dwell after roam completes.
    if roam_done:
        time.sleep(15)

    fire(rex, END_SNIPPET, "PIEEND")
    time.sleep(6)

    text = read_log()[baseline:]
    roam = read_roam()
    for rl in roam.splitlines()[-12:]:
        lines.append("  roam: " + rl)

    check("pie world created", "UEDPIE_0_LM_SILID_GroundFloor" in text)
    check("game mode took over", "LogLoad: Game class is 'SILIDGameMode'" in text)
    check("run state initialized", "LogSILID: RunState phase=" in text)
    check("opening entered Driving", "SILID opening: phase -> Driving" in text)
    receipts = [l for l in text.splitlines() if "SILID opening: drive pos=" in l]
    check("car actually moved", any("travelled=0 " not in l + " " for l in receipts),
          receipts[-1][-80:] if receipts else "none")
    check("roam script reached PIE world", "world=/Game/SILID/Maps/UEDPIE" in roam
          or "world=UEDPIE" in roam or "world=LM_SILID" in roam, (roam.splitlines()[1:2] or ["?"])[0][:60])
    check("roam moved a pawn", ("wp 1/" in roam or "roam done" in roam)
          and "NO_PAWN" not in roam and "NO_WORLD" not in roam)
    check("roam completed traversal", roam_done, "%d wp lines" % roam.count("\nwp "))

    hung = any(m in text for m in ("DXGI_ERROR_DEVICE_REMOVED", "DXGI_ERROR_DEVICE_HUNG",
                                   "D3D device being lost", "appError called", "Fatal error"))
    check("no device hang (full session)", not hung, "DXGI/appError/Fatal present" if hung else "")

    # Confirm the session stayed alive long enough (PIE end is logged by us or
    # the editor; absence of a crash is the main signal).
    lines.append("  session log chars (this run): %d" % len(text))
    return finish()


raise SystemExit(main())
