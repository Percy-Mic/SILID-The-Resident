"""Join every downloaded Poly Haven GLTF into one centered GLB per asset.
Run with Blender background mode:
  blender.exe -b -p Scripts/PreparePolyHavenAll.py
Reads:  ue5/Content/Raw/Models/<asset>/<asset>_2k.gltf (+ textures)
Writes: ue5/Saved/ImportReady/PH_<asset>.glb   (materials + 2k textures inside)
Polys are capped by simplification only if the mesh exceeds the budget.
"""
import bpy, os, glob, sys, mathutils

ROOT = r"C:\Users\Admin\Downloads\SILID-main"
RAW = os.path.join(ROOT, "ue5", "Content", "Raw", "Models")
OUT = os.path.join(ROOT, "ue5", "Saved", "ImportReady")
BUDGET = 60000  # triangles per prop; HD4600 budget
os.makedirs(OUT, exist_ok=True)

def reset():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for x in list(block):
            if x.users == 0:
                block.remove(x)

def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)

def prepare(path):
    name = os.path.basename(os.path.dirname(path))
    out = os.path.join(OUT, "PH_%s.glb" % name)
    if os.path.exists(out + ".flag"):
        print("[prep] skip", name, flush=True)
        return
    reset()
    try:
        bpy.ops.import_scene.gltf(filepath=path)
    except Exception as exc:
        print("[prep] FAIL import", name, exc, flush=True)
        return
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        print("[prep] FAIL no mesh", name, flush=True)
        return
    # bake node transforms
    for o in meshes:
        o.data.transform(o.matrix_world)
        o.location = (0, 0, 0)
        o.rotation_euler = (0, 0, 0)
        o.scale = (1, 1, 1)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    total = tri_count(obj)
    if total > BUDGET:
        m = obj.modifiers.new("dec", "DECIMATE")
        m.ratio = max(0.05, BUDGET / total)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=m.name)
        print("[prep] decimated %s %d -> %d" % (name, total, tri_count(obj)), flush=True)
    # center: origin at floor center
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    minx = min(p.x for p in corners); maxx = max(p.x for p in corners)
    miny = min(p.y for p in corners); maxy = max(p.y for p in corners)
    minz = min(p.z for p in corners)
    obj.data.transform(mathutils.Matrix.Translation(
        mathutils.Vector((-(minx + maxx) * .5, -(miny + maxy) * .5, -minz))))
    obj.name = "PH_" + name
    bpy.ops.export_scene.gltf(
        filepath=out, export_format="GLB", use_selection=True,
        export_apply=True, export_materials="EXPORT", export_image_format="AUTO",
        export_yup=True)
    open(out + ".flag", "w").close()
    print("[prep] OK %s tris=%d -> %s" % (name, tri_count(obj), out), flush=True)

for gltf in sorted(glob.glob(os.path.join(RAW, "*", "*_2k.gltf"))):
    prepare(gltf)
print("[prep] DONE", flush=True)
