# S6 V2 native execution recovery — 2026-10-20

## Resultado

`RESULT = PARTIAL / IN_PROGRESS` (`ACTIVITY_COMPLETION_PERCENT = 64%`). O host
Windows executou com sucesso um comando one-shot no MXC e uma sessão nativa
persistent recebeu `ROOT_PING`, respondeu `ACK:ROOT_PING` e saiu com exit 0.
Isso confirma startup e round-trip básico persistente de stdin/stdout. Não
confirma JSONL, execução de jobs de teste, lifecycle de receipts, isolamento
de rede por perfil, supervisão de árvore de processos ou autonomia. O backend
selecionado é `MXC_ON_ACTUAL_WINDOWS_HOST`. Option B não foi selecionada; o
caminho legacy elevated não foi provado nem selecionado.

## Evidência de execução recebida

Antes desta prova, ocorreu uma falha no executor uma vez: `native MXC is
unavailable on this executor`. O erro não foi repetido.

Depois, o root executou, pelo canal de escalonamento aprovado, o comando oficial
one-shot no contexto do host:

```text
codex -c windows.sandbox=mxc sandbox --include-managed-config --permission-profile :workspace -- cmd.exe /d /c echo MXC_HOST_OK
```

Resultado informado: exit code `0`; stdout `MXC_HOST_OK`. Essa evidência suporta
somente startup do comando no MXC do host e o caminho básico de retorno
root→processo→stdout/exit→root. Não foram submetidos jobs nem verificados
`submit/status/cancel/result`, receipts/JUnit, timeout/cancel, término da árvore,
negação de rede específica ao perfil ou dois jobs em sequência.

Evidência adicional informada: sessão nativa persistente recebeu `ROOT_PING`,
devolveu `ACK:ROOT_PING` e exit `0`. Isso prova round-trip básico por stdin/stdout
na sessão persistente; não valida o protocolo JSONL nem qualquer operação de
job.

## Acidente de diagnóstico

`codex sandbox windows --help`, no CLI 0.163, foi interpretado como se fosse
launcher legacy e terminou em
`orchestrator_helper_exit_nonzero: setup helper exited with status Some(1)`.
Nenhuma ação funcional foi iniciada. O comando não foi repetido. Isso não
constitui evidência de execução funcional nem de disponibilidade do backend
legacy elevated.

## Pós-checagem read-only e limites

- Configuração global: mtime anterior à tentativa registrado; hash atual
  informado como `E9765DB...D7F0`. O hash anterior não está disponível, então a
  igualdade exata antes/depois é `UNKNOWN`.
- Configuração do projeto: mtime anterior registrado; hash informado como
  `45D0...E8BF`. Não foi fornecido hash anterior para comparação; igualdade
  exata antes/depois é `UNKNOWN`.
- `Get-LocalUser` falhou; inventário de usuários do sandbox é `UNKNOWN`.
- Nenhum nome de helper foi visível na inspeção; isso não prova ausência global
  de helpers.
- Nenhuma edição nem provisionamento consciente foi feito nesta atividade.
- Não foi produzida evidência de bloqueio de rede para o perfil específico.

## Estado e safepoint

```text
ACTIVITY = S6_V2_NATIVE_EXECUTION_RECOVERY
ACTIVITY_COMPLETION_PERCENT = 64%
ACTIVITY_STATUS = PARTIAL / IN_PROGRESS
HOST_MXC_AVAILABLE = YES
SELECTED_BACKEND = MXC_ON_ACTUAL_WINDOWS_HOST
INFRASTRUCTURE_EXECUTION_READINESS = BLOCKED / ACCESS DENIED / ROOT CAUSE UNKNOWN / READ-ONLY DIAGNOSIS FIRST
NATIVE_EXECUTION_VERIFIED = STARTUP_AND_BASIC_PERSISTENT_BIDIRECTIONAL_TRANSPORT
BIDIRECTIONAL_CONTROL_VERIFIED = BASIC_PERSISTENT_PTY_PING_ACK_ONLY
PERSISTENT_PTY_ROUND_TRIP = PASS / ROOT_PING -> ACK:ROOT_PING / EXIT 0
JSONL_JOB_PROTOCOL = NOT_VERIFIED
INFRASTRUCTURE_PROFILE = FIXED / PROTOCOL TESTS ONLY / 150s TOTAL / 120s DIAGNOSTIC
S6_PROFILES = AFFECTED=25s TOTAL/12s DIAGNOSTIC; HARNESS=150s TOTAL/120s DIAGNOSTIC / UNAVAILABLE UNTIL INFRA GATE PASS
PROCESS_TREE_VERIFIED = NO
NETWORK_ISOLATION_VERIFIED = NO / PROFILE-SPECIFIC EVIDENCE REQUIRED
JOB_OBJECT_ASSOCIATION = NOT_VERIFIED / ACTIVE_PROCESS_COUNT_ZERO = NOT_VERIFIED
MXC_JOB_OBJECT_COMPATIBILITY = UNKNOWN
LOOPBACK_COMPATIBILITY = UNKNOWN
HARD_DEADLINE = WALL-CLOCK TOTAL / UP TO 5s RESERVED INSIDE TOTAL / NEVER EXTEND
AUTONOMY_GATE = BLOCKED
OPTION_B = NOT_SELECTED
LEGACY_ELEVATED = NOT_PROVEN / NOT_SELECTED
CONFIG_BEFORE_AFTER_HASH_EQUALITY = UNKNOWN
SANDBOX_USER_INVENTORY = UNKNOWN
FUNCTIONAL_JOBS_OR_TESTS_STARTED = NO / THIRD JSONL JOB DID NOT PUBLISH WORKER IDENTITY
THIRD_JSONL_JOB = 61295a78efe340ea902b73848f303ab8 / EXIT 3221225506 / 0xC0000022 STATUS_ACCESS_DENIED
WORKER_IDENTITY = NOT_PUBLISHED / WORKER_START = NOT_PROVEN
FAILED_JOB_STDOUT_STDERR = EMPTY / .sandbox/sandbox.log = ABSENT
REPORTED_ACTIVE_PROCESS_COUNT = 0 / IDENTITY UNPUBLISHED / NOT PROCESS-TREE EVIDENCE
WORKER_CANARY_CONNECTIONS = 0 / ONLY HOST LISTENER POSITIVE CONTROL / NOT NETWORK-ISOLATION EVIDENCE
ENVIRONMENT_PREREQUISITES = SystemDrive AND LOCALAPPDATA ABSENT IN EARLIER JOBS; INCLUDED BEFORE C0000022 APPEARED
ROOT_CAUSE = UNKNOWN
SECOND_SUBMIT_AFTER_FAILURE = NO / CANCEL_TIMEOUT_AUTONOMY_E2E = NOT_RUN
GIT_STAGE_COMMIT_PUSH = NO
```

