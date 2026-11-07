"""Import the remaining prepared Poly Haven GLBs (run until count stops growing).
Chained: imports in batches, then quits — one import pass per editor launch
keeps memory flat on the 8 GB machine. Skips already-imported assets.
"""
import unreal, os, glob

# Skip the revision-control checkout dialog entirely (this CVar is what the
# checkout prompt reads; the Saved ini flags alone did not suppress it).
unreal.SystemLibrary.execute_console_command(None,
    "r.Editor.SkipSourceControlCheckForEditablePackages 1")

SRC = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\ImportReady"
DEST = "/Game/SILID/Furniture/PolyHaven"
REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\polyhaven_batch_report.txt"

unreal.EditorAssetLibrary.make_directory(DEST)
glbs = sorted(glob.glob(os.path.join(SRC, "PH_*.glb")))
tasks = []
for path in glbs:
    name = os.path.splitext(os.path.basename(path))[0]
    if unreal.EditorAssetLibrary.does_asset_exist(DEST + "/" + name):
        continue
    t = unreal.AssetImportTask()
    t.filename = path
    t.destination_path = DEST
    t.destination_name = name
    t.automated = True
    t.save = True
    tasks.append(t)

unreal.log("[PH batch] importing %d of %d" % (len(tasks), len(glbs)))
if tasks:
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

# set complex-as-simple collision on everything just imported
ok = 0
for path in glbs:
    name = os.path.splitext(os.path.basename(path))[0]
    mesh = unreal.load_asset(DEST + "/" + name)
    if mesh:
        ok += 1
        try:
            body = mesh.get_editor_property("body_setup")
            body.set_editor_property("collision_trace_flag",
                                     unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            mesh.set_editor_property("body_setup", body)
        except Exception:
            pass
unreal.log("[PH batch] RESULT: %d assets present in /Game/SILID/Furniture/PolyHaven" % ok)
with open(REPORT, "w") as fh:
    fh.write("%d assets present\n" % ok)
