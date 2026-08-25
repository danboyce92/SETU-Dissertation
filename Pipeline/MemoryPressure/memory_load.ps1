param(
    [int]$PressurePercent,
    [string]$LogPath,
    [int]$HoldSeconds = 900
)

# Allocates a percentage of CURRENTLY FREE memory 
try {
    # Try block necessary due to hanging in previous runs
    $nativeMethods = @"
    using System;
    using System.Runtime.InteropServices;

    public static class NativeMemory {
        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool VirtualLock(IntPtr lpAddress, UIntPtr dwSize);

        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool SetProcessWorkingSetSize(IntPtr hProcess, IntPtr dwMinimumWorkingSetSize, IntPtr dwMaximumWorkingSetSize);

        [DllImport("kernel32.dll")]
        public static extern IntPtr GetCurrentProcess();
    }
"@
    Add-Type -TypeDefinition $nativeMethods -ErrorAction Stop

    $freeMB = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024
    $loadMB = [long]($freeMB * $PressurePercent / 100)
    $total = $loadMB * 1MB
    [long]$chunkSize = 500MB

    # Raise the process's working-set
    $wsTarget = [IntPtr]($total + 200MB)
    $wsResult = [NativeMemory]::SetProcessWorkingSetSize([NativeMemory]::GetCurrentProcess(), $wsTarget, $wsTarget)
    if (-not $wsResult) {
        throw "SetProcessWorkingSetSize failed (target ${wsTarget} bytes): Win32 error $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }

    $chunks = @()
    $handles = @()
    $written = 0

    while ($written -lt $total) {
        $sz = [Math]::Min($chunkSize, $total - $written)
        $b = New-Object byte[] $sz
        (New-Object Random).NextBytes($b)

        $handle = [System.Runtime.InteropServices.GCHandle]::Alloc($b, [System.Runtime.InteropServices.GCHandleType]::Pinned)
        $addr = $handle.AddrOfPinnedObject()
        $locked = [NativeMemory]::VirtualLock($addr, [UIntPtr][UInt64]$sz)
        if (-not $locked) {
            throw "VirtualLock failed on chunk at offset $written (size $sz): Win32 error $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error())"
        }

        $chunks += ,$b
        $handles += $handle
        $written += $sz
    }

    "SUCCESS: free was ${freeMB}MB, allocated and locked $written bytes ($PressurePercent% of free) at $(Get-Date)" | Out-File $LogPath
    Start-Sleep -Seconds $HoldSeconds
}
catch {
    "FAILED: $($_.Exception.Message) at $(Get-Date)" | Out-File $LogPath
}
