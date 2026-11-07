Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$ws = New-Object -ComObject WScript.Shell
$ok = $ws.AppActivate("SILID - Unreal Editor")
Start-Sleep -Milliseconds 1200
Write-Output "AppActivate: $ok"
# full virtual screen shot to see what's actually on top
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bmp.Size)
$bmp.Save("C:\Users\Admin\Downloads\SILID-main\ue5\BuildLogs\phase23_fullscreen.png")
Write-Output "fullscreen saved $($bounds.Width)x$($bounds.Height)"
