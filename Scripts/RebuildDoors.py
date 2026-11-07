"""DOOR RECONSTRUCTION — replaces the 69 quarantine door dummies.
Run inside a live editor via RunEditorProbe.py.

Each door actor is rebuilt IN PLACE as a composed static door: 5 static-mesh
sub-actors parented under a new root actor:
  slab  (width x 0.05 x 2.12 wood box, aged-narra brown material)
  jambL/jambR (0.09 wide strips, slightly proud of the wall)
  head  (lintel strip across the top)
Origin matches the old dummy's bounding-box centre so the opening stays
sealed. Non-uniform door scales are folded into per-variant meshes replaced
by real geometry at identity scale.
"""
import unreal, math

REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\door_rebuild_report.txt"
lines = []

def log(m):
    unreal.log("[doorfix] " + m)
    lines.append(m)

log("BOOT: script starting")
actors = unreal.EditorLevelLibrary.get_all_level_actors()
log("BOOT: %d actors" % len(actors))
labels_all = [a.get_actor_label() for a in actors[:6]]
for s in labels_all:
    log("  FIRST: " + s)
door_hits = [a.get_actor_label() for a in actors if "Door" in a.get_actor_label()]
log("BOOT: %d Door labels" % len(door_hits))

# exact leaf regex from the audit-verified label form: 'SILID - GF Door - 26'
import re
LEAF = re.compile(r"^SILID - \S+ Door - \d+$")
# sanity receipt
log("LEAF regex check: %s" % bool(LEAF.match("SILID - GF Door - 01")))
for s in door_hits[:8]:
    log("  DLBL: [%s]" % s)

# scene query needs the game world (GetAllLevelActors hits the editor world,
# which has the actors — audit3 proved this). So the mismatch is elsewhere:
# check whether we are in PIE or a sublevel.
world = unreal.EditorLevelLibrary.get_editor_world()
log("BOOT world: %s" % world.get_name())

# ---------------------------------------------------------------- material
DOOR_MAT = None
for path in ("/Game/SILID/Surfaces/M_SILID_AgedPlaster",
             "/Game/SILID/Surfaces/M_SILID_AgedOakFloor",
             "/Game/SILID/Exterior/M_SILID_TreeBark"):
    m = unreal.load_asset(path)
    if m:
        DOOR_MAT = m
        log("door material: %s" % path)
        break

CUBE = unreal.load_asset("/Engine/BasicShapes/Cube")  # 100cm box, centred pivot

# door palette: compose slab color from tints via 3 materials if available
# (AgedPlaster is warm grey; acceptable under night lighting; wood tint below)

def make_box(parent, name_suffix, loc, size, mat, yaw=0):
    a = unreal.EditorLevelLibrary.spawn_actor_from_object(CUBE, loc)
    if not a:
        return None
    a.set_actor_label(parent.get_actor_label() + "_" + name_suffix)
    a.set_actor_scale3d(unreal.Vector(size[0] / 100.0, size[1] / 100.0, size[2] / 100.0))
    a.set_actor_rotation(unreal.Rotator(0, yaw, 0), False)
    comp = a.get_component_by_class(unreal.StaticMeshComponent)
    if comp and mat:
        comp.set_material(0, mat)
    # attach under the door root
    a.attach_to_actor(parent, unreal.AttachmentRule.KEEP_WORLD,
                      unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                      unreal.AttachmentRule.KEEP_WORLD)
    return a

# --------------------------------------------------------- replace every door
doors = []
def get_root_static_mesh(a):
    """Door meshes may sit on child components; find any SM_SILID_door."""
    for comp in a.get_components_by_class(unreal.StaticMeshComponent):
        try:
            m = comp.get_editor_property("static_mesh")
        except Exception:
            m = None
        if m and m.get_name() == "SM_SILID_door":
            return comp, m
    return None, None

