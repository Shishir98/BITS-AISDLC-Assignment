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
$junit = Join-Path $output "junit.xml"
$coverageJson = Join-Path $output "traceability.json"
$coverageCsv = Join-Path $output "traceability.csv"
$uv = (Get-Command uv -ErrorAction Stop).Source
$quotedRoot = '"' + $root + '"'
$quotedJunit = '"' + $junit + '"'
$arguments = "run --active --locked --no-sync --directory $quotedRoot pytest -q tests --junitxml=$quotedJunit"
$command = "`"$uv`" $arguments"
$env:PYTHONPATH = Join-Path $root "src"

$pytestProcess = Start-Process -FilePath $uv -ArgumentList $arguments -WorkingDirectory $root `
    -RedirectStandardOutput $pytestStdout -RedirectStandardError $pytestStderr -Wait -PassThru

$testCases = @()
if (Test-Path -LiteralPath $junit) {
    try {
        [xml]$junitXml = Get-Content -LiteralPath $junit -Raw
        $testCases = @($junitXml.SelectNodes("//testcase"))
    }
    catch {
        $testCases = @()
    }
}

$traceabilityRows = @()
$uncovered = 0
foreach ($criterion in $config.traceability) {
    $mapped = @()
    foreach ($test in $criterion.tests) {
        $found = $false
        foreach ($testCase in $testCases) {
            $className = [string]$testCase.GetAttribute("classname")
            $testName = [string]$testCase.GetAttribute("name")
            if ($testName -eq $test.name -and
                ($className -eq $test.className -or $className.EndsWith("." + $test.className))) {
                $found = $true
                break
            }
        }
        if ($found) {
            $mapped += [pscustomobject]@{
                file = $test.file
                name = $test.name
            }
        }
    }

    $assessment = [string]$criterion.assessment
    if ($mapped.Count -eq 0) {
        $status = "MISSING"
    }
    elseif ($assessment -eq "complete") {
        $status = "COVERED"
    }
    else {
        $status = "PARTIAL"
    }
    if ($status -ne "COVERED") {
        $uncovered++
    }
    $traceabilityRows += [pscustomobject]@{
        ac = $criterion.ac
        at = $criterion.at
        status = $status
        testFile = if ($mapped.Count) { ($mapped.file -join ";") } else { "" }
        testName = if ($mapped.Count) { ($mapped.name -join ";") } else { "" }
        gaps = ($criterion.gaps -join " ")
    }
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
    testCaseCount = $testCases.Count
    acceptanceCriteriaCount = $traceabilityRows.Count
    uncoveredAcceptanceCriteriaCount = $uncovered
    missingSuiteDirectories = $missingSuites
    mappingIssues = $mappingIssues
    rows = $traceabilityRows
}
$coverageRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $coverageJson -Encoding UTF8
$traceabilityRows | Export-Csv -LiteralPath $coverageCsv -NoTypeInformation -Encoding UTF8

Write-Output "Command: $command"
Write-Output "Pytest exit code: $($pytestProcess.ExitCode)"
Write-Output "JUnit test cases: $($testCases.Count)"
Write-Output "Acceptance criteria without complete executable coverage: $uncovered"
Write-Output "Missing mandatory suite directories: $($missingSuites.Count)"
Write-Output "AC-to-AT mapping issues: $($mappingIssues.Count)"

if ($pytestProcess.ExitCode -ne 0 -or $uncovered -gt 0 -or $missingSuites.Count -gt 0 -or $mappingIssues.Count -gt 0) {
    exit 1
}
exit 0
