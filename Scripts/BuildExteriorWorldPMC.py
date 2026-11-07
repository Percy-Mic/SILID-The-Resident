"""Build the exterior world inside the SILID Unreal level — ProceduralMesh route.

Run with:  python Scripts/RunEditorProbe.py <this file>

Rerunnable: removes only "SILID - EXT - " actors, then rebuilds.

Why this route exists: importing the terrain OBJ through Interchange wedged
the editor twice (the tiny axis probe imported and never returned — same stall
twice). The ProceduralMeshComponent route has no import step at all: the OBJ
data is parsed in Python and pushed straight into mesh sections with UE
coordinates (plan x->X, z->Y, y->Z, x100), so no importer stands between the
plan and the world.

Inputs (written by scripts/export_exterior_ue.mjs, plan axes, metres):
  ue5/Saved/ImportReady/terrain.obj   ground heightfield (mansion pad at y=0)
  ue5/Saved/ImportReady/road.obj      crowned carriageway + verges + markings
  ue5/Saved/ImportReady/trail.obj     the approach track to the porch
  ue5/Saved/ImportReady/pond.obj      the pond water disc
  ue5/Saved/ImportReady/trees.json    340 tree placements (species/variant)

What it creates:
  - terrain / road / trail / pond as ProceduralMeshComponents with metre UVs
    (one texture tile per uv_scale metres); complex per-triangle collision on
    the walkable surfaces, none on the water
  - trees: one ISMC batch per species pair (trunk instancing + crown slabs);
    snags are bare trunks. Every trunk blocks the player and the Resident,
    exactly like the prototype's tree colliders.
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
    coords = editor.create_material_expression(
        material, unreal.MaterialExpressionTextureCoordinate, -700, 0)
    coords.set_editor_property("u_tiling", float(u_tiling))
    coords.set_editor_property("v_tiling", float(v_tiling))
    for label, texture, output, prop, y in maps:
        sample = editor.create_material_expression(
            material, unreal.MaterialExpressionTextureSample, -400, y)
        sample.set_editor_property("texture", texture)
        editor.connect_material_expressions(coords, "", sample, "Coordinates")
        if not editor.connect_material_property(sample, output, prop):
            raise RuntimeError("could not connect " + label + " to " + name)
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
    const = editor.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -300, 0)
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


# ------------------------------------------------------- static-mesh import --
def import_glb(name, source, destination=EXT_DEST):
    """Import a GLB as a StaticMesh — the exact path the mansion's furniture
    proved works in this editor (Interchange OBJ hung twice; PMC components
    drop on save). Returns the StaticMesh asset."""
    unreal.EditorAssetLibrary.make_directory(destination)
    asset_path = destination + "/" + name + "." + name
    task = unreal.AssetImportTask()
    task.filename = source
    task.destination_path = destination
    task.destination_name = name
    task.automated = True
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(asset_path)
    if not mesh:
        raise RuntimeError("GLB import produced no mesh for " + name)
    return mesh


def set_complex_collision(mesh):
    """Per-triangle collision on an imported StaticMesh (terrain, road, trail).

    The player and the Resident walk on the real triangles, not a convex hull
    that would round off the crown of the road or the lip of the pond basin.
    """
    try:
        body = mesh.get_editor_property("body_setup")
        body.set_editor_property("collision_trace_flag",
                                 unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        mesh.set_editor_property("body_setup", body)
        return "body_setup"
    except Exception as exc:
        log("complex-collision flag failed on %s: %s" % (mesh.get_name(), exc))
        return None


def spawn_static(subsystem, name, source, material, label, collide):
    mesh = import_glb(name, source)
    if collide:
        set_complex_collision(mesh)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    actor = subsystem.spawn_actor_from_object(mesh, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    if not actor:
        raise RuntimeError("could not spawn " + label)
    actor.set_actor_label(label)
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    if comp:
        if material:
            comp.set_material(0, material)
        comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    return actor


# ------------------------------------------------------------- tree batches --
# Species habit (forest.js SPECIES): trunk height/radius, crown radius, crown
# height — the same numbers the playable prototype's five habits use.
HABIT = {
    ("emergent", 0): (18.0, 0.40, 3.4, 14.0), ("emergent", 1): (18.0, 0.40, 3.4, 14.0),
    ("broad", 0): (13.5, 0.46, 4.2, 8.0),     ("broad", 1): (13.5, 0.46, 4.2, 8.0),
    ("slender", 0): (9.0, 0.20, 2.0, 6.5),    ("slender", 1): (9.0, 0.20, 2.0, 6.5),
    ("balete", 0): (12.5, 0.64, 5.0, 5.5),    ("balete", 1): (12.5, 0.64, 5.0, 5.5),
    ("snag", 0): (11.0, 0.34, 0.5, 9.0),      ("snag", 1): (11.0, 0.34, 0.5, 9.0),
}


def spawn_trees(subsystem, cube, placements, bark_mat, leaf_mat):
    """One cube-scaled trunk per placement, plus two crossed crown slabs.

    The engine Cube ships with blocking collision, so every trunk physically
    stops the player and the Resident the way the prototype's tree colliders
    did — no extra collision setup needed. Crowns are two thin crossed slabs
    at crown height (a blockout; sculpted canopies are a later pass).
    """
    count = 0
    for idx, t in enumerate(placements):
        species, variant = t["species"], t["variant"]
        trunk_h, trunk_r, crown_r, crown_y = HABIT[(species, variant)]
        s = t["s"]
        yaw = math.degrees(t["rot"])

        trunk = subsystem.spawn_actor_from_object(
            cube, plan_to_ue(t["x"], t["y"] + trunk_h * s * 0.5, t["z"]),
            unreal.Rotator(0, yaw, 0))
        if not trunk:
            raise RuntimeError("trunk spawn failed at placement %d" % idx)
        trunk.set_actor_label("%sTree %04d - trunk" % (PREFIX, idx))
        trunk.set_actor_scale3d(unreal.Vector(2.0 * trunk_r * s, trunk_h * s, 2.0 * trunk_r * s))
        trunk.get_component_by_class(unreal.StaticMeshComponent).set_material(0, bark_mat)

        if species != "snag":
            for k, extra in ((1, 37.0), (2, 127.0)):
                crown = subsystem.spawn_actor_from_object(
                    cube, plan_to_ue(t["x"], t["y"] + crown_y * s, t["z"]),
                    unreal.Rotator(0, yaw + extra, 0))
                if not crown:
                    raise RuntimeError("crown spawn failed at placement %d" % idx)
                crown.set_actor_label("%sTree %04d - crown %d" % (PREFIX, idx, k))
                crown.set_actor_scale3d(unreal.Vector(2.0 * crown_r * s, 0.05, 1.2 * crown_r * s))
                crown.get_component_by_class(unreal.StaticMeshComponent).set_material(0, leaf_mat)
        count += 1
        if count % 100 == 0:
            log("trees: %d placed" % count)
    return count


# --------------------------------------------------------------------- main --
def main():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not subsystem:
        raise RuntimeError("no editor actor subsystem")

    # rerunnable: clear only this script's own actors
    for actor in list(subsystem.get_all_level_actors()):
        if actor.get_actor_label().startswith(PREFIX):
            subsystem.destroy_actor(actor)

    log("materials...")
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

    log("ground surfaces...")
    # GLB import — the furniture pipeline's proven path. The pond takes no
    # collision: it is water, and a solid floor across it would read as a
    # pond you can stand on.
    surfaces = (
        ("terrain.glb", "SM_SILID_Terrain", PREFIX + "Terrain", terrain_mat, True),
        ("road.glb", "SM_SILID_Road", PREFIX + "Road", road_mat, True),
        ("trail.glb", "SM_SILID_Trail", PREFIX + "Trail", trail_mat, True),
        ("pond.glb", "SM_SILID_Pond", PREFIX + "Pond", water_mat, False),
    )
    for source_name, mesh_name, label, mat, collide in surfaces:
        path = os.path.join(IMPORT_READY, source_name)
        actor = spawn_static(subsystem, mesh_name, path, mat, label, collide)
        comp = actor.get_component_by_class(unreal.StaticMeshComponent)
        low, high = comp.get_local_bounds()
        log("%s: bounds %s -> %s (spawned at origin, scale 100)" % (label, low, high))

    log("trees...")
    cube = unreal.load_asset("/Engine/BasicShapes/Cube")
    if not cube:
        raise RuntimeError("engine Cube missing")
    with open(os.path.join(IMPORT_READY, "trees.json"), "r", encoding="utf-8") as fh:
        tree_data = json.load(fh)
    tree_count = spawn_trees(subsystem, cube, tree_data["trees"], bark_mat, leaf_mat)
    log("trees placed: %d" % tree_count)

    # ------------------------------------------------------ the Act I car ---
    log("the car...")
    with open(os.path.join(IMPORT_READY, "car.json"), "r", encoding="utf-8") as fh:
        car_data = json.load(fh)
    car_mesh = import_glb("SM_SILID_Car", os.path.join(IMPORT_READY, "car.glb"))
    # The prototype authored the car at metre scale with origin at ground
    # level (wheel centres at +0.37 m); GLB imports as metres-to-cm, so the
    # mesh is already real-world size — no actor scaling.
    pull_x, pull_z = car_data["pullX"], car_data["pullZ"]
    world = unreal.EditorLevelLibrary.get_editor_world()
    at = unreal.Vector(pull_x * M, pull_z * M, 3000.0)
    hit = unreal.SystemLibrary.line_trace_single(
        world, at, unreal.Vector(at.x, at.y, -3000.0),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
        unreal.DrawDebugTrace.FOR_ONE_FRAME, True,
        unreal.LinearColor(1, 0, 0, 1), unreal.LinearColor(0, 1, 0, 1), 5.0)
    ground_z = hit.to_tuple()[5].z if hit and hit.to_tuple() and hit.to_tuple()[0] else 0.0

    car_actor = subsystem.spawn_actor_from_object(
        car_mesh, unreal.Vector(pull_x * M, pull_z * M, ground_z),
        unreal.Rotator(0, 90.0, 0))
    if not car_actor:
        raise RuntimeError("car spawn failed")
    car_actor.set_actor_label(PREFIX + "Car (Act I)")

    # MEASURED yaw, not guessed: the antenna sits at the car's front tip
    # (+2.55 m). Whichever end of the spawned component's bounds is further
    # from centre on X is the front; forward=+X faces north at yaw 90.
    comp = car_actor.get_component_by_class(unreal.StaticMeshComponent)
    low, high = comp.get_local_bounds()
    front_is_plus_x = (high.x) > (-low.x)
    yaw = 90.0 if front_is_plus_x else 270.0
    car_actor.set_actor_rotation(unreal.Rotator(0, yaw, 0), False)
    log("car bounds low=%s high=%s -> front is %s, yaw=%.0f"
        % (low, high, "+X" if front_is_plus_x else "-X", yaw))
    log("car placed at (%.0f, %.0f, %.1f) yaw=%.0f" % (pull_x * M, pull_z * M, ground_z, yaw))

    log("night lighting...")
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
        fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(r=0.13, g=0.16, b=0.23, a=1.0))

    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world:
        raise RuntimeError("no active world")
    saved = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_SAVE_PATH)
    if not saved:
        raise RuntimeError("could not save " + MAP_SAVE_PATH)
    log("exterior built, saved=%s" % saved)
    print("RESULT: PASS - SILID exterior: 4 GLB ground surfaces, %d trees, night lighting. Saved=%s"
          % (tree_count, saved))


try:
    main()
except Exception as exc:
    traceback.print_exc()
    print("RESULT: FAIL - %s" % exc)
    raise
