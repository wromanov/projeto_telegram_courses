param(
    [string]$PythonHome
)

$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$venvSite = Join-Path $sourceRoot '.venv\Lib\site-packages'
if (-not $PythonHome) {
    $venvConfig = Join-Path $sourceRoot '.venv\pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $venvConfig -PathType Leaf)) {
        throw 'Não foi possível localizar o runtime pelo .venv\pyvenv.cfg.'
    }
    $homeLine = Get-Content -LiteralPath $venvConfig | Where-Object { $_ -match '^home\s*=' } | Select-Object -First 1
    if (-not $homeLine) {
        throw 'O .venv\pyvenv.cfg não informa a pasta do runtime Python.'
    }
    $PythonHome = ($homeLine -split '=', 2)[1].Trim()
}
$pythonExe = Join-Path $PythonHome 'python.exe'
$distRoot = Join-Path $sourceRoot 'dist'
$packageName = 'telegram-courses-windows-x64-candidate'
$packagePath = Join-Path $distRoot $packageName
$zipPath = Join-Path $distRoot "$packageName.zip"

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "CPython não encontrado em $PythonHome. Informe o runtime 3.14.7 x64 já instalado."
}
if (-not (Test-Path -LiteralPath $venvSite -PathType Container)) {
    throw 'Dependências do projeto não foram encontradas no .venv local.'
}
$runtimeVersion = (& $pythonExe --version 2>&1 | Out-String).Trim()
if ($runtimeVersion -ne 'Python 3.14.7') {
    throw "Versão de runtime incompatível: $runtimeVersion. O pacote exige CPython 3.14.7."
}
$architecture = (& $pythonExe -I -c 'import struct; print(struct.calcsize("P") * 8)' 2>&1 | Out-String).Trim()
if ($architecture -ne '64') {
    throw 'O pacote candidato exige runtime Windows x64.'
}
if ((Test-Path -LiteralPath $packagePath) -or (Test-Path -LiteralPath $zipPath)) {
    throw 'O destino do candidato já existe; nada foi sobrescrito.'
}

$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute o smoke test como usuário Windows comum, sem elevação.'
}

if (-not (Test-Path -LiteralPath $distRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $distRoot | Out-Null
}
$stagingPath = Join-Path $distRoot ('.telegram-courses-build-' + [guid]::NewGuid().ToString('N'))
$stagingPackage = Join-Path $stagingPath $packageName
$stagingZip = Join-Path $stagingPath "$packageName.zip"
$runtimePath = Join-Path $stagingPackage 'runtime'
$appPath = Join-Path $stagingPackage 'app'
$vendorPath = Join-Path $stagingPackage 'vendor'

New-Item -ItemType Directory -Path $stagingPackage, $runtimePath, $appPath, $vendorPath | Out-Null
foreach ($name in @('python.exe', 'python3.dll', 'python314.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt')) {
    $source = Join-Path $PythonHome $name
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $runtimePath $name)
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $runtimePath 'python.exe') -PathType Leaf)) {
    throw 'python.exe não foi copiado para o runtime do pacote.'
}
Copy-Item -LiteralPath (Join-Path $PythonHome 'DLLs') -Destination (Join-Path $runtimePath 'DLLs') -Recurse
New-Item -ItemType Directory -Path (Join-Path $runtimePath 'Lib') | Out-Null
& robocopy (Join-Path $PythonHome 'Lib') (Join-Path $runtimePath 'Lib') /E /XD site-packages __pycache__ test tests tkinter idlelib ensurepip /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP /NC /NS | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "Falha copiando a biblioteca padrão do CPython (robocopy $LASTEXITCODE)."
}

$applicationSource = Join-Path $sourceRoot 'src\telegram_courses'
Get-ChildItem -LiteralPath $applicationSource -File -Recurse | Where-Object {
    $_.Extension -in @('.py', '.sql')
} | ForEach-Object {
    $relativePath = $_.FullName.Substring($applicationSource.Length + 1)
    $destination = Join-Path $appPath $relativePath
    $destinationDirectory = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    }
    Copy-Item -LiteralPath $_.FullName -Destination $destination
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'launcher.py') -Destination $stagingPackage
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'launch.cmd') -Destination $stagingPackage
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination $stagingPackage
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'DEPENDENCY-VERSIONS.txt') -Destination $stagingPackage

