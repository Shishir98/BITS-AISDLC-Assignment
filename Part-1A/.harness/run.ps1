param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$EvidenceRoot = "",
    [switch]$LocalDevelopment
)

$ErrorActionPreference = "Stop"

function Write-DetachedEvidenceManifest {
    param(
        [string]$RunDirectory,
        [string]$EvidenceDirectory,
        [string]$RunIdentifier,
        [string]$CandidateDigest
    )

    $files = @(Get-ChildItem -LiteralPath $RunDirectory -File -Recurse -Force |
        Sort-Object { $_.FullName.Substring($RunDirectory.Length + 1).Replace("\", "/") })
    $entries = @()
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($RunDirectory.Length + 1).Replace("\", "/")
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $entries += [pscustomobject]@{ path = $relative; sha256 = $hash }
    }
    $canonical = ($entries | ForEach-Object { "$($_.path)  $($_.sha256)" }) -join "`n"
    $encoding = [System.Text.UTF8Encoding]::new($false)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = ([BitConverter]::ToString($sha.ComputeHash($encoding.GetBytes($canonical)))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
    $record = [pscustomobject]@{
        schemaVersion = 1
        runId = $RunIdentifier
        candidateDigest = $CandidateDigest
        generatedAt = [DateTimeOffset]::UtcNow.ToString("o")
        bundleDigest = $digest
        files = $entries
    }
    $manifestPath = Join-Path $EvidenceDirectory "$RunIdentifier.evidence-manifest.json"
    $record | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    return [pscustomobject]@{ path = $manifestPath; digest = $digest }
}

trap {
    $observedError = $_.ToString()
    if ($runRoot -and (Test-Path -LiteralPath $runRoot)) {
        try {
            $recoveryFailureRoot = Join-Path $runRoot "failures"
            New-Item -ItemType Directory -Force -Path $recoveryFailureRoot | Out-Null
            $recoveryFailurePath = Join-Path $recoveryFailureRoot "orchestrator.txt"
            [System.IO.File]::WriteAllText(
                $recoveryFailurePath,
                $observedError,
                [System.Text.UTF8Encoding]::new($false)
            )
            $recoveryGates = @()
            if ($allGates) {
                $recoveryGates = @($allGates)
            }
            $recoveryGates += [pscustomobject]@{
                name = "orchestrator"
                status = "FAIL"
                command = "Execute repository-candidate diagnostic orchestration"
                exitCode = 1
                startedAt = [DateTimeOffset]::UtcNow.ToString("o")
                finishedAt = [DateTimeOffset]::UtcNow.ToString("o")
                stdoutReference = ""
                stderrReference = "failures/orchestrator.txt"
                outputReferences = @("failures/orchestrator.txt")
            }
            $recoveryDigest = ""
            if ($initialManifest) {
                $recoveryDigest = [string]$initialManifest.digest
            }
            $recoveryResults = [pscustomobject]@{
                schemaVersion = 1
                runId = $runId
                validationMode = "repository-candidate-diagnostic-only"
                authoritative = $false
                decision = $null
                candidateDigest = $recoveryDigest
                finalCandidateDigest = ""
                startedAt = $startedAt
                finishedAt = [DateTimeOffset]::UtcNow.ToString("o")
                status = "FAILED"
                orchestrationError = $observedError
                gates = $recoveryGates
                outputDirectory = $runRoot
            }
            $recoveryResults | ConvertTo-Json -Depth 12 |
                Set-Content -LiteralPath (Join-Path $runRoot "results.json") -Encoding UTF8
            if ($evidenceBase -and $runId) {
                $null = Write-DetachedEvidenceManifest -RunDirectory $runRoot `
                    -EvidenceDirectory $evidenceBase -RunIdentifier $runId `
                    -CandidateDigest $recoveryDigest
            }
        }
        catch {
            [Console]::Error.WriteLine("Unable to persist the orchestration failure record: $($_.ToString())")
        }
    }
    [Console]::Error.WriteLine($observedError)
    exit 1
}

if (-not $LocalDevelopment) {
    [Console]::Error.WriteLine(
        "This repository runner is an untrusted candidate. D-01 has no demonstrated protected baseline or separate execution boundary; use -LocalDevelopment only for non-authoritative diagnostics."
    )
    exit 2
}

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$projectEnvironment = Join-Path $root ".venv"
if (Test-Path -LiteralPath (Join-Path $projectEnvironment "Scripts\python.exe")) {
    $env:VIRTUAL_ENV = $projectEnvironment
    $env:PATH = (Join-Path $projectEnvironment "Scripts") + ";" + $env:PATH
}
if (-not $EvidenceRoot) {
    $EvidenceRoot = Join-Path $env:LOCALAPPDATA "SmartTodoValidation\Part-1A"
}
$evidenceBase = [System.IO.Path]::GetFullPath($EvidenceRoot)
$rootPrefix = $root.TrimEnd("\") + "\"
if ($evidenceBase.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or
    $evidenceBase.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "EvidenceRoot must be outside the validation candidate."
}

$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMdd'T'HHmmssfff'Z'")
$runRoot = Join-Path $evidenceBase $runId
$initialSnapshot = Join-Path $runRoot "initial-snapshot"
$stagedRoot = Join-Path $runRoot "staged-candidate"
$finalSnapshot = Join-Path $runRoot "final-snapshot"
$gateRoot = Join-Path $runRoot "gates"
$failureRoot = Join-Path $runRoot "failures"
foreach ($directory in @($initialSnapshot, $stagedRoot, $finalSnapshot, $gateRoot, $failureRoot)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

function Get-CandidateFiles {
    param([string]$BasePath)

    $excludedDirectories = @(
        ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
        ".mypy_cache", ".tox", "build", "dist", "data", "evidence"
    )
    $excludedSuffixes = @(".pyc", ".pyo", ".tmp", ".log")
    $files = @(Get-ChildItem -LiteralPath $BasePath -File -Recurse -Force | Where-Object {
        $relative = $_.FullName.Substring($BasePath.Length + 1).Replace("\", "/")
        $segments = $relative.Split("/")
        $skip = $false
        foreach ($segment in $segments) {
            if ($segment -in $excludedDirectories) {
                $skip = $true
            }
        }
        -not $skip -and $_.Extension.ToLowerInvariant() -notin $excludedSuffixes
    })
    return @($files | Sort-Object { $_.FullName.Substring($BasePath.Length + 1).Replace("\", "/") })
}

function Get-Manifest {
    param(
        [string]$BasePath,
        [System.IO.FileInfo[]]$Files
    )

    $entries = @()
    foreach ($file in $Files) {
        if (($file.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Reparse points are not allowed in the candidate: $($file.FullName.Substring($BasePath.Length + 1))"
        }
        $relative = $file.FullName.Substring($BasePath.Length + 1).Replace("\", "/")
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $entries += [pscustomobject]@{ path = $relative; sha256 = $hash }
    }
    $canonical = ($entries | ForEach-Object { "$($_.path)  $($_.sha256)" }) -join "`n"
    $encoding = [System.Text.UTF8Encoding]::new($false)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = ([BitConverter]::ToString($sha.ComputeHash($encoding.GetBytes($canonical)))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
    return [pscustomobject]@{ digest = $digest; files = $entries }
}

function Copy-Candidate {
    param(
        [string]$BasePath,
        [System.IO.FileInfo[]]$Files,
        [string]$Destination
    )

    foreach ($file in $Files) {
        $relative = $file.FullName.Substring($BasePath.Length + 1)
        $destinationFile = Join-Path $Destination $relative
        $parent = Split-Path -Parent $destinationFile
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destinationFile -Force
    }
}

function Add-InternalGate {
    param(
        [string]$Name,
        [string]$Status,
        [int]$ExitCode,
        [string]$Command,
        [string]$Message
    )
    $now = [DateTimeOffset]::UtcNow.ToString("o")
    return [pscustomobject]@{
        name = $Name
        status = $Status
        command = $Command
        exitCode = $ExitCode
        startedAt = $now
        finishedAt = $now
        stdoutReference = ""
        stderrReference = ""
        outputReferences = @()
        message = $Message
    }
}

function Invoke-ComponentGate {
    param(
        [string]$Name,
        [string]$ScriptName,
        [string]$ScriptOutputName,
        [string[]]$ExtraOutputNames = @(),
        [string]$TrackedRoot = ""
    )
    $outputDirectory = Join-Path $gateRoot $Name
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    $stdoutPath = Join-Path $outputDirectory "$ScriptOutputName.stdout.txt"
    $stderrPath = Join-Path $outputDirectory "$ScriptOutputName.stderr.txt"
    $scriptPath = Join-Path $stagedRoot ".harness\$ScriptName"
    $powerShellPath = (Get-Process -Id $PID).Path
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -ProjectRoot "{1}" -OutputDirectory "{2}"' -f `
        $scriptPath, $stagedRoot, $outputDirectory
    if ($ScriptName -eq "test.ps1") {
        $arguments += ' -ConfigurationPath "' + (Join-Path $stagedRoot ".harness\mandatory-checks.json") + '"'
    }
    if ($ScriptName -eq "hygiene.ps1") {
        $arguments += ' -TrackedRoot "' + $TrackedRoot + '"'
    }
    $command = "`"$powerShellPath`" $arguments"
    $started = [DateTimeOffset]::UtcNow.ToString("o")
    $process = $null
    $exitCode = 1
    try {
        $process = Start-Process -FilePath $powerShellPath -ArgumentList $arguments `
            -WorkingDirectory $stagedRoot -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath -Wait -PassThru
        $exitCode = [int]$process.ExitCode
    }
    catch {
        [System.IO.File]::WriteAllText($stderrPath, $_.ToString(), [System.Text.UTF8Encoding]::new($false))
    }
    $finished = [DateTimeOffset]::UtcNow.ToString("o")
    $status = if ($exitCode -eq 0) { "PASS" } else { "FAIL" }
    $references = @()
    foreach ($outputReference in @("$Name/$ScriptOutputName.stdout.txt", "$Name/$ScriptOutputName.stderr.txt") + $ExtraOutputNames) {
        if (Test-Path -LiteralPath (Join-Path $gateRoot $outputReference)) {
            $references += "gates/$outputReference"
        }
    }
    $gate = [pscustomobject]@{
        name = $Name
        status = $status
        command = $command
        exitCode = $exitCode
        startedAt = $started
        finishedAt = $finished
        stdoutReference = "gates/$Name/$ScriptOutputName.stdout.txt"
        stderrReference = "gates/$Name/$ScriptOutputName.stderr.txt"
        outputReferences = $references
    }
    if ($status -ne "PASS") {
        $failurePath = Join-Path $failureRoot "$Name.txt"
        $observed = @(
            "Gate: $Name"
            "Command: $command"
            "Exit code: $exitCode"
            "Started: $started"
            "Finished: $finished"
            "--- stdout ---"
            if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw }
            "--- stderr ---"
            if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw }
        ) -join "`r`n"
        [System.IO.File]::WriteAllText($failurePath, $observed, [System.Text.UTF8Encoding]::new($false))
        $gate | Add-Member -NotePropertyName failureReportReference -NotePropertyValue "failures/$Name.txt"
    }
    return $gate
}

$allGates = @()
$startedAt = [DateTimeOffset]::UtcNow.ToString("o")
$candidateFiles = @(Get-CandidateFiles -BasePath $root)
$initialManifest = Get-Manifest -BasePath $root -Files $candidateFiles
Copy-Candidate -BasePath $root -Files $candidateFiles -Destination $initialSnapshot
Copy-Candidate -BasePath $root -Files $candidateFiles -Destination $stagedRoot
$initialManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $runRoot "candidate-manifest.json") -Encoding UTF8
$stageFiles = @(Get-CandidateFiles -BasePath $stagedRoot)
$stageManifest = Get-Manifest -BasePath $stagedRoot -Files $stageFiles
$mandatoryChecksPath = Join-Path $stagedRoot ".harness\mandatory-checks.json"
$mandatoryChecks = Get-Content -LiteralPath $mandatoryChecksPath -Raw | ConvertFrom-Json -ErrorAction Stop

if ($stageManifest.digest -eq $initialManifest.digest) {
    $allGates += Add-InternalGate -Name "candidate-integrity-before" -Status "PASS" -ExitCode 0 `
        -Command "SHA-256 candidate manifest comparison (source to staged snapshot)" `
        -Message "The staged bytes match the source candidate manifest."
}
else {
    $allGates += Add-InternalGate -Name "candidate-integrity-before" -Status "FAIL" -ExitCode 1 `
        -Command "SHA-256 candidate manifest comparison (source to staged snapshot)" `
        -Message "The staged snapshot differs from the source candidate."
}

$inventoryPath = Join-Path $stagedRoot ".harness\instruction-files.json"
$inventoryIssues = @()
if (-not (Test-Path -LiteralPath $inventoryPath)) {
    $inventoryIssues += "instruction-files.json is missing."
}
else {
    try {
        $inventory = Get-Content -LiteralPath $inventoryPath -Raw | ConvertFrom-Json -ErrorAction Stop
        $paths = @()
        foreach ($entry in $inventory) {
            $keys = @($entry.PSObject.Properties | ForEach-Object { [string]$_.Name })
            $requiredKeys = @("path", "purpose", "classification", "sha256", "approval_reference")
            $missingKeys = @($requiredKeys | Where-Object { $keys -notcontains $_ })
            $extraKeys = @($keys | Where-Object { $requiredKeys -notcontains $_ })
            if ($keys.Count -ne $requiredKeys.Count -or $missingKeys.Count -gt 0 -or $extraKeys.Count -gt 0) {
                $inventoryIssues += "An inventory entry does not contain exactly the required keys."
                continue
            }
            $path = [string]$entry.path
            if (-not $path -or $path -match "[*?]" -or [System.IO.Path]::IsPathRooted($path)) {
                $inventoryIssues += "An inventory path is empty, rooted, or contains a wildcard."
                continue
            }
            $paths += $path.Replace("\", "/")
            $filePath = Join-Path $stagedRoot ($path.Replace("/", "\"))
            if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
                $inventoryIssues += "An inventoried instruction file is missing: $path"
                continue
            }
            $actualHash = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualHash -ne ([string]$entry.sha256).ToLowerInvariant()) {
                $inventoryIssues += "An inventoried instruction digest does not match: $path"
            }
            if (-not [string]$entry.approval_reference) {
                $inventoryIssues += "An inventory approval reference is not present for: $path"
            }
        }
        if (($paths | Sort-Object -Unique).Count -ne $paths.Count) {
            $inventoryIssues += "The instruction inventory contains duplicate paths."
        }
    }
    catch {
        $inventoryIssues += "The instruction inventory is not valid JSON."
    }
}
if ($inventoryIssues.Count -eq 0) {
    $allGates += Add-InternalGate -Name "instruction-inventory" -Status "PASS" -ExitCode 0 `
        -Command "Validate exact instruction inventory entries and listed-file SHA-256 values" `
        -Message "All inventoried files and approval references verified."
}
else {
    $allGates += Add-InternalGate -Name "instruction-inventory" -Status "FAIL" -ExitCode 1 `
        -Command "Validate exact instruction inventory entries and listed-file SHA-256 values" `
        -Message ($inventoryIssues -join " ")
}

$allGates += Add-InternalGate -Name "governance-boundary" -Status "BLOCKED" -ExitCode 2 `
    -Command "Verify protected GitHub main workflow, human-approved baseline, and successful protected run" `
    -Message "D-01 design direction is closed on GitHub, but the workflow remains a repository candidate; its baseline is pending approval and no protected workflow run has been verified. Local gate output is diagnostic only."

$persistenceReadiness = $mandatoryChecks.persistenceContractReadiness
$d05ConfigValid = $null -ne $persistenceReadiness -and
    [string]$persistenceReadiness.d05Status -ceq "RESOLVED_BY_APPROVED_SPEC_AMENDMENT" -and
    [string]$persistenceReadiness.approvedSpecVersion -ceq "1.4.0" -and
    [string]$persistenceReadiness.humanApprovalDate -ceq "2026-11-13" -and
    $persistenceReadiness.applicationHandledRecoveryContractApproved -eq $true -and
    $persistenceReadiness.atomicVisibilityGuaranteed -eq $false -and
    $persistenceReadiness.crashDurabilityGuaranteed -eq $false -and
    $persistenceReadiness.rollbackTestsEstablishAtomicVisibility -eq $false -and
    @($persistenceReadiness.evidenceReferences).Count -eq 0
if ($d05ConfigValid) {
    $d05Gate = Add-InternalGate -Name "persistence-contract-readiness" -Status "PASS" -ExitCode 0 `
        -Command "Verify approved v1.4.0 application-level persistence contract" `
        -Message "D-05 resolved by human approval dated 2026-11-13. This gate asserts no Windows atomic-visibility or crash-durability guarantee."
}
else {
    $d05Gate = Add-InternalGate -Name "persistence-contract-readiness" -Status "FAIL" -ExitCode 1 `
        -Command "Verify approved v1.4.0 application-level persistence contract" `
        -Message "D-05 amendment controls are missing or inconsistent; no platform-guarantee claim is permitted."
    $d05FailurePath = Join-Path $failureRoot "persistence-contract-readiness.txt"
    $d05FailureReport = @(
        "Gate: persistence-contract-readiness"
        "Requirement: D-05 was resolved by the human-approved v1.4.0 application-level backup and recovery amendment."
        "Expected: Approval date 2026-11-13; no Windows atomic-visibility or crash-durability guarantee."
        "Observed status: $([string]$persistenceReadiness.d05Status)"
        "AT-014 tests establish application-handled persistence behavior only."
        "No Windows atomic-visibility or crash-durability evidence is claimed."
    ) -join "`r`n"
    [System.IO.File]::WriteAllText($d05FailurePath, $d05FailureReport, [System.Text.UTF8Encoding]::new($false))
    $d05Gate.outputReferences = @("failures/persistence-contract-readiness.txt")
    $d05Gate | Add-Member -NotePropertyName failureReportReference `
        -NotePropertyValue "failures/persistence-contract-readiness.txt"
}
$allGates += $d05Gate

if ($stageManifest.digest -eq $initialManifest.digest) {
    $allGates += Invoke-ComponentGate -Name "ruff" -ScriptName "lint.ps1" -ScriptOutputName "ruff"
    $allGates += Invoke-ComponentGate -Name "bandit" -ScriptName "security.ps1" -ScriptOutputName "security" `
        -ExtraOutputNames @("bandit/bandit.stdout.txt", "bandit/bandit.stderr.txt", "bandit/bandit.json")
    $allGates += Invoke-ComponentGate -Name "pytest-and-traceability" -ScriptName "test.ps1" -ScriptOutputName "tests" `
        -ExtraOutputNames @("pytest-and-traceability/junit.xml", "pytest-and-traceability/traceability.json", "pytest-and-traceability/traceability.csv")
    $allGates += Invoke-ComponentGate -Name "repository-hygiene" -ScriptName "hygiene.ps1" -ScriptOutputName "hygiene" `
        -ExtraOutputNames @("repository-hygiene/hygiene.json") -TrackedRoot $root
}
else {
    foreach ($gateName in @("ruff", "bandit", "pytest-and-traceability", "repository-hygiene")) {
        $allGates += Add-InternalGate -Name $gateName -Status "BLOCKED" -ExitCode 2 `
            -Command "Execute candidate gate against immutable staged snapshot" `
            -Message "Execution was skipped because source-to-stage digest verification failed."
    }
}

$allGates += Add-InternalGate -Name "human-review-and-decision" -Status "BLOCKED" -ExitCode 2 `
    -Command "Check for separately recorded human Bandit review and final ACCEPT/REJECT decision" `
    -Message "No human security disposition or final decision was supplied. The runner does not create, infer, or impersonate these records."

$finalFiles = @(Get-CandidateFiles -BasePath $root)
Copy-Candidate -BasePath $root -Files $finalFiles -Destination $finalSnapshot
$finalManifest = Get-Manifest -BasePath $root -Files $finalFiles
if ($finalManifest.digest -eq $initialManifest.digest) {
    $allGates += Add-InternalGate -Name "candidate-integrity-after" -Status "PASS" -ExitCode 0 `
        -Command "SHA-256 candidate manifest comparison (initial to final source)" `
        -Message "The source candidate remained unchanged during diagnostics."
}
else {
    $allGates += Add-InternalGate -Name "candidate-integrity-after" -Status "FAIL" -ExitCode 1 `
        -Command "SHA-256 candidate manifest comparison (initial to final source)" `
        -Message "The source candidate changed during diagnostics; publication requires a complete new validation run."
}

$finishedAt = [DateTimeOffset]::UtcNow.ToString("o")
$failed = @($allGates | Where-Object { $_.status -ne "PASS" })
$results = [pscustomobject]@{
    schemaVersion = 1
    runId = $runId
    validationMode = "repository-candidate-diagnostic-only"
    authoritative = $false
    decision = $null
    candidateDigest = $initialManifest.digest
    finalCandidateDigest = $finalManifest.digest
    candidateFileCount = $initialManifest.files.Count
    initialSnapshotReference = "initial-snapshot"
    stagedSnapshotReference = "staged-candidate"
    finalSnapshotReference = "final-snapshot"
    candidateManifestReference = "candidate-manifest.json"
    evidenceManifestReference = "$runId.evidence-manifest.json"
    startedAt = $startedAt
    finishedAt = $finishedAt
    status = if ($failed.Count -eq 0) { "PASS_DIAGNOSTIC_ONLY" } else { "FAILED" }
    gates = $allGates
    outputDirectory = $runRoot
}
$results | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $runRoot "results.json") -Encoding UTF8

foreach ($gate in $allGates | Where-Object { $_.status -ne "PASS" -and -not $_.failureReportReference }) {
    $failurePath = Join-Path $failureRoot "$($gate.name).txt"
    $failureText = @(
        "Gate: $($gate.name)"
        "Status: $($gate.status)"
        "Command: $($gate.command)"
        "Exit code: $($gate.exitCode)"
        "Observed: $($gate.message)"
    ) -join "`r`n"
    [System.IO.File]::WriteAllText($failurePath, $failureText, [System.Text.UTF8Encoding]::new($false))
    $gate | Add-Member -NotePropertyName failureReportReference -NotePropertyValue "failures/$($gate.name).txt"
}
$results | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $runRoot "results.json") -Encoding UTF8
$bundleManifest = Write-DetachedEvidenceManifest -RunDirectory $runRoot `
    -EvidenceDirectory $evidenceBase -RunIdentifier $runId `
    -CandidateDigest $initialManifest.digest

Write-Output "Run mode: non-authoritative repository-candidate diagnostic"
Write-Output "Candidate digest: $($initialManifest.digest)"
Write-Output "Results: $(Join-Path $runRoot 'results.json')"
Write-Output "Detached evidence manifest: $($bundleManifest.path)"
Write-Output "Evidence bundle digest: $($bundleManifest.digest)"
Write-Output "Candidate snapshot: $(Join-Path $runRoot 'staged-candidate')"
Write-Output "Failed or blocked gates: $($failed.Count)"
if ($failed.Count -gt 0) {
    exit 1
}
exit 0
