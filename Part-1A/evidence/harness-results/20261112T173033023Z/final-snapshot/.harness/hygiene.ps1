param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$TrackedRoot = $ProjectRoot
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$trackedRoot = (Resolve-Path -LiteralPath $TrackedRoot).Path
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$reportPath = Join-Path $output "hygiene.json"
$fixtureRoot = Join-Path $output "synthetic-scanner-fixtures"
New-Item -ItemType Directory -Force -Path $fixtureRoot | Out-Null

$fixtures = @(
    @{
        path = Join-Path $fixtureRoot ".env.synthetic"
        content = ("API_TOKEN=" + "fixture-value-only-not-a-real-credential-123456")
    },
    @{
        path = Join-Path $fixtureRoot "synthetic-private-key.pem"
        content = ("-----BEGIN " + "PRIVATE KEY-----`nFIXTURE ONLY - NOT A KEY`n-----END " + "PRIVATE KEY-----")
    },
    @{
        path = Join-Path $fixtureRoot "synthetic-credentials.txt"
        content = ("password=" + "fixture-only-not-a-real-password-123456")
    }
)
foreach ($fixture in $fixtures) {
    [System.IO.File]::WriteAllText($fixture.path, $fixture.content, [System.Text.UTF8Encoding]::new($false))
}

function Get-ContentFindings {
    param(
        [string]$RelativePath,
        [string]$Content
    )
    $findings = @()
    $leaf = [System.IO.Path]::GetFileName($RelativePath)
    if (($leaf -eq ".env" -or $leaf -match "^\.env\..+") -and $leaf -ne ".env.example") {
        $findings += "environment-file"
    }
    if ($Content -match "-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----") {
        $findings += "private-key"
    }
    if ($Content -match "(?im)\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|password|passwd|secret)\b\s*[:=]\s*(['""]?)(?!DUMMY\b|SYNTHETIC\b|example\b|changeme\b)[A-Za-z0-9._~+\/=-]{12,}") {
        $findings += "credential-like-value"
    }
    if ($Content -match "\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b") {
        $findings += "known-token-format"
    }
    return @($findings | Select-Object -Unique)
}

$fixtureChecks = @()
foreach ($fixture in $fixtures) {
    $content = [System.IO.File]::ReadAllText($fixture.path)
    $rules = @(Get-ContentFindings -RelativePath $fixture.path -Content $content)
    $expectedRule = if ([System.IO.Path]::GetFileName($fixture.path).StartsWith(".env")) { "environment-file" } `
        elseif ($fixture.path.EndsWith(".pem")) { "private-key" } else { "credential-like-value" }
    $fixtureChecks += [pscustomobject]@{
        fixture = [System.IO.Path]::GetFileName($fixture.path)
        expectedRule = $expectedRule
        detected = ($rules -contains $expectedRule)
    }
}

$gitRootText = & git -C $trackedRoot rev-parse --show-toplevel 2>$null
if ($LASTEXITCODE -ne 0 -or -not $gitRootText) {
    throw "Unable to establish the Git repository root for hygiene checks."
}
$gitRoot = [System.IO.Path]::GetFullPath(($gitRootText | Select-Object -First 1).Trim())
$trackedOutput = & git -C $trackedRoot ls-files 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to list tracked files for repository hygiene checks."
}

$trackedPaths = @()
foreach ($trackedPath in $trackedOutput) {
    $normalized = ([string]$trackedPath).Replace("\", "/")
    $projectPrefix = (Split-Path -Leaf $trackedRoot).Replace("\", "/") + "/"
    if ($normalized.StartsWith($projectPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring($projectPrefix.Length)
    }
    $trackedSourcePath = Join-Path $trackedRoot ($normalized.Replace("/", "\"))
    if (Test-Path -LiteralPath $trackedSourcePath -PathType Leaf) {
        $trackedPaths += $normalized
    }
}

$findings = @()
foreach ($path in $trackedPaths) {
    $leaf = [System.IO.Path]::GetFileName($path)
    if (($leaf -eq ".env" -or $leaf -match "^\.env\..+") -and $leaf -ne ".env.example") {
        $findings += [pscustomobject]@{ path = $path; rule = "tracked-environment-file" }
    }
    if ($path -match "(^|/)(\.venv|__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache|data)(/|$)" -or
        $path -match "\.(pyc|pyo|tmp)$" -or $path -match "(^|/)\.coverage($|[.-])") {
        $findings += [pscustomobject]@{ path = $path; rule = "tracked-generated-data" }
    }
    $fullPath = Join-Path $root ($path.Replace("/", "\"))
    if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
        $extension = [System.IO.Path]::GetExtension($fullPath).ToLowerInvariant()
        if ($extension -in @(".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".ps1", ".ini", ".cfg", ".pem", ".key", ".env")) {
            $content = [System.IO.File]::ReadAllText($fullPath)
            foreach ($rule in (Get-ContentFindings -RelativePath $path -Content $content)) {
                if ($rule -ne "environment-file") {
                    $findings += [pscustomobject]@{ path = $path; rule = $rule }
                }
            }
        }
    }
}

$actualCandidateFiles = @(Get-ChildItem -LiteralPath $root -File -Recurse -Force | Where-Object {
    $relative = $_.FullName.Substring($root.Length + 1).Replace("\", "/")
    $segments = $relative.Split("/")
    $skip = $false
    foreach ($segment in $segments) {
        if ($segment -in @(".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", "build", "dist", "data", "evidence")) {
            $skip = $true
        }
    }
    -not $skip -and $_.Extension.ToLowerInvariant() -in @(".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".ps1", ".ini", ".cfg", ".pem", ".key", ".env")
})
foreach ($file in $actualCandidateFiles) {
    $relative = $file.FullName.Substring($root.Length + 1).Replace("\", "/")
    $content = [System.IO.File]::ReadAllText($file.FullName)
    foreach ($rule in (Get-ContentFindings -RelativePath $relative -Content $content)) {
        $findings += [pscustomobject]@{ path = $relative; rule = $rule }
    }
}
$findings = @($findings | Sort-Object path, rule -Unique)
$fixturePass = @($fixtureChecks | Where-Object { -not $_.detected }).Count -eq 0
$record = [pscustomobject]@{
    trackedFileCount = $trackedPaths.Count
    candidateTextFileCount = $actualCandidateFiles.Count
    syntheticFixtureChecks = $fixtureChecks
    syntheticFixtureChecksPassed = $fixturePass
    findingCount = $findings.Count
    findings = $findings
    secretsOmitted = $true
}
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8

Write-Output "Tracked files inspected: $($trackedPaths.Count)"
Write-Output "Publication-candidate text files inspected: $($actualCandidateFiles.Count)"
Write-Output "Synthetic scanner fixtures passed: $fixturePass"
Write-Output "Hygiene findings: $($findings.Count)"
Write-Output "Hygiene report: $reportPath"
if (-not $fixturePass -or $findings.Count -gt 0) {
    exit 1
}
exit 0
