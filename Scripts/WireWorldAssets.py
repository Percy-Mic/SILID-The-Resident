"""Wire imported Poly Haven assets and audio into the SILID world.
Run inside a live editor via RunEditorProbe.py (remote execution).

What it does (idempotent — safe to re-run):
 1. Assigns real PH_* furniture to the furniture-slot StaticMesh actors the
    build scripts left as placeholder-box tagged 'PHSlot_<Name>' in
    LM_SILID_GroundFloor, if such slots exist.
 2. Creates/updates the ASILIDAudioDirector actor with the imported SN_* sound
    waves: night ambience loop, tension drone, and stinger pool.
 3. Saves the level.
Writes Saved/world_wiring_report.txt with a RESULT line.
"""
import unreal

# Skip the revision-control checkout dialog entirely.
unreal.SystemLibrary.execute_console_command(None,
    "r.Editor.SkipSourceControlCheckForEditablePackages 1")

LEVEL = "/Game/SILID/Maps/LM_SILID_GroundFloor"
REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\world_wiring_report.txt"
lines = []

def log(m):
    unreal.log("[wire] " + m)
    lines.append(m)

# ---- 1. audio director -----------------------------------------------------
AUDIO = "/Game/SILID/Audio"
def sn(name):
    a = unreal.load_asset("%s/SN_%s" % (AUDIO, name))
    return a

ambient = sn("Country_Night_Front_MB_01") or sn("Country_Night_Front_MB_01")
tension = sn("amb_JD_drone_pulsing_darkness")
stingers = [s for s in [sn("Sinematic_-_Stingers_11")] if s]

director = None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_class().get_name() == "SILIDAudioDirector":
        director = a
        break
if not director:
    cls = unreal.load_class(None, "/Script/SILID.SILIDAudioDirector")
    if not cls:
        log("RESULT: FAIL no SILIDAudioDirector class (module not loaded?)")
    else:
        director = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, unreal.Vector(0, 0, 100))
        director.set_actor_label("SILID Audio Director")
        log("spawned audio director")

if director:
    if ambient:
        try:
            director.set_editor_property("ambient_loop", ambient)
            log("ambient loop = %s (%.1fs)" % (ambient.get_name(), ambient.get_editor_property("duration")))
        except Exception as exc:
            log("WARN ambient bind failed: %s" % exc)
    else:
        log("WARN: night ambience sound not found")
    if tension:
        try:
            director.set_editor_property("tension_loop", tension)
            log("tension loop = %s" % tension.get_name())
        except Exception as exc:
            log("WARN tension bind failed: %s" % exc)
    if stingers:
        try:
            director.set_editor_property("stingers", stingers)
            log("stinger pool = %d" % len(stingers))
        except Exception as exc:
            log("WARN stingers bind failed: %s" % exc)
    unreal.EditorAssetLibrary.save_directory("/Game/SILID")

# ---- 2. furniture slot assignment ------------------------------------------
found_slots = 0
placed = 0
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    label = a.get_actor_label()
    if label.startswith("PHSlot_"):
        found_slots += 1
        want = label.replace("PHSlot_", "PH_")
        mesh = unreal.load_asset("/Game/SILID/Furniture/PolyHaven/" + want)
        if mesh:
            comp = a.get_editor_property("StaticMeshComponent") or a.get_component_by_class(unreal.StaticMeshComponent)
            if comp:
                comp.set_static_mesh(mesh)
                placed += 1
log("furniture slots: %d found, %d filled" % (found_slots, placed))

# ---- 2b. replace any placed quarantine dummy meshes -------------------------
DUMMIES = {"SM_SILID_bed": "PH_GothicBed_01", "SM_SILID_armchair": "PH_ArmChair_01",
           "SM_SILID_sofa": "PH_Sofa_01", "SM_SILID_table": "PH_WoodenTable_01",
           "SM_SILID_chair": "PH_WoodenChair_01", "SM_SILID_bookshelf": "PH_wooden_bookshelf_worn",
           "SM_SILID_nightstand": "PH_ClassicNightstand_01", "SM_SILID_round_table": "PH_round_wooden_table_01",
           "SM_SILID_vase": "PH_ceramic_vase_01", "SM_SILID_wall_clock": "PH_wall_clock",
           "SM_SILID_oil_lamp": "PH_vintage_oil_lamp", "SM_SILID_plant": "PH_potted_plant_01",
           "SM_SILID_tea_set": "PH_tea_set_01", "SM_SILID_door": None,
           "SM_SILID_alarm_clock": "PH_mantel_clock_01", "SM_SILID_kettle": "PH_vintage_electric_kettle"}
replaced = 0
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    comp = a.get_component_by_class(unreal.StaticMeshComponent) if a else None
    if not comp:
        continue
    m = comp.get_static_mesh()
    if not m:
        continue
    mn = m.get_name()
    if mn in DUMMIES:
        repl = DUMMIES[mn]
        if repl:
            new = unreal.load_asset("/Game/SILID/Furniture/PolyHaven/" + repl)
            if new:
                comp.set_static_mesh(new)
                replaced += 1
                log("replaced %s -> %s on %s" % (mn, repl, a.get_actor_label()))
log("dummy replacements: %d" % replaced)

# ---- 3. save ----------------------------------------------------------------
unreal.EditorLevelLibrary.save_current_level()
ok = (ambient is not None) and (director is not None)
log("RESULT: %s placed=%d slots=%d" % ("PASS" if ok else "PARTIAL", placed, found_slots))
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
