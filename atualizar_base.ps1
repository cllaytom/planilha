# Reimporta a planilha oficial para o banco (idempotente: atualiza, nao duplica).
# Use sempre que alterar a planilha no Excel.

$origem = "D:\area  nova\planilha clientes\GERENCIAMENTO DE ASSINATURAS IPTV 86.7 - Copia.xlsb"

if (-not (Test-Path $origem)) {
    Write-Error "Planilha nao encontrada: $origem"
    exit 1
}

$env:PYTHONPATH = $PSScriptRoot
python "$PSScriptRoot\scripts\importar_planilha.py" $origem
