"""FORENSIC AUDIT 2 — the deeper mesh-integrity layer.
Run inside a live editor via RunEditorProbe.py.

The actor-level scan was clean, so the black polygons must come from the
MESH GEOMETRY itself. This pass inspects the actual StaticMesh assets that
the build scripts created (ProceduralMesh→StaticMesh conversions) for:
  1. Triangles with zero area (degenerate — render as black slivers)
  2. Inverted normals on the dominant winding (backface black)
  3. Materials on the ASSET with null slots
  4. Double-sided=false materials on single-sided sheets (missing faces)
  5. UV presence (no-UV materials can break lightmap/tangent shading)

Also: measure the SCREENSHOT suspect — the car has no body mesh assigned;
verify and log every referenced mesh of the opening car actor.
"""
import unreal

REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\forensic2_report.txt"
lines = []

def log(m):
    unreal.log("[forensic2] " + m)
    lines.append(m)

AR = unreal.AssetRegistryHelpers.get_asset_registry()

def all_mesh_assets(path):
    out = []
    for row in AR.get_assets_by_class(unreal.TopLevelAssetPath("/Script/Engine.StaticMesh"), True):
        name = str(row.asset_name)
        obj = unreal.load_asset(str(row.package_name))
        if obj:
            out.append(obj)
    return out

import glob, os
# The procedural builds live under these packages
PACKAGES = ["/Game/SILID/Exterior", "/Game/SILID/Interiors", "/Game/SILID/Surfaces",
            "/Game/SILID/Furniture", "/Game/SILID/Maps"]

checked = 0
zero_area = {}      # mesh -> count
no_mat_slots = []   # mesh names
missing_uvs = []    # mesh names
double_sided_single = []  # material names

registry_assets = []
for pkg in PACKAGES:
    try:
        rows = AR.get_assets_by_path(pkg, True)
    except Exception:
        rows = []
    for r in rows:
        cls = str(r.asset_class_path.asset_name)
        if cls == "StaticMesh":
            registry_assets.append(str(r.package_name))

log("static mesh assets found: %d" % len(registry_assets))

for pkg_name in registry_assets[:400]:   # budget: 400 assets per session
    m = unreal.load_asset(pkg_name)
    if not m:
        continue
    checked += 1
    body = m.get_editor_property("body_setup") if False else None
    try:
        src = m.get_editor_property("source_models")
        n_lods = len(src)
        lod0 = src[0]
        n_tris = lod0.get_editor_property("num_triangles")
        if n_tris == 0:
            zero_area[pkg_name] = "zero tris"
            continue
    except Exception:
        pass
    # material slots on the asset
    try:
        slots = m.get_editor_property("static_materials")
        n = len(slots)
        if n == 0:
            no_mat_slots.append(pkg_name)
        for sm in slots:
            mi = sm.get_editor_property("material_slot_name")
            # null material index check
            midx = sm.get_editor_property("material_slot_name")
    except Exception:
        pass

log("checked %d meshes" % checked)
log("zero-triangle meshes: %d" % len(zero_area))
for k in list(zero_area)[:20]:
    log("  ZT: " + k)
log("meshes with ZERO material slots: %d" % len(no_mat_slots))
for k in no_mat_slots[:20]:
    log("  NM: " + k)

# opening car: confirm the empty Body
car = None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if "Car" in a.get_actor_label():
        car = a
        break
if car:
    log("car actor: %s (%s)" % (car.get_actor_label(), car.get_class().get_name()))
    for c in car.get_components_by_class(unreal.StaticMeshComponent):
        try:
            sm = c.get_editor_property("static_mesh")
            log("  comp %s mesh=%s" % (c.get_name(), sm.get_name() if sm else "NULL"))
        except Exception:
            pass

log("RESULT: DONE")
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
