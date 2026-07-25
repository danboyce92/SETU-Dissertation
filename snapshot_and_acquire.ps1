
#CONFIG
$VmrunPath      = "C:\Program Files\VMware\VMware Workstation\vmrun.exe"
$VmxPath        = "E:\VMLocations\VM01 Win10 8Gb.vmx"
$SnapshotName   = "Test1"

$GuestUser      = "winpmem-admin"
$GuestPassword  = "Password123!"

$GuestWinpmem   = "\\vmware-host\Shared Folders\SharedFolder\winpmem\go-winpmem_amd64_1.0-rc2_signed.exe"
$GuestOutput    = "\\vmware-host\Shared Folders\SharedFolder\Acquisitions\Tests\acquisition.raw"

# Take the snapshot 
Write-Host "Taking snapshot '$SnapshotName'..."
& $VmrunPath -T ws snapshot $VmxPath $SnapshotName

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: snapshot failed (exit code $LASTEXITCODE). Aborting."
    exit 1
}
Write-Host "Snapshot complete."

# Run Acquisition
Write-Host "Starting WinPmem acquisition inside guest..."
& $VmrunPath -T ws -gu $GuestUser -gp $GuestPassword runProgramInGuest $VmxPath `
    $GuestWinpmem acquire --nosparse $GuestOutput

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: acquisition failed (exit code $LASTEXITCODE)."
    exit 1
}
Write-Host "Acquisition complete: $GuestOutput"
