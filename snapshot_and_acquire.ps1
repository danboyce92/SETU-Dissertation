
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SnapshotName,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$OutputFileName
)

#CONFIG
$VmrunPath      = "C:\Program Files\VMware\VMware Workstation\vmrun.exe"
$VmxPath        = "E:\VMLocations\VM01 Win10 8Gb.vmx"

$GuestUser      = "winpmem-admin"
$GuestPassword  = "Password123!"

$GuestWinpmem   = "\\vmware-host\Shared Folders\SharedFolder\winpmem\go-winpmem_amd64_1.0-rc2_signed.exe"
$GuestOutput    = "\\vmware-host\Shared Folders\SharedFolder\Acquisitions\Tests\$OutputFileName"

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
