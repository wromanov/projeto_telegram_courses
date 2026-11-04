# S7 — Implementação corretiva contratada — 2026-10-26

## Registro da atividade

~~~text
ACTIVITY_ID = S7_CONTRACTED_CORRECTIVE_IMPLEMENTATION_2026-10-26
ACTIVITY_COMPLETION_PERCENT = 100% / implementação corretiva e gates offline concluídos; aceite formal da S7 permanece separado e pendente
ROUTER_INVOCATION = USER_EXPLICIT / codex-task-router / roteamento e gate aplicados
AGENTS_USED = ROOT; mechanical_implementer; validator; diagnostic_analyst; scribe
AGENT_MODELS_AND_EFFORTS = Declarações dos TOMLs: mechanical_implementer gpt-6-luna/high (projeto); validator gpt-6-luna/high (global e projeto); diagnostic_analyst gpt-6.1-sol/medium (global e projeto); scribe gpt-6-luna/high (projeto; global declara medium); modelo/effort do ROOT não expostos. Atribuições reais do runtime não foram verificadas independentemente.
CONTRACT_STATUS = APPROVED / aprovação expressa registrada em 2026-10-26
CORRECTIONS_IMPLEMENTED = FIX-01..FIX-06 / correções S7 autorizadas; duas correções de fixture limitadas ao teste RASMOO
ENVIRONMENT_GATE = PASS no contexto Windows nativo validado / perfil restrito padrão permaneceu incompatível com socketpair e asyncio
FOCUSED_TESTS = GATE A 19 PASS; GATE B 38 PASS; GATE C 31 PASS; Gate C exigiu dois ciclos corretivos de teste
MIGRATION_006 = PASS / repository assíncrono executou migrate duas vezes e preservou versão 006 e high-water legado
FULL_OFFLINE_REGRESSION = PASS / 340 passed, 11 subtests passed, 0 failures, 0 errors, 0 skips
RUFF = PASS / .venv\Scripts\ruff.exe check --no-cache nos 12 arquivos Python desta atividade
DIFF_CHECK = PASS / git diff --check exit 0; avisos LF→CRLF do working tree; scan independente sem whitespace final nos 13 arquivos de código/teste/migration
IDENTITY_INTEGRITY = PASS para os casos sintéticos offline executados / ausência de evidência positiva de exclusão remota permanece aberta
S7_A1 = PASS / idempotência, replay, novas mensagens e monotonicidade de high-water exercitados
S7_A2 = PARTIAL / falha, rollback, retomada e checkpoint parcial exercitados; caso específico de cancelamento não foi comprovado
S7_A3 = PASS / identidade legada desconhecida, mismatch, NOT_OBSERVED e preservação exercitados
S7_A4 = PARTIAL / ausência e falha de acesso diferenciadas; A4-C permanece OPEN_DECISION sem fonte positiva de exclusão remota
S7_A5 = PASS / migração assíncrona, aplicação repetida, rollback, FK, WAL e reopen exercitados em DB temporário
S7_A6 = PARTIAL / rotas genérica e RASMOO em duas execuções e scan parcial exercitados; falha de catálogo como falha global não foi demonstrada por assertion S7 específica
S7_ACCEPTANCE = PENDING_USER_APPROVAL
S8_STATUS = DEFERRED / NOT_AUTHORIZED
REAL_TELEGRAM_CALLS = 0
GIT_PUBLICATION = NO / sem stage, commit ou push
PROJECT_STATE_RECONCILIATION = PASS / ROOT revisou campos e resumos; git diff --check exit 0 (avisos LF→CRLF somente); scan de whitespace do relatório limpo; nenhum source/test foi alterado nesta QA
DELIVERY_STATUS = SENT / DESTINATION=Projeto Telegram 3.0 / THREAD_ID=6add6aa9-12e0-83e8-b02f-870f0a0edaf9 / isError=false
NEXT_EXACT_ACTION = Aguardar decisão humana separada sobre o aceite formal S7. Manter S8 deferred e não autorizada.
~~~

