# S6 V2 common aligned real proof — 2026-10-18

```text
ACTIVITY = S6_V2_COMMON_ALIGNED_REAL_PROOF
RESULT = PASS
EXECUTION = WINDOWS_NATIVE / NON_ELEVATED / HUMAN NATIVE CONFIRMATION
REAL_TELEGRAM_CALLS = YES / one authorized proof, two phases
REAL_DOWNLOAD = YES / 11,649,955 bytes
TARGET = channel -1002758699600 / message 598 / DOCUMENT / 11,649,955 bytes
MODE = OPERATIONAL_ONLY / ALIGNED_TWO_PROCESS_RESUME
V1_ACTIVE = YES
V2_EFFECTIVE = NO / child-process single-proof scope only
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
```

## Execução e gates

O usuário autorizou uma prova real e forneceu a confirmação nativa no Windows
PowerShell externo. O preflight confirmou o usuário `ROMA_CASA\walac` sem
elevação, Developer Mode habilitado, Python 3.14.7 AMD64, sessão protegida e
cofre de credenciais disponíveis. A execução usou um root novo e isolado:

```text
C:\Users\walac\AppData\Local\Temp\s6a-b30ef00e2b2d\s6-v2-real-proof-3294a1d261864fdf9f645ac201e99b27
```

A identidade remota foi validada como canal `-1002758699600`, mensagem `598`,
mídia `DOCUMENT`, tamanho `11,649,955` bytes. Nenhum login, fallback ou acesso
à SQLite operacional/histórico `.part` ocorreu.

| Fase | PID | Exit | Resultado | Evidência principal |
|---|---:|---:|---|---|
| 1 | 30492 | 0 | `PROCESS_INTERRUPTED` planejado | Checkpoint de 1,048,576 bytes confirmado; SQLite `FAILED_RETRYABLE`; prefixo SHA-256 `dee6ef9f3ed4b021b55cefb90d9f03cfbc958cc1dbb6d00238b2a7576ae72a95`; recibo e progresso válidos |
| 2 | 13300 | 0 | `PROCESS_COMPLETED` | PID distinto; checkpoint reaberto; releitura integral de 1,048,576 bytes com SHA-256 correspondente; finalização e reconciliação SQLite/ledger válidas |

O arquivo final foi confirmado dentro do root isolado com `11,649,955` bytes.
O hash local independente corresponde ao recibo e ao SQLite:
`3bfe15fabb50cd47ddc2b40aa06881bf5a17faff6bb5729c2e34d38ef1edd5c4`.
O estado persistido é `COMPLETED_V2`; a classificação é `UNVERIFIED_ORIGIN`
(`REMOTE_HASH_UNVERIFIABLE_EOF`), sem alegação de verificação independente da
origem. Para o cenário alinhado, overlap é corretamente
`NOT_APPLICABLE_ALIGNED`.

## Orçamento e reconciliação

| Contador agregado reconciliado | Uso | Limite efetivo do launcher | Máximo aprovado | Resultado |
|---|---:|---:|---:|---|
| `GetFile` | 49 | 94 | 139 | PASS |
| `GetFileHashes` | 12 | 92 | 138 | PASS |
| bytes reservados | 12,845,056 | 24,641,536 | 36,438,016 | PASS |
| bytes incertos | 0 | 0 | PASS |

Contadores auxiliares observados nos recibos: fase 1 `identity_GetMessages=1`,
`restore_calls=1`, `known_remote_calls=6`; fase 2 `identity_GetMessages=2`,
`GetMe=1`, `restore_calls=1`, `known_remote_calls=72`. O harness informa
`TELETHON_CONNECT_RPC_COUNT_UNKNOWN` e `total_api_requests=null`; não se infere
uma contagem total de RPCs internos não instrumentados. A reserva, o ledger da
fase 2 e a reconciliação com o ledger da fase 1 são coerentes; a reserva de
disco requerida foi `1,084,343,203` bytes, abaixo dos `43,744,169,984` bytes
livres observados.

O recibo de fase 2 indica `stderr_observed=true`, mas não registra erro,
`STOP` nem exit diferente de zero. O stack log contém amostras limitadas do
loop de eventos aguardando I/O, sem exceção. O recibo preserva apenas o
booleano de stderr, não seu texto bruto.

Os relatórios de fase, recibos de processo, progresso, resumo do escopo
autorizado e relatório final versionados foram preservados em
[`s6-v2-real-proof-3294a1d261864fdf9f645ac201e99b27`](s6-v2-real-proof-3294a1d261864fdf9f645ac201e99b27/).
O payload final permanece apenas no root temporário de execução; não foi
duplicado no repositório. A saída final do launcher foi `PROOF_RESULT=PASS`,
`Harness exit code: 0`, `LAUNCHER_EXIT=0`.

## Estado e próximo passo

`S6_OFFLINE_ACCEPTANCE` permanece `PASS`, apoiado pelo E2E offline e pelo gate
de symlink/regressão reportado em
[`S6_SYMLINK_GATE_FINAL_VALIDATION_2026-10-18.md`](S6_SYMLINK_GATE_FINAL_VALIDATION_2026-10-18.md).
O aceite formal S6 continua pendente e o checkpoint da sprint continua
deferido. Nenhum teste não alinhado foi executado ou autorizado. Próxima ação:
decisão do usuário sobre eventual prova real não alinhada. Nenhuma fonte foi
alterada e não houve staging, commit ou push.
