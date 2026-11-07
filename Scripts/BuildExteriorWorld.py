"""Build the exterior world inside the SILID Unreal level.

Run with:  python Scripts/RunEditorProbe.py <this file>   (or via BuildMansion.py)

Rerunnable: removes only "SILID - EXT - " actors, and re-imports the exterior
meshes fresh (a stale mesh from an older run would carry wrong coordinates).

Inputs (written by scripts/export_exterior_ue.mjs — plan axes: +x east, +z north,
+y up, metres; the game's UE mapping is x->X, z->Y, y->Z, 1 m = 100 uu):
  ue5/Saved/ImportReady/terrain.obj   ground heightfield (mansion pad at y=0)
  ue5/Saved/ImportReady/road.obj      crowned carriageway + verges + markings
  ue5/Saved/ImportReady/trail.obj     the approach track to the porch
  ue5/Saved/ImportReady/pond.obj      the pond water disc
  ue5/Saved/ImportReady/trees.json    340 tree placements (species/variant/scale)

How the geometry lands correctly: this editor's OBJ importer maps axes and
units its own way (Y-up source, possible sign flips, possible unit scaling).
Rather than guess, the script first imports a tiny asymmetric probe tetra,
reads its world bounds, and derives the exact mapping (axis permutation, sign,
unit scale) from the numbers it measured. Every OBJ is then written THROUGH
that mapping, so the terrain stands under the mansion at the coordinates the
plan — and the playable prototype — used.

What it creates:
  - terrain / road / trail / pond as static meshes with metre-based planar UVs
    (so the forest-ground and asphalt photographs tile at their real size)
  - collision enabled complex-as-simple on every ground surface
  - trees: one batch actor per species/variant holding two
    InstancedStaticMeshComponents (trunk cylinder + crossed leaf cards)
  - night sky: moonlight, skylight fill, exponential height fog
"""

import json
import math
import os
import traceback

import unreal

ROOT = r"C:\Users\Admin\Downloads\SILID-main"
IMPORT_READY = os.path.join(ROOT, "ue5", "Saved", "ImportReady")
TEX_SRC = os.path.join(ROOT, "public", "assets", "textures")
TEX_DEST = "/Game/SILID/Surfaces"
EXT_DEST = "/Game/SILID/Exterior"
MAP_SAVE_PATH = "/Game/SILID/Maps/LM_SILID_GroundFloor"
PREFIX = "SILID - EXT - "
M = 100.0  # plan metres -> UE centimetres

# Filled in by calibrate(): how the OBJ importer maps axes and units.
MAPPING = None   # obj axis name -> (ue axis index, sign)
K = 1.0          # uniform scale the importer applies (obj unit -> UE cm)

TRUNK_MESH = None
LEAF_MESH = None


def log(msg):
    unreal.log("[SILID ext] " + msg)
    print("[SILID ext] " + msg, flush=True)


def plan_to_ue(x, y, z):
    """plan metres -> UE location (cm): x->X, z->Y, y->Z."""
    return unreal.Vector(x * M, z * M, y * M)


# --------------------------------------------------------------- materials ---
def import_texture(name, filename, normal=False, linear=False):
    asset_path = TEX_DEST + "/" + name + "." + name
    texture = unreal.load_asset(asset_path)
    if not texture:
        source = os.path.join(TEX_SRC, filename)
        if not os.path.isfile(source):
            raise RuntimeError("texture missing: " + source)
        task = unreal.AssetImportTask()
        task.filename = source
        task.destination_path = TEX_DEST
        task.destination_name = name
        task.automated = True
        task.save = True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = unreal.load_asset(asset_path)
    if not texture:
        raise RuntimeError("could not import texture " + asset_path)
    if normal:
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("srgb", False)
    elif linear:
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        texture.set_editor_property("srgb", False)
    unreal.EditorAssetLibrary.save_loaded_asset(texture)
    return texture


