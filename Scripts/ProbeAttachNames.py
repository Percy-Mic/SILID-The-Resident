"""Probe: what attach-rule enums and attach methods does this build expose?"""
import unreal

lines = []
matches = [name for name in dir(unreal) if "ttach" in name]
lines.append("ATTACH NAMES: " + repr(matches))
for name in matches:
    thing = getattr(unreal, name)
    try:
        members = [m for m in dir(thing) if not m.startswith("_")]
        lines.append("%s members: %s" % (name, repr(members)))
    except Exception as exc:
        lines.append("%s: %s" % (name, exc))

out = r"C:\Users\Admin\Downloads\SILID-main\ue5\Saved\attach_names_report.txt"
with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print(lines[0], flush=True)
