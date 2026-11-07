Add-Type -AssemblyName System.Drawing
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);
public struct RECT { public int L, T, R, B; }
"@ -Name U32 -Namespace W

$sig2 = @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class WinFind2 {
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
  public static IntPtr FindByTitleFragment(uint pid, string frag) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) {
        var sb = new StringBuilder(256); GetWindowText(h, sb, 256);
        if (sb.ToString().Contains(frag)) { found = h; return false; }
      }
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
"@
Add-Type -TypeDefinition $sig2

$pid2 = (Get-Process UnrealEditor).Id
$hwnd = [WinFind2]::FindByTitleFragment([uint32]$pid2, "SILID - Unreal Editor")
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "NOT FOUND"; exit 1 }
[void][W.U32]::ShowWindow($hwnd, 9)
[void][W.U32]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 1200

$r = New-Object W.U32+RECT
[void][W.U32]::GetWindowRect($hwnd, [ref]$r)
Write-Output "window rect: L=$($r.L) T=$($r.T) R=$($r.R) B=$($r.B)"

# Play button in the level-editor toolbar, from the screenshot: (489, 77) in client coords
$cx = $r.L + 489
$cy = $r.T + 77
[W.U32]::mouse_event(0x0002, 0, 0, 0, 0)  # left down
[W.U32]::mouse_event(0x0004, 0, 0, 0, 0)  # left up
Start-Sleep -Milliseconds 300
# move cursor there first (mouse_event with MOVE flags uses relative coords; use absolute)
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
"@ -Name U32b -Namespace W
[void][W.U32b]::SetCursorPos($cx, $cy)
Start-Sleep -Milliseconds 400
[W.U32]::mouse_event(0x0002, 0, 0, 0, 0)
[W.U32]::mouse_event(0x0004, 0, 0, 0, 0)
Write-Output "clicked play at $cx,$cy"
Start-Sleep -Seconds 12

# screenshot
$bmp = New-Object System.Drawing.Bitmap(($r.R-$r.L), ($r.B-$r.T))
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
$bmp.Save("C:\Users\Admin\Downloads\SILID-main\ue5\BuildLogs\phase23_pie_after_click.png")
Write-Output "shot saved"
