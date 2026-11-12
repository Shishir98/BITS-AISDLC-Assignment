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
$stdout = Join-Path $output "ruff.stdout.txt"
$stderr = Join-Path $output "ruff.stderr.txt"
$uv = (Get-Command uv -ErrorAction Stop).Source
$quotedRoot = '"' + $root + '"'
$arguments = "run --active --locked --no-sync --directory $quotedRoot ruff check src tests"
$command = "`"$uv`" $arguments"

$process = Start-Process -FilePath $uv -ArgumentList $arguments -WorkingDirectory $root `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr -Wait -PassThru

Write-Output "Command: $command"
Write-Output "Ruff exit code: $($process.ExitCode)"
exit $process.ExitCode