## Escopo e resultado

O usuário aprovou expressamente o contrato corretivo S7 e autorizou implementação e validação offline exclusivamente para S7. Esta atividade implementou FIX-01 a FIX-06, executou os gates autorizados e preservou S6 como CLOSED_WITH_EXCEPTIONS, V1 ativa, V2 global desligada, os limites S5 e a política REMOTE_HASH_REQUIRED / fail-closed.

Foram alterados seis módulos de produção, adicionada a migration 007 e ajustados seis arquivos de testes. As migrations 001–006 não foram alteradas. O Gate C encontrou dois defeitos no fixture RASMOO: o descritor opcional de mídia era iterado como coleção de pares; após a correção, as consultas de snapshot pediam uma coluna id inexistente. Dois ciclos corretivos, dentro do limite autorizado, alteraram somente tests/integration/test_s7_incremental_cli.py. O Gate C final passou.

A conclusão desta atividade não encerra nem aceita formalmente a sprint S7. S7-A2 e S7-A4 permanecem parciais; S7-A6 permanece parcial pelo critério de falha global de catálogo não demonstrado. A4-C continua em aberto por ausência de fonte positiva para confirmar exclusão remota. S8 continua diferida e não autorizada.

## Roteamento e ownership

O gate do codex-task-router foi invocado explicitamente. Foram consultados o skill de roteamento, agent-catalog, model-policy, routing-matrix e os perfis TOML globais e do projeto. A atividade correu em modo multiagente conforme a autorização do pedido.

- ROOT coordenou, integrou, executou e adjudicou os gates.
- mechanical_implementer foi o único writer de código e testes.
- validator fez revisão independente read-only e não executou testes.
- diagnostic_analyst investigou read-only a demora do Gate B; não repetiu a auditoria Architect.
- scribe materializou este relatório e a atualização documental.

Os modelos e efforts acima são declarações encontradas nos TOMLs. A atribuição efetiva de runtime não foi verificada independentemente.

## Ambiente

O runtime usado nos gates dinâmicos foi o contexto Windows nativo elevado previamente validado: PowerShell 7.6.5, CPython 3.14.7 no .venv e pytest 9.1.1. Os gates usaram TEMP/TMP e basetemp isolados. I/O de arquivo temporário passou nesse contexto; resultados anteriores de socketpair e asyncio Proactor/Selector com saída natural 0 foram reutilizados sem repetir probes documentadas.

No perfil restrito padrão, TEMP I/O passou, mas socketpair excedeu 3 segundos e o asyncio mínimo excedeu 15 segundos. Isso não foi tratado como resultado do perfil nativo.

## Gates e evidências

| Gate | Comando/escopo | Resultado |
|---|---|---|
| A — casos das correções | Python -I -B, pytest -q, cache desabilitado, basetemp isolado; 14 node IDs selecionados | 19 passed em 6,06 s. A lista exata dos 14 selectors não foi preservada nesta atividade e não é reconstruída por inferência. |
| B — identidade e proteção de caminhos | tests/unit/test_s6_v2.py; tests/integration/test_cli_smoke.py; test_offline_download_rerun_is_deduplicated | Primeira execução foi interrompida após mais de 8 min sem resumo; nenhum resultado foi contado como PASS. A análise estática apontou custo do snapshot integral. Um node diagnóstico passou em 53,74 s e a stack aos 30 s estava em pathlib.open. Com essa evidência, a reexecução detalhada terminou naturalmente: 38 passed em 1042,07 s (17:22), zero failures/errors/skips. O node mais lento, test_t09_configuration_matrix_runs_through_cli, levou 544,29 s. |
| C — integração S7 | tests/integration/test_s7_incremental_sync.py e test_s7_incremental_cli.py | Após dois ciclos corretivos somente de teste: 31 passed em 12,01 s; exit 0. |
| D — migration 006 | test_legacy_complete_scan_remains_a_confirmed_baseline | 1 passed em 0,78 s; migrate assíncrono repetido, versão 006 e high-water legado preservados. |
| E — regressão offline acumulada | Python -B -m pytest -vv --durations=20 --tb=short -p no:cacheprovider --basetemp isolado tests/unit tests/integration | A primeira invocação com -I parou na coleta por ModuleNotFoundError: tools; nenhuma asserção foi executada. A versão sem -I manteve -B e coletou 340 testes: 340 passed, 11 subtests passed, em 1319,06 s (21:59); exit 0, sem falhas, erros ou skips. tests/manual_proofs e o Harness S6 não foram executados. |
| F — QA estático | .venv\Scripts\ruff.exe check --no-cache nos 12 arquivos Python da atividade; git diff --check; scan trailing whitespace em 13 arquivos de código/teste/migration | Ruff passou (1,298 s); git diff --check exit 0, com avisos de conversão LF→CRLF; scan retornou NO_TRAILING_WHITESPACE. |

