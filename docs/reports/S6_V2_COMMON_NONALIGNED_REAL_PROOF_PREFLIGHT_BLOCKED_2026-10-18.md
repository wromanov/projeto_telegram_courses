# S6 V2 common nonaligned real proof — preflight blocked — 2026-10-18

```text
ACTIVITY = S6_V2_COMMON_NONALIGNED_REAL_PROOF
RESULT = BLOCKED_BEFORE_REAL_EXECUTION
EXECUTION = CODEX_SANDBOX_PREFLIGHT_ONLY / NO NATIVE LAUNCHER CONFIRMATION
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REMOTE_IDENTITY_CHECK = NOT PERFORMED
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_OFFLINE_ACCEPTANCE = PASS / PRESERVED FROM PRIOR OFFLINE AND ALIGNED GATES
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
```

## Resultado observado

A solicitação de prova real não alinhada não chegou à confirmação exata do
launcher nativo. Não houve apresentação nem entrada de confirmação, execução
de fase ou validação de identidade remota. Portanto, o resultado é
`BLOCKED_BEFORE_REAL_EXECUTION`; não é falha da identidade Telegram e não
produziu evidência de comportamento real para o cenário não alinhado.

No preflight somente de status executado sob o sandbox Codex, o usuário local
foi `ROMA_CASA\walac`, não elevado, Developer Mode foi reportado como ativo,
Python `3.14.7` AMD64, artefato de sessão protegida presente e espaço livre de
`47,800,913,920` bytes. O secure preflight do processo, contudo, retornou
`credential_vault=NO` e `protected_session=NO`. Esses dois valores descrevem
somente o processo no sandbox e **não** determinam a prontidão do Windows
nativo.

Na prova real alinhada anterior, executada em PowerShell externo nativo, o
usuário também era `ROMA_CASA\walac`, não elevado, com Developer Mode ativo,
cofre e sessão protegida disponíveis. Essa evidência permanece válida para
aquela execução alinhada e não pode ser transferida para o contexto sandbox
nem para uma futura execução não alinhada. O relatório anterior é
[S6 V2 common aligned real proof](S6_V2_COMMON_ALIGNED_REAL_PROOF_2026-10-18.md).

## Diagnóstico estático do bloqueio

O launcher `tools/manual_proofs/Invoke-S6V2Proof.ps1` apresenta a confirmação
literal `EXECUTE S6 V2 PROOF common OPERATIONAL_ONLY aligned`, imprime somente
o cenário aligned e despacha `--case aligned` (linhas 106–121 e 170). Assim,
não há fluxo de autorização do launcher para o caso solicitado.

Em `tools/manual_proofs/s6_v2_proof_harness.py`, `unaligned-prepared` existe
como entrada de cálculo de orçamento, mas o `dry_run` common a filtra e mantém
somente aligned (linhas 1754–1767). O fluxo real exige `case_name ==
"aligned"`; autorização, validação do processo filho, preflight de fase 2 e
validação do recibo também fixam `allowed_cases == ["aligned"]` ou
`case == "aligned"` (por exemplo, linhas 1713–1717, 2197–2205, 2833–2837,
2918–2924). Logo, o harness atual não consegue executar com segurança o caso
real não alinhado.

Há ainda uma falha de reconciliação a corrigir antes de tornar esse caso
executável: em `ProofGateway.stream_media` (linhas 1598–1607), quando um bloco
ultrapassa `interrupt_after`, o adaptador entrega somente os 123 bytes
restantes e interrompe, mas a reserva contabilizada corresponde ao bloco
wire inteiro de 262,144 bytes. Os 262,021 bytes não entregues não são
reconciliados pelo adaptador/ledger; a diferença impede afirmar a
reconciliação de orçamento para a prova não alinhada.

O cálculo atual do cenário aligned também não deve ser reutilizado para o
caso não alinhado. Para o prefixo de `1,048,699` bytes (1 MiB + 123), o
Architect estimou caps recalculados de `GetFile=95`, `GetFileHashes=92` e
bytes reservados `24,903,680`, ainda dentro dos máximos aprovados de
`139`, `138` e `36,438,016`, respectivamente. **Esses valores são estimativas
diagnósticas, não caps implementados nem autorização para execução.**

A política existente exige root de evidência novo e isolado; roots históricos
não podem ser reutilizados para essa prova.

## Estado e próximo passo

O gate de symlink, seus dois testes reais e a regressão anteriormente
executada permanecem PASS. `S6_OFFLINE_ACCEPTANCE=PASS` permanece preservado
pelos gates offline existentes e pela prova alinhada já concluída. Este
bloqueio não reabre nem altera o contrato S6 congelado, não altera semântica
V1 e não torna V2 efetiva. Aceite formal S6 continua `PENDING`; checkpoint da
sprint continua `DEFERRED`.

O passo mínimo recomendado é obter autorização do usuário para uma correção
limitada do harness/launcher/testes e validação offline do caso não alinhado.
Somente depois dessa correção e validação offline poderá ser apresentada uma
nova confirmação nativa específica. Nenhuma confirmação ou chamada real fica
pré-autorizada por este registro.

```text
SANDBOX_PREFLIGHT_USER = ROMA_CASA\walac / NON_ELEVATED
SANDBOX_DEVELOPER_MODE = 1
SANDBOX_PYTHON = 3.14.7 AMD64
SANDBOX_SESSION_ARTIFACT = PRESENT
SANDBOX_FREE_DISK_BYTES = 47800913920
SANDBOX_SECURE_PREFLIGHT = credential_vault=NO / protected_session=NO
NATIVE_RUNTIME_READINESS = NOT_ESTABLISHED_BY_SANDBOX_PREFLIGHT
LAUNCHER_CONFIRMATION = NOT_PRESENTED
REAL_SYMLINK_OR_TELEGRAM_OPERATIONS = NONE
OFFLINE_ACCEPTANCE = PASS / PRESERVED
NEXT_ACTION = USER_AUTHORIZATION_FOR_BOUNDED_OFFLINE_HARNESS_LAUNCHER_TEST_CORRECTION
```
