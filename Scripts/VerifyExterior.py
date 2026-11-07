"""Verify the SILID exterior build: actor census + traversal traces.

Extends the interior traverse probe's method to the outside world. Traces
downward at plan-space points whose heights are known from the prototype's
own terrain function, and counts the exterior actors by label.

Receipt: Saved/exterior_report.txt (RESULT PASS/FAIL).
"""

import unreal

MAP = "/Game/SILID/Maps/LM_SILID_GroundFloor"
REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\exterior_report.txt"
PREFIX = "SILID - EXT - "

lines = []
fails = []

# (label, plan_x, plan_z, expected_z_cm, tolerance_cm)
# Heights from the prototype: mansion pad dead flat 0; road masked flat ~0.5;
# pond bed carved to about -2; pond surface is water (no collision) so the
# trace should pass through it and hit the bed; the trail rides the field.
PROBES = [
    ("Mansion pad centre",      0.0,    0.0,    0,   30),
    ("Road at car pull-off",  -58.6,   -6.0,   10,   60),
    ("Trail mid-approach",    -15.0,   17.5,   50,  120),
    ("Forest floor east",      40.0,  -30.0,  120, 300),
    ("Pond bed (through water)", -30.0, 46.0, -220, 220),
]


def run():
    loaded = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    lines.append("map loaded: %s" % bool(loaded))
    if not loaded:
        fails.append("map load")
        return

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    census = {}
    for actor in subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if label.startswith(PREFIX):
            key = label[len(PREFIX):].split(" - ")[0].split(" ")[0]
            census[key] = census.get(key, 0) + 1
    lines.append("exterior actor census: %s" % census)
    for required in ("Terrain", "Road", "Trail", "Pond", "Moonlight", "Night"):
        if not any(required.lower() in k.lower() for k in census):
            fails.append("missing exterior actor: " + required)
    trees = census.get("Tree", 0)
    if trees < 340:
        fails.append("trees=%d (expected 340)" % trees)

    world = unreal.EditorLevelLibrary.get_editor_world()
    # Start each trace 250 cm above the expected height and stop 250 cm below:
    # low enough to stay under the mansion's roof (the pad sits inside the
    # house footprint), high enough to clear terrain relief and furniture.
    for label, x_m, z_m, expect, tol in PROBES:
        x, y = x_m * 100.0, z_m * 100.0
        hit = unreal.SystemLibrary.line_trace_single(
            world,
            unreal.Vector(x, y, expect + 250.0),
            unreal.Vector(x, y, expect - 250.0),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False, [], unreal.DrawDebugTrace.FOR_ONE_FRAME, True,
            unreal.LinearColor(1, 0, 0, 1), unreal.LinearColor(0, 1, 0, 1), 5.0,
        )
        if hit is None:
            lines.append("%-28s NO HIT (trace returned None)" % label)
            fails.append(label + ": no hit")
            continue
        tup = hit.to_tuple()
        blocked = tup[0] if tup else None
        if not blocked:
            lines.append("%-28s NOTHING SOLID BELOW" % label)
            fails.append(label + ": no ground")
            continue
        loc = tup[5]
        z = loc.z
        ok = abs(z - expect) <= tol
        lines.append("%-28s ground z=%8.1f (expected ~%d)" % (label, z, expect))
        if not ok:
            fails.append("%s ground %.0f, expected ~%d" % (label, z, expect))

    # the interior must still be there: one trace on the GF slab and one in B1
    for label, x_m, z_m, floor in (("GF slab", 0.0, 0.0, 0), ("B1 cellar", -4.5, -2.0, -340)):
        x, y = x_m * 100.0, z_m * 100.0
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(x, y, floor * 1.0 + 300.0), unreal.Vector(x, y, floor * 1.0 - 300.0),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
            unreal.DrawDebugTrace.FOR_ONE_FRAME, True,
            unreal.LinearColor(1, 0, 0, 1), unreal.LinearColor(0, 1, 0, 1), 5.0)
        if hit is None:
            lines.append("%-28s interior MISSING (trace None)" % label)
            fails.append(label + ": interior gone")
            continue
        tup = hit.to_tuple()
        if not tup or not tup[0]:
            lines.append("%-28s interior MISSING" % label)
            fails.append(label + ": interior gone")
        else:
            lines.append("%-28s solid at z=%.1f" % (label, tup[5].z))


run()
lines.append("probes done, failures=%d" % len(fails))
lines.append("RESULT: " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print(lines[-1], flush=True)
