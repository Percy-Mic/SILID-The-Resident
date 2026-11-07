Add-Type -AssemblyName System.Windows.Forms
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
public struct RECT { public int L, T, R, B; }
"@ -Name U32 -Namespace W
Add-Type -AssemblyName System.Drawing

function Shot($name) {
  $h = [W.U32]::FindWindow($null, "SILID - Unreal Editor")
  $r = New-Object W.U32+RECT
  [void][W.U32]::GetWindowRect($h, [ref]$r)
  $bmp = New-Object System.Drawing.Bitmap(($r.R-$r.L), ($r.B-$r.T))
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
  $bmp.Save("C:\Users\Admin\Downloads\SILID-main\ue5\BuildLogs\$name")
}

# focus the main editor window
$h = [W.U32]::FindWindow($null, "SILID - Unreal Editor")
if ($h -eq [IntPtr]::Zero) { Write-Output "no window"; exit 1 }
[void][W.U32]::ShowWindow($h, 9)
[void][W.U32]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 900

# 1. open console, start PIE
[System.Windows.Forms.SendKeys]::SendWait("{~}")
Start-Sleep -Milliseconds 1200
[System.Windows.Forms.SendKeys]::SendWait("PIE Enter")
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Write-Output "PIE requested"
Start-Sleep -Seconds 10
Shot "phase23_pie_start.png"
Write-Output "shot1"
