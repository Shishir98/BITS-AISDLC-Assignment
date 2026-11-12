param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$ConfigurationPath = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
if (-not $ConfigurationPath) {
    $ConfigurationPath = Join-Path $root ".harness\mandatory-checks.json"
}
$config = Get-Content -LiteralPath $ConfigurationPath -Raw | ConvertFrom-Json
$mappingIssues = @()
$mappedAtIds = @($config.traceability | ForEach-Object { [string]$_.at })
foreach ($requiredAt in $config.pytest.acceptanceTestIds) {
    if ($mappedAtIds -notcontains [string]$requiredAt) {
        $mappingIssues += "No AC mapping exists for $requiredAt."
    }
}
foreach ($mappedAt in $mappedAtIds) {
    if (@($config.pytest.acceptanceTestIds) -notcontains $mappedAt) {
        $mappingIssues += "Unexpected test mapping exists for $mappedAt."
    }
}
if (($mappedAtIds | Sort-Object -Unique).Count -ne $mappedAtIds.Count) {
    $mappingIssues += "The AC-to-AT mapping contains duplicate test IDs."
}
$pytestStdout = Join-Path $output "pytest.stdout.txt"
$pytestStderr = Join-Path $output "pytest.stderr.txt"
$collectionStdout = Join-Path $output "pytest-collection.stdout.txt"
$collectionStderr = Join-Path $output "pytest-collection.stderr.txt"
$junit = Join-Path $output "junit.xml"
$coverageJson = Join-Path $output "traceability.json"
$coverageCsv = Join-Path $output "traceability.csv"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPYCACHEPREFIX = Join-Path $output "python-cache"
$uv = (Get-Command uv -ErrorAction Stop).Source
$quotedRoot = '"' + $root + '"'
$quotedJunit = '"' + $junit + '"'
$collectionArguments = "run --active --locked --no-sync --directory $quotedRoot pytest --collect-only -q -p no:cacheprovider tests"
$collectionCommand = "`"$uv`" $collectionArguments"
$arguments = "run --active --locked --no-sync --directory $quotedRoot pytest -q -p no:cacheprovider tests --junitxml=$quotedJunit"
$command = "`"$uv`" $arguments"
$env:PYTHONPATH = Join-Path $root "src"

$collectionProcess = Start-Process -FilePath $uv -ArgumentList $collectionArguments -WorkingDirectory $root `
    -RedirectStandardOutput $collectionStdout -RedirectStandardError $collectionStderr -Wait -PassThru
$collectedNodeIds = @()
if ($collectionProcess.ExitCode -eq 0) {
    $collectedNodeIds = @(Get-Content -LiteralPath $collectionStdout | ForEach-Object {
        $nodeId = ([string]$_).Trim()
        if ($nodeId -match '^tests[\\/].+\.py::.+$') { $nodeId.Replace("\", "/") }
    } | Where-Object { $_ })
}
else {
    $mappingIssues += "Pytest collection failed with exit code $($collectionProcess.ExitCode)."
}
if (($collectedNodeIds | Sort-Object -Unique).Count -ne $collectedNodeIds.Count) {
    $mappingIssues += "Pytest collection produced duplicate node IDs."
}

$pytestProcess = Start-Process -FilePath $uv -ArgumentList $arguments -WorkingDirectory $root `
    -RedirectStandardOutput $pytestStdout -RedirectStandardError $pytestStderr -Wait -PassThru

$testCases = @()
$junitParseError = ""
if (Test-Path -LiteralPath $junit) {
    try {
        [xml]$junitXml = Get-Content -LiteralPath $junit -Raw
        $testCases = @($junitXml.SelectNodes("//testcase"))
    }
    catch {
        $junitParseError = $_.Exception.Message
        $mappingIssues += "JUnit XML could not be parsed: $junitParseError"
    }
}
else {
    $mappingIssues += "Pytest did not create the required JUnit XML file."
}