O teste que importa tools.manual_proofs dentro da regressão offline substituiu credenciais e TelethonGateway por fakes. Ele não carregou sessão nem executou RPC. Não houve chamadas reais ao Telegram, downloads reais, acesso ao banco original, alteração de .part ou de proof S6.

O primeiro resultado de Gate C foi 30 passed / 1 failed por construção do fixture. Após o primeiro ciclo, o teste revelou a consulta inválida da coluna id; o schema catalog_node_identity usa a chave composta e catalog_node_id. O segundo ciclo ajustou somente as duas consultas de snapshot. O resultado final de Gate C e a regressão acumulada confirmaram o fixture corrigido.

## Compatibilidade e estado de aceite

- FIX-01: high-water confirmado monotônico; cursores parciais não são promovidos.
- FIX-02: identidade de downloads legados tem proveniência desconhecida explícita; ausência de prova não autoriza reuse.
- FIX-03: mídia ausente observada permanece NOT_OBSERVED e não vira tombstone.
- FIX-04: ownership é tri-state; UNKNOWN não é tratado como DEAD; FAILED_RETRYABLE com owner liberado continua admissível.
- FIX-05: fixtures incluem cadeia legada, reapply de migrations, rollback, FK/WAL/reopen, CLI RASMOO e estados de ownership/identidade.
- FIX-06: as 20 falhas históricas continuam classificadas como 9 V2 / 9 CLI / 2 migration; node IDs e recibos continuam UNRECONCILED. Os testes verdes desta atividade não reduzem administrativamente essa linha de base.

S7-A1 passou porque os casos cobrem primeira inserção, replay, nova mensagem, edição e monotonicidade. S7-A2 é parcial porque falha/rollback/retomada foram exercitados, mas um caso específico de cancelamento não foi comprovado. S7-A3 passou nos casos exercitados de identidade e preservação. S7-A4 permanece parcial por A4-C. S7-A5 passou nos casos de schema e migration temporários. S7-A6 é parcial: os caminhos generic e RASMOO completam duas execuções e o scan parcial não recompõe o catálogo, mas o critério de falha de catálogo que se propaga como falha global não possui assertion específica demonstrada aqui.

O aceite formal da S7 continua decisão humana. Nenhuma evidência desta atividade autoriza iniciar S8 ou operar contra Telegram.

## Estado Git e preservação

Repo root: C:\Users\walac\desenvolvimento\projeto_telegram_courses. Branch work/s0-bootstrap, HEAD 98d9d6b9ce152b8d2764a4d160fcbdf4722fb257, upstream origin/work/s0-bootstrap. O working tree já continha WIP extenso de S6/S7; ele foi preservado. Não houve reset, clean, stash, stage, commit ou push.

