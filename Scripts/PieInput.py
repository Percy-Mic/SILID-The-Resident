"""Real-input PIE probe for the SILID keyboard/mouse repair.

Launches nothing itself: the companion shell script starts the editor, then this
driver connects over the Python remote-execution channel, starts real PIE with
the editor's Play shortcut (UE 5.4's Python API exposes only Simulate), lets
the opening drive reach Stopped (which releases the controller's drive gate),
ensures the local player pawn is a SILIDCharacter, and sends actual OS
keyboard/mouse events to the PIE window. Character location and
control rotation are read back through the remote channel, so the assertions are
about observed gameplay, not compilation.

Usage: python Scripts/PieInput.py
Receipt: Saved/pie_input_report.txt
"""

import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

REPO = r"C:\Users\Admin\Downloads\SILID-main\ue5"
LOG = os.path.join(REPO, "Saved", "Logs", "SILID.log")
OUT = os.path.join(REPO, "Saved", "pie_input_report.txt")
WORLD_FILE = os.path.join(REPO, "Saved", "pie_world_probe.txt")
STATE_FILE = os.path.join(REPO, "Saved", "pie_input_state.json")
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

FIND_WORLD = r"""
import unreal
def find_world():
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        for name in ('get_game_world', 'get_pie_world', 'get_play_world'):
            fn = getattr(ues, name, None)
            if fn:
                w = fn()
                if w and 'UEDPIE' in w.get_path_name():
                    return w
    except Exception:
        pass
    try:
        fn = getattr(unreal.EditorLevelLibrary, 'get_pie_worlds', None)
        if fn:
            ws = fn()
            if ws:
                return ws[0]
    except Exception:
        pass
    return None

def controller_pawn(pc):
    if not pc:
        return None
    for name in ('get_character', 'get_controlled_pawn', 'get_pawn'):
        fn = getattr(pc, name, None)
        if fn is None:
            continue
        try:
            p = fn()
        except Exception:
            continue
        if p:
            return p
    for attr in ('pawn', 'character'):
        try:
            p = getattr(pc, attr, None)
        except Exception:
            continue
        if p:
            return p
    return None

def find_pawn(world):
    # The player controller's pawn is the only pawn that receives the
    # keyboard/mouse action bindings; prefer it over any AI character.
    try:
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        p = controller_pawn(pc)
        if p:
            return p
    except Exception:
        pass
    try:
        cls = unreal.load_class(None, '/Script/SILID.SILIDCharacter')
        if cls:
            actors = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
            if actors:
                return actors[0]
    except Exception:
        pass
    try:
        actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Pawn)
        return actors[0] if actors else None
    except Exception:
        return None
"""

STATE_SNIPPET = FIND_WORLD + r"""
import json
out = r'__STATE_FILE__'
data = {}
try:
    world = find_world()
    data['world'] = world.get_path_name() if world else ''
    pawn = find_pawn(world) if world else None
    data['pawn'] = pawn.get_name() if pawn else ''
    data['pawn_class'] = pawn.get_class().get_name() if pawn else ''
    if pawn:
        loc = pawn.get_actor_location()
        rot = pawn.get_actor_rotation()
        data['loc'] = [loc.x, loc.y, loc.z]
        data['actor'] = [rot.pitch, rot.yaw, rot.roll]
    pc = unreal.GameplayStatics.get_player_controller(world, 0) if world else None
    pc_pawn = controller_pawn(pc) if pc else None
    if pc:
        data['pc'] = pc.get_name()
        data['pc_class'] = pc.get_class().get_name()
        data['pc_pawn'] = pc_pawn.get_name() if pc_pawn else ''
        data['pc_pawn_class'] = pc_pawn.get_class().get_name() if pc_pawn else ''
        data['is_player'] = bool(pawn and pc_pawn and pc_pawn.get_name() == pawn.get_name())
        rot = pc.get_control_rotation()
        data['ctrl'] = [rot.pitch, rot.yaw, rot.roll]
    try:
        cls = unreal.load_class(None, '/Script/SILID.SILIDCharacter')
        data['characters'] = len(unreal.GameplayStatics.get_all_actors_of_class(world, cls)) if (world and cls) else 0
    except Exception:
        data['characters'] = -1
    try:
        data['player_starts'] = len(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerStart)) if world else 0
    except Exception:
        data['player_starts'] = -1
except Exception as exc:
    data['error'] = repr(exc)
with open(out, 'w') as fh:
    json.dump(data, fh)
""".replace("__STATE_FILE__", STATE_FILE)