$traceabilityRows = @()
$uncovered = 0
$configuredNodeIds = @()
foreach ($criterion in $config.traceability) {
    $mapped = @()
    foreach ($test in $criterion.tests) {
        $expectedNodeId = ([string]$test.file).Replace("\", "/") + "::" + [string]$test.name
        $nodeId = ([string]$test.nodeId).Replace("\", "/")
        if ($nodeId -ne $expectedNodeId) {
            $mappingIssues += "Configured node ID does not match its file and test name for $($criterion.at): $nodeId."
        }
        $configuredNodeIds += $nodeId
        $collectionMatches = @($collectedNodeIds | Where-Object { $_ -ceq $nodeId })
        $expectedClassName = ([string]$test.file).Replace("/", ".").Replace("\", ".")
        $expectedClassName = $expectedClassName.Substring(0, $expectedClassName.Length - 3)
        if ([string]$test.className -cne $expectedClassName) {
            $mappingIssues += "Configured pytest class/module does not match the normalized test file for $nodeId."
        }
        $junitMatches = @()
        foreach ($testCase in $testCases) {
            $className = [string]$testCase.GetAttribute("classname")
            $testName = [string]$testCase.GetAttribute("name")
            if ($testName -ceq [string]$test.name -and $className -ceq $expectedClassName) {
                $junitMatches += $testCase
            }
        }
        if ($collectionMatches.Count -ne 1) {
            $executionStatus = "NOT_COLLECTED"
        }
        elseif ($junitMatches.Count -ne 1) {
            $executionStatus = "MISSING_JUNIT_CASE"
        }
        elseif ($junitMatches[0].SelectSingleNode("./failure|./error|./skipped")) {
            $executionStatus = "FAIL"
        }
        else {
            $executionStatus = "PASS"
        }
        if ($collectionMatches.Count -ne 1) {
            $mappingIssues += "Expected exactly one collected pytest node for $nodeId; found $($collectionMatches.Count)."
        }
        if ($junitMatches.Count -ne 1) {
            $mappingIssues += "Expected exactly one exact JUnit case for $nodeId; found $($junitMatches.Count)."
        }
        if ($executionStatus -eq "FAIL") {
            $mappingIssues += "The mapped pytest case failed: $nodeId."
        }
        $mapped += [pscustomobject]@{
            file = $test.file
            name = $test.name
            nodeId = $nodeId
            executionStatus = $executionStatus
            outputReferences = "pytest.stdout.txt;pytest.stderr.txt;junit.xml"
        }
    }

    $assessment = [string]$criterion.assessment
    if ($mapped.Count -eq 0) {
        $status = "MISSING"
    }
    elseif (@($mapped | Where-Object { $_.executionStatus -ne "PASS" }).Count -gt 0) {
        $status = "FAIL"
    }
    elseif ($assessment -eq "full") {
        $status = "FULL"
    }
    else {
        $status = "PARTIAL"
    }
    if ($status -ne "FULL") {
        $uncovered++
    }
    $traceabilityRows += [pscustomobject]@{
        ac = $criterion.ac
        at = $criterion.at
        status = $status
        executionStatus = (($mapped.executionStatus | Sort-Object -Unique) -join ";")
        testFile = if ($mapped.Count) { ($mapped.file -join ";") } else { "" }
        testName = if ($mapped.Count) { ($mapped.name -join ";") } else { "" }
        nodeId = if ($mapped.Count) { ($mapped.nodeId -join ";") } else { "" }
        outputReferences = if ($mapped.Count) { ($mapped.outputReferences -join ";") } else { "" }
        gaps = ($criterion.gaps -join " ")
    }
}
if (($configuredNodeIds | Sort-Object -Unique).Count -ne $configuredNodeIds.Count) {
    $mappingIssues += "A pytest node ID is mapped more than once."
}

$missingSuites = @()
foreach ($suite in $config.pytest.requiredSuiteDirectories) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $suite) -PathType Container)) {
        $missingSuites += $suite
    }
}

$coverageRecord = [pscustomobject]@{
    candidateRoot = $root
    junitReference = "junit.xml"
    collectionCommand = $collectionCommand
    collectionExitCode = $collectionProcess.ExitCode
    collectionStdoutReference = "pytest-collection.stdout.txt"
    collectionStderrReference = "pytest-collection.stderr.txt"
    junitParseError = $junitParseError
    testCaseCount = $testCases.Count
    acceptanceCriteriaCount = $traceabilityRows.Count
    acceptanceCriteriaWithoutFullCoverageCount = $uncovered
    missingSuiteDirectories = $missingSuites
    mappingIssues = $mappingIssues
    rows = $traceabilityRows
}
$coverageRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $coverageJson -Encoding UTF8
$traceabilityRows | Export-Csv -LiteralPath $coverageCsv -NoTypeInformation -Encoding UTF8
if (Test-Path -LiteralPath $env:PYTHONPYCACHEPREFIX) {
    Remove-Item -LiteralPath $env:PYTHONPYCACHEPREFIX -Recurse -Force
}

Write-Output "Command: $command"
Write-Output "Pytest exit code: $($pytestProcess.ExitCode)"
Write-Output "Pytest collection exit code: $($collectionProcess.ExitCode)"
Write-Output "JUnit test cases: $($testCases.Count)"
Write-Output "Acceptance criteria without full executable coverage: $uncovered"
Write-Output "Missing mandatory suite directories: $($missingSuites.Count)"
Write-Output "AC-to-AT mapping issues: $($mappingIssues.Count)"

if ($collectionProcess.ExitCode -ne 0 -or $pytestProcess.ExitCode -ne 0 -or
    $uncovered -gt 0 -or $missingSuites.Count -gt 0 -or $mappingIssues.Count -gt 0) {
    exit 1
}
exit 0
