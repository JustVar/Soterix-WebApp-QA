<#
.SYNOPSIS
  The scheduled run on a Windows machine: pull, run the tests marked
  `livestream` (or any target), keep the run's report page on this machine.

.DESCRIPTION
  Why a Windows machine: the QA server streams H.265, and Chrome decodes it
  only through a platform decoder. Windows Chrome has one out of the box.
  Chrome on Linux needs a GPU and a Wayland display (docs/LINUX_H265.md).

  Three guards, in PowerShell 5.1:
  1. One run at a time: a stale predecessor (pid file) is killed with its
     process tree before the new run starts.
  2. A cap on the whole run: pytest-timeout's only Windows method kills the
     whole session at the first hang, so the cap is on the process instead
     (taskkill /T after RunCapMinutes).
  3. The clone follows origin/main exactly (git reset --hard); evidence under
     reports/ is untracked and survives.

  The run writes its own report page under reports\runs\<run>\run.html. The
  last log line names it. Nothing leaves the machine.

  Trials on a developer checkout: always pass -NoReset (the reset discards
  uncommitted work).

.EXAMPLE
  .\livestream-run.ps1                                   # the scheduled form
  .\livestream-run.ps1 -NoReset                          # a trial on this checkout
  .\livestream-run.ps1 -Target tests/ui/maps -Marker none -NoReset -DryRun
#>
param(
    [string]$Repo = "C:\qa\Soterix-WebApp-QA",
    [string]$Target = "tests/ui",
    [string]$Marker = "livestream",      # "none" runs the whole target
    [int]$Workers = 2,
    [int]$MaxFail = 50,
    [int]$RunCapMinutes = 90,
    [switch]$NoReset,
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

Write-Log "=== run start (target: $Target, marker: '$Marker')"
if (-not (Test-Path $Python)) { Write-Log "no venv at $Python; see deploy/windows-runner/README.md"; exit 1 }

# The suite reads QA_USER / QA_PASSWORD from .env (config/env/qa.py), or
# from the environment when a trial sets them there. Without them it stops
# at login, so stop here with a clear line instead.
$envFile = Join-Path $Repo '.env'
$inFile = (Test-Path $envFile) -and (Select-String -Path $envFile -Pattern '^QA_USER=.' -Quiet)
if (-not $env:QA_USER -and -not $inFile) {
    Write-Log "=== stopped: QA_USER is not set in $envFile (README.md, 'What the machine needs')"
    exit 1
}

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

# --headed is not a preference here, it is the reason the run works.
# Headless Chrome on Windows answers MediaSource.isTypeSupported('hvc1')
# with true and then never decodes a frame: measured on one test, same
# minute, same server, only this flag different. Headless left the player
# at readyState 1 with currentTime 0.00 for 30 s while the socket delivered
# 124 frames in 8 s, and the app showed "The camera failed to load". Headed
# reached readyState 4 and passed in 25 s. A headed browser needs a desktop,
# which is why the task logs on interactively and why the machine signs in
# automatically.
$pytestArgs = @('-m', 'pytest', $Target, '-n', "$Workers", '-rfEs', "--maxfail=$MaxFail", '-p', 'no:cacheprovider', '--headed')
# -Marker none runs the whole target (an empty string cannot be passed
# through `powershell -File`).
if ($Marker.Trim() -and $Marker.Trim() -ne 'none') { $pytestArgs += @('-m', $Marker.Trim()) }
$out = Join-Path $LogDir 'livestream-run.out'
$err = Join-Path $LogDir 'livestream-run.err'
Write-Log "=== pytest: $Python $($pytestArgs -join ' ')"
if ($DryRun) {
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    Write-Log "=== dry run done (nothing ran)"
    exit 0
}

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
    Write-Log "=== run cap ($RunCapMinutes min) hit after ${elapsed}s: killing the process tree"
    & taskkill /PID $proc.Id /T /F | Out-Null
    $rc = 124
} else {
    $rc = $proc.ExitCode
}
Write-Log "=== pytest exit: $rc after ${elapsed}s (124 = run cap)"
# The -rfEs summary is the last lines of the run's output.
if (Test-Path $out) { Get-Content $out -Tail 25 | ForEach-Object { Add-Content -Path $Log -Value "    $_" -Encoding utf8 } }

# The run page is written at session end, so a capped run has none.
$runsDir = Join-Path $Repo 'reports\runs'
$page = $null
if ($rc -ne 124 -and (Test-Path $runsDir)) {
    $latest = Get-ChildItem $runsDir -Directory | Sort-Object LastWriteTime | Select-Object -Last 1
    if ($latest -and (Test-Path (Join-Path $latest.FullName 'run.html'))) { $page = Join-Path $latest.FullName 'run.html' }
}
Remove-Item $PidFile -ErrorAction SilentlyContinue
if ($page) {
    Write-Log "=== run done: open $page"
} else {
    Write-Log "=== run done: no run page was written (a capped or crashed session writes none; read $out)"
}