Não existe fingerprint de todos os arquivos anterior ao primeiro edit desta atividade. O primeiro snapshot registrado, às 2026-10-26T01:22:30-03:00, foi capturado depois das alterações autorizadas iniciais em sqlite_repository.py e da migration 007. Portanto, ele não é apresentado como baseline pré-edit.

### SHA-256 final dos arquivos desta atividade

~~~text
B153DB3C09A755A70651CAC360F6968030A680A817510305FB83A00C587B7AC0  src/telegram_courses/sqlite_repository.py
F958ADB731385E31EAD0CD8CE6180DDE48B4967D632C2062F4F629DD4E7C94F8  src/telegram_courses/download_repository.py
46D8B079BE1B56DA51916FC7F6176D6A07A532EAF38191F48B3F667F6CE11C52  src/telegram_courses/downloads.py
D7AE3EBC54D8FC5474F4140C92EB126B4223C1F1E22B73AAA4E5CE9D0BD6361E  src/telegram_courses/message_scanner.py
E6308931E2840309B353138FCBA0B259A0DA8C1A681753C88A340550435AD3D8  src/telegram_courses/s5_downloads.py
BF3864AD20B130A23A0837521A954702CB1B0A7EF2ECA01A7B6620F7BC7D9809  src/telegram_courses/cli.py
555FA6D9A143A7E25BC12935CD962EC061E802A0D770EBAC4B7DF36D4E26C20F  src/telegram_courses/migrations/007_s7_corrective_identity_observation.sql
ED27BCB96C85E71A1C8879DB4B59629D60EDF073DAD48CBB5B37195385D5936F  tests/integration/test_s7_incremental_sync.py
783C4B3521B767CD4D5EEFBC4E1F79F5FD2305C2816F2AB2FE811D6DD4DF9BA3  tests/integration/test_s7_incremental_cli.py
0B1072DB4EB3C725EAAA4262D6B84DBB18C65526104F62BABA5766A7AD5815E3  tests/integration/test_sqlite_repository.py
6669B1DD49FFA2CFDD20D56A2BA4029A4FF18E274BFA6630E15EDB6C880CDF5E  tests/integration/test_cli_smoke.py
5C7D97E068123E5651285C263C67F332333FE924CF2FD99F8F7DE49706846A3B  tests/integration/test_download_flow.py
D695D5AC168661E3AB703367BFFF97D6959EE4E2455E7CF420C5D373FFD1EB1B  tests/unit/test_s6_v2.py
~~~

Migrations 001–006 permaneceram bytewise inalteradas:

~~~text
FD20A36268EA068F12A086F75081AE1E943F061753F8D04A35E59C1C25C1B2E7  001_initial.sql
3FCC6D0B9F345B83D18BAF14E503D8101000223D52E850A6F10E301F8180E5EB  002_catalog.sql
AAD7F2CCF97A2DBD8716F803EE0D4ADEE68E0C37040FE5A5249830A8C1EADAF2  003_catalog_unresolved.sql
6C03150152EB539D3C523132E1E6DE8A863715DDC89ECBF384BBAF8EE9BEAE7B  004_downloads.sql
746261727EBB1E621718D5A933514545E9515DBBC3DDEDE74400C165F23AB9D2  005_s6_integrity_v2.sql
63F44B90B97B2EB8DB0A2388AED506100F9BC25E0538F72B2D693B6A1D0DF35B  006_s7_incremental_sync.sql
~~~

## Entrega e continuidade

Relatório anterior preservado: docs/reports/S7_INCREMENTAL_SYNC_IMPLEMENTATION/REPORT.md. A continuidade corrente registra a implementação corretiva completa, gates A–F concluídos, S7-A2/A4/A6 parciais e aceite pendente. O mapa de authorities e o histórico decisório apontam para este relatório e para o contrato corretivo aprovado, sem alterar o texto do contrato integrado congelado.

DELIVERY_STATUS = SENT / resumo enviado ao chat Projeto Telegram 3.0 / threadId 6add6aa9-12e0-83e8-b02f-870f0a0edaf9 / isError=false
