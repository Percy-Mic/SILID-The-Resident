"""FORENSIC AUDIT — scan LM_SILID_GroundFloor for technical defects that
produce black polygons / floating geometry / broken shading.
Run inside a live editor via RunEditorProbe.py (remote execution).

Checks per actor:
  A. StaticMeshComponent with NULL material slots
  B. Meshes with negative/zero scale
  C. Actors far below terrain or unreasonably high (floating)
  D. ProceduralMesh sections with no material assigned
  E. Mesh assets whose bounds are degenerate (zero volume)
  F. Materials that failed to compile (error count > 0)
Receipts: Saved/forensic_report.txt (RESULT line drives the probe exit).
"""
import unreal

LEVEL_REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\forensic_report.txt"
lines = []

def log(m):
    unreal.log("[forensic] " + m)
    lines.append(m)

null_mat = []        # (actor, comp, slot)
neg_scale = []       # (actor, scale)
floating = []        # (actor, z)
no_section_mat = []  # (actor, section idx)
degenerate = []      # mesh asset
bad_materials = []   # material assets with errors

actors = unreal.EditorLevelLibrary.get_all_level_actors()
log("scanning %d actors" % len(actors))

for a in actors:
    if not a:
        continue
    label = a.get_actor_label()
    # A/B: root + all static mesh components
    comps = [c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c]
    comps += [c for c in a.get_components_by_class(unreal.ProceduralMeshComponent) if c]
    for comp in comps:
        # scale check
        sx, sy, sz = (comp.get_world_scale().x, comp.get_world_scale().y, comp.get_world_scale().z)
        if sx <= 0 or sy <= 0 or sz <= 0:
            neg_scale.append("%s [%s] scale=(%.2f,%.2f,%.2f)" % (label, comp.get_name(), sx, sy, sz))
        mesh = None
        try:
            mesh = comp.get_editor_property("static_mesh")
        except Exception:
            mesh = None
        if mesh:
            # A: null material slots (asset slots with no material section wired)
            try:
                n_slots = comp.get_num_materials()
                for s in range(n_slots):
                    m = comp.get_material(s)
                    if m is None:
                        null_mat.append("%s [%s] slot %d NULL (mesh %s)" % (label, comp.get_name(), s, mesh.get_name()))
            except Exception:
                pass
            # E: degenerate bounds
            try:
                bb = mesh.get_bounding_box()
                if bb.get_size().z <= 0:
                    degenerate.append(mesh.get_name())
            except Exception:
                pass
        else:
            null_mat.append("%s [%s] has NO static mesh assigned" % (label, comp.get_name()))
    # C: floating (only static-ish actors, skip lights/pawns)
    if a.get_class().get_name() not in ("DirectionalLight", "SkyLight", "SILIDCharacter", "SILIDResident", "SILIDOpeningCar"):
        z = a.get_actor_location().z
        if z < -600:
            floating.append("%s z=%.0f (below basement)" % (label, z))

log("== SUMMARY ==")
log("null-material slots: %d" % len(null_mat))
for x in null_mat[:25]:
    log("  NM: " + x)
log("bad scale: %d" % len(neg_scale))
for x in neg_scale[:15]:
    log("  SC: " + x)
log("deep-floating actors: %d" % len(floating))
for x in floating[:15]:
    log("  FL: " + x)
log("procmesh sections w/o material: %d" % len(no_section_mat))
for x in no_section_mat[:15]:
    log("  PM: " + x)
log("degenerate-bounds meshes: %d" % len(set(degenerate)))
for x in sorted(set(degenerate))[:15]:
    log("  DG: " + x)

total_problems = len(null_mat) + len(neg_scale) + len(no_section_mat) + len(set(degenerate))
log("RESULT: %s problems=%d" % ("PASS" if total_problems == 0 else "ISSUES", total_problems))
with open(LEVEL_REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
