Add-Type -AssemblyName System.Windows.Forms
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
"@ -Name U32 -Namespace W
# find the MAIN editor window by exact title (not the -log console)
$h = [W.U32]::FindWindow($null, "SILID - Unreal Editor")
if ($h -eq [IntPtr]::Zero) { Write-Output "main window NOT found"; exit 1 }
[void][W.U32]::ShowWindow($h, 9)
[void][W.U32]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 900
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("{~}")
Start-Sleep -Milliseconds 1000
[System.Windows.Forms.SendKeys]::SendWait("PIE Enter")
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Write-Output "sent to main window"
