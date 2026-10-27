param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$previousBackend = $env:RAG_BACKEND
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or later is required.' }
    }
    & $pythonPath -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

    # This shortcut intentionally starts the keyless local demo.
    # Follow the README's separate instructions for opt-in API mode.
    $env:RAG_BACKEND = 'demo'
    & $pythonPath manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
    & $pythonPath manage.py build_index --backend demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo index creation failed.' }
    Write-Host "Local extractive demo: http://127.0.0.1:$Port/"
    & $pythonPath manage.py runserver "127.0.0.1:$Port"
    if ($LASTEXITCODE -ne 0) { throw 'The development server stopped with an error.' }
}
finally {
    if ($null -eq $previousBackend) { Remove-Item Env:RAG_BACKEND -ErrorAction SilentlyContinue }
    else { $env:RAG_BACKEND = $previousBackend }
    Pop-Location
}
