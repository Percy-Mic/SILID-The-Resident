"""Place the Act I opening car (ASILIDOpeningCar) at the roadside pull-off.

Run with:  python Scripts/RunEditorProbe.py <this file>

Replaces the placeholder cube-trunk car the exterior build spawned with the
real opening-sequence actor at the same surveyed spot — the pull-off the
prototype's terrain math and the opening state machine both use.
"""

import json
import os
import traceback

import unreal

ROOT = r"C:\Users\Admin\Downloads\SILID-main"
IMPORT_READY = os.path.join(ROOT, "ue5", "Saved", "ImportReady")
MAP_SAVE_PATH = "/Game/SILID/Maps/LM_SILID_GroundFloor"
PREFIX = "SILID - EXT - "
CAR_CLASS_PATH = "/Script/SILID.SILIDOpeningCar"
M = 100.0


def log(msg):
    unreal.log("[SILID opening] " + msg)
    print("[SILID opening] " + msg, flush=True)


def main():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not subsystem:
        raise RuntimeError("no editor actor subsystem")

    car_class = unreal.load_class(None, CAR_CLASS_PATH)
    if not car_class:
        raise RuntimeError("SILIDOpeningCar is not compiled — build SILIDEditor first.")

    # Remove the placeholder trunk-cube car and any prior opening actor.
    for actor in list(subsystem.get_all_level_actors()):
        label = actor.get_actor_label()
        if label.startswith(PREFIX + "Car ") and "trunk" in label:
            subsystem.destroy_actor(actor)
        elif label == PREFIX + "Car (Act I)":
            subsystem.destroy_actor(actor)

    with open(os.path.join(IMPORT_READY, "car.json"), "r", encoding="utf-8") as fh:
        car_data = json.load(fh)
    pull_x, pull_z = car_data["pullX"] * M, car_data["pullZ"] * M

    # Ground the car exactly where the terrain survey said the shoulder is.
    world = unreal.EditorLevelLibrary.get_editor_world()
    at = unreal.Vector(pull_x, pull_z, 3000.0)
    hit = unreal.SystemLibrary.line_trace_single(
        world, at, unreal.Vector(at.x, at.y, -3000.0),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
        unreal.DrawDebugTrace.FOR_ONE_FRAME, True,
        unreal.LinearColor(1, 0, 0, 1), unreal.LinearColor(0, 1, 0, 1), 5.0)
    ground_z = hit.to_tuple()[5].z if hit and hit.to_tuple() and hit.to_tuple()[0] else 0.0

    car = subsystem.spawn_actor_from_class(
        car_class, unreal.Vector(pull_x, pull_z, ground_z), unreal.Rotator(0, 90, 0))
    if not car:
        raise RuntimeError("SILIDOpeningCar spawn failed")
    car.set_actor_label(PREFIX + "Car (Act I)")

    # The opening car brings its own static body; the placeholder mesh asset
    # can stay in the content browser for later dressing work.
    saved = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_SAVE_PATH)
    if not saved:
        raise RuntimeError("could not save " + MAP_SAVE_PATH)
    log("opening car placed at (%.0f, %.0f, %.1f), saved=%s" % (pull_x, pull_z, ground_z, saved))
    print("RESULT: PASS - Act I opening car placed at the pull-off. Saved=%s" % saved)


try:
    main()
except Exception as exc:
    traceback.print_exc()
    print("RESULT: FAIL - %s" % exc)
    raise
