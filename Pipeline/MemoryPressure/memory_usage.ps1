param(
    [string]$LogPath
)

# Identifies current memory usage and returns to logpath
$os = Get-CimInstance Win32_OperatingSystem
$totalKB = $os.TotalVisibleMemorySize
$freeKB = $os.FreePhysicalMemory
$usedPercent = [math]::Round((($totalKB - $freeKB) / $totalKB) * 100, 2)

$usedPercent | Out-File $LogPath
