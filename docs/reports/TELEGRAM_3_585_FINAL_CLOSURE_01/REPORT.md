# TELEGRAM-3-585-FINAL-CLOSURE-01 — relatório consolidado

```text
ACTIVITY_ID = TELEGRAM-3-585-FINAL-CLOSURE-01
EXECUTION_HOST = ROMA_CASA / Codex local Windows
EXECUTION_MODE = GATE_1_COMPLETE / GATE_2_RECOVERY_COMPLETE
GATE1_DECISION = PASS_WITH_FINDINGS_TECHNICAL / PROCESS_EXCEPTION_ACCEPTED_WITH_RESERVATION
GATE1_TEST_RESULTS = FULL_SUITE_829_PASS_11_SUBTESTS_PASS / FOCUSED_569_PASS / FIXTURE_SEQUENCE_2_PASS / HASH_SUBSET_INCLUDED
GATE1_INDEPENDENT_REVIEW = ACCEPT_WITH_FINDINGS
GATE1_FINDINGS = comportamento socketpair/event loop depende do contexto; 5 consultas Git read-only históricas aceitas com ressalvas, sem retroatividade; 3 findings Ruff global fora do escopo
GATE1_DIAGNOSTIC = timeout externo no Codex supervisionado e sucesso no PowerShell nativo; a política exata que causa a diferença não foi identificada
SOLUTION_CONTRACT = diagnóstico offline em ambos contextos com timeout externo; fixture finaliza handler em finally; bateria focada e regressão completa; revisão independente; sem mudanças de produção/S9/V2
GATE2_AUTHORIZATION = AUTHORIZED_BY_USER_MESSAGE_2026-11-03 / limited to one final attempt after G0/G4
GATE2_DECISION = PASS / AUTHORIZED_AND_EXECUTED_WITH_HUMAN_G0_G4
GATE2_PREFLIGHT = PASS_READ_ONLY / DB quick_check ok / identity local match / attempts=3 / prefix size and hash match previous marker / 586,587 untouched / no concurrent project Python / disk capacity sufficient
G0 = PASS / operador confirmou SIM no Windows PowerShell 5.1 nativo
G4 = PASS / operador confirmou S após plano fresco: somente 585; 1 mídia; 170323 bytes pendentes; limite PASS; REMOTE_HASH_REQUIRED e REMOTE_HASH_FULL
RECOVERY585 = COMPLETED / quarta tentativa única passou no pós-guard
ATTEMPTS = 4_CUMULATIVE / 3_PRIOR + 1_THIS_ACTIVITY
DOWNLOAD_BYTES = 170323 / FINAL_FILE_BYTES = 6199635
REMOTE_HASH_RESULT = REMOTE_HASH_REQUIRED / REMOTE_HASH_FULL_COMPLETED / NO_DOWNGRADE
PREFIX_INTEGRITY = PRESERVED / local SHA-256 e prefixo original passaram no pós-guard
FINAL_FILE_STATUS = DOWNLOADED / post-validation PASS
S9_IMPACT = no production, S9 or V2 code/contract changes; operation limited to message 585; global S9 approval not implied
GIT_OPERATIONS = 5_READ_ONLY_QUERIES_HISTORICAL / 0_DURING_GATE2_EXECUTION / NO_MUTATION
TELEGRAM_RPC_COUNT = EXECUTION_OCCURRED / exact count not emitted in captured output
OPERATIONAL_DATA_TOUCHED = one authorized recovery of message 585 / DB reports DOWNLOADED and attempts=4 / 586,587 untouched
RESIDUAL_RISKS = cinco consultas Git read-only históricas foram aceitas com ressalvas, sem conformidade retroativa; três findings Ruff globais fora do escopo; resposta remota detalhada da terceira tentativa não preservada, portanto sua causa segue sem comprovação
OVERALL_STATUS = COMPLETED / GATE1_TECHNICAL_PASS_WITH_FINDINGS / GATE2_PASS / RECOVERY585_COMPLETED
NEXT_ACTION = nenhuma para recuperação 585; 586/587 exigem autorização operacional específica
DELIVERY_STATUS = SENT_UNCONFIRMED / MCP_ACCEPTED / READBACK_NOT_OBSERVED
```

