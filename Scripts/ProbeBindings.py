"""One-shot binding inventory: what can this editor's Python actually do?

After three blind fixes (add_instance_component, register_component,
add_component_by_class — each 'no attribute'), stop guessing and dump the
real surface. Prints every method whose name contains the keywords we need:
component ownership, attachment, procedural mesh creation, instancing.
"""

import unreal

lines = []


def dump(obj, label, keywords):
    names = [n for n in dir(obj) if any(k in n.lower() for k in keywords)]
    lines.append("%s: %s" % (label, ", ".join(sorted(names)) or "(none)"))


actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
    unreal.Actor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
if actor:
    dump(actor, "Actor", ("component", "attach", "root"))
    # try every plausible component-creation route and record which exists
    routes = [
        ("new_object(comp, actor)", lambda: unreal.new_object(unreal.ProceduralMeshComponent, actor)),
        ("new_object(comp)", lambda: unreal.new_object(unreal.ProceduralMeshComponent)),
        ("comp(actor)", lambda: unreal.ProceduralMeshComponent(actor)),
        ("comp()", lambda: unreal.ProceduralMeshComponent()),
    ]
    for label, fn in routes:
        try:
            comp = fn()
            if comp:
                lines.append("ROUTE OK: %s -> %s" % (label, comp.get_class().get_name()))
                dump(comp, "PMC", ("register", "attach", "create_mesh", "section", "collision"))
                break
        except Exception as exc:
            lines.append("route %s failed: %s" % (label, exc))

    try:
        ismc = unreal.new_object(unreal.InstancedStaticMeshComponent, actor)
        lines.append("ROUTE OK: new_object(ISMC, actor) -> ok")
        dump(ismc, "ISMC", ("register", "attach", "add_instance", "instance"))
    except Exception as exc:
        lines.append("ISMC new_object failed: %s" % exc)

    actor.destroy_actor()
else:
    lines.append("could not spawn probe actor")

lines.append("RESULT: PASS - binding inventory dumped")
out = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\binding_report.txt"
with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines), flush=True)
