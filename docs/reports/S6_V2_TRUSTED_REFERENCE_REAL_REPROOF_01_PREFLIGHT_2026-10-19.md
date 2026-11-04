# S6 V2 TRUSTED_REFERENCE — real reproof 01 preflight

```text
ACTIVITY = S6_V2_TRUSTED_REFERENCE_REAL_REPROOF_01
RESULT = BLOCKED
BLOCK_POINT = BEFORE_LAUNCHER_CONFIRMATION / BEFORE_TELEGRAM
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_RETRY = NO
PROOF_CHILD_PROCESSES = NOT_STARTED
V1_ACTIVE = YES
V2_EFFECTIVE = NO
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
NEXT_ACTION = OFFLINE_FAILURE_ADJUDICATION
```

## Preflight observado

O repositório permaneceu em `work/s0-bootstrap`, `HEAD=98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`. A árvore já continha múltiplas alterações e artefatos não rastreados de atividades anteriores; nenhum foi revertido ou publicado. Desde a validação offline do timeout, esta atividade não alterou fonte, launcher, testes ou evidência. A adição anterior do teste sintético de cancelamento consta no relatório offline da remediação.

Authorities revisadas: `PROJECT_GOVERNANCE_BINDING.json`, `ACTIVE_AUTHORITY_MAP.md`, `PROJECT_STATE.md`, `APPROVALS_AND_DECISIONS.md`, contrato S6 V1, contrato de homologação `TRUSTED_REFERENCE` e adendo de timeout. O contrato V1 permaneceu inalterado (SHA-256 `AA2B4F019F28EC5DB7F0D8CF085B10C274F376271BCC65A0438D8609829F42B2`). O digest da proposta V2 (`C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52`) confere com a ratificação registrada; V2 permanece inefetiva. A remediação offline e as regressões/E2Es sintéticas estão PASS conforme o [relatório de remediação](S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION_2026-10-19.md).

No processo PowerShell externo, não elevado, foram observados: PowerShell 7.6.5; usuário `ROMA_CASA\walac`; Python 3.14.7, 64-bit AMD64; 43.006.537.728 bytes livres em C:; probe nativo de criação de diretório temporário PASS; maior path derivado planejado com 117 caracteres. A referência foi lida somente para validar tamanho `1.119.129.690` bytes e SHA-256 `3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c`. O preflight local status-only informou `credential_vault=YES`, `protected_session=YES`, provider `WINDOWS_PROTECTED_VAULT`; não houve conexão Telegram, RPC ou escrita de credenciais/sessão. A referência original não foi modificada.

## Gate bloqueador

O código do harness contém a política por cenário: `common / OPERATIONAL_ONLY` usa 3.600 segundos por processo e 900 segundos agregados; `controlled / TRUSTED_REFERENCE` usa 4.500 e 4.800 segundos; inatividade semântica de 180 segundos; heartbeat de 15 segundos; grace máximo de 30 segundos dentro do deadline. O deadline de 900 segundos não é selecionado para `TRUSTED_REFERENCE` no harness.

Porém, `Invoke-S6V2Proof.ps1` não exibe esses limites efetivos antes do `Read-Host` de confirmação. Seu resumo de execução mostra alvo, modo, prefixo, budgets, workers/tentativas/FloodWait e status V1/V2, mas não mostra os deadlines, inatividade, heartbeat nem grace. Assim, o requisito do usuário de que o launcher exiba a política de timeout efetiva antes da confirmação não foi satisfeito. Não foi aberto o fluxo `Execute`, não foi gerada nem digitada a confirmação literal e nenhum filho de prova foi iniciado.

A atividade proíbe implementar alterações durante esta execução. Portanto, o gate permanece bloqueado e a única prova autorizada não foi iniciada. Esta evidência não é `FAIL` de download ou de integridade; não houve tentativa Telegram. Qualquer nova execução real requer nova autorização explícita, além da adjudicação offline e do fechamento do gate de telemetria do launcher.

## Reconciliação final

```text
REMOTE_IDENTITY = NOT_CHECKED / no Telegram RPC
REFERENCE_VALIDATION = PASS / exact expected size and SHA-256 / read-only
PHASE_1_PID = NOT_STARTED
PHASE_1_EXIT = NOT_STARTED
PHASE_1_CHECKPOINT = NOT_CREATED
PHASE_2_PID = NOT_STARTED
PHASE_2_EXIT = NOT_STARTED
PHASE_1_DURATION_SECONDS = NOT_APPLICABLE
PHASE_2_DURATION_SECONDS = NOT_APPLICABLE
AGGREGATE_DURATION_SECONDS = NOT_APPLICABLE
PROCESS_TIMEOUT_EFFECTIVE = 4500s / harness policy verified; not surfaced by launcher before confirmation
AGGREGATE_DEADLINE_EFFECTIVE = 4800s / harness policy verified; not surfaced by launcher before confirmation
PROGRESS_HEARTBEAT_EFFECTIVE = 15s / harness policy verified; not surfaced by launcher before confirmation
FINAL_BYTES = NOT_CREATED
FINAL_SHA256 = NOT_CREATED
REFERENCE_COMPARISON = NOT_RUN
FINAL_STATE = NOT_CREATED
GETFILE_CALLS = 0
GETFILEHASHES_CALLS = 0
IDENTITY_GETMESSAGES_CALLS = 0
RESERVED_BYTES = 0
UNCERTAIN_BYTES = 0
SQLITE_RECONCILIATION = NOT_APPLICABLE / proof database not created
LEDGER_RECONCILIATION = NOT_APPLICABLE / proof ledger not created
PROCESS_BOUNDARY = NO_PHASE_CHILD_PROCESSES
SAFETY_GATE = BLOCKED_BEFORE_LAUNCHER_CONFIRMATION / no Telegram or RPC activity
REFERENCE_ORIGINAL_PRESERVED = YES
PREVIOUS_PROOF_EVIDENCE_PRESERVED = YES / read-only
V1_ACTIVE = YES
V2_EFFECTIVE = NO
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
NEXT_ACTION = OFFLINE_FAILURE_ADJUDICATION
```
