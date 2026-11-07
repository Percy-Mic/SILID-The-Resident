# Compile the SILID game module with UnrealBuildTool via Build.bat
# (Build.bat resolves the engine's own bundled .NET runtime; calling
# UnrealBuildTool.exe directly needs a system .NET 6 that is not installed).
# Usage: powershell -File Scripts\BuildSILID.ps1
$ErrorActionPreference = "Continue"
$Build = "C:\Program Files\Epic Games\UE_5.4\Engine\Build\BatchFiles\Build.bat"
& $Build SILIDEditor Win64 Development `
    -project="C:\Users\Admin\Downloads\SILID-main\ue5\SILID.uproject" `
    -waitmutex 2>&1 | Select-Object -Last 60
