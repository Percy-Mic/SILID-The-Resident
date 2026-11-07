"""Probe: state of the SILID - EXT - Terrain actor and its PMC component."""
import unreal

REPORT = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\pmc_state_report.txt"
lines = []

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
terrain = None
for actor in subsystem.get_all_level_actors():
    if actor.get_actor_label() == "SILID - EXT - Terrain":
        terrain = actor
        break

if not terrain:
    lines.append("NO Terrain actor found")
else:
    procs = terrain.get_components_by_class(unreal.ProceduralMeshComponent)
    lines.append("actor: %s" % terrain.get_actor_label())
    lines.append("PMC components found: %d" % len(procs))
    for comp in procs:
        lines.append("PMC[%d] registered=%s" % (i, comp.is_registered()))
        for prop in ("use_complex_as_simple_collision", "b_use_complex_as_simple_collision"):
            try:
                lines.append("  %s = %s" % (prop, comp.get_editor_property(prop)))
            except Exception:
                lines.append("  %s = (unreadable)" % prop)
        try:
            body = comp.get_editor_property("body_instance")
            lines.append("  collision_enabled = %s" % body.get_editor_property("collision_enabled"))
        except Exception as exc:
            lines.append("  body_instance unreadable: %s" % exc)
        try:
            lines.append("  local_bounds = %s" % comp.get_local_bounds())
        except Exception as exc:
            lines.append("  bounds unreadable: %s" % exc)
        try:
            lines.append("  component_location = %s" % comp.get_editor_property("relative_location"))
        except Exception:
            pass

lines.append("RESULT: DONE")
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines), flush=True)
