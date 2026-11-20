$ErrorActionPreference = 'Stop'

$listener = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $owners = ($listener | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
    throw "Port 11434 is already listening (PID $owners). Stop that Ollama process manually, then rerun this script."
}

$ollamaCommand = Get-Command 'ollama.exe' -ErrorAction SilentlyContinue
if (-not $ollamaCommand) {
    $ollamaCommand = Get-Command 'ollama' -ErrorAction Stop
}

$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
if ($env:OLLAMA_NO_CLOUD -ne '1' -or $env:OLLAMA_HOST -ne '127.0.0.1:11434') {
    throw 'The local-only Ollama server environment could not be established.'
}

$server = Start-Process -FilePath $ollamaCommand.Source -ArgumentList 'serve' -PassThru -NoNewWindow
$deadline = [DateTimeOffset]::UtcNow.AddSeconds(45)
$version = $null
$inventory = $null
while ([DateTimeOffset]::UtcNow -lt $deadline) {
    if ($server.HasExited) {
        throw "The Ollama server process exited with code $($server.ExitCode)."
    }
    try {
        $version = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
        $inventory = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
        break
    }
    catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $version -or -not $inventory) {
    Stop-Process -Id $server.Id
    throw 'The Ollama server did not become ready within 45 seconds.'
}

$evidenceDirectory = Join-Path $PSScriptRoot '..\evidence\local-runtime'
New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
$evidence = [ordered]@{
    schema_version = 1
    verified = $true
    verification_method = 'Controlled PowerShell launcher set OLLAMA_NO_CLOUD before starting this Ollama process; the child process inherits its launch environment.'
    ollama_no_cloud = $env:OLLAMA_NO_CLOUD
    ollama_host = $env:OLLAMA_HOST
    server_started_after_setting = $true
    process_id = $server.Id
    process_name = 'ollama.exe'
    launched_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    ollama_version = $version.version
    local_model_inventory = $inventory.models
}
$evidencePath = Join-Path $evidenceDirectory 'ollama-server-process.json'
$evidence | ConvertTo-Json -Depth 12 | Set-Content -Path $evidencePath -Encoding utf8

Write-Output "Ollama is running as PID $($server.Id) on 127.0.0.1:11434."
Write-Output "OLLAMA_NO_CLOUD=1 was set before process launch; evidence: $evidencePath"
Write-Output 'Confirm the configured model is installed in ollama list and /api/tags before evaluation.'