def textured_material(name, maps, u_tiling, v_tiling):
    path = TEX_DEST + "/" + name + "." + name
    material = unreal.load_asset(path)
    if material:
        return material
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(name, TEX_DEST, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError("could not create material " + name)
    editor = unreal.MaterialEditingLibrary
    coords = editor.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -700, 0)
    coords.set_editor_property("u_tiling", float(u_tiling))
    coords.set_editor_property("v_tiling", float(v_tiling))
    for filename, texture, output, prop, y in maps:
        sample = editor.create_material_expression(material, unreal.MaterialExpressionTextureSample, -400, y)
        sample.set_editor_property("texture", texture)
        editor.connect_material_expressions(coords, "", sample, "Coordinates")
        if not editor.connect_material_property(sample, output, prop):
            raise RuntimeError("could not connect " + filename + " to " + name)
    editor.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def flat_material(name, color, rough=0.9, metal=0.0):
    path = EXT_DEST + "/" + name + "." + name
    material = unreal.load_asset(path)
    if material:
        return material
    unreal.EditorAssetLibrary.make_directory(EXT_DEST)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(name, EXT_DEST, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError("could not create material " + name)
    editor = unreal.MaterialEditingLibrary
    const = editor.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -300, 0)
    const.set_editor_property("constant", unreal.LinearColor(color[0], color[1], color[2], 1.0))
    editor.connect_material_property(const, "", unreal.MaterialProperty.MP_BASE_COLOR)
    r = editor.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 200)
    r.set_editor_property("r", rough)
    editor.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    m = editor.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 320)
    m.set_editor_property("r", metal)
    editor.connect_material_property(m, "", unreal.MaterialProperty.MP_METALLIC)
    editor.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


# ------------------------------------------------------------ OBJ handling ---
def obj_tris(path):
    """Read the exporter's OBJ into (verts, faces) in PLAN coordinates.

    Two face styles appear: the exporter writes relative negatives
    ("f -3 -2 -1" — the three verts just written), and this script's own
    writers emit positive 1-based indices. Both resolve here; a negative
    OBJ index counts back from the CURRENT vertex count.
    """
    verts, faces = [], []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("v "):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("f "):
                face = [int(tok.split("/")[0]) for tok in line.split()[1:]]
                n = len(verts)
                faces.append(tuple((i - 1) if i > 0 else (n + i) for i in face))
    return verts, faces


def obj_from_plan(x, y, z):
    """plan metres -> obj coordinates that import at UE (x, z, y) cm."""
    t = (x * M, z * M, y * M)  # target UE cm
    out = [0.0, 0.0, 0.0]
    for ai, (u, sign) in MAPPING.items():
        out[OBJ_AXIS_INDEX[ai]] = sign * t[u] / K
    return out


def obj_to_plan(o):
    """Inverse of obj_from_plan — used to recover plan metres for UVs."""
    t = [0.0, 0.0, 0.0]
    for ai, (u, sign) in MAPPING.items():
        t[u] = sign * K * o[OBJ_AXIS_INDEX[ai]]
    return (t[0] / M, t[2] / M, t[1] / M)  # (plan x, plan y(up), plan z)


def write_obj(path, name, plan_verts, faces, uv_scale):
    """Write verts/UVs/faces in the importer's coordinate space.

    UVs are planar top-down over the plan (u = plan_x, v = plan_z), scaled so
    one texture tile covers uv_scale metres — the tiling lives in the UVs, and
    the material is authored at tiling 1,1.
    """
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("o %s\n" % name)
        for v in plan_verts:
            fh.write("v %.4f %.4f %.4f\n" % tuple(obj_from_plan(*v)))
        for v in plan_verts:
            px, _, pz = obj_to_plan(obj_from_plan(*v))
            fh.write("vt %.6f %.6f\n" % (px / uv_scale, pz / uv_scale))
        for f in faces:
            fh.write("f %d/%d %d/%d %d/%d\n" % (
                f[0] + 1, f[0] + 1, f[1] + 1, f[1] + 1, f[2] + 1, f[2] + 1))


