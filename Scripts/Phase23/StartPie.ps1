Add-Type -AssemblyName System.Windows.Forms
Add-Type -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
"@ -Name U32 -Namespace W
$p = Get-Process UnrealEditor -ErrorAction Stop
[void][W.U32]::ShowWindow($p.MainWindowHandle, 9)
[void][W.U32]::SetForegroundWindow($p.MainWindowHandle)
Start-Sleep -Milliseconds 500
# Tilde (console) then the command, then Enter
[System.Windows.Forms.SendKeys]::SendWait("{~}")
Start-Sleep -Milliseconds 800
[System.Windows.Forms.SendKeys]::SendWait("PIE Enter")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Write-Output "sent"
