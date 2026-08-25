
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SnapshotName,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$OutputFileName,

    [Parameter(Position = 2)]
    [ValidateSet(0, 1, 2)]
    [int]$Pressure = 0,

    [Parameter(Mandatory = $true)]
    [string]$Config,

    [Parameter(Mandatory = $true)]
    [int]$RunNumber,

    [double]$UnstunDelaySeconds = 6.0
)

#CONFIG
$VmrunPath      = "C:\Program Files\VMware\VMware Workstation\vmrun.exe"
$VmxPath        = "E:\VMStorage\VM04_Win11\VM04 Win11 8Gb.vmx"

$GuestUser      = "researcher"
$GuestPassword  = "Password123!"

$VmwareLogPath  = "E:\VMStorage\VM04_Win11\vmware.log"
$GuestWinpmem   = "\\vmware-host\Shared Folders\SharedFolder\winpmem\go-winpmem_amd64_1.0-rc2_signed.exe"
$GuestOutput    = "\\vmware-host\Shared Folders\SharedFolder\Acquisitions\$OutputFileName"

$XlsxPath       = "E:\Research\SharedFolder\Data\Data.xlsx"
$RecordTimingScript = "E:\Research\Pipeline\record_run_timing_Async.py"

$UnstunMarker = "SnapshotVMXTakeSnapshotWork: Initiated lazy snapshot"

# Kill any leftover memory_load.ps1 process from a previous run
Write-Host "Clearing any leftover memory load from a previous run..."
$killCommand = 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*memory_load.ps1*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }'
& $VmrunPath -T ws -gu $GuestUser -gp $GuestPassword runProgramInGuest $VmxPath `
    "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command $killCommand

$pressurePercent = @{ 0 = 0; 1 = 25; 2 = 50 }[$Pressure]

if ($pressurePercent -gt 0) {
    Write-Host "Starting memory load: $pressurePercent% of currently free RAM inside guest..."
    $loadScript = "\\vmware-host\Shared Folders\SharedFolder\scripts\memory_load.ps1"
    $loadLog = "\\vmware-host\Shared Folders\SharedFolder\Acquisitions\Tests\$OutputFileName.loadlog.txt"

    & $VmrunPath -T ws -gu $GuestUser -gp $GuestPassword runProgramInGuest $VmxPath -noWait `
        "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden `
        -File $loadScript -PressurePercent $pressurePercent -LogPath $loadLog -HoldSeconds 3600

    Write-Host "Waiting for memory load to settle..."
    Start-Sleep -Seconds 45
}

# Measure memory usage 
Write-Host "Measuring current memory usage..."
$memUsageScript = "\\vmware-host\Shared Folders\SharedFolder\scripts\memory_usage.ps1"
$memUsageLog = "\\vmware-host\Shared Folders\SharedFolder\Acquisitions\Tests\$OutputFileName.memusage.txt"
& $VmrunPath -T ws -gu $GuestUser -gp $GuestPassword runProgramInGuest $VmxPath `
    "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
    -File $memUsageScript -LogPath $memUsageLog
$memoryUsage = (Get-Content "E:\Research\SharedFolder\Acquisitions\Tests\$OutputFileName.memusage.txt").Trim()
Write-Host "Memory usage: $memoryUsage%"


# Take the snapshot - Async
# Instead of blocking on vmrun.exe
Write-Host "Taking snapshot '$SnapshotName' (async trigger mode)..."

$snapshotTriggerTime = Get-Date
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $VmrunPath
$psi.Arguments = "-T ws snapshot `"$VmxPath`" $SnapshotName"
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true

Write-Host "vmrun command line: $($psi.FileName) $($psi.Arguments)"
$vmrunProcess = [System.Diagnostics.Process]::Start($psi)

# Read stdout/stderr asynchronously
$stdoutBuilder = New-Object System.Text.StringBuilder
$stderrBuilder = New-Object System.Text.StringBuilder
$stdoutEvent = Register-ObjectEvent -InputObject $vmrunProcess -EventName OutputDataReceived -Action {
    if ($EventArgs.Data) { $Event.MessageData.AppendLine($EventArgs.Data) | Out-Null }
} -MessageData $stdoutBuilder
$stderrEvent = Register-ObjectEvent -InputObject $vmrunProcess -EventName ErrorDataReceived -Action {
    if ($EventArgs.Data) { $Event.MessageData.AppendLine($EventArgs.Data) | Out-Null }
} -MessageData $stderrBuilder
$vmrunProcess.BeginOutputReadLine()
$vmrunProcess.BeginErrorReadLine()

# Give vmrun a moment and check if it failed
Start-Sleep -Milliseconds 1500
if ($vmrunProcess.HasExited) {
    Write-Host "ERROR: vmrun exited immediately (code $($vmrunProcess.ExitCode)) -- snapshot was never actually triggered."
    Start-Sleep -Milliseconds 200  # let any final async output land
    if ($stdoutBuilder.Length -gt 0) { Write-Host "STDOUT:`n$($stdoutBuilder.ToString())" }
    if ($stderrBuilder.Length -gt 0) { Write-Host "STDERR:`n$($stderrBuilder.ToString())" }
    Unregister-Event -SourceIdentifier $stdoutEvent.Name
    Unregister-Event -SourceIdentifier $stderrEvent.Name
    exit 1
}
Write-Host "vmrun still running after 1.5s, proceeding with fixed delay..."

