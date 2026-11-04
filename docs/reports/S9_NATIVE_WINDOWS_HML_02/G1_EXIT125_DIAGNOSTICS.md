# S9 G1 — matriz de saída 125 e diagnóstico sanitizado

## Matriz estática

| Ponto | Comportamento |
| --- | --- |
| Bootstrap: origem do módulo diferente ou ambiente supervisionado inválido | Retorna 125; emite `MODULE_ORIGIN_MISMATCH` ou `INVALID_ENVIRONMENT`. |
| Bootstrap: argumentos, consulta ou carregamento do módulo falham com exceção | Processo termina com 1; emite identificador fixo da falha. |
| Worker retorna antes da inicialização T24 | O worker retorna 2 ou 4; a finalização T24 pode converter para 125 por não haver handler válido. Ambos os diagnósticos são emitidos separadamente. |
| Worker falha após inicialização T24 | O worker mantém seu retorno 4; T24 só altera para 125 se a finalização falhar. |
| Exceção não tratada no worker | Processo mantém saída 1; emite identificador fixo, sem traceback ou texto de exceção. Falha adicional de finalização também é identificada separadamente. |
| Finalização T24 retorna 125 ou lança exceção | Emite `FINALIZATION_FAILED` ou `FINALIZATION_EXCEPTION`; mantém a semântica original de saída. |

O recibo da execução anterior contém `CHILD_EXIT_NONZERO` e 125, sem ramo interno ou observação de rede. O código, portanto, não identifica retroativamente a causa nem prova que houve ou não RPC.

## Instrumentação

O subprocesso G1 emite objetos JSON na saída de erro com somente `event`, `phase`, `state` e `failure_class`. As fases cobrem bootstrap, entrada do worker, contexto/manifesto, inicialização T24, abertura do gateway, descoberta, persistência da evidência, logging e finalização T24. As classes e razões são escolhidas em listas fixas; não são incluídos mensagens de exceções, caminhos, credenciais, identificadores do canal ou payload.

O diagnóstico é independente dos handlers T24 e pode aparecer antes da persistência do recibo. Se a saída de erro estiver indisponível, a emissão é best-effort e pode ser perdida; ela não é um recibo do ledger. O bloqueio e os códigos de saída permanecem os mesmos. As falhas esperadas do worker e da finalização são diagnosticadas separadamente. O bootstrap suprime traceback de exceções tratadas e mantém saída 1 nesses casos.

## Validação e retomada

Foram aprovados 46 testes offline focados de bootstrap, worker, gateway falso, G0 e T24, incluindo falha do fluxo diagnóstico e erro inesperado do worker. Um teste adicional executou o bootstrap isolado em outro processo e confirmou bloqueio de ambiente não supervisionado com saída 125. Ruff e compileall passaram. A instrumentação não prova a causa histórica e não afirma que o defeito subjacente foi corrigido. Nenhum Telegram real, segredo DPAPI, S10 ou publicação Git foi usado.

O contrato S9 conserva SHA256 `BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2`. Para a próxima execução nativa autorizada, usar uma nova run; G0 e G4 continuam interativos:

```powershell
Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
& '.\tools\RUN_S9_NATIVE_WINDOWS_HML_02.ps1'
```

Se G1 falhar, compartilhar apenas as linhas JSON com `event=s9.g1.diagnostic`. A tentativa anterior não dispõe dessas linhas e não deve ser reutilizada.
