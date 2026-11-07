Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
public struct RECT { public int L, T, R, B; }
"@ -Name U32 -Namespace W

# enumerate this process's windows and activate the one titled "SILID - Unreal Editor"
$proc = Get-Process UnrealEditor
$target = $null
foreach ($w in $proc) {
  if ($w.MainWindowTitle -eq "SILID - Unreal Editor") { $target = $w.MainWindowHandle }
}
if (-not $target -or $target -eq [IntPtr]::Zero) {
  # fall back: enumerate all top-level windows of the process via .NET
  $target = $proc[0].MainWindowHandle
}
[void][W.U32]::ShowWindow($target, 9)
[void][W.U32]::SetForegroundWindow($target)
Start-Sleep -Milliseconds 1500
$fg = [W.U32]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[void][W.U32]::GetWindowText($fg, $sb, 256)
Write-Output "foreground now: '$($sb.ToString())' (target hwnd $target)"
