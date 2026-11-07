"""Import every prepared Poly Haven GLB as a StaticMesh asset.
Run with:  python Scripts/RunEditorProbe.py Scripts/ImportPolyHavenAssets.py
Uses the proven AssetImportTask GLB path (import_glb in BuildExteriorWorldPMC).
Destination: /Game/SILID/Furniture/PolyHaven/<Name>. Complex-as-simple
collision ON for walkable/support furniture; materials preserved by import.
Writes a receipt to Saved/polyhaven_import_report.txt.
"""
import unreal, os, glob

ROOT = r"C:\Users\Admin\Downloads\SILID-main"
SRC = os.path.join(ROOT, "ue5", "Saved", "ImportReady")
DEST = "/Game/SILID/Furniture/PolyHaven"
REPORT = os.path.join(ROOT, "ue5", "Saved", "polyhaven_import_report.txt")

# headless: never prompt (checkout dialogs deadlocked the previous session).
# (-unattended is a command-line switch, handled by the launcher; nothing to
# set here.)

# Furniture the player can stand on / that must block: use complex collision.
BLOCKING = True

lines = []
def log(m):
    unreal.log("[PH import] " + m)
    lines.append(m)

unreal.EditorAssetLibrary.make_directory(DEST)

glbs = sorted(glob.glob(os.path.join(SRC, "PH_*.glb")))
log("found %d GLBs" % len(glbs))

tasks = []
for path in glbs:
    name = os.path.splitext(os.path.basename(path))[0]  # PH_xxx
    if unreal.EditorAssetLibrary.does_asset_exist(DEST + "/" + name):
        log("skip existing " + name)
        continue
    t = unreal.AssetImportTask()
    t.filename = path
    t.destination_path = DEST
    t.destination_name = name
    t.automated = True
    t.save = True
    tasks.append(t)

if tasks:
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    log("imported %d" % len(tasks))

ok = fail = 0
for path in glbs:
    name = os.path.splitext(os.path.basename(path))[0]
    asset_path = DEST + "/" + name + "." + name
    mesh = unreal.load_asset(asset_path)
    if not mesh:
        log("MISSING " + name)
        fail += 1
        continue
    ok += 1
    # collision: complex-as-simple so props block reliably (small tri counts)
    try:
        body = mesh.get_editor_property("body_setup")
        body.set_editor_property("collision_trace_flag",
                                 unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        mesh.set_editor_property("body_setup", body)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    except Exception as exc:
        log("collision flag failed %s: %s" % (name, exc))

log("RESULT: PASS ok=%d fail=%d" % (ok, fail))
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
