# Make a Windows machine able to run tests unattended.
#
# Run it in an elevated PowerShell (the title bar must say "Administrator:" -
# a prompt sitting in C:\WINDOWS\system32 is not proof of elevation).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File kiosk-setup.ps1
#
# It is safe to run again, and it reads back everything it sets, because the
# first pass at this machine reported settings it had not actually applied.
#
# What it does NOT do: automatic sign-in. That stores a password in the
# registry, so a person does it at the machine. Without it, a restart leaves
# no desktop and a headed browser cannot start.
$ErrorActionPreference = 'Continue'

# Active hours: local hours, 0-23, at most 18 apart. 02:00-20:00 covers the
# 09:00 UTC nightly, which is 03:00 in Central time.
$ACTIVE_START = 2
$ACTIVE_END = 20

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
      ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "run this from an elevated PowerShell"
    exit 1
}

"== power: a machine that sleeps leaves the network mid-run"
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

"== windows update"
# Group Policy keys do nothing on Windows 11 Home, which has no policy engine.
# Writing them and believing them is how this machine spent a day looking
# protected while it was not.
$edition = (Get-CimInstance Win32_OperatingSystem).Caption
$pol = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
if ($edition -match 'Home') {
    if (Test-Path $pol) { Remove-Item $pol -Recurse -Force -ErrorAction SilentlyContinue }
    "  $edition has no policy engine, so active hours is the control that works"
}
$ux = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
New-Item -Path $ux -Force | Out-Null
Set-ItemProperty -Path $ux -Name 'SmartActiveHoursState' -Value 0 -Type DWord
Set-ItemProperty -Path $ux -Name 'ActiveHoursStart' -Value $ACTIVE_START -Type DWord
Set-ItemProperty -Path $ux -Name 'ActiveHoursEnd' -Value $ACTIVE_END -Type DWord

"== make the automatic sign-in checkbox reachable"
# Windows 11 ships DevicePasswordLessBuildVersion=2, which hides "Users must
# enter a user name and password to use this computer" from netplwiz entirely,
# so the setting looks unavailable rather than unset. This only offers the
# option. It signs nobody in and stores no password: a person ticks the box at
# the machine, and Windows keeps that password as an LSA secret.
$pwless = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device'
if (Test-Path $pwless) {
    Set-ItemProperty -Path $pwless -Name 'DevicePasswordLessBuildVersion' -Value 0 -Type DWord
}

"== chrome: a browser that changes version mid-run changes the result"
# Both the task AND the two services. Disabling the task alone leaves the
# services Automatic, and a stopped Automatic service starts again.
foreach ($svc in Get-Service -Name '*GoogleUpdater*' -ErrorAction SilentlyContinue) {
    Stop-Service -Name $svc.Name -Force -ErrorAction SilentlyContinue
    Set-Service -Name $svc.Name -StartupType Disabled -ErrorAction SilentlyContinue
}
foreach ($t in Get-ScheduledTask -TaskPath '\GoogleSystem\GoogleUpdater\' -ErrorAction SilentlyContinue) {
    Disable-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -ErrorAction SilentlyContinue | Out-Null
}

"== read back what the machine reports, not what was asked for"
$fail = 0
function Check($label, $got, $want) {
    $ok = "$got" -eq "$want"
    "  {0,-34} {1,-28} {2}" -f $label, $got, $(if ($ok) { "ok" } else { "WANTED $want" })
    if (-not $ok) { $script:fail++ }
}
$q = { param($sub, $name)
    (powercfg /query SCHEME_CURRENT $sub $name | Select-String 'Current AC Power Setting Index') -replace '.*: ', '' }
Check 'sleep on AC'        (& $q SUB_SLEEP STANDBYIDLE).Trim() '0x00000000'
Check 'display off on AC'  (& $q SUB_VIDEO VIDEOIDLE).Trim()   '0x00000000'
$now = Get-ItemProperty -Path $ux
Check 'active hours start' $now.ActiveHoursStart $ACTIVE_START
Check 'active hours end'   $now.ActiveHoursEnd   $ACTIVE_END
Check 'windows picks its own hours' $now.SmartActiveHoursState 0
if ($edition -match 'Home') { Check 'inert policy keys removed' (Test-Path $pol) $false }
if (Test-Path $pwless) {
    Check 'netplwiz offers auto sign-in' (Get-ItemProperty $pwless -Name DevicePasswordLessBuildVersion).DevicePasswordLessBuildVersion 0
}
foreach ($svc in Get-Service -Name '*GoogleUpdater*' -ErrorAction SilentlyContinue) {
    Check "updater $($svc.Name.Substring(0, [Math]::Min(22, $svc.Name.Length)))" (Get-Service $svc.Name).StartType 'Disabled'
}
foreach ($t in Get-ScheduledTask -TaskPath '\GoogleSystem\GoogleUpdater\' -ErrorAction SilentlyContinue) {
    Check 'updater task' $t.State 'Disabled'
}

$auto = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -Name AutoAdminLogon -ErrorAction SilentlyContinue).AutoAdminLogon
""
"  automatic sign-in: $(if ($auto -eq '1') { 'on' } else { 'OFF - a person sets this at the machine' })"
"  chrome version   : " + (Get-Item 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ErrorAction SilentlyContinue).VersionInfo.ProductVersion
""
if ($fail) { "$fail setting(s) did not take. Read the lines marked WANTED above."; exit 1 }
"every setting read back as asked."