`NEXT_ACTION` (safepoint): correlação somente dos logs OS já existentes no
intervalo do incidente e inspeção de ACLs/atributos dos caminhos exatos de
runtime/snapshot registrados pelo job. Não executar outro job nem alterar
permissões/policy. Se a causa do access denied permanecer desconhecida,
encaminhar pacote sanitizado ao admin/suporte do executor; retomar somente após
correção autorizada. O gate permanece `BLOCKED`; não iniciar S6 checks.

O contrato materializado está em
[`S6_V2_NATIVE_MXC_EXECUTOR_RECOVERY_CONTRACT_2026-10-20.md`](../contracts/S6_V2_NATIVE_MXC_EXECUTOR_RECOVERY_CONTRACT_2026-10-20.md).

## Evidências referenciadas

- Relato do root sobre a falha MXC anterior, uma única vez, e seu não-repeat;
  transcript/digest independente não fornecido.
- Relato do root com comando host one-shot, exit code e stdout acima; transcript
  independente não fornecido neste pacote.
- Relato do root da sessão persistente `ROOT_PING` → `ACK:ROOT_PING`, exit 0;
  transcript independente não fornecido neste pacote.
- Pós-checagem read-only informada pelo root, com os limites e valores parciais
  registrados acima.
- Checkpoint anterior:
  [S6_V2_NATIVE_EXECUTION_GATE_2026-10-20.md](S6_V2_NATIVE_EXECUTION_GATE_2026-10-20/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20.md).
- Continuidade atualizada: `docs/continuity/PROJECT_STATE.md` e
  `docs/continuity/CONTINUITY_RECORD.md`.

## Lacunas documentais não resolvidas

Transcripts/digests independentes para a falha anterior, comando host, sessão
persistente e pós-checagem não foram fornecidos. Hashes anteriores das
configurações não estão disponíveis para comparação; o inventário local de
usuários permanece `UNKNOWN`; visibilidade de nomes de helpers não resolve
presença global. Faltam evidências do protocolo JSONL, jobs, lifecycle completo,
receipt/JUnit, timeout/cancelamento, árvore de processos, negação de rede por
perfil e dois jobs autônomos em sequência. Portanto,
`AUTONOMY_GATE = BLOCKED`.

## Atualização documental — contrato infra MXC

O pedido explícito atual autorizou a materialização do contrato infra
activity-scoped e sua implementação bounded, com testes iniciais limitados ao
protocolo infra no executor novo. O contrato seleciona
`MXC_ON_ACTUAL_WINDOWS_HOST` e adiciona o perfil offline fixo `Infrastructure`,
exclusivo para o novo arquivo de teste de protocolo. `Affected` e `Harness`
permanecem fixos para S6 checks e indisponíveis antes do gate infra. O contrato
define JSONL por stdin/stdout de sessão host persistente. A seleção de perfil,
path e command vem de tabela interna allowlisted; requisições JSONL não podem
fornecer command, path ou plugin. `tests/manual_proofs/test_s6_v2_mxc_host_executor.py`
é o arquivo novo de teste autorizado; opcionalmente pode ser criado
`tools/manual_proofs/s6_v2_mxc_host_executor.py`.

