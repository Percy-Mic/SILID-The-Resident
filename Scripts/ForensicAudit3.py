"""FORENSIC AUDIT 3 — find the REAL black-polygon geometry.
Run inside a live editor via RunEditorProbe.py.

Passes 1-2: actor/material layer clean. So the big black shapes are likely:
  a) HUGE meshes whose bbox exceeds the lightmap/shadow bounds, OR
  b) meshes with mismatched actor scale (e.g. a wall built in metres placed
     with scale 100 -> stretches UVs and normals), OR
  c) meshes rendered with the *default* world-grid material (grey/black
     checker) because their package material failed to load.

This pass:
  1. Lists the 25 LARGEST meshes by bbox diagonal with their actor scale
     and material names -> finds (a), (b), (c) in one table.
  2. Finds every actor whose label contains 'Floor'/'Wall'/'Roof'/'Terrain'
     AND whose material name contains 'WorldGridMaterial'/None.
  3. Samples triangle counts of the top suspects (lightmap resolution).
"""
import unreal

REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\forensic3_report.txt"
lines = []

def log(m):
    unreal.log("[forensic3] " + m)
    lines.append(m)

def diag(bb):
    lo = bb.min_position if hasattr(bb, "min_position") else bb.min
    hi = bb.max_position if hasattr(bb, "max_position") else bb.max
    # Box exposes .min/.max (x,y,z named fields) on 5.4 python
    try:
        lo = bb.min
        hi = bb.max
    except Exception:
        pass
    sx = hi.x - lo.x; sy = hi.y - lo.y; sz = hi.z - lo.z
    return (sx * sx + sy * sy + sz * sz) ** 0.5

entries = []      # (diag_cm, label, mesh_name, scale, mats)
grid_hits = []
QUARANTINE = {"SM_SILID_alarm_clock", "SM_SILID_armchair", "SM_SILID_bed", "SM_SILID_bookshelf",
              "SM_SILID_chair", "SM_SILID_door", "SM_SILID_kettle", "SM_SILID_nightstand",
              "SM_SILID_oil_lamp", "SM_SILID_plant", "SM_SILID_round_table", "SM_SILID_sofa",
              "SM_SILID_table", "SM_SILID_tea_set", "SM_SILID_vase", "SM_SILID_wall_clock"}
quarantine_uses = {}
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if not a:
        continue
    comps = a.get_components_by_class(unreal.StaticMeshComponent)
    for comp in comps:
        mesh = comp.get_editor_property("static_mesh")
        if not mesh:
            continue
        bb = mesh.get_bounding_box()
        d = diag(bb)
        mats = []
        try:
            for s in range(comp.get_num_materials()):
                m = comp.get_material(s)
                mats.append(m.get_name() if m else "NULL")
        except Exception:
            pass
        sc = comp.get_world_scale()
        entries.append((d, a.get_actor_label(), mesh.get_name(),
                        "(%.1f,%.1f,%.1f)" % (sc.x, sc.y, sc.z), ",".join(mats) or "NONE"))
        if mesh.get_name() in QUARANTINE:
            key = mesh.get_name()
            quarantine_uses[key] = quarantine_uses.get(key, 0) + 1
        joined = ",".join(mats).lower()
        if any(x in joined for x in ("worldgrid", "basicshapes")) or joined in ("none", "null", ""):
            grid_hits.append("%s mesh=%s mats=%s scale=(%.1f,%.1f,%.1f) diag=%.0fcm" %
                             (a.get_actor_label(), mesh.get_name(), joined, sc.x, sc.y, sc.z, d))

entries.sort(reverse=True)
log("== 25 largest meshes ==")
for d, label, mesh, sc, mats in entries[:25]:
    log("  LG: diag=%.0fcm  %s  mesh=%s  scale=%s  mats=[%s]" % (d, label, mesh, sc, mats))

log("== quarantine dummy meshes IN USE: %d kinds ==" % len(quarantine_uses))
for k, v in sorted(quarantine_uses.items(), key=lambda kv: -kv[1]):
    log("  QU: %s x%d" % (k, v))

log("== default/grid-material actors: %d ==" % len(grid_hits))
for g in grid_hits[:25]:
    log("  GR: " + g)

log("RESULT: DONE")
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
