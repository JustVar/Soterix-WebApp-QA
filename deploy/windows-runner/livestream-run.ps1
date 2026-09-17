<#
.SYNOPSIS
  The scheduled livestream run on a Windows machine: pull, run the tests
  marked `livestream` per box, publish each run to the archive on spartan1.

.DESCRIPTION
  Why a Windows machine: the QA tenants stream H.265, and Chrome decodes it
  only through a platform decoder. Windows Chrome has one out of the box.
  Since 09/17/2026 spartan1 decodes it too (Intel GPU, VA-API, headed on a
  headless Weston: deploy/spartan1/README.md) and its nightly runs the
  livestream tests; this machine is the fallback for the day that breaks
  (register row 47).

  Same guards as deploy/spartan1/nightly.sh, in PowerShell 5.1:
  1. One run at a time: a stale predecessor (pid file) is killed with its
     process tree before the new run starts.
  2. A cap on the whole run per box: pytest-timeout's only Windows method
     kills the whole session at the first hang, so the cap is on the process
     instead (taskkill /T after RunCapMinutes).
  3. The clone follows origin/main exactly (git reset --hard); evidence under
     reports/ is untracked and survives.

  Trials on a developer checkout: always pass -NoReset (the reset discards
  uncommitted work) and usually -NoPublish.

.EXAMPLE
  .\livestream-run.ps1                                  # the scheduled form
  .\livestream-run.ps1 -Boxes us -NoReset -NoPublish    # a trial on this checkout
  .\livestream-run.ps1 -Target tests/ui/maps -Marker none -Boxes us -NoReset -NoPublish -DryRun
#>
param(
    [string]$Repo = "C:\qa\Soterix-WebApp-QA",
    [string]$Target = "tests/ui",
    [string]$Marker = "livestream",      # "none" runs the whole target
    [string]$Boxes = "india us",
    [int]$Workers = 2,
    [int]$MaxFail = 50,
    [int]$RunCapMinutes = 90,
    [switch]$NoReset,
    [switch]$NoPublish,
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
$Python = Join-Path $Repo 'venv\Scripts\python.exe'
$LogDir = Join-Path $Repo 'logs'
$Log = Join-Path $LogDir 'livestream-run.log'
$PidFile = Join-Path $LogDir 'livestream-run.pid'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Write-Log([string]$Message) {
    $line = "$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ss') $Message"
    Add-Content -Path $Log -Value $line -Encoding utf8
    Write-Output $line
}

Write-Log "=== livestream run start (target: $Target, marker: '$Marker', boxes: $Boxes)"
if (-not (Test-Path $Python)) { Write-Log "no venv at $Python; see deploy/windows-runner/README.md"; exit 1 }

# Guard 1: one run at a time.
if (Test-Path $PidFile) {
    $old = (Get-Content $PidFile | Select-Object -First 1)
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
        Write-Log "previous run (pid $old) still alive: killing its process tree"
        if (-not $DryRun) { & taskkill /PID $old /T /F | Out-Null }
    }
}
Set-Content -Path $PidFile -Value $PID

Set-Location $Repo
# Guard 3: the clone follows origin/main.
if ($NoReset) {
    Write-Log "code: $(git log -1 --format='%h %s') (no reset: trial on this checkout)"
} elseif ($DryRun) {
    Write-Log "would: git fetch origin; git reset --hard origin/main; pip install -r requirements.txt"
} else {
    git fetch -q origin
    git reset -q --hard origin/main
    Write-Log "code: $(git log -1 --format='%h %s')"
    & $Python -m pip install -q -r requirements.txt
}

$published = @()
foreach ($box in ($Boxes -split '\s+' | Where-Object { $_ })) {
    # The suite reads QA_<BOX>_USER / QA_<BOX>_PASSWORD from .env for the box
    # it is asked for (config/env/qa.py); without them it stops at login.
    $key = "QA_$($box.ToUpper())_USER"
    $envFile = Join-Path $Repo '.env'
    if (-not (Test-Path $envFile) -or -not (Select-String -Path $envFile -Pattern "^$key=." -Quiet)) {
        Write-Log "=== $box skipped: $key is not set in $envFile"
        continue
    }
    $env:BOX = $box
    $pytestArgs = @('-m', 'pytest', $Target, '-n', "$Workers", '-rfEs', "--maxfail=$MaxFail", '-p', 'no:cacheprovider')
    # -Marker none runs the whole target (an empty string cannot be passed
    # through `powershell -File`).
    if ($Marker.Trim() -and $Marker.Trim() -ne 'none') { $pytestArgs += @('-m', $Marker.Trim()) }
    $out = Join-Path $LogDir "livestream-$box.out"
    $err = Join-Path $LogDir "livestream-$box.err"
    Write-Log "=== ${box}: $Python $($pytestArgs -join ' ')"
    if ($DryRun) { continue }

    $started = Get-Date
    # Guard 2: the run cap. Start-Process so the cap can kill the whole tree.
    $proc = Start-Process -FilePath $Python -ArgumentList $pytestArgs -WorkingDirectory $Repo `
        -NoNewWindow -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
    # PowerShell 5.1: ExitCode stays empty unless the handle was read before
    # the process ended (the first trial logged "pytest exit:  after 50s").
    $null = $proc.Handle
    $finished = $proc.WaitForExit($RunCapMinutes * 60 * 1000)
    $elapsed = [int]((Get-Date) - $started).TotalSeconds
    if (-not $finished) {
        Write-Log "=== $box run cap ($RunCapMinutes min) hit after ${elapsed}s: killing the process tree"
        & taskkill /PID $proc.Id /T /F | Out-Null
        $rc = 124
    } else {
        $rc = $proc.ExitCode
    }
    Write-Log "=== $box pytest exit: $rc after ${elapsed}s (124 = run cap)"
    # The -rfEs summary is the last lines of the run's output.
    if (Test-Path $out) { Get-Content $out -Tail 25 | ForEach-Object { Add-Content -Path $Log -Value "    $_" -Encoding utf8 } }

    # Publish the archived run (written at session end, so not after a cap).
    if ($NoPublish) {
        Write-Log "=== ${box}: publish skipped (-NoPublish)"
    } elseif ($rc -eq 124) {
        Write-Log "=== ${box}: nothing archived to publish (the cap killed the session before it wrote)"
    } else {
        & $Python tools/publish_run.py 2>&1 | ForEach-Object { Add-Content -Path $Log -Value "    $_" -Encoding utf8 }
        Write-Log "=== ${box}: publish exit $LASTEXITCODE (0 published, 1 scp failed, 2 nothing to publish)"
        if ($LASTEXITCODE -eq 0) { $published += $box }
    }
}

Remove-Item $PidFile -ErrorAction SilentlyContinue
Write-Log "=== livestream run done (published: $($published -join ', '))"