O job pode ler somente runtime mínimo explícito e imutável/read-only: Python da
`.venv` e dependências necessárias, snapshot allowlisted de inputs e código do
novo executor/launcher se necessário. Outputs ficam apenas na raiz exclusiva
do run; se permissões managed efetivas exigirem checkout mais amplo, o
resultado é `BLOCKED`. Não disponibilizar checkout completo, `.env`, `.codex`
sensível, vault, sessions, SQLite operacional, histórico/receipts antigas ou
referências.

Deadlines são wall-clock totais, incluindo inicialização MXC, worker,
encerramento OS e publicação/reconciliação do receipt. `Infrastructure` tem
150s total / 120s diagnóstico; `Affected` 25s / 12s; `Harness` 150s / 120s.
Reservar até 5s dentro do total para kill/reap/publicação; nunca estender hard
deadline. Exigir associação ao Job Object antes de liberar o processo e
`ACTIVE_PROCESS_COUNT = 0`; sem isso, `BLOCKED`. Compatibilidade MXC/Job Object
e loopback permanece `UNKNOWN` até evidência. As únicas evidências nativas
atuais seguem sendo os pings host; não provam JSONL nem execução funcional.

As alterações e testes isolados do harness S6 permanecem bloqueados até o gate
infra passar. O gate não passou nesta atividade. O terceiro job JSONL retornou
`STATUS_ACCESS_DENIED` antes de publicar a identidade do worker; não há prova de
que um worker tenha começado. Nenhum pytest funcional começou, não houve novo
submit após essa falha, e cancel/timeout/autonomia E2E não foram executados.
O contrato infra já existe, mas a próxima ação corrente é read-only: correlacionar
somente logs OS existentes e ACLs/atributos dos caminhos exatos registrados
pelo job. Nenhuma nova execução nem mudança de permissões/policy está
autorizada neste safepoint.

## Diagnóstico read-only do terceiro job JSONL — 2026-10-20

O job `61295a78efe340ea902b73848f303ab8` terminou com exit
`3221225506 / 0xC0000022 STATUS_ACCESS_DENIED`. stdout e stderr vieram vazios;
`WORKER_IDENTITY_NOT_PUBLISHED`. O contador ativo foi reportado como zero
porque a identidade do worker não foi publicada; isso não prova que um worker
tenha iniciado, nem que não existam descendentes ou que a árvore foi encerrada.
Não existe `.sandbox/sandbox.log` para esse job.

Nos jobs anteriores, `SystemDrive` e `LOCALAPPDATA` estavam ausentes; depois
esses pré-requisitos foram incluídos e surgiu o bloqueio `C0000022`. Essa
sequência não determina a causa-raiz, que permanece `UNKNOWN`. O worker canary
reportou zero conexões; houve apenas o controle positivo do listener no host.
Como não há prova de worker iniciado, o canary não prova isolamento de rede.

Não começou pytest funcional; não houve segundo submit após o erro, nem
cancelamento, timeout ou autonomia E2E. `MXC_ON_ACTUAL_WINDOWS_HOST` permanece
selecionado e disponível somente para startup/round-trip básico. Fallback
legacy não foi provado; Option B não foi selecionada. Gate permanece
`BLOCKED`.

```text
ACTIVITY_COMPLETION_PERCENT = 64%
ACTIVITY_STATUS = PARTIAL / IN_PROGRESS
THIRD_JSONL_JOB = 61295a78efe340ea902b73848f303ab8
EXIT = 3221225506 / 0xC0000022 STATUS_ACCESS_DENIED
STDOUT_STDERR = EMPTY
WORKER_IDENTITY = NOT_PUBLISHED / WORKER_START = NOT_PROVEN
SANDBOX_LOG = ABSENT
REPORTED_ACTIVE_PROCESS_COUNT = 0 / CAUSED_BY MISSING WORKER IDENTITY / NOT TREE EVIDENCE
WORKER_CANARY_CONNECTIONS = 0 / POSITIVE CONTROL = HOST LISTENER ONLY
ENVIRONMENT = SystemDrive/LOCALAPPDATA ABSENT IN EARLIER JOBS; LATER INCLUDED BEFORE ACCESS DENIED
ROOT_CAUSE = UNKNOWN
FUNCTIONAL_PYTEST = NOT_STARTED
SECOND_SUBMIT = NO / CANCEL_TIMEOUT_AUTONOMY_E2E = NOT_RUN
HOST_MXC = SELECTED / AVAILABLE FOR STARTUP AND BASIC PING ONLY
LEGACY_FALLBACK = NOT_PROVEN / OPTION_B = NOT_SELECTED
NETWORK_ISOLATION = NOT_PROVEN / PROCESS_TREE = NOT_PROVEN / AUTONOMY_GATE = BLOCKED
NEXT_ACTION = READ-ONLY CORRELATE EXISTING OS LOGS AND ACL/ATTRIBUTES FOR EXACT JOB-RECORDED RUNTIME/SNAPSHOT PATHS
SAFE_RESUME_POINT = No new execution or permission/policy change. If cause remains unknown, send sanitized evidence to executor admin/support; resume only after authorized correction.
```
