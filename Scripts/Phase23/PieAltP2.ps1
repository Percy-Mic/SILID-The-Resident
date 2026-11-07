Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
public struct RECT { public int L, T, R, B; }
"@ -Name U32 -Namespace W
$sig2 = @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class WF8 {
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public static System.Collections.Generic.List<object[]> List(uint pid) {
    var res = new System.Collections.Generic.List<object[]>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { var sb = new StringBuilder(256); GetWindowText(h, sb, 256);
        res.Add(new object[]{ h, sb.ToString() }); } return true; }, IntPtr.Zero);
    return res;
  }
}
"@
Add-Type -TypeDefinition $sig2

$pid2 = (Get-Process UnrealEditor).Id
$wins = [WF8]::List([uint32]$pid2)
$main = [IntPtr]::Zero
foreach ($w in $wins) {
  $h = [IntPtr]$w[0]; $t = [string]$w[1]
  Write-Output "win: $h '$t'"
  if ($t -match 'UnrealEditor\.exe') { [void][W.U32]::ShowWindow($h, 6); Write-Output "  -> minimized console" }
  if ($t -eq 'SILID - Unreal Editor') { $main = $h }
}
if ($main -eq [IntPtr]::Zero) { Write-Output "no main"; exit 1 }
[void][W.U32]::ShowWindow($main, 3)
[void][W.U32]::SetForegroundWindow($main)
Start-Sleep -Milliseconds 1500
$r = New-Object W.U32+RECT
[void][W.U32]::GetWindowRect($main, [ref]$r)
Write-Output "editor rect: L=$($r.L) T=$($r.T) W=$($r.R-$r.L) H=$($r.B-$r.T)"

# click the viewport center to give it input focus
$vcx = $r.L + [int](($r.R-$r.L) * 0.45)
$vcy = $r.T + [int](($r.B-$r.T) * 0.55)
[void][W.U32]::SetCursorPos($vcx, $vcy)
Start-Sleep -Milliseconds 300
[W.U32]::mouse_event(0x0002,0,0,0,0); Start-Sleep -Milliseconds 60; [W.U32]::mouse_event(0x0004,0,0,0,0)
Start-Sleep -Milliseconds 600

# Alt+P starts PIE (default Unreal binding)
[System.Windows.Forms.SendKeys]::SendWait("%(p)")
Write-Output "Alt+P sent"
Start-Sleep -Seconds 15

$bmp = New-Object System.Drawing.Bitmap(($r.R-$r.L), ($r.B-$r.T))
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
$bmp.Save("C:\Users\Admin\Downloads\SILID-main\ue5\BuildLogs\phase23_pie_try6.png")
Write-Output "shot saved"