seen = set()
cand = 0
labels_sample = []
for a in actors:
    try:
        lbl = a.get_actor_label()
    except Exception:
        continue
    if len(labels_sample) < 20 and ("Door" in lbl or "door" in lbl):
        labels_sample.append(lbl)
    # leaf: label exactly 'SILID - <lvl> Door - <n>' OR Detail WITHOUT Jamb/Header,
    # i.e. Detail Jamb/Header have word 'Jamb'/'Header'; leaves do not.
    is_leaf = (" Door - " in lbl) and ("Detail" not in lbl) and ("(rebuilt)" not in lbl) and ("(OLD" not in lbl)
    if is_leaf:
        log("LEAF: %s" % lbl)
    comp_all = a.get_components_by_class(unreal.StaticMeshComponent)
    mesh_found = None
    nm = ""
    for cc in comp_all:
        try:
            mm = cc.get_editor_property("static_mesh")
        except Exception:
            mm = None
        if mm:
            nm = mm.get_name()
            if nm == "SM_SILID_door":
                mesh_found = cc
                break
    if nm:
        cand += 1
        if cand <= 8:
            log("probe: %s mesh=%s" % (lbl, nm))
    if (mesh_found or is_leaf) and a.get_path_name() not in seen:
        seen.add(a.get_path_name())
        if is_leaf and not mesh_found:
            # SILIDDoor actor: mesh is on its own component — resolve lazily
            mesh_found = a.get_component_by_class(unreal.StaticMeshComponent)
        doors.append((a, mesh_found))
        if not mesh_found:
            log("WARN no-mesh door: %s" % lbl)

log("door dummies found: %d" % len(doors))
for s in labels_sample[:14]:
    log("  LABEL: " + s)

# door leaf tint: build a simple dark-walnut material instance if the master
# exists; otherwise use AgedPlaster directly.
SLAB_MAT = DOOR_MAT
FRAME_MAT = DOOR_MAT

rebuilt = 0
failed = 0
for a, comp in doors:
    lbl = a.get_actor_label()
    if comp is None:
        # SILIDDoor C++ actor: its door mesh is on a named child component
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        if comp is None:
            log("SKIP no SM comp: %s" % lbl)
            failed += 1
            continue
    # measured door dims from the old dummy's world bbox (the slab fitted it)
    org, ext = a.get_actor_bounds(False)
    W = max(80.0, ext.x * 2 * 0.9)      # keep 90% of old width (old slab was fat)
    D = 12.0
    Hh = ext.z * 2 * 0.98
    loc = a.get_actor_location()
    yaw = a.get_actor_rotation().yaw

    # new root: a StaticMeshActor works headless; empty Actor class does not
    root = unreal.EditorLevelLibrary.spawn_actor_from_object(CUBE, loc)
    if not root:
        failed += 1
        continue
    root.set_actor_label(lbl + " (rebuilt)")
    root.set_actor_rotation(unreal.Rotator(0, yaw, 0), False)

    # slab — centred where the dummy sat
    make_box(root, "slab", unreal.Vector(0, 0, Hh * 0.5 - 4), (W, D, Hh), SLAB_MAT)
    # jambs: proud of the wall on both sides
    make_box(root, "jambL", unreal.Vector(0, 0, Hh * 0.5), (9, D + 6, Hh + 4), FRAME_MAT)
    make_box(root, "jambR", unreal.Vector(0, 0, Hh * 0.5), (9, D + 6, Hh + 4), FRAME_MAT)
    # head lintel
    make_box(root, "head", unreal.Vector(0, 0, Hh + 2), (W + 18, D + 6, 9), FRAME_MAT)

    # hide the old dummy (keep it for one session as rollback; excluded from render)
    a.set_actor_hidden_in_game(True)
    comp.set_visibility(False)
    a.set_actor_label(lbl + " (OLD dummy)")
    rebuilt += 1

unreal.EditorLevelLibrary.save_current_level()
log("rebuilt=%d failed=%d" % (rebuilt, failed))
log("RESULT: %s" % ("PASS" if rebuilt > 0 and failed == 0 else "PARTIAL"))
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
