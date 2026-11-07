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

# Locate the real editor window by enumerating all top-level windows of the
# UnrealEditor process and picking the one whose title contains "SILID".
$sig2 = @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class WinFind {
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
$hwnd = [WinFind]::FindByTitleFragment([uint32]$pid2, "SILID - Unreal Editor")
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "NOT FOUND"; exit 1 }

# minimize the log console first so it cannot steal focus back
[void][W.U32]::ShowWindow($hwnd, 3)   # SW_MAXIMIZE
[void][W.U32]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 1500
$fg = [W.U32]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[void][W.U32]::GetWindowText($fg, $sb, 256)
Write-Output "foreground: '$($sb.ToString())'"

if ($fg -eq $hwnd) {
  # console -> command -> enter
  [System.Windows.Forms.SendKeys]::SendWait("{~}")
  Start-Sleep -Milliseconds 1200
  [System.Windows.Forms.SendKeys]::SendWait("PIE Enter")
  Start-Sleep -Milliseconds 400
  [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
  Write-Output "sent"
  Start-Sleep -Seconds 12
  # screenshot of the window
  $r = New-Object W.U32+RECT
  [void][W.U32]::GetWindowRect($hwnd, [ref]$r)
  $bmp = New-Object System.Drawing.Bitmap(($r.R-$r.L), ($r.B-$r.T))
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
  $bmp.Save("C:\Users\Admin\Downloads\SILID-main\ue5\BuildLogs\phase23_pie_started.png")
  Write-Output "shot saved"
}
