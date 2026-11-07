Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
public struct RECT { public int L, T, R, B; }
"@ -Name U32 -Namespace W

$HWND = [IntPtr]722356
function Focus { [void][W.U32]::ShowWindow($HWND, 9); [void][W.U32]::SetForegroundWindow($HWND); Start-Sleep -Milliseconds 700 }
function Shot($name) {
  $r = New-Object W.U32+RECT
  [void][W.U32]::GetWindowRect($HWND, [ref]$r)
  $bmp = New-Object System.Drawing.Bitmap(($r.R-$r.L), ($r.B-$r.T))
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
  $bmp.Save("C:\Users\Admin\Downloads\SILID-main\ue5\BuildLogs\$name")
}
function Key($k, $waitMs) { [System.Windows.Forms.SendKeys]::SendWait($k); Start-Sleep -Milliseconds $waitMs }

# ---- start PIE: console, command, enter
Focus
Key "{~}" 1200
Key "PIE Enter" 400
Key "{ENTER}" 100
Write-Output "PIE requested"
Start-Sleep -Seconds 12
Shot "phase23_pie_start.png"
Write-Output "shot taken"