$vendorModules = @('aiosqlite', 'colorama', 'cryptg', 'markdown_it', 'mdurl', 'pyaes', 'pyasn1', 'pygments', 'rich', 'rsa', 'telethon')
$vendorMetadata = @(
    'aiosqlite-0.22.1.dist-info', 'colorama-0.4.6.dist-info', 'cryptg-0.6.0.dist-info',
    'markdown_it_py-4.2.0.dist-info', 'mdurl-0.1.2.dist-info', 'pyaes-1.6.1.dist-info',
    'pyasn1-0.6.4.dist-info', 'pygments-2.21.0.dist-info', 'rich-15.0.0.dist-info',
    'rsa-4.9.1.dist-info', 'telethon-1.45.0.dist-info'
)
foreach ($entry in @($vendorModules + $vendorMetadata)) {
    $source = Join-Path $venvSite $entry
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "Dependência fixada ausente: $entry"
    }
    $destination = Join-Path $vendorPath $entry
    New-Item -ItemType Directory -Path $destination | Out-Null
    & robocopy $source $destination /E /XD __pycache__ /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP /NC /NS | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Falha copiando dependência do pacote: $entry"
    }
}

$searchPath = "python314.zip`n.`nLib`nDLLs`n..\app`n..\vendor`n"
[IO.File]::WriteAllText(
    (Join-Path $runtimePath 'python314._pth'),
    $searchPath,
    [System.Text.UTF8Encoding]::new($false)
)

