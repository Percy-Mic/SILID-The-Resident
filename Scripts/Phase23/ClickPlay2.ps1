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
public static class WF3 {
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
  public static IntPtr FindByTitleFragment(uint pid, string frag) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { var sb = new StringBuilder(256); GetWindowText(h, sb, 256);
        if (sb.ToString().Contains(frag)) { found = h; return false; } } return true; }, IntPtr.Zero);
    return found;
  }
  public static System.Collections.Generic.List<IntPtr> AllOf(uint pid) {
    var l = new System.Collections.Generic.List<IntPtr>();
    EnumWindows((h, x) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) l.Add(h); return true; }, IntPtr.Zero);
    return l;
  }
}
"@
Add-Type -TypeDefinition $sig2

# minimize every VS Code window (pid lookup by name)
Get-Process Code -ErrorAction SilentlyContinue | ForEach-Object {
  $h = $_.MainWindowHandle
  if ($h -ne [IntPtr]::Zero) { [void][W.U32]::ShowWindow($h, 6) }  # SW_MINIMIZE
}
# minimize the -log console (title contains 'UnrealEditor' console or 'SILID - log')
Get-Process | Where-Object { $_.MainWindowTitle -match 'UnrealEditor|log' -and $_.Name -ne 'UnrealEditor' } | ForEach-Object {
  if ($_.MainWindowHandle -ne [IntPtr]::Zero) { [void][W.U32]::ShowWindow($_.MainWindowHandle, 6) }
}
Start-Sleep -Milliseconds 1500

$pid2 = (Get-Process UnrealEditor).Id
$hwnd = [WF3]::FindByTitleFragment([uint32]$pid2, "SILID - Unreal Editor")
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "editor window NOT FOUND"; exit 1 }
[void][W.U32]::ShowWindow($hwnd, 9)
[void][W.U32]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 1500

$r = New-Object W.U32+RECT
[void][W.U32]::GetWindowRect($hwnd, [ref]$r)
Write-Output "editor rect: L=$($r.L) T=$($r.T) R=$($r.R) B=$($r.B)"

# Play button at ~(489,77) client coords
$cx = $r.L + 489; $cy = $r.T + 77
[void][W.U32]::SetCursorPos($cx, $cy)
Start-Sleep -Milliseconds 400
[W.U32]::mouse_event(0x0002,0,0,0,0); Start-Sleep -Milliseconds 60; [W.U32]::mouse_event(0x0004,0,0,0,0)
Write-Output "clicked $cx,$cy"
Start-Sleep -Seconds 14

$bmp = New-Object System.Drawing.Bitmap(($r.R-$r.L), ($r.B-$r.T))
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
$bmp.Save("C:\Users\Admin\Downloads\SILID-main\ue5\BuildLogs\phase23_pie_after_click2.png")
Write-Output "shot saved"
