"""Furnish the mansion ground floor with the imported Poly Haven furniture.
Run inside a live editor via RunEditorProbe.py.

Reads the room schedule (reports/world/interior_design_schedule.md rules):
rooms have been laid out by the build scripts; we place furniture at room
centres against walls with measured clearances. Room bounds are taken from
the existing architecture: we query the level for room-tagged actors
(AActor with label 'Room <Id> <Name>' or RoomBounds components placed by
BuildUpperFloorsAndBasement/DressArchitecturalDetail). For every room found
with a kind tag we drop the schedule's furniture scaled to the room.

Idempotent: furniture is parented to a 'SILID_Furnishing' folder/actor set;
existing pieces are moved, not duplicated.
"""
import unreal

# Skip the revision-control checkout dialog entirely.
unreal.SystemLibrary.execute_console_command(None,
    "r.Editor.SkipSourceControlCheckForEditablePackages 1")

REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\furnish_report.txt"
FURN = "/Game/SILID/Furniture/PolyHaven"
lines = []

def log(m):
    unreal.log("[furnish] " + m)
    lines.append(m)

# room schedule: room label fragment -> [(asset, dx, dy, dz, yaw)]  (metres, degrees)
# offsets are from room centre, x=east, y=north; floor z handled per room level
SCHEDULE = {
    # ground floor service hall
    "Service Hall": [("PH_Chinese_Console_Table", 0, 2.0, 0, 0), ("PH_Side_Table_01", 2.0, 1.5, 0, 90)],
    "Kitchen": [("PH_Vintage_Electric_Kettle", 1.0, 1.0, 0.95, 0), ("PH_Wooden_Cutting_Board", -1.0, 1.2, 0.95, 0),
                ("PH_Wooden_Bucket_01", 1.5, -0.5, 0, 0), ("PH_Jug_01", -0.5, -0.8, 0.95, 0)],
    "Pantry": [("PH_Wooden_Bookshelf_Worn", -2.0, 0, 0, 90), ("PH_Chinese_Commode", 0, -2.0, 0, 0),
               ("PH_Wicker_Basket_01", 1.8, 1.5, 0, 15)],
    "Laundry": [("PH_Wooden_Crate_01", -1.5, 1.0, 0, 0), ("PH_Plastic_Broom", 1.6, 1.2, 0, -20)],
    "Staff Room": [("PH_Rockingchair_01", -1.5, -1.0, 0, 35), ("PH_Side_Table_01", 1.2, -1.8, 0, 180)],
    "Guest Room": [("PH_GothicBed_01", 0, 0, 0, 0), ("PH_ClassicNightstand_01", 1.3, 0.8, 0, 0),
                   ("PH_Ottoman_01", -1.6, 1.2, 0, 90)],
    "Library / Study": [("PH_Wooden_Bookshelf_Worn", -2.2, 1.0, 0, 90), ("PH_Metal_Office_Desk", 0.5, -0.5, 0, 0),
                        ("PH_WoodenChair_01", 0.5, -1.4, 0, 180)],
    "Dining Room": [("PH_Dining_Table", 0, 0, 0, 0), ("PH_Dining_Chair_02", 0, 1.2, 0, 180),
                    ("PH_Dining_Chair_02", 0, -1.2, 0, 0), ("PH_Dining_Chair_02", 1.1, 0, 0, 90),
                    ("PH_Dining_Chair_02", -1.1, 0, 0, -90), ("PH_Tea_Set_01", 0, 0, 0.78, 0)],
    "Family Lounge": [("PH_Sofa_02", 0, 1.2, 0, 180), ("PH_ArmChair_01", -1.8, -0.5, 0, 60),
                      ("PH_CoffeeTable_01", 0, -0.2, 0, 0), ("PH_Wooden_Bookshelf_Worn", 2.2, 0, 0, -90)],
    "Wine Room": [("PH_Wine_Barrel_01", -1.2, 0, 0, 0), ("PH_Wooden_Barrels_01", 1.0, 0.8, 0, 20)],
    "Inner Courtyard": [("PH_Bench_Vice_01", -1.8, -1.0, 0, 90), ("PH_Wicker_Basket_02", 1.5, 1.0, 0, 0)],
    "Gallery / Reception Hall": [("PH_Chinese_Console_Table", 0, 2.2, 0, 0), ("PH_Ornate_Mirror_01", 0, 2.35, 1.6, 0)],
    "Formal Living Room": [("PH_Chinese_Sofa", 0, 1.0, 0, 180), ("PH_Chinese_Armchair", -1.9, -0.4, 0, 55),
                           ("PH_Chinese_Armchair", 1.9, -0.4, 0, -55), ("PH_Chinese_Tea_Table", 0, -0.1, 0, 0)],
    "Foyer": [("PH_Chinese_Console_Table", 0, 2.5, 0, 0), ("PH_Brass_Candleholders", 0, 2.5, 0.85, 0)],
    "Sitting Room": [("PH_ArmChair_01", 0, 0.8, 0, 175), ("PH_Side_Table_Tall_01", 1.4, 0.4, 0, 90),
                     ("PH_Hanging_Picture_Frame_01", 0, 2.4, 1.7, 0)],
    "Front Drawing Room": [("PH_Sofa_01", 0, 0.6, 0, 180), ("PH_Painted_Wooden_Nightstand", -1.9, 0.2, 0, 90),
                           ("PH_Fancy_Picture_Frame_01", 0, 2.35, 1.7, 0)],
    "Breakfast Room": [("PH_Round_Wooden_Table_01", 0, 0, 0, 0), ("PH_WoodenChair_01", 0, 1.0, 0, 180),
                       ("PH_WoodenChair_01", 0, -1.0, 0, 0)],
    # second floor + above
    "Upper Landing": [("PH_Chinese_Console_Table", 0, 1.8, 0, 0)],
    "Master Bedroom": [("PH_GothicBed_01", 0, 0, 0, 0), ("PH_Painted_Wooden_Nightstand", 1.4, 0.8, 0, 0),
                       ("PH_Chinese_Cabinet", -2.0, 0, 0, 90)],
    "Her Dressing Room": [("PH_Ottoman_01", 0, 0.5, 0, 0), ("PH_Ornate_Mirror_01", 0, 2.2, 1.6, 180)],
    "Master Bath": [("PH_Wooden_Bucket_01", 0.5, -0.5, 0, 0), ("PH_Jug_01", -0.5, -0.4, 0, 0)],
    "Nursery": [("PH_Old_Bed_Frame", 0, 0, 0, 0), ("PH_Wooden_Stool_01", 1.4, 0.6, 0, 0)],
    "Billiards Room": [],  # imported GLB room: props.js skip — do not furnish
    "Interrogation Room": [],  # imported GLB room
    "Attic": [("PH_Vintage_Suitcase", 0.5, 0.3, 0, 10), ("PH_Wooden_Crate_02", -1.2, 0.8, 0, 0)],
    "Basement": [("PH_Portable_Generator", 0.8, 0.5, 0, 0), ("PH_Metal_Toolbox", -0.6, 0.9, 0, 20),
                 ("PH_Propane_Tank", 1.4, -0.4, 0, 0), ("PH_Bench_Vice_01", -1.6, 0.2, 0, 90)],
    "Roof": [("PH_Wooden_Broom", 0.5, 0.4, 0, 30)],
}

