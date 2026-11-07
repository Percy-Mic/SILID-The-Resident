"""Import the downloaded Sonniss WAV files as SoundWave assets.
Run via RunEditorProbe.py (remote execution in a live editor).
Destination: /Game/SILID/Audio/
Large ambience files (>8 MB) are imported without compression-flag changes;
UE 5.4 defaults handle 44.1k/48k 16-bit PCM fine for 2D ambience.
Writes Saved/audio_import_report.txt with a RESULT line.
"""
import unreal, os, glob

ROOT = r"C:\Users\Admin\Downloads\SILID-main"
SRC = os.path.join(ROOT, "ue5", "Content", "Raw", "Audio")
DEST = "/Game/SILID/Audio"
REPORT = os.path.join(ROOT, "ue5", "Saved", "audio_import_report.txt")

lines = []
def log(m):
    unreal.log("[audio import] " + m)
    lines.append(m)

unreal.EditorAssetLibrary.make_directory(DEST)
wavs = sorted(glob.glob(os.path.join(SRC, "*.wav")))
log("found %d wav files" % len(wavs))

# friendly asset names: RoomType_Description -> SN_<name>
tasks = []
for path in wavs:
    base = os.path.splitext(os.path.basename(path))[0]
    if base.endswith(".M"):
        base = base[:-2]  # Sonniss '.M' mono marker: not a valid asset suffix
    name = "SN_" + base.replace(" ", "_").replace(":", "_").replace(".", "_").replace("__", "_")[:64]
    if unreal.EditorAssetLibrary.does_asset_exist(DEST + "/" + name):
        log("skip existing " + name)
        continue
    t = unreal.AssetImportTask()
    t.filename = path
    t.destination_path = DEST
    t.destination_name = name
    t.automated = True
    t.save = True
    tasks.append(t)

if tasks:
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    log("imported %d" % len(tasks))

# the '.M' import lands as <name>.M — if the bare name is missing, adopt it
for path in wavs:
    base = os.path.splitext(os.path.basename(path))[0]
    if base.endswith(".M"):
        base = base[:-2]
        bare = "SN_" + base.replace(" ", "_").replace(":", "_").replace(".", "_").replace("__", "_")[:64]
        if not unreal.EditorAssetLibrary.does_asset_exist(DEST + "/" + bare):
            dotted = bare + ".M"
            if unreal.EditorAssetLibrary.does_asset_exist(DEST + "/" + dotted):
                unreal.EditorAssetLibrary.rename_asset(DEST + "/" + dotted, DEST + "/" + bare)
                log("adopted %s <- %s" % (bare, dotted))

ok = fail = 0
for path in wavs:
    base = os.path.splitext(os.path.basename(path))[0]
    if base.endswith(".M"):
        base = base[:-2]
    name = "SN_" + base.replace(" ", "_").replace(":", "_").replace(".", "_").replace("__", "_")[:64]
    asset = unreal.load_asset(DEST + "/" + name)
    if asset:
        ok += 1
        log("OK %s dur=%.1fs" % (name, asset.get_editor_property("duration")))
    else:
        fail += 1
        log("MISSING " + name)

log("RESULT: %s ok=%d fail=%d" % ("PASS" if fail == 0 else "FAIL", ok, fail))
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