TELEPORT_SNIPPET = FIND_WORLD + r"""
world = find_world()
pawn = find_pawn(world)
if pawn:
    pawn.set_actor_location(unreal.Vector(__X__, __Y__, __Z__), False, False)
    pawn.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False)
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    if pc:
        pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
"""

SETUP_PLAYER_SNIPPET = FIND_WORLD + r"""
import unreal
world = find_world()
if world:
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = controller_pawn(pc) if pc else None
    if not pawn or 'SILIDCharacter' not in pawn.get_class().get_name():
        cls = unreal.load_class(None, '/Script/SILID.SILIDCharacter')
        if cls:
            loc = unreal.Vector(-5675.0, -3422.0, 200.0)
            rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
            spawned = unreal.GameplayStatics.begin_spawn_actor_from_class(world, cls, loc, rot)
            if spawned:
                unreal.GameplayStatics.finish_spawn_actor(spawned)
            if spawned and pc:
                pc.possess(spawned)
                pawn = spawned
    if pawn and pc:
        loc = unreal.Vector(-6075.0, -2500.0, 200.0)
        rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
        pawn.set_actor_location(loc, False, False)
        pawn.set_actor_rotation(rot, False)
        pc.set_control_rotation(rot)
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


# ---------------------------------------------------------------- OS input ---

user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def window_list():
    found = []

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.append((hwnd, buf.value, pid.value))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return found


def pick_pie_window():
    candidates = [w for w in window_list() if "silid" in w[1].lower() or "preview" in w[1].lower()]
    for hwnd, title, pid in candidates:
        if "preview" in title.lower():
            return hwnd, title
    # Play-in-selected-viewport keeps the game inside the main editor window.
    for hwnd, title, pid in candidates:
        if "unreal editor" in title.lower():
            return hwnd, title
    for hwnd, title, pid in candidates:
        low = title.lower()
        if "mingw" not in low and "cmd" not in low and "powershell" not in low:
            return hwnd, title
    return None, ""


def focus_window(hwnd):
    if not hwnd:
        return False
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.35)
        return user32.GetForegroundWindow() == hwnd
    except Exception:
        return False


def click_center(hwnd):
    try:
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        user32.SetCursorPos(cx, cy)
        time.sleep(0.15)
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
        time.sleep(0.25)
    except Exception:
        pass


def key_event(vk, down):
    user32.keybd_event(vk, 0, 0 if down else 0x0002, 0)


def tap_key(vk, hold=0.7):
    key_event(vk, True)
    time.sleep(hold)
    key_event(vk, False)
    time.sleep(0.45)


def mouse_move(dx, dy):
    user32.mouse_event(0x0001, int(dx), int(dy), 0, 0)  # MOUSEEVENTF_MOVE


def pick_editor_window():
    candidates = [w for w in window_list()
                  if "unreal editor" in w[1].lower() or "silid" in w[1].lower()]
    for hwnd, title, pid in candidates:
        if "unreal editor" in title.lower() and "preview" not in title.lower():
            return hwnd, title
    for hwnd, title, pid in candidates:
        low = title.lower()
        if ("mingw" not in low and "cmd" not in low and "powershell" not in low
                and "preview" not in low):
            return hwnd, title
    return None, ""


def alt_key(vk):
    key_event(0x12, True)   # Alt
    time.sleep(0.12)
    key_event(vk, True)
    time.sleep(0.08)
    key_event(vk, False)
    key_event(0x12, False)


# --------------------------------------------------------------- assertions ---

def read_state(rex, wait=5.0):
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass
    run(rex, STATE_SNIPPET)
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            with open(STATE_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("loc"):
                return data
        except (OSError, ValueError):
            pass
        time.sleep(0.15)
    return {}


def teleport(rex, x, y, z):
    run(rex, TELEPORT_SNIPPET.replace("__X__", str(x)).replace("__Y__", str(y)).replace("__Z__", str(z)))
    time.sleep(0.7)


def delta(a, b):
    if not a.get("loc") or not b.get("loc"):
        return None
    return (b["loc"][0] - a["loc"][0], b["loc"][1] - a["loc"][1], b["loc"][2] - a["loc"][2])


def main():
    lines = ["SILID input repair - real PIE keyboard/mouse probe"]
    fails = []

    def check(name, ok, detail=""):
        lines.append("%-40s %s %s" % (name, "OK" if ok else "FAIL", detail))
        if not ok:
            fails.append(name)

    def finish():
        lines.append("RESULT: " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("\n".join(lines), flush=True)
        return 0 if not fails else 2

    try:
        os.remove(STATE_FILE)
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
    editor_hwnd, editor_title = pick_editor_window()
    lines.append("  editor window: %s" % (editor_title or "NOT FOUND"))
    focused = focus_window(editor_hwnd)
    lines.append("  editor focus: %s" % ("OK" if focused else "FAIL"))
    if editor_hwnd:
        click_center(editor_hwnd)
        time.sleep(0.3)
        alt_key(0x4E)  # New Editor Window PIE if bound
        lines.append("  editor start: Alt+N sent")
        time.sleep(8)
        if "PIE: Play in editor total start time" not in read_log()[baseline:]:
            key_event(0x1B, True)
            key_event(0x1B, False)
            time.sleep(0.3)
            click_center(editor_hwnd)
            time.sleep(0.2)
            alt_key(0x50)  # Play in Selected Viewport fallback
            lines.append("  editor start: Alt+P fallback sent")
    else:
        lines.append("  editor start: NOT SENT (no window)")

    started = False
    deadline = time.time() + 90
    while time.time() < deadline:
        if "PIE: Play in editor total start time" in read_log()[baseline:]:
            started = True
            break
        time.sleep(2)
    check("pie session started", started)
    if not started:
        return finish()

    stopped = False
    deadline = time.time() + 180
    while time.time() < deadline:
        if "SILID opening: phase -> Stopped" in read_log()[baseline:]:
            stopped = True
            break
        time.sleep(2)
    check("opening reached Stopped", stopped)
    if not stopped:
        return finish()

    setup = run(rex, SETUP_PLAYER_SNIPPET)
    if setup:
        lines.append("  player setup: %s" % setup[-160:].replace("\n", " "))
    time.sleep(1.5)
    origin_state = read_state(rex)
    origin = origin_state.get("loc")
    on_foot = (bool(origin) and bool(origin_state.get("is_player"))
               and "SILIDCharacter" in origin_state.get("pawn_class", ""))
    check("player character on foot", on_foot,
          "world=%s pc=%s pc_pawn=%s class=%s loc=%s chars=%s starts=%s" % (
              origin_state.get("world", "")[-40:], origin_state.get("pc", ""),
              origin_state.get("pc_pawn", ""), origin_state.get("pawn_class", ""),
              origin, origin_state.get("characters"), origin_state.get("player_starts")))
    if not on_foot:
        fire(rex, END_SNIPPET, "PIEEND")
        return finish()

    hwnd, title = pick_pie_window()
    lines.append("  pie window: %s" % (title or "NOT FOUND"))
    focused = focus_window(hwnd)
    lines.append("  focus: %s" % ("OK" if focused else "FAIL"))
    if hwnd:
        click_center(hwnd)

    base_x, base_y, base_z = origin[0], origin[1], origin[2] + 10.0

    # Keyboard: each test starts from the same stand-point, facing +X.
    key_specs = [
        ("W", 0x57, 1, 0, "forward"),
        ("S", 0x53, -1, 0, "backward"),
        ("A", 0x41, 0, -1, "left"),
        ("D", 0x44, 0, 1, "right"),
    ]
    for name, vk, ex, ey, label in key_specs:
        teleport(rex, base_x, base_y, base_z)
        before = read_state(rex)
        focus_window(hwnd)
        tap_key(vk, 0.7)
        after = read_state(rex)
        d = delta(before, after)
        if d is None:
            check("keyboard %s (%s)" % (name, label), False, "no state")
            continue
        along = d[0] * ex + d[1] * ey
        cross = abs(d[0] * ey - d[1] * ex)
        ok = along > 20.0 and cross < max(20.0, along * 0.6)
        check("keyboard %s (%s)" % (name, label), ok,
              "delta=(%.0f,%.0f,%.0f) along=%.0f cross=%.0f" % (d[0], d[1], d[2], along, cross))

    # Mouse: pitch/yaw are read from the controller, not inferred.
    teleport(rex, base_x, base_y, base_z)
    before = read_state(rex)
    focus_window(hwnd)
    click_center(hwnd)
    mouse_move(0, -80)
    time.sleep(0.35)
    up = read_state(rex)
    pitch_up = (up.get("ctrl", [0, 0, 0])[0] - before.get("ctrl", [0, 0, 0])[0]) if up else 0.0
    check("mouse up looks up", pitch_up > 1.0, "pitch delta=%+.2f" % pitch_up)

    mouse_move(0, 80)
    time.sleep(0.35)
    down = read_state(rex)
    pitch_down = (down.get("ctrl", [0, 0, 0])[0] - up.get("ctrl", [0, 0, 0])[0]) if down and up else 0.0
    check("mouse down looks down", pitch_down < -1.0, "pitch delta=%+.2f" % pitch_down)

    mouse_move(80, 0)
    time.sleep(0.35)
    right = read_state(rex)
    yaw_right = (right.get("ctrl", [0, 0, 0])[1] - down.get("ctrl", [0, 0, 0])[1]) if right and down else 0.0
    check("mouse right looks right", yaw_right > 1.0, "yaw delta=%+.2f" % yaw_right)

    mouse_move(-80, 0)
    time.sleep(0.35)
    left = read_state(rex)
    yaw_left = (left.get("ctrl", [0, 0, 0])[1] - right.get("ctrl", [0, 0, 0])[1]) if left and right else 0.0
    check("mouse left looks left", yaw_left < -1.0, "yaw delta=%+.2f" % yaw_left)

    # Simultaneous movement + look.
    teleport(rex, base_x, base_y, base_z)
    before = read_state(rex)
    focus_window(hwnd)
    click_center(hwnd)
    key_event(0x57, True)
    mouse_move(0, -50)
    time.sleep(0.6)
    key_event(0x57, False)
    time.sleep(0.3)
    both = read_state(rex)
    d = delta(before, both)
    pitch = (both.get("ctrl", [0, 0, 0])[0] - before.get("ctrl", [0, 0, 0])[0]) if both else 0.0
    check("W + look simultaneously", bool(d) and d[0] > 20.0 and pitch > 1.0,
          "dx=%+.0f pitch=%+.2f" % (d[0] if d else 0, pitch))

    fire(rex, END_SNIPPET, "PIEEND")
    time.sleep(6)

    text = read_log()[baseline:]
    bad = [m for m in ("DXGI_ERROR_DEVICE_REMOVED", "DXGI_ERROR_DEVICE_HUNG",
                       "D3D device being lost", "appError called", "Fatal error")
           if m in text]
    check("no rendering/device errors", not bad, ", ".join(bad))
    errors = [l for l in text.splitlines() if "Error:" in l or "LogSILID: Error" in l]
    check("no new log errors", not errors, errors[-1][-80:] if errors else "")
    lines.append("  session log chars (this run): %d" % len(text))

    return finish()


raise SystemExit(main())