# Fixed delay
Write-Host "Waiting fixed delay of $UnstunDelaySeconds s for checkpoint completion..."
Start-Sleep -Seconds $UnstunDelaySeconds

# Run Acquisition
Write-Host "Starting WinPmem acquisition inside guest..."
$acquisitionStart = Get-Date

& $VmrunPath -T ws -gu $GuestUser -gp $GuestPassword runProgramInGuest $VmxPath `
    $GuestWinpmem acquire --nosparse $GuestOutput
$acquisitionEnd = Get-Date

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: acquisition failed (exit code $LASTEXITCODE)."
    exit 1
}
Write-Host "Acquisition complete: $GuestOutput"

$vmrunProcess.WaitForExit()
$snapshotEnd = Get-Date

if ($vmrunProcess.ExitCode -ne 0) {
    Write-Host "WARNING: vmrun snapshot exited non-zero (code $($vmrunProcess.ExitCode)) after acquisition already ran. Check snapshot integrity."
}

# Read vmware log to determine true gap
$trueUnstunTimestampUtc = $null

$logLines = Get-Content -Path $VmwareLogPath
$displayNameAnchor = "displayName = $SnapshotName"
$anchorIndex = -1

for ($i = $logLines.Count - 1; $i -ge 0; $i--) {
    if ($logLines[$i] -like "*$displayNameAnchor*") {
        $anchorIndex = $i
        break
    }
}

if ($anchorIndex -lt 0) {
    Write-Host "WARNING: displayName anchor for '$SnapshotName' not found anywhere in vmware.log."
} else {
    
    $quotedNameMarker = "$UnstunMarker '$SnapshotName':"
    for ($i = $anchorIndex; $i -lt $logLines.Count; $i++) {
        if ($logLines[$i] -like "*$quotedNameMarker*" -and $logLines[$i] -match '^(?<ts>\S+)\s') {
            $trueUnstunTimestampUtc = [datetime]::Parse(
                $Matches['ts'],
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::AdjustToUniversal -bor [System.Globalization.DateTimeStyles]::AssumeUniversal
            )
            break
        }
    }
}

if ($null -eq $trueUnstunTimestampUtc) {
    Write-Host "WARNING: could not find '$UnstunMarker' line for '$SnapshotName' in vmware.log -- true gap cannot be computed for this run."
}

# Checkpoint-prep duration
$measuredCheckpointDuration = $null
if ($null -ne $trueUnstunTimestampUtc) {
    $measuredCheckpointDuration = ($trueUnstunTimestampUtc - $snapshotTriggerTime.ToUniversalTime()).TotalSeconds
}

# Timing summary
$snapshotDuration = $snapshotEnd - $snapshotTriggerTime
$acquisitionDuration = $acquisitionEnd - $acquisitionStart

$trueGapSeconds = $null
if ($null -ne $trueUnstunTimestampUtc) {
    $trueGapSeconds = ($acquisitionStart.ToUniversalTime() - $trueUnstunTimestampUtc).TotalSeconds
}

# Legacy gap, recorded but never used
$legacyGap = $acquisitionStart - $snapshotEnd

Write-Host "`n--- Timing summary ---"
Write-Host "Configured unstun delay used: $UnstunDelaySeconds s"
if ($null -ne $trueGapSeconds) {
    Write-Host "TRUE GAP (real unstun timestamp -> acquisition start): $trueGapSeconds s"
    Write-Host "Measured checkpoint duration (trigger -> real unstun timestamp): $measuredCheckpointDuration s"
} else {
    Write-Host "TRUE GAP: could not be computed (marker not found post-hoc)"
}
Write-Host "Acquisition duration:    $($acquisitionDuration.TotalSeconds) s"
Write-Host "Snapshot duration (trigger->vmrun exit, legacy-comparable): $($snapshotDuration.TotalSeconds) s"
Write-Host "Legacy-style gap (vmrun exit -> acquire start, now uninteresting): $($legacyGap.TotalSeconds) s"

# Record the timing
$trueGapArg = if ($null -ne $trueGapSeconds) { $trueGapSeconds } else { -1 }
$measuredCheckpointArg = if ($null -ne $measuredCheckpointDuration) { $measuredCheckpointDuration } else { -1 }

python $RecordTimingScript --xlsx $XlsxPath --config $Config --run $RunNumber `
    --snapshot-duration $snapshotDuration.TotalSeconds `
    --acquisition-duration $acquisitionDuration.TotalSeconds `
    --gap $legacyGap.TotalSeconds `
    --true-gap $trueGapArg `
    --configured-delay $UnstunDelaySeconds `
    --measured-checkpoint-duration $measuredCheckpointArg `
    --memory-usage $memoryUsage
