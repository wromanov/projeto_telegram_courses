# S6 V2 common nonaligned real proof — 2026-10-18

```text
ACTIVITY = S6_V2_COMMON_NONALIGNED_REAL_PROOF
RESULT = PASS
EXECUTION = EXTERNAL WINDOWS POWERSHELL / ROMA_CASA\walac / NON_ELEVATED
MODE = OPERATIONAL_ONLY
SCENARIO = unaligned-prepared
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
```

## Identidade remota e isolamento

Após o usuário digitar a confirmação literal exibida pelo launcher, a prova validou canal `-1002758699600`, mensagem `598`, mídia `DOCUMENT`, tamanho esperado `11,649,955` bytes. O preflight local reportou cofre protegido e sessão disponível; a execução foi não elevada e manteve o override de `LOCALAPPDATA` limitado à árvore do launcher, restaurado ao final.

O harness usou root isolado novo:

`C:\Users\walac\AppData\Local\Temp\s6a-b30ef00e2b2d\s6-v2-real-proof-6bda55b17fa64529a0160629a5a70f0d`

O SQLite operacional original e `.part` históricos não foram acessados. O arquivo final ficou dentro do root da prova; os componentes do caminho foram inspecionados e nenhum era reparse point.

## Retomada não alinhada

Fase 1: PID `7948`, processo encerrado antes da fase 2, exit `0`, `PROCESS_INTERRUPTED / CONTROLLED_INTERRUPT`. O checkpoint local tinha `1,048,699` bytes, estado SQLite `FAILED_RETRYABLE` e hash SHA-256 `9b18920ece9bf91c2077d44cfe19ac53b9b9dd5f14d0c3e7d4a8d787d7adb8bf`.

Fase 2: PID distinto `10916`, exit `0`, checkpoint reaberto e prefixo completo de `1,048,699` bytes relido. O hash relido coincide com o do checkpoint. A requisição alinhada em `1,048,576` bytes transferiu um bloco wire de `262,144` bytes; o overlap de `123` bytes comparou corretamente, `262,021` bytes de sufixo foram reutilizados sem duplicação, e a próxima requisição começou no cursor local `1,310,720`.

O download final foi finalizado em `COMPLETED_V2`, com `11,649,955` bytes e SHA-256 `3bfe15fabb50cd47ddc2b40aa06881bf5a17faff6bb5729c2e34d38ef1edd5c4`. O hash foi recalculado diretamente do arquivo local e bate com os recibos, evidência SQLite e relatório agregado. A classe de integridade permanece `UNVERIFIED_ORIGIN`; o EOF da cobertura de hash remoto é explicitamente não verificável.

## Contadores e reconciliação

```text
PHASE_1_PID = 7948 / EXIT 0 / CONTROLLED_INTERRUPT
PHASE_1_PREFIX = 1048699 / SHA-256 9b18920ece9bf91c2077d44cfe19ac53b9b9dd5f14d0c3e7d4a8d787d7adb8bf
PHASE_2_PID = 10916 / EXIT 0 / PROCESS_COMPLETED
FULL_PREFIX_REREAD = 1048699 / MATCH
REMOTE_ALIGNED_OFFSET = 1048576
OVERLAP_EXPECTED = 123 / VERIFIED = 123 / PASS
NEXT_LOCAL_AND_REMOTE_OFFSET = 1310720
FINAL_BYTES = 11649955
FINAL_SHA256 = 3bfe15fabb50cd47ddc2b40aa06881bf5a17faff6bb5729c2e34d38ef1edd5c4
FINAL_STATE = COMPLETED_V2
INTEGRITY_CLASSIFICATION = UNVERIFIED_ORIGIN
GETFILE = 50 / EFFECTIVE_CAP 95 / APPROVED_MAX 139
GETFILEHASHES = 12 / EFFECTIVE_CAP 92 / APPROVED_MAX 138
IDENTITY_GETMESSAGES = 3 / GETME = 2 / KNOWN_REMOTE_CALLS = 79
TELETHON_CONNECT_INTERNAL_RPC_AND_TOTAL_API_REQUESTS = NOT_INSTRUMENTED
RESERVED_BYTES = 13107200 / EFFECTIVE_CAP 24903680 / APPROVED_MAX 36438016
PAYLOAD_RECEIVED = 12960675 / UNCERTAIN_BYTES = 0
SQLITE_STATE_AND_LEDGER_RECONCILIATION = PASS
PROOF_SQLITE_INTEGRITY_CHECK = ok
BUDGET_SQLITE_INTEGRITY_CHECK = ok
WITHIN_APPROVED_CAPS = YES
ORIGINAL_OPERATIONAL_SQLITE_ACCESS = NO
HISTORICAL_PART_ACCESS = NO
```

O resultado agregado reporta `PROOF_RESULT=PASS`; recibos de ambas as fases, progresso, ledger e estados SQLite foram reconciliados. `UNVERIFIED_ORIGIN` é preservado e não é apresentado como verificação independente da origem.

## Aceite e continuidade

`S6_OFFLINE_ACCEPTANCE=PASS` permanece válido, incluindo os gates de symlink anteriores, a validação offline nonaligned e as 214 regressões afetadas aprovadas. A prova real nonaligned agora também é PASS. V1 continua ativa e V2 permanece globalmente inefetiva. Isso não aprova formalmente S6 nem encerra a sprint.

```text
REAL_TELEGRAM_CALLS = AUTHORIZED BY USER'S EXACT NATIVE CONFIRMATION / OBSERVED PER PHASE
REAL_DOWNLOADS = 1 DOCUMENT / 11649955 BYTES
S6_NONALIGNED_PROOF = PASS
S6_OFFLINE_ACCEPTANCE = PASS
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
PROJECT_STATE_RECONCILIATION = PASS
NEXT_ACTION = USER_CONTROLLED_REFERENCE_PROOF_DECISION
```
