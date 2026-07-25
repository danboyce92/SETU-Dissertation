
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SnapshotName,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$OutputFileName,

    #Load pressure level
    [Parameter(Position = 2)]
    [ValidateSet(0, 1, 2)]
    [int]$Pressure = 0
)

#CONFIG
$VmrunPath      = "C:\Program Files\VMware\VMware Workstation\vmrun.exe"
$VmxPath        = "E:\VMLocations\VM01 Win10 8Gb.vmx"

$GuestUser      = "winpmem-admin"
$GuestPassword  = "Password123!"

$GuestWinpmem   = "\\vmware-host\Shared Folders\SharedFolder\winpmem\go-winpmem_amd64_1.0-rc2_signed.exe"
$GuestOutput    = "\\vmware-host\Shared Folders\SharedFolder\Acquisitions\Tests\$OutputFileName"

#Kill any previous load that needs cleaning up from a previous run
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
        -File $loadScript -PressurePercent $pressurePercent -LogPath $loadLog -HoldSeconds 900

    Write-Host "Waiting for memory load to settle..."
    Start-Sleep -Seconds 15
}

# Take the snapshot 
Write-Host "Taking snapshot '$SnapshotName'..."
$snapshotStart = Get-Date
& $VmrunPath -T ws snapshot $VmxPath $SnapshotName
$snapshotEnd = Get-Date

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: snapshot failed (exit code $LASTEXITCODE). Aborting."
    exit 1
}
Write-Host "Snapshot complete."

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

# Timing summary
$snapshotDuration = $snapshotEnd - $snapshotStart
$acquisitionDuration = $acquisitionEnd - $acquisitionStart
$gap = $acquisitionStart - $snapshotEnd

Write-Host "`n--- Timing summary ---"
Write-Host "Snapshot duration:       $($snapshotDuration.TotalSeconds) s"
Write-Host "Gap (snapshot->acquire): $($gap.TotalSeconds) s"
Write-Host "Acquisition duration:    $($acquisitionDuration.TotalSeconds) s"
