# S6 V2 common nonaligned offline validation — 2026-10-18

```text
ACTIVITY = S6_V2_COMMON_NONALIGNED_REAL_PROOF
STAGE = OFFLINE_HARNESS_AND_REGRESSION_VALIDATION
RESULT = PASS / READY_FOR_FRESH_NATIVE_CONFIRMATION
EXECUTION_CONTEXT = WINDOWS_NATIVE_POWERSHELL / ROMA_CASA\walac / NON_ELEVATED
PYTHON = PROJECT_VENV / 3.14.7 AMD64
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REMOTE_IDENTITY_CHECK = NOT_PERFORMED
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
```

## Escopo e correções validadas

A validação offline cobriu o cenário `unaligned-prepared` em `common / OPERATIONAL_ONLY`, com prefixo sintético de 1.048.699 bytes, offset remoto alinhado em 1.048.576 bytes e overlap de 123 bytes. Nenhum gateway Telegram real, credencial ou sessão protegida foi usado.

O caminho de retomada foi corrigido para validar o cursor de append contra o total atualizado após reutilizar o sufixo alinhado. A reconciliação física do checkpoint da fase 1 ocorre na fronteira do handoff, enquanto o arquivo `.part` ainda existe; a validação agregada posterior não tenta reabrir esse arquivo depois da finalização atômica. Os testes também reconciliam o checkpoint e exercitam as variantes adulteradas ainda no momento em que o checkpoint está disponível.

## Evidência de testes

Gates focados em PowerShell nativo, usuário não elevado:

- handoff offline de dois processos para casos `aligned` e `unaligned-prepared`;
- resume não alinhado com fixture local;
- rejeição de overlap divergente antes de continuação remota;
- resultado: `4 passed`.

Regressões afetadas executadas com Python 3.14.7 e `--basetemp` curto e isolado fora do repositório:

```text
tests/manual_proofs/test_s6_v2_proof_harness.py
tests/unit/test_s6_v2.py
tests/unit/test_downloads.py
tests/integration/test_download_flow.py
RESULT = 214 passed / 0 failed / exit 0 / 86.22s
BASE = C:\Users\walac\AppData\Local\Temp\s6r-0098a6feccd64ad79a79e7d662585c7b
```

Os eventos do harness foram sintéticos e isolados; o teste de handoff retornou `PROOF_RESULT=PASS` para os dois cenários. Não houve chamada de identidade, RPC, download, login, mudança de modo fallback, alteração semântica de V1, mudança de política Windows, elevação ou operação Git.

## Decisão e próximo passo

Os gates offline não alinhados passam e complementam a prova real aligned já aprovada. Isso não é uma prova Telegram não alinhada. A janela externa do launcher foi aberta com o target, modo, perfil e evidence parent fixados. A confirmação não foi digitada e a fase real não começou. A pessoa usuária deve conferir que o preflight exibido pelo launcher está PASS e interromper se houver qualquer falha. A confirmação esperada para este perfil é `EXECUTE S6 V2 PROOF common OPERATIONAL_ONLY unaligned-prepared`. Ao prosseguir, manter os limites aprovados e interromper em qualquer divergência de identidade, prefixo, overlap, checkpoint, ledger ou orçamento.

```text
NONALIGNED_OFFLINE_HANDOFF = PASS / 2 independent synthetic processes
PREFIX = 1048699 / REMOTE_ALIGNED_OFFSET = 1048576 / OVERLAP = 123
CONTINUATION = VALIDATED / UNCERTAIN_BYTES = 0
REGRESSION = PASS / 214 passed / 0 failed
OFFLINE_ACCEPTANCE = PASS
NATIVE_REAL_NONALIGNED_PROOF = NOT_STARTED / FRESH USER CONFIRMATION REQUIRED
LAUNCHER_STATE = EXTERNAL POWERSHELL OPEN / CONFIRMATION NOT ENTERED
V1_ACTIVE = YES / V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING / SPRINT_CHECKPOINT = DEFERRED
PROJECT_STATE_RECONCILIATION = PASS
NEXT_ACTION = CHECK_EXTERNAL_PREFLIGHT_THEN_USER_TYPES_EXACT_CONFIRMATION_IF_PASS
EXACT_CONFIRMATION = EXECUTE S6 V2 PROOF common OPERATIONAL_ONLY unaligned-prepared
```