# ------------------------------------------- importer axis/unit calibration ---
# A tetra whose extents differ per axis (3/4/7) and whose min corner is
# asymmetric (1,2,3): the imported bounds reveal the axis permutation, any
# sign flips, and the importer's unit scale in three numbers.
PROBE_VERTS = [(1.0, 2.0, 3.0), (4.0, 2.0, 3.0), (1.0, 6.0, 3.0), (1.0, 2.0, 10.0)]
PROBE_FACES = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
# (full span, centre) per obj axis, in obj units
PROBE_SRC = {"x": (3.0, 2.5), "y": (4.0, 4.0), "z": (7.0, 6.5)}
OBJ_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def calibrate(subsystem):
    """Measure how this editor's OBJ import maps axes and units.

    Returns a description string; sets globals MAPPING and K. A world point
    imported from obj coords O lands at UE P with P[u] = sign * K * O[axis].
    """
    global MAPPING, K
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    path = os.path.join(IMPORT_READY, "axis_probe.obj")
    with open(path, "w") as fh:
        fh.write("o AxisProbe\n")
        for v in PROBE_VERTS:
            fh.write("v %f %f %f\n" % tuple(v))
        for f in PROBE_FACES:
            fh.write("f %d %d %d\n" % tuple(i + 1 for i in f))
    unreal.EditorAssetLibrary.make_directory(EXT_DEST)
    if unreal.EditorAssetLibrary.does_asset_exist(EXT_DEST + "/SM_AxisProbe"):
        unreal.EditorAssetLibrary.delete_asset(EXT_DEST + "/SM_AxisProbe")
    task = unreal.AssetImportTask()
    task.filename = path
    task.destination_path = EXT_DEST
    task.destination_name = "SM_AxisProbe"
    task.automated = True
    task.save = True
    tools.import_asset_tasks([task])
    imported = list(task.imported_object_paths or [])
    mesh_path = imported[0] if imported else EXT_DEST + "/SM_AxisProbe.SM_AxisProbe"
    mesh = unreal.load_asset(mesh_path)
    if not mesh:
        raise RuntimeError("calibration OBJ import produced no mesh — OBJ pipeline unavailable")
    actor = subsystem.spawn_actor_from_object(mesh, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    if not actor:
        raise RuntimeError("calibration mesh could not be spawned")
    origin, extent = actor.get_actor_bounds(False)
    subsystem.destroy_actor(actor)
    unreal.EditorAssetLibrary.delete_asset(EXT_DEST + "/SM_AxisProbe")

    e = [extent.x, extent.y, extent.z]
    o = [origin.x, origin.y, origin.z]
    cands = []
    for ai_name, (span, centre) in PROBE_SRC.items():
        for u in range(3):
            k = e[u] / span
            if 0.001 < k < 1000.0:
                cands.append((k, ai_name, u))
    chosen = None
    for k0, _, _ in cands:
        assign = {}
        consistent = True
        for kk, ai, u in cands:
            if abs(kk - k0) / max(abs(k0), 1e-6) < 0.02:
                if ai in assign and assign[ai] != u:
                    consistent = False
                    break
                assign[ai] = u
        if consistent and len(assign) == 3 and len(set(assign.values())) == 3:
            chosen = (k0, assign)
            break
    if not chosen:
        raise RuntimeError(
            "could not calibrate OBJ axes from origin=%s extent=%s" % (origin, extent))
    K, axes = chosen
    MAPPING = {}
    for ai_name, (span, centre) in PROBE_SRC.items():
        u = axes[ai_name]
        no_flip = abs(o[u] - K * centre)
        flip = abs(o[u] + K * centre)
        MAPPING[ai_name] = (u, -1.0 if flip < no_flip else 1.0)
    names = ("X", "Y", "Z")
    desc = ", ".join(
        "obj.%s->UE.%s%s" % (a, names[MAPPING[a][0]], "*" if MAPPING[a][1] < 0 else "")
        for a in ("x", "y", "z")
    )
    log("calibrated OBJ mapping: %s, unit scale K=%g" % (desc, K))
    return desc


# ----------------------------------------------------------- mesh import ----
def make_static_mesh(name, plan_verts, faces, uv_scale):
    """Import a StaticMesh via a temp OBJ written through the calibrated map.

    The temp OBJ already carries final UE centimetre coordinates, so the
    spawned actor needs no scaling. Stale assets from older runs are deleted
    first — their coordinates predate the calibration and cannot be trusted.
    """
    unreal.EditorAssetLibrary.make_directory(EXT_DEST)
    asset_path = EXT_DEST + "/" + name + "." + name
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)
    tmp = os.path.join(IMPORT_READY, name + ".src.obj")
    write_obj(tmp, name, plan_verts, faces, uv_scale)
    task = unreal.AssetImportTask()
    task.filename = tmp
    task.destination_path = EXT_DEST
    task.destination_name = name
    task.automated = True
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(asset_path)
    if not mesh:
        raise RuntimeError("OBJ import produced no mesh for " + name)
    return mesh


