param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$stdout = Join-Path $output "bandit.stdout.txt"
$stderr = Join-Path $output "bandit.stderr.txt"
$json = Join-Path $output "bandit.json"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPYCACHEPREFIX = Join-Path $output "python-cache"
$uv = (Get-Command uv -ErrorAction Stop).Source
$quotedRoot = '"' + $root + '"'
$arguments = "run --active --locked --no-sync --directory $quotedRoot bandit -r src -f json"
$command = "`"$uv`" $arguments"

$process = Start-Process -FilePath $uv -ArgumentList $arguments -WorkingDirectory $root `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr -Wait -PassThru
if (Test-Path -LiteralPath $env:PYTHONPYCACHEPREFIX) {
    Remove-Item -LiteralPath $env:PYTHONPYCACHEPREFIX -Recurse -Force
}

$jsonValid = $false
if (Test-Path -LiteralPath $stdout) {
    try {
        $rawJson = [System.IO.File]::ReadAllText($stdout)
        $null = $rawJson | ConvertFrom-Json -ErrorAction Stop
        [System.IO.File]::Copy($stdout, $json, $true)
        $jsonValid = $true
    }
    catch {
        Write-Output "Bandit stdout was not valid JSON; raw stdout and stderr remain preserved."
    }
}

Write-Output "Command: $command"
Write-Output "Bandit exit code: $($process.ExitCode)"
Write-Output "Machine-readable JSON valid: $jsonValid"
if (-not $jsonValid) {
    exit 2
}
exit $process.ExitCode