$launcher = Join-Path $stagingPackage 'launcher.py'
$runtime = Join-Path $runtimePath 'python.exe'
$tempBase = [IO.Path]::GetFullPath($env:TEMP)
if ($tempBase.StartsWith($sourceRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'TEMP aponta para dentro do repositório; configure TEMP e TMP fora da pasta do projeto.'
}
$smokeRoot = Join-Path $tempBase ('telegram-courses-package-smoke-' + [guid]::NewGuid().ToString('N'))
$smokeLocalAppData = Join-Path $smokeRoot 'local-app-data'
$smokeProfile = Join-Path $smokeRoot 'profile'
New-Item -ItemType Directory -Path $smokeLocalAppData, $smokeProfile | Out-Null

$oldEnvironment = @{
    LOCALAPPDATA = $env:LOCALAPPDATA
    USERPROFILE = $env:USERPROFILE
    TELEGRAM_COURSES_CONFIG = $env:TELEGRAM_COURSES_CONFIG
    TELEGRAM_COURSES_DATABASE_PATH = $env:TELEGRAM_COURSES_DATABASE_PATH
    TELEGRAM_COURSES_DOWNLOAD_DIR = $env:TELEGRAM_COURSES_DOWNLOAD_DIR
}
try {
    $env:LOCALAPPDATA = $smokeLocalAppData
    $env:USERPROFILE = $smokeProfile
    Remove-Item Env:TELEGRAM_COURSES_CONFIG -ErrorAction SilentlyContinue
    Remove-Item Env:TELEGRAM_COURSES_DATABASE_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:TELEGRAM_COURSES_DOWNLOAD_DIR -ErrorAction SilentlyContinue

    & $runtime -I $launcher smoke
    if ($LASTEXITCODE -ne 0) { throw 'Smoke de inicialização do aplicativo falhou.' }
    & $runtime -I $launcher --help
    if ($LASTEXITCODE -ne 0) { throw 'Smoke de ajuda da CLI falhou.' }

    $settingsPath = Join-Path $smokeLocalAppData 'telegram_courses_data\settings.toml'
    $databasePath = Join-Path $smokeLocalAppData 'telegram_courses_data\catalog.sqlite3'
    if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) {
        throw 'Configuração inicial não foi criada em LOCALAPPDATA.'
    }
    $settingsHashBefore = (Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash
    $settingsContents = Get-Content -LiteralPath $settingsPath -Raw
    if ($settingsContents -match '(?i)api.?hash|password|secret|token|session') {
        throw 'A configuração padrão contém um nome de campo sensível.'
    }
    if ($settingsContents -match [regex]::Escape($stagingPackage)) {
        throw 'A configuração persistente aponta para dentro do pacote.'
    }

    & $runtime -I -c "import asyncio,sys; from telegram_courses.sqlite_repository import SQLiteMessageRepository; asyncio.run(SQLiteMessageRepository(sys.argv[1]).migrate())" $databasePath
    if ($LASTEXITCODE -ne 0) { throw 'Smoke de persistência do banco local falhou.' }
    & $runtime -I $launcher catalog list
    if ($LASTEXITCODE -ne 0) { throw 'Smoke do comando de catálogo falhou.' }
    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
        throw 'O banco de dados não foi criado fora do pacote.'
    }
    & $runtime -I $launcher smoke
    if ($LASTEXITCODE -ne 0) { throw 'Smoke de reabertura do aplicativo falhou.' }
    $settingsHashAfter = (Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash
    if ($settingsHashAfter -ne $settingsHashBefore) {
        throw 'As configurações padrão mudaram ao reabrir o aplicativo.'
    }
}
finally {
    foreach ($name in $oldEnvironment.Keys) {
        if ($null -eq $oldEnvironment[$name]) {
            Remove-Item ("Env:" + $name) -ErrorAction SilentlyContinue
        } else {
            Set-Item ("Env:" + $name) $oldEnvironment[$name]
        }
    }
}

$forbiddenFiles = Get-ChildItem -LiteralPath $stagingPackage -File -Recurse -Force | Where-Object {
    $_.Name -match '(?i)^(credentials\.dpapi|session\.dpapi|settings\.toml|catalog\.sqlite3|\.env(?:\..*)?|.*\.session(?:-journal)?)$' -or
    $_.Extension -match '(?i)^\.(sqlite|sqlite3|db|log|pyc|pyo)$'
}
if ($forbiddenFiles) {
    throw 'O pacote contém um arquivo de estado local que não pode ser distribuído.'
}
$files = Get-ChildItem -LiteralPath $stagingPackage -File -Recurse -Force | ForEach-Object {
    [ordered]@{
        path = $_.FullName.Substring($stagingPackage.Length + 1).Replace('\', '/')
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        bytes = $_.Length
    }
}
$manifest = [ordered]@{
    schema = 'telegram-courses-windows-candidate-v1'
    status = 'CANDIDATE_UNVERIFIED'
    target = 'Windows x64; user mode'
    python = 'CPython 3.14.7'
    file_count = @($files).Count
    files = @($files)
}
$manifestJson = $manifest | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText(
    (Join-Path $stagingPackage 'package-manifest.json'),
    $manifestJson + "`n",
    [System.Text.UTF8Encoding]::new($false)
)

Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory(
    $stagingPackage,
    $stagingZip,
    [IO.Compression.CompressionLevel]::Optimal,
    $false
)
$archive = [IO.Compression.ZipFile]::OpenRead($stagingZip)
try {
    if (-not ($archive.Entries | Where-Object { $_.FullName -eq 'launch.cmd' })) {
        throw 'O arquivo ZIP não contém o comando de inicialização.'
    }
    if (-not ($archive.Entries | Where-Object { $_.FullName -eq 'package-manifest.json' })) {
        throw 'O arquivo ZIP não contém o manifesto de hashes.'
    }
} finally {
    $archive.Dispose()
}

Move-Item -LiteralPath $stagingPackage -Destination $packagePath
Move-Item -LiteralPath $stagingZip -Destination $zipPath
Write-Output "CANDIDATE_UNVERIFIED: $packagePath"
Write-Output "ZIP: $zipPath"
Write-Output "SMOKE_LOCALAPPDATA: $smokeLocalAppData"
