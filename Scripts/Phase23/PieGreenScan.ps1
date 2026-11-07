Add-Type -AssemblyName System.Drawing
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
public struct RECT { public int L, T, R, B; }
"@ -Name U32 -Namespace W
$sig2 = @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class WF18 {
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public static IntPtr Find(uint pid, string frag) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { var sb = new StringBuilder(256); GetWindowText(h, sb, 256);
        if (sb.ToString().Contains(frag)) { found = h; return false; } } return true; }, IntPtr.Zero);
    return found;
  }
}
"@
Add-Type -TypeDefinition $sig2
$pid2 = (Get-Process UnrealEditor).Id
$hwnd = [WF18]::Find([uint32]$pid2, "SILID - Unreal Editor")
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "NOT FOUND"; exit 1 }
[void][W.U32]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 1200
$r = New-Object W.U32+RECT
[void][W.U32]::GetWindowRect($hwnd, [ref]$r)
$W = $r.R - $r.L; $H = $r.B - $r.T
Write-Output "window: $W x $H"

# capture the toolbar strip
$bmp = New-Object System.Drawing.Bitmap($W, $H)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)

# scan y in [55..110] for the green Play triangle (high G, low-ish R/B)
$best = $null
for ($y = 55; $y -lt 110; $y += 2) {
  for ($x = 380; $x -lt 560; $x += 1) {
    $c = $bmp.GetPixel($x, $y)
    if ($c.G -gt 120 -and $c.G -gt $c.R + 40 -and $c.G -gt $c.B + 40) {
      if (-not $best -or $x -gt $best[0]) { $best = @($x, $y, $c.R, $c.G, $c.B) }
    }
  }
}
if ($best) {
  Write-Output "Play button found at physical client ($($best[0]), $($best[1])) color R=$($best[2]) G=$($best[3]) B=$($best[4])"
  $cx = $r.L + $best[0]; $cy = $r.T + $best[1]
  [void][W.U32]::SetCursorPos($cx, $cy)
  Start-Sleep -Milliseconds 500
  [W.U32]::mouse_event(0x0002,0,0,0,0); Start-Sleep -Milliseconds 110; [W.U32]::mouse_event(0x0004,0,0,0,0)
  Write-Output "clicked screen ($cx,$cy)"
  Start-Sleep -Seconds 20
  $bmp2 = New-Object System.Drawing.Bitmap($W, $H)
  $g2 = [System.Drawing.Graphics]::FromImage($bmp2)
  $g2.CopyFromScreen($r.L, $r.T, 0, 0, $bmp2.Size)
  $bmp2.Save("C:\Users\Admin\Downloads\SILID-main\ue5\BuildLogs\phase23_pie_try13.png")
  Write-Output "shot saved"
} else {
  Write-Output "NO GREEN FOUND in strip"
}
