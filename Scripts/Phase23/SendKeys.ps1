param([string]$Keys, [int]$DelayMs = 120)
Add-Type -AssemblyName System.Windows.Forms
$sig = @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
"@
Add-Type -MemberDefinition $sig -Name U32 -Namespace W
$p = Get-Process UnrealEditor -ErrorAction Stop
[void][W.U32]::ShowWindow($p.MainWindowHandle, 9)
[void][W.U32]::SetForegroundWindow($p.MainWindowHandle)
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait($Keys)
Start-Sleep -Milliseconds $DelayMs
