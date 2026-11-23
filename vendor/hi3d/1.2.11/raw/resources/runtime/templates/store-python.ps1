# No named parameters: every argument belongs to Python, including -c and -m.
$pythonArguments = @($args | ForEach-Object { [string]$_ })
$TimeoutSeconds = 300
$ErrorActionPreference = 'Stop'

function Quote-NativeArgument([string]$Value) {
    # Windows CommandLineToArgvW quoting, including trailing backslashes.
    return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}

$jobDirectory = $null
try {
    $python = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{{STORE_PYTHON_BASE64}}'))
    $cwd = (Get-Location).Path
    if (-not (Test-Path -LiteralPath $cwd -PathType Container)) { throw 'WorkingDirectory must be a directory' }
    $packageRoot = Split-Path -Parent $python
    while ($packageRoot -and -not (Test-Path -LiteralPath (Join-Path $packageRoot 'AppxManifest.xml'))) {
        $packageRoot = Split-Path -Parent $packageRoot
    }
    if (-not $packageRoot) { throw 'Python is not inside an installed Store package' }
    [xml]$manifest = Get-Content -LiteralPath (Join-Path $packageRoot 'AppxManifest.xml') -Raw
    $package = Get-AppxPackage -Name $manifest.Package.Identity.Name | Where-Object { $_.InstallLocation -eq $packageRoot } | Select-Object -First 1
    if (-not $package) { throw 'The Python Store package is not registered for the current user' }
    $jobDirectory = Join-Path $cwd ('.hi3d-python-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $jobDirectory | Out-Null
    $requestPath = Join-Path $jobDirectory 'request.json'
    $payload = @{ python = $python; cwd = $cwd; arguments = $pythonArguments; timeout = $TimeoutSeconds }
    [IO.File]::WriteAllText($requestPath, ($payload | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    # Activate the existing GUI executable in its dedicated background mode.
    # No PowerShell console or VBScript host is created by this activation.
    $application = @($manifest.Package.Applications.Application)[0]
    $hostExecutable = Join-Path $packageRoot $application.Executable
    $workerArguments = '--hi3d-store-python-request ' + (Quote-NativeArgument $requestPath)
    Invoke-CommandInDesktopPackage -PackageFamilyName $package.PackageFamilyName -AppId $application.Id -PreventBreakaway -Command $hostExecutable -Args $workerArguments
    $resultPath = Join-Path $jobDirectory 'result.json'
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds + 15)
    while (-not (Test-Path -LiteralPath $resultPath)) {
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Store Python activation did not return a result before the deadline' }
        Start-Sleep -Milliseconds 100
    }
    $result = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
    [Console]::Out.Write([string]$result.stdout)
    [Console]::Error.Write([string]$result.stderr)
    exit [int]$result.exitCode
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
} finally {
    # Only remove this invocation's fresh, explicitly named directory.
    if ($jobDirectory -and (Test-Path -LiteralPath (Join-Path $jobDirectory 'result.json'))) {
        $cleanupPath = [IO.Path]::GetFullPath($jobDirectory)
        if ((Split-Path -Parent $cleanupPath) -ne $cwd -or (Split-Path -Leaf $cleanupPath) -notmatch '^\.hi3d-python-[a-f0-9]{32}$') { throw 'Refusing to remove an unexpected request directory' }
        Remove-Item -LiteralPath $cleanupPath -Recurse -Force
    }
}
