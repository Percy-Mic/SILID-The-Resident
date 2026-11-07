"""Non-destructive SILID project audit.

Run with UnrealEditor-Cmd -run=pythonscript -script=Scripts/AuditProject.py.
Writes machine-readable JSON and a compact text summary under Saved/Audit.
It does not save any map or asset.
"""
import collections
import json
import os
import traceback

import unreal

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_DIR, "Saved", "Audit")
OUT_JSON = os.path.join(OUT_DIR, "project_inventory.json")
OUT_TXT = os.path.join(OUT_DIR, "project_inventory.txt")
MAP_PATHS = [
    "/Game/SILID/Maps/LM_SILID_GroundFloor",
    "/Game/LM_SILID_Base",
]

os.makedirs(OUT_DIR, exist_ok=True)
report = {
    "project": PROJECT_DIR,
    "assets": [],
    "asset_class_counts": {},
    "meshes": [],
    "maps": {},
    "errors": [],
}


def safe(label, fn, default=None):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - audit must keep going
        report["errors"].append("%s: %s" % (label, exc))
        return default


def path_name(obj):
    if obj is None:
        return None
    try:
        return obj.get_path_name()
    except Exception:
        return str(obj)


registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = registry.get_assets_by_path("/Game", recursive=True)
for a in assets:
    pkg = str(safe("package_name", lambda a=a: a.package_name, ""))
    name = str(safe("asset_name", lambda a=a: a.asset_name, ""))
    if not pkg or not name:
        continue
    cls = str(safe("asset_class_path", lambda a=a: a.asset_class_path.asset_name, ""))
    if not cls:
        cls = str(safe("asset_class", lambda a=a: a.asset_class, ""))
    item = {"package": pkg, "name": name, "class": cls}
    report["assets"].append(item)
    report["asset_class_counts"][cls] = report["asset_class_counts"].get(cls, 0) + 1

for item in sorted(report["assets"], key=lambda x: (x["class"], x["package"])):
    if item["class"] != "StaticMesh":
        continue
    mesh = safe("load " + item["package"], lambda p=item["package"]: unreal.EditorAssetLibrary.load_asset(p))
    if mesh is None:
        continue
    tris = safe("tris " + item["package"], lambda m=mesh: int(m.get_num_triangles(0)), None)
    verts = safe("verts " + item["package"], lambda m=mesh: int(m.get_num_vertices(0)), None)
    lods = safe("lods " + item["package"], lambda m=mesh: int(m.get_num_lods()), None)
    mats = safe("mats " + item["package"], lambda m=mesh: [path_name(m.get_material(i)) for i in range(8) if m.get_material(i)], [])
    report["meshes"].append({
        "asset": item["name"],
        "package": item["package"],
        "triangles_lod0": tris,
        "vertices_lod0": verts,
        "lods": lods,
        "materials": mats,
    })

for map_path in MAP_PATHS:
    map_info = {"path": map_path, "loaded": False, "actors": [], "class_counts": {}}
    report["maps"][map_path] = map_info
    if not safe("exists " + map_path, lambda p=map_path: unreal.EditorAssetLibrary.does_asset_exist(p), False):
        map_info["error"] = "asset does not exist"
        continue
    loaded = safe("load_map " + map_path, lambda p=map_path: unreal.EditorLoadingAndSavingUtils.load_map(p))
    if not loaded:
        map_info["error"] = "load_map failed"
        continue
    map_info["loaded"] = True
    actors = safe("actors " + map_path, lambda: unreal.EditorLevelLibrary.get_all_level_actors(), [])
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
            cls = str(actor.get_class().get_name())
            loc = actor.get_actor_location()
            entry = {
                "label": label,
                "class": cls,
                "location": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)],
            }
            try:
                if isinstance(actor, unreal.StaticMeshActor):
                    comp = actor.static_mesh_component
                    sm = comp.static_mesh if comp else None
                    entry["mesh"] = path_name(sm)
            except Exception:
                pass
            try:
                if isinstance(actor, unreal.Light):
                    entry["intensity"] = float(actor.get_editor_property("intensity"))
                    entry["light_component_class"] = actor.get_class().get_name()
            except Exception:
                pass
            map_info["actors"].append(entry)
            map_info["class_counts"][cls] = map_info["class_counts"].get(cls, 0) + 1
        except Exception as exc:
            report["errors"].append("actor in %s: %s" % (map_path, exc))

with open(OUT_JSON, "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2)

lines = []
lines.append("SILID project audit")
lines.append("Assets: %d" % len(report["assets"]))
for cls, count in sorted(report["asset_class_counts"].items(), key=lambda kv: (-kv[1], kv[0])):
    lines.append("  %-24s %d" % (cls, count))
lines.append("")
lines.append("Static meshes: %d" % len(report["meshes"]))
for m in sorted(report["meshes"], key=lambda x: -(x["triangles_lod0"] or 0)):
    lines.append("  %-34s tris=%-8s verts=%-8s lods=%s" % (
        m["asset"], m["triangles_lod0"], m["vertices_lod0"], m["lods"]))
lines.append("")
for map_path, info in report["maps"].items():
    lines.append("Map %s loaded=%s actors=%d" % (map_path, info.get("loaded"), len(info.get("actors", []))))
    for cls, count in sorted(info.get("class_counts", {}).items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append("  %-32s %d" % (cls, count))
    if info.get("error"):
        lines.append("  ERROR: %s" % info["error"])
lines.append("")
lines.append("Errors: %d" % len(report["errors"]))
for err in report["errors"][:80]:
    lines.append("  " + err)

with open(OUT_TXT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

print("\n".join(lines))
print("WROTE " + OUT_JSON)
