<#
.SYNOPSIS
  Register (or replace) the scheduled task that runs livestream-run.ps1.

.DESCRIPTION
  Daily at -At (machine local time), as the given user, highest run level.
  The task calls PowerShell with the run script and the default parameters;
  change the schedule here and re-run, the script's behaviour in
  livestream-run.ps1.

  The task logs on INTERACTIVELY, so it runs in the signed-in desktop
  session. That is not a preference: the run passes --headed, because
  headless Chrome on Windows claims H.265 support and then never decodes a
  frame (README.md). A headed browser with no desktop cannot start, so the
  machine must also sign in automatically. A task that ran as S4U or with a
  stored password would land in session 0, find no desktop, and fail every
  streaming test the way the first trial did.

  The cost of Interactive: the task runs only while somebody is signed in.
  Automatic sign-in covers that after a restart. If the machine is ever
  found signed out, the run did not happen and the log has no entry.

.EXAMPLE
  .\register-task.ps1                                # 05:00 daily, current user
  .\register-task.ps1 -At 04:30 -Repo D:\qa\Soterix-WebApp-QA
  .\register-task.ps1 -Unregister
#>
param(
    [string]$Repo = "C:\qa\Soterix-WebApp-QA",
    [string]$At = "05:00",
    # The machine, never USERDOMAIN: a local account's domain is the computer,
    # and on a workgroup machine USERDOMAIN reads WORKGROUP, which names no
    # account, so the registration fails with "No mapping between account
    # names and security IDs". Pass -User for a domain account.
    [string]$User = "$env:COMPUTERNAME\$env:USERNAME",
    [string]$TaskName = "QA livestream run",
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "removed task '$TaskName'"
    exit 0
}

$script = Join-Path $Repo 'deploy\windows-runner\livestream-run.ps1'
if (-not (Test-Path $script)) { throw "no run script at $script; clone the repo there first (README.md)" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Repo `"$Repo`"" `
    -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 5) `
    -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Interactive, not S4U: the run is --headed and a headed browser needs a
# desktop. See the description above.
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
Write-Output "task '$TaskName': $($task.State), daily at $At as $User, script $script"
Write-Output "logon type: $($task.Principal.LogonType)   (Interactive is required: the run is --headed)"
$auto = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -Name AutoAdminLogon -ErrorAction SilentlyContinue).AutoAdminLogon
if ($auto -ne '1') {
    Write-Warning "automatic sign-in is OFF. An interactive task runs only while somebody is signed in, so after a restart this run will not happen. Set it with netplwiz (README.md)."
}
Write-Output "run it now with: Start-ScheduledTask -TaskName '$TaskName'   (then read $Repo\logs\livestream-run.log)"
