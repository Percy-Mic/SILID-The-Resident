"""Download Poly Haven CC0 furniture GLTF bundles for SILID.
Run with PowerShell:  powershell -File Scripts/DownloadPolyHavenModels.ps1
Downloads the 2k gltf bundle (gltf + bin + textures) per asset into
ue5/Content/Raw/Models/<asset>/, then the list is imported via the editor
Python import script (the proven glb/Interchange path).
Poly Haven license: CC0 1.0 (public domain). Source: https://polyhaven.com
"""
$ErrorActionPreference = "Continue"
$dest_root = "c:\Users\Admin\Downloads\SILID-main\ue5\Content\Raw\Models"
New-Item -ItemType Directory -Force -Path $dest_root | Out-Null

# Filipino-ancestral-house appropriate set: aged wood, rattan/wicker, capiz-era
$assets = @(
    "ArmChair_01",            # victorian carved wood armchair - sala
    "chinese_armchair",       # hardwood chair seen in ancestral homes
    "chinese_cabinet",        # aparador-like hardwood cabinet
    "chinese_commode",
    "chinese_console_table",
    "chinese_sofa",
    "chinese_tea_table",
    "CoffeeTable_01",
    "dining_table",
    "dining_chair_02",
    "gallinera_chair",        # classic Filipino gallinera
    "gallinera_table",
    "GothicBed_01",           # old carved bed
    "ClassicNightstand_01",
    "wooden_bookshelf_worn",
    "Shelf_01",
    "side_table_01",
    "side_table_tall_01",
    "Sofa_01",
    "sofa_02",
    "vintage_day_bed",
    "Rockingchair_01",        # ancestral-house rocking chair
    "WoodenChair_01",
    "WoodenTable_01",
    "WoodenTable_02",
    "WoodenTable_03",
    "round_wooden_table_01",
    "small_wooden_table_01",
    "wooden_stool_01",
    "painted_wooden_nightstand",
    "vintage_oil_lamp",
    "Chandelier_01",
    "wall_clock",
    "vintage_grandfather_clock_01",
    "Television_01",          # old CRT-era television
    "television_02",
    "vintage_radio_transceiver",
    "cassette_player",
    "boombox",
    "tea_set_01",
    "brass_candleholders",
    "ceramic_vase_01",
    "brass_vase_01",
    "wicker_basket_01",
    "wicker_basket_02",
    "antique_ceramic_vase_01",
    "mantel_clock_01",
    "ornate_mirror_01",
    "fancy_picture_frame_01",
    "fancy_picture_frame_02",
    "standing_picture_frame_01",
    "hanging_picture_frame_01",
    "hanging_picture_frame_02",
    "potted_plant_01",
    "potted_plant_02",
    "fern_02",
    "sungka_board",           # Filipino sungka mancala board
    "sungka_board_02",
    "wooden_lantern_01",
    "Lantern_01",
    "old_bed_frame",
    "Ottoman_01",
    "vintage_telephone_wall_clock",
    "wooden_cutting_board",
    "jug_01",
    "pot_enamel_01",
    "wooden_bucket_01",
    "wine_barrel_01",
    "wooden_barrels_01",
    "vintage_electric_kettle",
    "vintage_microwave",
    "metal_office_desk",
    "wooden_crate_01",
    "wooden_crate_02",
    "old_military_crate",
    "vintage_suitcase",
    "metal_jerrycan",
    "propane_tank",
    "signal_flashlight",
    "vintage_flashlight",
    "lightbulb_01",
    "security_camera_01",
    "bench_vice_01",
    "metal_toolbox",
    "cross_pein_hammer",
    "flathead_screwdriver",
    "handsaw_wood",
    "portable_generator",
    "power_box_01",
    "rusted_spade_01",
    "old_tyre",
    "wooden_broom",
    "plastic_broom",
    "dead_tree_trunk",
    "dead_quiver_branch_01",
    "rock_07",
    "moss_01",
    "fern_02"
)

$api = "https://api.polyhaven.com/files"
$dl  = "https://dl.polyhaven.org"

foreach ($a in $assets) {
    $outdir = Join-Path $dest_root $a
    if (Test-Path (Join-Path $outdir "downloaded.flag")) { Write-Output "skip $a"; continue }
    try {
        $resp = Invoke-WebRequest -Uri "$api/$a" -UseBasicParsing -TimeoutSec 60
        $j = $resp.Content | ConvertFrom-Json
    } catch { Write-Output "META-FAIL $a"; continue }

    # pick 2k gltf, fallback 1k
    $g = $null
    foreach ($res in @("2k","1k")) {
        $node = $j.gltf.PSObject.Properties[$res]
        if ($node) { $g = $node.Value; break }
    }
    if (-not $g) { Write-Output "NO-GLTF $a"; continue }

    New-Item -ItemType Directory -Force -Path $outdir | Out-Null
    $main = Join-Path $outdir (([uri]::UnescapeDataString(($g.gltf.url -split "/")[-1])))
    try {
        Invoke-WebRequest -Uri $g.gltf.url -OutFile $main -UseBasicParsing -TimeoutSec 300
    } catch { Write-Output "DL-FAIL $a"; continue }

    foreach ($inc in $g.gltf.include.PSObject.Properties) {
        $rel = $inc.Name -replace "/", "\"
        $target = Join-Path $outdir $rel
        $tdir = Split-Path $target -Parent
        if (-not (Test-Path $tdir)) { New-Item -ItemType Directory -Force -Path $tdir | Out-Null }
        try { Invoke-WebRequest -Uri $inc.Value.url -OutFile $target -UseBasicParsing -TimeoutSec 300 } catch { Write-Output "TEX-FAIL $a $($inc.Name)" }
    }
    New-Item -ItemType File -Force -Path (Join-Path $outdir "downloaded.flag") | Out-Null
    Write-Output "OK $a"
}
Write-Output "DONE"
