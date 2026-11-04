<#
.SYNOPSIS
Runs an isolated S6 V2 DryRun, or gates a future proof behind native confirmation.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('DryRun', 'Execute', 'OfflineE2E')]
    [string] $Mode,

    [Parameter(Mandatory = $true)]
    [ValidateSet('common', 'controlled')]
    [string] $Target,

    [Parameter(Mandatory = $true)]
    [ValidateSet('OPERATIONAL_ONLY', 'TRUSTED_REFERENCE')]
    [string] $IntegrityMode,

    [ValidateSet('aligned', 'unaligned-prepared')]
    [string] $Case = 'aligned',

    [ValidateSet('8MiB', '128MiB')]
    [string] $PrefixProfile = '8MiB',

    [string] $EvidenceParent,

    [string] $ResumeEvidenceRoot
)

$ErrorActionPreference = 'Stop'

function Assert-NoReparseDirectoryPath {
    param([Parameter(Mandatory = $true)][string] $Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $driveRoot = [System.IO.Path]::GetPathRoot($fullPath)
    $cursor = $driveRoot
    $relative = $fullPath.Substring($driveRoot.Length)
    foreach ($segment in ($relative -split '[\\/]')) {
        if ([string]::IsNullOrWhiteSpace($segment)) { continue }
        $cursor = Join-Path $cursor $segment
        $entry = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        if (-not $entry.PSIsContainer -or
            (($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'Evidence path contains a non-directory or reparse point.'
        }
    }
}

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$pythonPath = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
$harnessPath = Join-Path $PSScriptRoot 's6_v2_proof_harness.py'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Repository virtual-environment Python was not found.'
}
if (-not (Test-Path -LiteralPath $harnessPath -PathType Leaf)) {
    throw 'S6 V2 proof harness was not found.'
}
if ([string]::IsNullOrWhiteSpace($EvidenceParent)) {
    $EvidenceParent = $env:TEMP
}
if ($Target -ceq 'controlled') {
    if ([string]::IsNullOrWhiteSpace($env:TEMP)) {
        throw 'Native TEMP directory is unavailable.'
    }
    if (-not (Test-Path -LiteralPath $env:TEMP -PathType Container)) {
        throw 'Native TEMP directory does not exist.'
    }
    Assert-NoReparseDirectoryPath -Path $env:TEMP
    $EvidenceParent = Join-Path $env:TEMP 's6v2'
    if (-not (Test-Path -LiteralPath $EvidenceParent -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $EvidenceParent)
    }
}
if ([string]::IsNullOrWhiteSpace($EvidenceParent)) {
    throw 'An evidence parent directory is required.'
}
$EvidenceParent = [System.IO.Path]::GetFullPath($EvidenceParent)
if (-not (Test-Path -LiteralPath $EvidenceParent -PathType Container)) {
    throw 'Evidence parent directory does not exist.'
}
Assert-NoReparseDirectoryPath -Path $EvidenceParent
if ($Target -ceq 'controlled') {
    $plannedRoot = Join-Path $EvidenceParent 's6t-00000000000000000000000000000000'
    $plannedPaths = @(
        (Join-Path $plannedRoot 'authorization.json'),
        (Join-Path $plannedRoot 'aligned\phase-1.json'),
        (Join-Path $plannedRoot 'aligned\phase-2.json'),
        (Join-Path $plannedRoot 'aligned\phase-1.child.json'),
        (Join-Path $plannedRoot 'aligned\phase-2.child.json'),
        (Join-Path $plannedRoot 'aligned\downloads\proof-document.bin.part'),
        (Join-Path $plannedRoot 'aligned\reference-manifest.v1.json'),
        (Join-Path $plannedRoot 's6-v2-proof-report.json')
    )
    if (($plannedPaths | Where-Object { $_.Length -gt 240 }).Count -gt 0) {
        throw 'Derived controlled proof paths exceed the 240 character native path limit.'
    }
}

if ($Mode -eq 'OfflineE2E') {
    if ($Target -cne 'common' -or $IntegrityMode -cne 'OPERATIONAL_ONLY') {
        throw 'OfflineE2E is limited to the common OPERATIONAL_ONLY profile.'
    }
    if (-not [string]::IsNullOrWhiteSpace($ResumeEvidenceRoot)) {
        throw 'OfflineE2E always requires a fresh isolated test root.'
    }

    $offlineRoot = Join-Path $EvidenceParent "s6-v2-offline-e2e-$([Guid]::NewGuid().ToString('N'))"
    [void](New-Item -ItemType Directory -Path $offlineRoot)
    $testSelector = 'tests/manual_proofs/test_s6_v2_proof_harness.py::test_two_process_handoff_real_harness_lifecycle_offline'
    $previousBytecodeSetting = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONDONTWRITEBYTECODE = '1'
        Push-Location $repositoryRoot
        try {
            & $pythonPath '-m' 'pytest' '-q' '-p' 'no:cacheprovider' '--basetemp' $offlineRoot $testSelector
            $pythonExitCode = $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }
    finally {
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecodeSetting
    }
    Write-Output "OFFLINE_E2E_ROOT=$offlineRoot"
    if ($pythonExitCode -eq 0) {
        Write-Output 'OFFLINE_E2E=PASS'
        exit 0
    }
    Write-Output 'OFFLINE_E2E=FAIL'
    exit $pythonExitCode
}

$profileLocalAppData = $env:LOCALAPPDATA
if ([string]::IsNullOrWhiteSpace($profileLocalAppData)) {
    throw 'Inherited LOCALAPPDATA is unavailable; proof execution is blocked.'
}
try {
    Push-Location $repositoryRoot
    try {
    $arguments = @($harnessPath, '--target', $Target, '--mode', $IntegrityMode,
                   '--evidence-parent', $EvidenceParent)
    if ($Target -ceq 'controlled') {
        $arguments += @('--prefix-profile', $PrefixProfile)
    }
    if ($Mode -eq 'DryRun') {
        if (-not [string]::IsNullOrWhiteSpace($ResumeEvidenceRoot)) {
            throw 'DryRun cannot resume a real proof.'
        }
        & $pythonPath @arguments '--dry-run'
        $pythonExitCode = $LASTEXITCODE
    }
    else {
        if (($Target -ceq 'common' -and $IntegrityMode -cne 'OPERATIONAL_ONLY') -or
            ($Target -ceq 'controlled' -and $IntegrityMode -cne 'TRUSTED_REFERENCE')) {
            throw 'Selected mode is not authorized for this fixed target profile.'
        }
        if (-not [string]::IsNullOrWhiteSpace($ResumeEvidenceRoot)) {
            throw 'This authorization requires a fresh isolated proof root; resume is disabled.'
        }
        if ($Target -ceq 'controlled') {
            if ($Case -cne 'aligned') {
                throw 'TRUSTED_REFERENCE requires the aligned controlled case.'
            }
            if ($PrefixProfile -ceq '8MiB') {
                $prefixBytes = 8388608
                $phase1GetFileCap = 32
                $phase2AttemptGetFileCap = 4238
                $getfileEffectiveCap = 8508
                $getfilehashesEffectiveCap = 8542
                $reservedBytesEffectiveCap = 2230321152
                $identityGetMessagesEffectiveCap = 5
            }
            else {
                $prefixBytes = 134217728
                $phase1GetFileCap = 512
                $phase2AttemptGetFileCap = 3758
                $getfileEffectiveCap = 8028
                $getfilehashesEffectiveCap = 8542
                $reservedBytesEffectiveCap = 2104492032
                $identityGetMessagesEffectiveCap = 5
            }
            $scenario = "TRUSTED_REFERENCE; PREFIX_PROFILE=$PrefixProfile; PREFIX_BYTES=$prefixBytes; PHASE1_GETFILE=$phase1GetFileCap; PHASE2_GETFILE_PER_ATTEMPT=$phase2AttemptGetFileCap; PHASE2_ATTEMPTS=2; HASHES_PER_ATTEMPT=4271; HASHES_AGGREGATE=$getfilehashesEffectiveCap"
            $targetChannel = '-1002368271467'
            $targetMessage = '7603'
            $targetMediaId = '5089068167339181674'
            $targetBytes = '1119129690'
            $getfileApprovedMax = 8508
            $getfilehashesApprovedMax = 8542
            $reservedBytesApprovedMax = 2230321152
            $requiredConfirmation = "EXECUTE S6 V2 PROOF controlled TRUSTED_REFERENCE channel=-1002368271467 message=7603 media=5089068167339181674 bytes=1119129690 aligned PREFIX_PROFILE=$PrefixProfile PREFIX_BYTES=$prefixBytes GETFILE_CAP=$getfileEffectiveCap HASHES_CAP=$getfilehashesEffectiveCap IDENTITY_GETMESSAGES_CAP=$identityGetMessagesEffectiveCap RESERVED_BYTES=$reservedBytesEffectiveCap"
        }
        elseif ($Case -ceq 'aligned') {
            $scenario = 'aligned; PREFIX_BYTES=1048576; REMOTE_ALIGNED_OFFSET=1048576; CHUNK_BYTES=262144; OVERLAP=0 / NOT_APPLICABLE_ALIGNED'
            $getfileEffectiveCap = 94
            $getfilehashesEffectiveCap = 92
            $reservedBytesEffectiveCap = 24641536
            $targetChannel = '-1002758699600'
            $targetMessage = '598'
            $targetMediaId = '5175124468544046445'
            $targetBytes = '11649955'
            $getfileApprovedMax = 139
            $getfilehashesApprovedMax = 138
            $reservedBytesApprovedMax = 36438016
            $requiredConfirmation = "EXECUTE S6 V2 PROOF common OPERATIONAL_ONLY $Case"
        }
        else {
            $scenario = 'unaligned-prepared; PREFIX_BYTES=1048699; REMOTE_ALIGNED_OFFSET=1048576; CHUNK_BYTES=262144; OVERLAP=123'
            $getfileEffectiveCap = 95
            $getfilehashesEffectiveCap = 92
            $reservedBytesEffectiveCap = 24903680
            $targetChannel = '-1002758699600'
            $targetMessage = '598'
            $targetMediaId = '5175124468544046445'
            $targetBytes = '11649955'
            $getfileApprovedMax = 139
            $getfilehashesApprovedMax = 138
            $reservedBytesApprovedMax = 36438016
            $requiredConfirmation = "EXECUTE S6 V2 PROOF common OPERATIONAL_ONLY $Case"
        }
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $sessionPath = Join-Path $profileLocalAppData 'telegram_courses\session.dpapi'
        $sessionArtifact = if (Test-Path -LiteralPath $sessionPath -PathType Leaf) { 'PRESENT' } else { 'MISSING' }
        Write-Output "WINDOWS_USER=$identity"
        Write-Output "WINDOWS_PROFILE=$env:USERPROFILE"
        Write-Output "LOCALAPPDATA_PROCESS_OVERRIDE=$profileLocalAppData"
        Write-Output 'LOCALAPPDATA_SOURCE=INHERITED_UNMODIFIED'
        Write-Output "PROTECTED_SESSION_PATH=$sessionPath"
        Write-Output "PROTECTED_SESSION_ARTIFACT=$sessionArtifact"
        Write-Output "TARGET_CHANNEL=$targetChannel"
        Write-Output "TARGET_MESSAGE=$targetMessage"
        Write-Output "TARGET_MEDIA_ID=$targetMediaId"
        Write-Output 'TARGET_TYPE=DOCUMENT'
        Write-Output "TARGET_SIZE=$targetBytes"
        Write-Output "MODE=$IntegrityMode"
        Write-Output "PREFIX_PROFILE=$PrefixProfile"
        Write-Output "SCENARIO=$scenario"
        Write-Output 'WORKERS=1; ATTEMPTS_PHASE1=1; ATTEMPTS_PHASE2=2; AGGREGATE_ATTEMPTS=3; FLOODWAIT_MAX_SECONDS=120'
        Write-Output "GETFILE_APPROVED_MAX=$getfileApprovedMax; GETFILE_EFFECTIVE_CAP=$getfileEffectiveCap"
        Write-Output "GETFILEHASHES_APPROVED_MAX=$getfilehashesApprovedMax; GETFILEHASHES_EFFECTIVE_CAP=$getfilehashesEffectiveCap"
        if ($Target -ceq 'controlled') {
            Write-Output "IDENTITY_GETMESSAGES_EFFECTIVE_CAP=$identityGetMessagesEffectiveCap; IDENTITY_GETMESSAGES_APPROVED_MAX=5"
        }
        Write-Output "RESERVED_BYTES_APPROVED_MAX=$reservedBytesApprovedMax; RESERVED_BYTES_EFFECTIVE_CAP=$reservedBytesEffectiveCap"
        Write-Output 'V1_ACTIVE=YES; V2_EFFECTIVE=NO'
        Write-Output 'FRESH_ISOLATED_ROOT=YES; HISTORICAL_PROOF_ROOTS=NOT_REUSED'
        Write-Output 'SECURE_PREFLIGHT=LOCAL_STATUS_ONLY; NO_TELEGRAM_CONNECT; NO_RPC; NO_AUTH_WRITES'
        Write-Output 'TIMEOUT_POLICY_PREFLIGHT=LOCAL_EFFECTIVE_CONFIGURATION; NO_TELEGRAM_CALLS'
        $timeoutPolicyOutput = @(& $pythonPath $harnessPath '--timeout-policy-status-only' '--target' $Target '--mode' $IntegrityMode)
        $timeoutPolicyExitCode = $LASTEXITCODE
        if ($timeoutPolicyExitCode -ne 0 -or $timeoutPolicyOutput.Count -ne 1) {
            Write-Output 'TIMEOUT_POLICY_PREFLIGHT=FAIL; CONFIRMATION=BLOCKED'
            exit 5
        }
        try {
            $timeoutPolicy = $timeoutPolicyOutput[0] | ConvertFrom-Json -ErrorAction Stop
            $timeoutPolicyHash = [string]$timeoutPolicy.policy_sha256
            $policyProcessTimeout = [int]$timeoutPolicy.process_timeout_effective_seconds
            $policyAggregateDeadline = [int]$timeoutPolicy.aggregate_deadline_effective_seconds
            $policyInactivityTimeout = [int]$timeoutPolicy.semantic_inactivity_timeout_seconds
            $policyHeartbeat = [int]$timeoutPolicy.progress_heartbeat_seconds
            $policyCancellationGrace = [int]$timeoutPolicy.cancellation_grace_max_seconds
            $policyGraceInsideDeadline = [bool]$timeoutPolicy.grace_inside_hard_deadline
            $policyContractMatch = [bool]$timeoutPolicy.contract_match
        }
        catch {
            Write-Output 'TIMEOUT_POLICY_PREFLIGHT=FAIL; CONFIRMATION=BLOCKED'
            exit 5
        }
        $scenarioMatches = (($Target -ceq 'controlled' -and $IntegrityMode -ceq 'TRUSTED_REFERENCE') -or
                            ($Target -ceq 'common' -and $IntegrityMode -ceq 'OPERATIONAL_ONLY'))
        if (-not $scenarioMatches -or $timeoutPolicy.target -cne $Target -or
            $timeoutPolicy.mode -cne $IntegrityMode -or $timeoutPolicyHash -notmatch '^[0-9a-f]{64}$' -or
            -not $policyContractMatch -or
            $policyProcessTimeout -le 0 -or $policyAggregateDeadline -le 0 -or
            $policyInactivityTimeout -le 0 -or $policyHeartbeat -le 0 -or
            $policyCancellationGrace -lt 0 -or -not $policyGraceInsideDeadline) {
            Write-Output 'TIMEOUT_POLICY_PREFLIGHT=FAIL; CONTRACT_OR_SCENARIO_DIVERGENCE=YES; CONFIRMATION=BLOCKED'
            exit 5
        }
        Write-Output "TARGET=$Target"
        Write-Output "MODE=$IntegrityMode"
        Write-Output "PROCESS_TIMEOUT_EFFECTIVE_SECONDS=$policyProcessTimeout"
        Write-Output "AGGREGATE_DEADLINE_EFFECTIVE_SECONDS=$policyAggregateDeadline"
        Write-Output "SEMANTIC_INACTIVITY_TIMEOUT_SECONDS=$policyInactivityTimeout"
        Write-Output "PROGRESS_HEARTBEAT_SECONDS=$policyHeartbeat"
        Write-Output "CANCELLATION_GRACE_MAX_SECONDS=$policyCancellationGrace"
        Write-Output "GRACE_INSIDE_HARD_DEADLINE=$(if ($policyGraceInsideDeadline) { 'YES' } else { 'NO' })"
        Write-Output 'TIMEOUT_POLICY_PREFLIGHT=PASS; VALUES_FROM_EFFECTIVE_HARNESS_CONFIGURATION=YES'
        $targetPreflightOutput = @(& $pythonPath $harnessPath '--preconfirmation-status-only' '--target' $Target '--mode' $IntegrityMode '--prefix-profile' $PrefixProfile '--evidence-parent' $EvidenceParent)
        $targetPreflightExitCode = $LASTEXITCODE
        if ($targetPreflightExitCode -ne 0 -or $targetPreflightOutput.Count -ne 1) {
            Write-Output 'TARGET_REFERENCE_PREFLIGHT=FAIL; CONFIRMATION=BLOCKED'
            exit 5
        }
        try {
            $targetPreflight = $targetPreflightOutput[0] | ConvertFrom-Json -ErrorAction Stop
            $declaredTarget = $targetPreflight.target
            $preflightReference = $targetPreflight.reference
        }
        catch {
            Write-Output 'TARGET_REFERENCE_PREFLIGHT=FAIL; OUTPUT=INVALID; CONFIRMATION=BLOCKED'
            exit 5
        }
        if ($targetPreflight.status -cne 'PASS' -or $targetPreflight.rpc_calls -ne 0 -or
            $declaredTarget.channel_id -ne -1002368271467 -or
            $declaredTarget.message_id -ne 7603 -or
            [string]$declaredTarget.media_id -cne '5089068167339181674' -or
            $declaredTarget.media_kind -cne 'DOCUMENT' -or
            $declaredTarget.expected_bytes -ne 1119129690 -or
            $preflightReference.bytes -ne 1119129690 -or
            $preflightReference.sha256 -cne '3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c' -or
            $targetPreflight.v1_active -ne $true -or $targetPreflight.v2_global_effective -ne $false) {
            Write-Output 'TARGET_REFERENCE_PREFLIGHT=FAIL; CONTRACT_OR_IDENTITY_DIVERGENCE=YES; CONFIRMATION=BLOCKED'
            exit 5
        }
        Write-Output 'TARGET_DECLARED_IDENTITY_PREFLIGHT=PASS; RPC_CALLS=0'
        Write-Output "REFERENCE_SIZE_PREFLIGHT=$($preflightReference.bytes)"
        Write-Output "REFERENCE_SHA256_PREFLIGHT=$($preflightReference.sha256)"
        Write-Output "REFERENCE_ACCESS_MODE=$($preflightReference.access_mode)"
        Write-Output 'TARGET_REFERENCE_PREFLIGHT=PASS; CONFIRMATION=NOT_YET_REQUESTED'
        $preflightOutput = @(& $pythonPath $harnessPath '--secure-preflight-status-only')
        $preflightExitCode = $LASTEXITCODE
        if ($preflightOutput.Count -ne 1) {
            Write-Output 'SECURE_PREFLIGHT=NO; PREFLIGHT_OUTPUT=INVALID'
            exit 5
        }
        try {
            $preflight = $preflightOutput[0] | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            Write-Output 'SECURE_PREFLIGHT=NO; PREFLIGHT_OUTPUT=INVALID'
            exit 5
        }
        Write-Output "SECURE_VAULT_AVAILABLE=$($preflight.credential_vault)"
        Write-Output "PROTECTED_SESSION_AVAILABLE=$($preflight.protected_session)"
        Write-Output "SECURE_PROVIDER=$($preflight.provider)"
        if ($preflightExitCode -ne 0 -or $preflight.credential_vault -cne 'YES' -or $preflight.protected_session -cne 'YES') {
            Write-Output 'REAL_EXECUTION=NOT_STARTED'
            Write-Output 'STOP=SECURE_PREFLIGHT_FAILED'
            exit 5
        }
        Write-Output 'No login, fallback mode or V1 semantic change is allowed.'
        $confirmation = Read-Host "Type exactly: $requiredConfirmation"
        if ($confirmation -cne $requiredConfirmation) {
            Write-Output 'REAL_EXECUTION=NOT_STARTED'
            Write-Output 'STOP=NATIVE_CONFIRMATION_NOT_MATCHED'
            exit 5
        }

        $authorizationBytes = New-Object byte[] 32
        $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $random.GetBytes($authorizationBytes)
        }
        finally {
            $random.Dispose()
        }
        $authorizationToken = [BitConverter]::ToString($authorizationBytes).Replace('-', '').ToLowerInvariant()
        $previousAuthorization = $env:S6_V2_PROOF_AUTH
        try {
            $env:S6_V2_PROOF_AUTH = $authorizationToken
            & $pythonPath @arguments '--case' $Case '--native-launcher-confirmed' '--expected-timeout-policy-sha256' $timeoutPolicyHash
            $pythonExitCode = $LASTEXITCODE
        }
        finally {
            $env:S6_V2_PROOF_AUTH = $previousAuthorization
            [Array]::Clear($authorizationBytes, 0, $authorizationBytes.Length)
            $authorizationToken = $null
        }
    }
    }
    finally {
        Pop-Location
    }
}
finally {
    $profileLocalAppData = $null
}

Write-Output "Harness exit code: $pythonExitCode"
if ($pythonExitCode -ne 0) {
    exit $pythonExitCode
}