## Escopo executado

- Corrigido o teste de scan supervisionado para registrar a admissão do processo filho no ledger e definir o estágio `scan`; a fixture finaliza o handler operacional em `finally`, enquanto `capsys` ainda está ativo, evitando que o handler retenha o stream e contamine testes seguintes.
- Corrigida a fixture do manifesto sintético G1 para usar `SYNTHETIC_TARGET`, coerente com o canal descoberto e com o alias de escopo; os dois cenários que compartilham a fixture recebem a correção.
- Os validadores de produção e o caminho de hashes não foram alterados.
- Reconciliados os rótulos duplicados de continuidade: somente o checkpoint mais recente permanece marcado como vigente; checkpoints anteriores foram renomeados sem mudar as decisões registradas.

## Verificações

- Um teste mínimo de `socket.socketpair()`/`asyncio.new_event_loop()` com timeout externo de 5 s excedeu o limite no contexto Codex supervisionado e passou no PowerShell nativo. Isso demonstra dependência do contexto de execução; a regra de sandbox/política exata responsável não foi identificada. Nenhum ajuste de produção foi proposto para mascarar a diferença.
- O teste de scan, executado sozinho, passava, mas deixava um handler de logging retido e ligado ao stream temporário do `capsys`. No processo supervisionado, o handler permanecia fail-closed e interferia nos testes G1 seguintes. Após a fixture chamar `finalize_s9_child_exit_code` em `finally`, a sequência scan→G1 passou 2/2.
- Regressão completa no PowerShell nativo, com timeout externo de 15 min, `faulthandler_timeout=180` e `basetemp` sob Windows Temp: **829 passed, 11 subtests passed em 779.95 s**, código de saída 0. Houve uma captura de stack aos 180 s durante um E2E; a execução prosseguiu e concluiu com sucesso.
- Bateria focada de 25 arquivos relevantes: **569 passed em 349.69 s**, código de saída 0. O teste E2E custoso foi coberto pela suíte completa.
- Uma execução preliminar da suíte com `basetemp` dentro do repositório terminou em 815 passed / 14 failed / 11 subtests em 378.94 s; os erros decorreram de guards DPAPI/session acionados pela localização temporária. Essa execução não foi usada como resultado válido; a regressão completa subsequente foi executada com temporário externo ao repositório.
- Ruff direcionado aos seis arquivos Python do escopo passou. Ruff global (`src tests tools`) mantém três findings em `manual_proofs` fora do escopo: dois imports não ordenados e uma variável não usada.
- `compileall -q src tests tools` passou.
- A revisão independente foi `ACCEPT_WITH_FINDINGS`: nenhum defeito material novo de hashes; confirmou validação integral dos lotes, prova com faixas verificadas, opt-in do EOF restrito ao piloto 585 e `REMOTE_HASH_FULL` antes da finalização. A revisão estática não substitui a regressão executável nem comprova por comparação histórica os contratos S9/V2.

## Findings de processo e evidência

- **Alto — processo:** foram executadas cinco consultas Git somente de leitura (repo root, branch, HEAD, status e remotes), apesar da instrução expressa de não executar operações Git. Não houve staging, alteração Git ou publicação. A exceção não foi ocultada nem convertida em conformidade.
- **Médio — ambiente:** o event loop/socketpair excede timeout no contexto Codex supervisionado e passa no PowerShell nativo. Diagnóstico identifica dependência do contexto, mas não a política interna específica. A regressão completa foi validada no PowerShell nativo.
- **Médio — Ruff global:** três achados em arquivos `manual_proofs` fora do escopo permanecem sem alteração.
- **Informativo — evidência histórica:** a resposta exata do Telegram na terceira tentativa não foi preservada; a hipótese do lote com EOF excedente continua não comprovada como causa daquela falha real.

Durante o preflight não ocorreu RPC nem download; o banco operacional e o `.part` foram inspecionados somente em leitura. Depois, o operador confirmou G0 e G4 em console nativo e a quarta tentativa única foi executada para a mensagem 585. O CLI concluiu com uma mídia, zero falhas, 170.323 bytes transferidos e status `COMPLETED`; o pós-guard confirmou `ATTEMPTS=4`, `DOWNLOADED`, SHA-256 local, preservação do prefixo, caminho `REMOTE_HASH_FULL` e ausência de tentativas em 586/587. A captura não informa o número exato de RPCs.

