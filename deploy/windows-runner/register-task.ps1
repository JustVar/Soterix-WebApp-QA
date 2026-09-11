<#
.SYNOPSIS
  Register (or replace) the scheduled task that runs livestream-run.ps1.

.DESCRIPTION
  Daily at -At (machine local time), as the given user, highest run level,
  whether or not anyone is logged on. The task calls PowerShell with the
  run script and the default parameters; change the schedule here and
  re-run, the script's behaviour in livestream-run.ps1.

  The S4U logon type runs without a stored password and cannot reach
  network shares, which this run never needs: git and scp use local key
  files. If scp under the task ever asks for a password, re-register with
  -StorePassword, which prompts once and stores the credential in the
  task (LogonType Password).

.EXAMPLE
  .\register-task.ps1                                # 05:00 daily, current user
  .\register-task.ps1 -At 04:30 -Repo D:\qa\Soterix-WebApp-QA
  .\register-task.ps1 -Unregister
#>
param(
    [string]$Repo = "C:\qa\Soterix-WebApp-QA",
    [string]$At = "05:00",
    [string]$User = "$env:USERDOMAIN\$env:USERNAME",
    [string]$TaskName = "QA livestream run",
    [switch]$StorePassword,
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

if ($StorePassword) {
    $cred = Get-Credential -UserName $User -Message "Password for the task's account"
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -User $cred.UserName -Password $cred.GetNetworkCredential().Password -RunLevel Highest -Force | Out-Null
} else {
    $principal = New-ScheduledTaskPrincipal -UserId $User -LogonType S4U -RunLevel Highest
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Force | Out-Null
}
$task = Get-ScheduledTask -TaskName $TaskName
Write-Output "task '$TaskName': $($task.State), daily at $At as $User, script $script"
Write-Output "run it now with: Start-ScheduledTask -TaskName '$TaskName'   (then read $Repo\logs\livestream-run.log)"