def enable_ground_collision(mesh, comp):
    """Make a ground surface block the player and the AI.

    Interchange OBJ imports arrive with no collision primitives. For terrain,
    per-triangle (complex) collision IS the right collision, so the mesh's
    body setup is switched to complex-as-simple; several API spellings are
    tried because the surface moved between engine builds.
    """
    comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    comp.set_collision_profile_name("BlockAll")
    attempts = []
    try:
        body = mesh.get_editor_property("body_setup")
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        attempts.append("body_setup: ok")
    except Exception as exc:
        attempts.append("body_setup: %s" % exc)
    try:
        mesh.set_editor_property("collision_complexity", unreal.CollisionComplexity.CTC_USE_COMPLEX_AS_SIMPLE)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        attempts.append("collision_complexity: ok")
    except Exception as exc:
        attempts.append("collision_complexity: %s" % exc)
    log("collision on %s: %s" % (mesh.get_name(), "; ".join(attempts)))


def spawn_static(subsystem, name, plan_verts, faces, material, label, uv_scale):
    mesh = make_static_mesh(name, plan_verts, faces, uv_scale)
    actor = subsystem.spawn_actor_from_object(mesh, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    if not actor:
        raise RuntimeError("could not spawn " + label)
    actor.set_actor_label(label)
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    if comp:
        if material:
            comp.set_material(0, material)
        comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        comp.set_editor_property("cast_shadow", False)
        enable_ground_collision(mesh, comp)
    return actor


# ------------------------------------------------------------- tree batches --
def make_ismc(root, socket, mesh, material):
    comp = unreal.InstancedStaticMeshComponent()
    comp.set_static_mesh(mesh)
    if material:
        comp.set_material(0, material)
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.setup_attachment(root.get_root_component(), socket)
    root.add_instance_component(comp)
    comp.register_component()
    return comp


def spawn_tree_batch(subsystem, label, placements, trunk_h, trunk_r, crown_r, crown_y,
                     bark_mat, leaf_mat, with_leaves):
    """One Actor per species/variant: trunk ISMC + crossed leaf-card ISMC.

    The trunk mesh is a 2 m tall, 0.5 m radius cylinder (axis on plan +y, so
    UE +Z after import); the leaf card is a flat 1 m quad. Instance scales
    convert those authored sizes to the species habit.
    """
    root = subsystem.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    if not root:
        raise RuntimeError("could not spawn tree batch " + label)
    root.set_actor_label(label)

    trunk = make_ismc(root, "Trunks", TRUNK_MESH, bark_mat)
    leaf = make_ismc(root, "Leaves", LEAF_MESH, leaf_mat) if with_leaves else None

    for t in placements:
        s = t["s"]
        yaw = math.degrees(t["rot"])
        # trunk: scale xz = R/0.5 = 2R, z = H/2 (mesh half-height is 1 m)
        trunk.add_instance(unreal.Transform(
            location=plan_to_ue(t["x"], t["y"] + trunk_h * s * 0.5, t["z"]),
            rotation=unreal.Rotator(0, yaw, 0),
            scale=unreal.Vector(2.0 * trunk_r * s, 2.0 * trunk_r * s, trunk_h * s * 0.5),
        ), False)
        if leaf:
            # two crossed cards per tree, offset half a turn
            for extra in (0.0, 90.0):
                leaf.add_instance(unreal.Transform(
                    location=plan_to_ue(t["x"], t["y"] + crown_y * s, t["z"]),
                    rotation=unreal.Rotator(0, yaw + extra + 37.0, 0),
                    scale=unreal.Vector(2.0 * crown_r * s, 2.0 * crown_r * s, 0.6),
                ), False)
    return root


# --------------------------------------------------------------------- main --
def main():
    global TRUNK_MESH, LEAF_MESH
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not subsystem:
        raise RuntimeError("no editor actor subsystem")

    # rerunnable: clear only this script's own actors
    for actor in list(subsystem.get_all_level_actors()):
        if actor.get_actor_label().startswith(PREFIX):
            subsystem.destroy_actor(actor)

    # 1. how does THIS editor map OBJ axes/units? everything else depends on it
    calibrate(subsystem)

    # 2. materials — textured sets tile at 1,1 because the UVs carry metres
    forest_diff = import_texture("SILID_ForestGround_D", "forrest_ground_01/forrest_ground_01_diff_1k.jpg")
    forest_nor = import_texture("SILID_ForestGround_N", "forrest_ground_01/forrest_ground_01_nor_gl_1k.jpg", normal=True)
    forest_rough = import_texture("SILID_ForestGround_R", "forrest_ground_01/forrest_ground_01_rough_1k.jpg", linear=True)
    terrain_mat = textured_material("M_SILID_ForestGround", [
        ("forest_diff", forest_diff, "RGB", unreal.MaterialProperty.MP_BASE_COLOR, -250),
        ("forest_nor", forest_nor, "RGB", unreal.MaterialProperty.MP_NORMAL, 0),
        ("forest_rough", forest_rough, "R", unreal.MaterialProperty.MP_ROUGHNESS, 250),
    ], 1.0, 1.0)

    asph_diff = import_texture("SILID_Asphalt_D", "asphalt_02/asphalt_02_diff_2k.jpg")
    asph_nor = import_texture("SILID_Asphalt_N", "asphalt_02/asphalt_02_nor_gl_2k.jpg", normal=True)
    asph_rough = import_texture("SILID_Asphalt_R", "asphalt_02/asphalt_02_rough_2k.jpg", linear=True)
    road_mat = textured_material("M_SILID_Asphalt", [
        ("asphalt_diff", asph_diff, "RGB", unreal.MaterialProperty.MP_BASE_COLOR, -250),
        ("asphalt_nor", asph_nor, "RGB", unreal.MaterialProperty.MP_NORMAL, 0),
        ("asphalt_rough", asph_rough, "R", unreal.MaterialProperty.MP_ROUGHNESS, 250),
    ], 1.0, 1.0)

    trail_mat = flat_material("M_SILID_TrailEarth", (0.55, 0.48, 0.36), rough=0.98)
    water_mat = flat_material("M_SILID_PondWater", (0.06, 0.11, 0.10), rough=0.12, metal=0.25)
    bark_mat = flat_material("M_SILID_TreeBark", (0.28, 0.23, 0.18), rough=0.95)
    leaf_mat = flat_material("M_SILID_LeafCard", (0.28, 0.36, 0.20), rough=0.9)
    snag_mat = flat_material("M_SILID_DeadWood", (0.38, 0.34, 0.28), rough=0.97)

    # 3. ground surfaces — uv_scale is metres per texture tile
    surfaces = (
        ("terrain.obj", "SM_SILID_Terrain", terrain_mat, PREFIX + "Terrain", 5.0),
        ("road.obj", "SM_SILID_Road", road_mat, PREFIX + "Road", 3.2),
        ("trail.obj", "SM_SILID_Trail", trail_mat, PREFIX + "Trail", 2.0),
        ("pond.obj", "SM_SILID_Pond", water_mat, PREFIX + "Pond", 1.0),
    )
    for obj_name, mesh_name, mat, label, uv_scale in surfaces:
        path = os.path.join(IMPORT_READY, obj_name)
        verts, faces = obj_tris(path)
        spawn_static(subsystem, mesh_name, verts, faces, mat, label, uv_scale)
        log("%s: %d verts / %d tris placed" % (mesh_name, len(verts), len(faces)))

    # 4. shared tree meshes
    trunk_obj = os.path.join(IMPORT_READY, "trunk.obj")
    if not os.path.isfile(trunk_obj):
        ring, half_h, radius = 10, 1.0, 0.5
        verts_t = [(math.cos((i / ring) * 2 * math.pi) * radius, -half_h, math.sin((i / ring) * 2 * math.pi) * radius) for i in range(ring)]
        verts_t += [(math.cos((i / ring) * 2 * math.pi) * radius, half_h, math.sin((i / ring) * 2 * math.pi) * radius) for i in range(ring)]
        faces_t = []
        for i in range(ring):
            j = (i + 1) % ring
            faces_t.append((i, j, ring + j))
            faces_t.append((i, ring + j, ring + i))
        faces_t.append(tuple(reversed(range(ring))))
        faces_t.append(tuple(ring + i for i in range(ring)))
        write_obj(trunk_obj, "SM_SILID_TreeTrunk", verts_t, faces_t, 1.0)
    TRUNK_MESH = make_static_mesh("SM_SILID_TreeTrunk", *obj_tris(trunk_obj), 1.0)

    leaf_obj = os.path.join(IMPORT_READY, "leaf.obj")
    if not os.path.isfile(leaf_obj):
        write_obj(leaf_obj, "SM_SILID_LeafCard",
                  [(-0.5, 0, -0.5), (0.5, 0, -0.5), (0.5, 0, 0.5), (-0.5, 0, 0.5)],
                  [(0, 1, 2), (0, 2, 3), (0, 2, 1), (0, 3, 2)], 1.0)
    LEAF_MESH = make_static_mesh("SM_SILID_LeafCard", *obj_tris(leaf_obj), 1.0)

    # 5. trees — the prototype's own placements, grouped per species/variant
    with open(os.path.join(IMPORT_READY, "trees.json"), "r", encoding="utf-8") as fh:
        tree_data = json.load(fh)
    by_arch = {}
    for t in tree_data["trees"]:
        by_arch.setdefault((t["species"], t["variant"]), []).append(t)

    # species habit (forest.js SPECIES): trunk height/radius, crown radius, crown height
    HABIT = {
        ("emergent", 0): (18.0, 0.40, 3.4, 14.0), ("emergent", 1): (18.0, 0.40, 3.4, 14.0),
        ("broad", 0): (13.5, 0.46, 4.2, 8.0),     ("broad", 1): (13.5, 0.46, 4.2, 8.0),
        ("slender", 0): (9.0, 0.20, 2.0, 6.5),    ("slender", 1): (9.0, 0.20, 2.0, 6.5),
        ("balete", 0): (12.5, 0.64, 5.0, 5.5),    ("balete", 1): (12.5, 0.64, 5.0, 5.5),
        ("snag", 0): (11.0, 0.34, 0.5, 9.0),      ("snag", 1): (11.0, 0.34, 0.5, 9.0),
    }
    total = 0
    for (species, variant), placements in sorted(by_arch.items()):
        trunk_h, trunk_r, crown_r, crown_y = HABIT[(species, variant)]
        spawn_tree_batch(subsystem, "%sTree %s %d" % (PREFIX, species, variant),
                         placements, trunk_h, trunk_r, crown_r, crown_y,
                         bark_mat, leaf_mat, with_leaves=(species != "snag"))
        total += len(placements)
        log("trees %s/%d: %d instances" % (species, variant, len(placements)))
    log("trees total: %d across %d archetypes" % (total, len(by_arch)))

    # 6. night lighting: a low moon, faint sky fill, cool ground fog
    moon = subsystem.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 9000), unreal.Rotator(-38, 210, 0))
    if moon:
        moon.set_actor_label(PREFIX + "Moonlight")
        light = moon.get_component_by_class(unreal.DirectionalLightComponent)
        light.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        light.set_editor_property("intensity", 1.0)
        light.set_editor_property("light_color", unreal.Color(r=140, g=160, b=205, a=255))

    sky = subsystem.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 7000), unreal.Rotator(0, 0, 0))
    if sky:
        sky.set_actor_label(PREFIX + "Night Sky Fill")
        comp = sky.get_component_by_class(unreal.SkyLightComponent)
        comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        comp.set_editor_property("intensity", 0.18)
        try:
            comp.recapture_sky()
        except Exception:
            pass

    fog = subsystem.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 3000), unreal.Rotator(0, 0, 0))
    if fog:
        fog.set_actor_label(PREFIX + "Night Fog")
        fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
        fc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        fc.set_editor_property("fog_density", 0.05)
        fc.set_editor_property("fog_height_falloff", 0.25)
        fc.set_editor_property("fog_max_opacity", 0.85)
        fc.set_editor_property("fog_inscattering_luminance", unreal.Color(r=32, g=40, b=58, a=255))

    # 7. save
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world:
        raise RuntimeError("no active world")
    saved = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_SAVE_PATH)
    if not saved:
        raise RuntimeError("could not save " + MAP_SAVE_PATH)
    log("exterior built, saved=%s" % saved)
    print("RESULT: PASS - SILID exterior: terrain/road/trail/pond, %d trees, night lighting. Saved=%s" % (total, saved))


try:
    main()
except Exception as exc:
    traceback.print_exc()
    print("RESULT: FAIL - %s" % exc)
    raise
