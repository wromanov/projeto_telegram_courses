# S9 bootstrap de schema — correção offline

**Atividade:** `TELEGRAM_S9_BOOTSTRAP_SCHEMA_REMEDIATION_01`
**Atividade pai:** `TELEGRAM_S9_NATIVE_WINDOWS_HML_02`
**Data:** 2026-11-02
**Resultado:** correção implementada e validada offline; preflight nativo ainda não executado.

## Decisão e autoridade

O operador pediu que o ROOT chamasse o perfil `diagnostic_analyst` para propor a solução e que o ROOT implementasse. O diagnóstico foi somente leitura; a implementação ficou no ROOT. O perfil declara `gpt-6.1-sol / medium`; o runtime não expôs os metadados efetivos de modelo/effort, portanto esses metadados ficam `UNVERIFIED`.

`ROUTING_MODE_ACTUAL = MULTIAGENT / ROOT + diagnostic_analyst`
`SCOPE = OFFLINE_SCHEMA_BOOTSTRAP / S9_FROZEN / NO_S10 / NO_GIT_PUBLICATION`.

## Causa confirmada

O `_preflight()` em `tools/s9_native_windows_hml_02.py` tentava ler uma fotografia de catálogo final antes de criar a execução e apresentar G0. Essa leitura exigia tabelas e contagens que só podem existir depois da descoberta, varredura e catalogação S9. Com isso, ausência de schema/dados futuros era tratada como impedimento anterior a G0, embora o contrato coloque a aceitação quantitativa em G3.

O banco preparado permanece evidência local incompleta: integrity check `ok`, somente migration 1, zero `catalog_nodes` e sem as tabelas finais observadas no diagnóstico anterior. A correção não inventa nem preenche contagens.

## Correção implementada

- Para cada execução, a ferramenta copia o SQLite isolado para a pasta privada da execução e aplica nessa cópia o caminho oficial e idempotente `DownloadRepository.migrate()` → repositórios SQLite. A origem HML e o banco original não são migrados nem sobrescritos.
- A cópia precisa terminar com migrations 1–7, schema/colunas requeridos, `integrity_check`, `foreign_key_check` e guard privado válidos antes de oferecer G0. Bancos novos recebem o schema oficial completo.
- A proposta de manifesto é explicitamente planejada: mínimos `TRACK=1`, `COURSE=2`, `MODULE=2`, expectativa `PENDING_G3`, sem declarar observações ou unresolved count ainda inexistentes. Os limites S9 continuam fixos: 200 mensagens, 600 observações, 1 item, 128 MiB por item, 512 MiB agregados, 1 worker, 1 tentativa e hash remoto obrigatório. Manifesto é imutável e vinculado por hash.
- Se o banco local não resolver uma única identidade RASMOO, a ferramenta pede o channel ID no TTY local sem registrá-lo em logs. G1 também exige correspondência de título/username com o alias aprovado; divergência bloqueia.
- G3 valida contagens observadas contra os mínimos, registra os valores observados e bloqueia quando insuficientes. Compatibilidade com manifestos legados de contagens exatas foi preservada.
- G0 continua interativo e anterior à primeira RPC. G4 continua interativo e anterior à fila/download. O limite de uma hora só começa depois da preparação da execução; não foi iniciado nesta validação.

## Arquivos

- `tools/s9_native_windows_hml_02.py`
- `src/telegram_courses/s9_real_gate_producers.py`
- `src/telegram_courses/s9_gate_reconciliation.py`
- `tests/unit/test_s9_bootstrap_schema.py` (novo)
- `tests/unit/test_s9_real_gate_producers.py`
- `tests/unit/test_s9_gate_reconciliation.py`
- `docs/continuity/PROJECT_STATE.md`
- `docs/continuity/CONTINUITY_RECORD.md`
- `docs/continuity/handoff/LAST_HANDOFF.md`

## Validação

Comando offline focado executado:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .pytest-temp-s9-bootstrap-escalated-20261102 tests/unit/test_s9_bootstrap_schema.py tests/unit/test_s9_real_gate_producers.py tests/unit/test_s9_gate_reconciliation.py tests/integration/test_sqlite_repository.py tests/integration/test_s9_queue_flow.py
```

Resultado: **130 passed**, 0 falhas, em 202,85 s. Os testes usam SQLite temporário e gateways sintéticos; nenhuma RPC real foi chamada. A tentativa no sandbox restrito não conseguiu iniciar o loop asyncio por bloqueio do socket local do AppContainer; a mesma seleção offline foi então executada no runtime aprovado, sem acesso/uso do Telegram.

Também passaram `ruff check`, `compileall`, parse AST do PowerShell 5.1 e `git diff --check`. O SHA256 do contrato congelado permanece `BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2`.

O resumo sanitizado foi enviado pela integração nativa ao chat canônico `Projeto Telegram 3.0`; a ferramenta confirmou o destino, porém a leitura subsequente ainda não mostrou a nova mensagem. Portanto, a entrega está `ACKNOWLEDGED / READBACK_NOT_CONFIRMED`; não foi feita tentativa por outro canal.

## Estado operacional e retomada

```text
IMPLEMENTATION = READY_FOR_NATIVE_PREFLIGHT
OFFLINE_VALIDATION = PASS / 130_TESTS
NATIVE_ACL_AND_SQLITE_GUARDS = NOT_REVALIDATED_IN_THIS_RUNTIME
NATIVE_LAUNCHER_PREFLIGHT = NOT_RUN
G0_READY = CONDITIONAL_ON_NATIVE_PREFLIGHT / G0_PASS = NOT_RUN
G4_REQUIRED = YES / G4_PASS = NOT_RUN
REAL_TELEGRAM_RPC = 0 / REAL_DOWNLOAD_BYTES = 0
ONE_HOUR_DEADLINE = NOT_STARTED
CANONICAL_REPORT_DELIVERY = ACKNOWLEDGED / READBACK_NOT_CONFIRMED
S10 = NOT_EXECUTED / GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
```

No PowerShell 5.1 nativo, o operador pode retomar com:

```powershell
Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
& '.\tools\RUN_S9_NATIVE_WINDOWS_HML_02.ps1'
```

O operador deve inspecionar a proposta e responder ao G0 no terminal antes de qualquer RPC; o G4 será solicitado antes do download. Este relatório não afirma que ACL, G0 ou G4 passaram no host nativo. O contrato S9, banco isolado original e conteúdo DPAPI foram preservados; nenhum secret foi lido.