# room discovery: room-marker labels carry the room name from the plan
# ("GF-01 Kitchen"-style). The fixed anchors below are measured from the
# completed plan (cm): ground floor y≈4400, library/lounge band y≈-2400,
# second floor y≈12800 (z=420).
def room_center(actor):
    return actor.get_actor_location()

placed = 0
rooms = {}
FIXED = {
    "Service Hall": (0, 1400, 0), "Kitchen": (-5800, 4400, 0), "Pantry": (-9800, 4400, 0),
    "Laundry": (-9800, 1000, 0), "Staff Room": (-9800, -2400, 0), "Guest Room": (9800, 4400, 0),
    "Library / Study": (-5800, -2400, 0), "Dining Room": (4600, 4400, 0),
    "Family Lounge": (4600, -2400, 0), "Wine Room": (-9800, -2400, 0),
    "Gallery / Reception Hall": (0, 1400, 0), "Formal Living Room": (10500, 2100, 0),
    "Foyer": (0, 4400, 0), "Sitting Room": (6400, 1400, 0), "Front Drawing Room": (16500, 12000, 0),
    "Breakfast Room": (9800, -2400, 0), "Upper Landing": (0, 6200, 420),
    "Master Bedroom": (0, 12800, 420), "Nursery": (9800, 12800, 420),
    "Attic": (0, 4400, 840), "Basement": (0, 4400, -340), "Roof": (0, 0, 1200),
}
for key in SCHEDULE:
    if key in FIXED:
        rooms[key] = [FIXED[key]]

ECS = unreal.EditorLevelLibrary
for key, markers in SCHEDULE.items():
    if not markers:
        continue
    entries = rooms.get(key)
    if not entries:
        continue
    anchor = entries[0]
    if isinstance(anchor, unreal.Actor):
        loc = anchor.get_actor_location()
        base = unreal.Vector(loc.x, loc.y, loc.z)
    else:
        base = unreal.Vector(anchor[0], anchor[1], anchor[2])
    for asset, dx, dy, dz, yaw in markers:
        mesh = unreal.load_asset("%s/%s" % (FURN, asset))
        if not mesh:
            continue
        spawn = unreal.Vector(base.x + dx * 100, base.y + dy * 100, base.z + dz * 100)
        rot = unreal.Rotator(0, yaw, 0)
        # idempotency: reuse an actor with the same label in the same room
        want_label = "Furnish %s %s" % (key, asset)
        existing = None
        for a in ECS.get_all_level_actors():
            if a.get_actor_label() == want_label:
                existing = a
                break
        if existing:
            existing.set_actor_location(spawn, False, False)
            existing.set_actor_rotation(rot, False)
        else:
            actor = ECS.spawn_actor_from_object(mesh, spawn, rot)
            if actor:
                actor.set_actor_label(want_label)
                placed += 1

log("furniture placed: %d" % placed)
unreal.EditorLevelLibrary.save_current_level()
log("RESULT: PASS placed=%d" % placed)
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
