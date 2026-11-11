# sobe a API em modo desenvolvimento (local)
$env:PYTHONPATH = $PSScriptRoot

$banco = Join-Path $PSScriptRoot "dados\assinaturas.db"
if (-not (Test-Path $banco)) {
    $origem = "D:\area  nova\planilha clientes\GERENCIAMENTO DE ASSINATURAS IPTV 86.7 - Copia.xlsb"
    if (Test-Path $origem) {
        Write-Host "Banco nao encontrado. Importando $origem ..."
        python "$PSScriptRoot\scripts\importar_planilha.py" $origem
    } else {
        Write-Warning "Banco vazio e planilha de origem nao encontrada. Rode scripts\importar_planilha.py."
    }
}

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