## Contrato de solução proposto pelo Diagnostic Analyst

1. Manter a investigação do event loop estritamente offline: sondagem mínima com timeout externo no PowerShell nativo e no Codex supervisionado; registrar diferença sem inferir a política interna não observada.
2. Conter o defeito da fixture em teste: finalizar o handler/admissão em `finally` enquanto o stream do `capsys` ainda está válido. Não relaxar o comportamento fail-closed nem alterar produção/S9/V2.
3. Validar na ordem: sequência scan→G1, bateria focada, regressão completa com diretório temporário fora do repositório e revisão independente.
4. Manter os findings Ruff globais existentes fora do escopo como findings explícitos, sem correção colateral nesta atividade.

Este contrato descreve a solução de diagnóstico e teste aplicada. A recuperação operacional foi autorizada separadamente e ocorreu somente após o preflight e as confirmações humanas G0/G4; isso não aprova globalmente S9 nem autoriza operações para 586/587.

## Gate 2 — autorização, preflight e preparação

O operador confirmou Gate 2 em 2026-11-03, limitado a uma quarta e última tentativa. O preflight local somente leitura passou: `PRAGMA quick_check=ok`; curso/módulo e identidade capturada correspondem ao registro local; `attempts=3`, `FAILED_RETRYABLE`, categoria `REMOTE_HASH_RANGE_INVALID`; `.part` de 6.029.312 bytes confere com o marcador da terceira tentativa; final ausente; 586/587 sem tentativas; nenhum processo Python concorrente; espaço suficiente. A divergência inicial de `SCOPE_MATCH` foi causada por codificação do literal no canal PowerShell/Python; a verificação corrigida confirmou o escopo.

Foram preparados [guard read-only](../../../tools/telegram_3_resume_585_fourth_guard.py) e [launcher one-shot](../../../tools/RUN_TELEGRAM_3_RECOVER_585_FOURTH_ONCE.ps1). O launcher preserva os marcadores antigos e cria um marcador distinto por `CreateNew` somente depois de G0; define 1 worker, uma tentativa por fila, teto de 6.291.456 bytes, 1.800 s e `REMOTE_HASH_REQUIRED` com prova integral obrigatória. G0 e G4 exigem console interativo; G4 só deve ser confirmado se o plano fresco selecionar exclusivamente 585, indicar 170.323 bytes pendentes, limite PASS e garantia `REMOTE_HASH_FULL`. O ambiente atual é PowerShell 7.6.5 com stdin redirecionado e não pode receber essas confirmações; o launcher recusa esse ambiente e exige Windows PowerShell 5.1 nativo em ROMA_CASA. Até então, a tentativa não começou e o marcador da quarta não existe.

Verificações de preparação: AST Python PASS, parser PowerShell 7 PASS, parser Windows PowerShell 5.1 PASS e preflight do novo guard PASS. Na execução real, o operador digitou `SIM` em G0 e `S` em G4 após revisar o plano fresco (uma mídia, mensagem 585, 170.323 bytes, limite PASS, integridade estrita). A fila terminou `COMPLETED`, 1/1 concluída, zero falhas, uma tentativa e 170.323 bytes transferidos. O pós-guard registrou `RECOVERY585_FOURTH_POST=PASS`, `ATTEMPTS=4`, `STATE=DOWNLOADED`, `REMOTE_HASH_MODE=REQUIRED`, prefixo preservado e 586/587 ainda pendentes e intocados. O launcher reportou 13 segundos totais.

## Entrega ao chat canônico

A primeira tentativa de envio do relatório foi rejeitada pelo auto-review. Após a recuperação, o relatório consolidado atualizado foi enviado via MCP ao chat canônico `Projeto Telegram 3.0`; a ferramenta aceitou o envio e retornou o ID do chat. O readback imediato continuou exibindo o conteúdo anterior, portanto `SENT_UNCONFIRMED / READBACK_NOT_OBSERVED`. Não reenviar para evitar duplicidade.
