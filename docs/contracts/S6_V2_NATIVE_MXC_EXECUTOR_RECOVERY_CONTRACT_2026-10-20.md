# Contrato de recuperação do executor MXC nativo S6 V2 — 2026-10-20

```text
DOCUMENT_ROLE = ACTIVITY_SCOPED_INFRASTRUCTURE_IMPLEMENTATION_CONTRACT
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_V2_NATIVE_EXECUTION_RECOVERY
DATE = 2026-10-20
AUTHORITY = CURRENT_EXPLICIT_USER_AUTHORIZATION_RELAYED_BY_ROOT
CANONICAL_AUTHORITY = NO
CONTRACT_STATUS = MATERIALIZED / ACTIVITY-SCOPED
SELECTED_BACKEND = MXC_ON_ACTUAL_WINDOWS_HOST
IMPLEMENTATION_AUTHORIZATION = YES / BOUNDED INFRASTRUCTURE OWNERSHIP BELOW
INFRASTRUCTURE_PROTOCOL_TEST_AUTHORIZATION = YES / NEW TEST FILE ONLY / NEW EXECUTOR
S6_ISOLATED_HARNESS_CHANGES_AND_TESTS = BLOCKED UNTIL INFRASTRUCTURE GATE PASS
V1_ACTIVE = YES
V2_GLOBAL = OFF
GIT_STAGE_COMMIT_PUSH = NO
```

## 1. Objetivo e fronteira

Implementar e validar a infraestrutura bounded que permite executar o perfil
offline fixo `Infrastructure` somente para testes do protocolo no novo arquivo
de testes. Os perfis fixos `Affected` e `Harness` são reservados aos S6 checks e
ficam indisponíveis até o gate infra passar. Jobs MXC usam o host Windows,
sessão persistente, isolamento por invocação, evidências reconciliáveis e
encerramento de processos verificável. Este contrato é
activity-scoped e não altera requisitos canônicos, arquitetura geral do
produto, S6 V1 ou authorities de continuidade.

A autorização atual cobre a implementação infra nos arquivos abaixo e os
testes do protocolo de infraestrutura no executor novo. A sequência de gates é
dependência técnica dentro da atividade, sem uma sequência de microaprovações.
Nenhum teste/correção isolado do harness S6 começa antes de o gate infra passar.

## 2. Backend, transporte e invocação

- Backend único selecionado: `MXC_ON_ACTUAL_WINDOWS_HOST`. Não introduzir
  fallback para Option B, legacy elevated ou sandbox mais permissivo.
- Transporte de controle: uma sessão host persistente criada por
  `exec_command`, com JSONL em stdin/stdout. stderr e stdout de cada job devem
  ser preservados em arquivos separados dentro da raiz exclusiva daquele run.
- Seleção de perfil, path e command vêm exclusivamente de uma tabela interna
  allowlisted. Requisições JSONL não podem fornecer comandos, paths nem
  plugins; não aceitar valores arbitrários desses tipos nem interpolá-los em
  execução.
- Cada job executa um `codex sandbox` foreground independente, com
  `-c windows.sandbox=mxc`, `--include-managed-config` e um permission profile
  offline específico naquela invocação. Não alterar configuração salva/global
  ou do projeto.
- O único perfil disponível antes do gate infra é o fixo `Infrastructure`, usado
  exclusivamente para os testes de protocolo em
  `tests/manual_proofs/test_s6_v2_mxc_host_executor.py`. `Affected` e `Harness`
  permanecem fixos para os S6 checks e indisponíveis antes do gate infra.
- Cada profile custom por invocação deve definir `network.enabled=false` e
  restringir filesystem ao runtime mínimo explicitamente allowlisted, inputs
  somente leitura e output daquele job.
- Se a política managed impedir o permission profile ou seu escopo, parar
  `BLOCKED`; não tentar perfil, configuração ou fallback mais permissivo.
- Permissões managed efetivas fazem parte do requisito. Se o runtime mínimo
  ainda exigir acesso a checkout mais amplo sob essas permissões, parar
  `BLOCKED`.

## 3. Snapshot, inputs, credenciais e outputs

- O job pode ler somente runtime mínimo explicitamente allowlisted e
  immutable/read-only: Python da `.venv` e dependências necessárias, snapshot
  allowlisted de inputs e código do novo executor/launcher, quando necessários.
  Se o runtime mínimo ainda exigir acesso a um checkout mais amplo, parar
  `BLOCKED`.
- Cada job recebe um snapshot allowlisted exclusivo; não compartilhar snapshot
  mutável entre jobs. Inputs são somente leitura.
- Toda escrita de resultado, output, receipt, JUnit, stdout e stderr fica
  restrita à raiz exclusiva daquele run.
- Não disponibilizar o checkout completo do repositório, `.env`, `.codex`
  sensível, sessões, vault, SQLite operacional, raízes/receipts históricos ou
  referências. Não copiar credenciais para snapshot, environment ou job.
- A policy do launcher deve remover/omitir fontes de credenciais e variáveis
  sensíveis do ambiente do job; incluir configuração managed não autoriza
  fornecer credenciais nem ampliar o escopo de filesystem.
- Registrar snapshot e `RunSpec` com hashes antes e depois de cada execução,
  permitindo reconciliar identidade e integridade do que foi recebido e
  produzido.

## 4. Protocolo e evidências por job

- A sessão host expõe as operações JSONL `submit`, `status`, `cancel` e
  `result`. O round-trip simples `ROOT_PING`/`ACK:ROOT_PING` observado até aqui
  é somente evidência de transporte básico, não implementação nem validação
  destas operações.
- As mensagens devem permitir atribuir respostas ao job e reconciliar o
  resultado solicitado com o mesmo job; framing inválido, identidade ausente
  ou resultado contraditório é fail-closed.
- Um job tem um único receipt final, com identidade única, publicado
  atomicamente na raiz do run. Não aceitar múltiplos receipts finais para o
  mesmo job nem sucesso sem receipt válido.
- JUnit deve corresponder à identidade exata do job e ser reconciliável com o
  receipt, seleção/perfil, exit code e contagens. Receipt/JUnit divergente
  bloqueia PASS.
- stdout e stderr permanecem em streams/arquivos separados e limitados à raiz
  do run. Erros de controle e job devem manter identidade de run para
  reconciliação.

## 5. Timeout, cancelamento e árvore de processos

- O deadline de cada profile é wall-clock total, incluindo inicialização MXC,
  worker, encerramento OS e publicação/reconciliação do receipt. Medir com
  relógio monotônico; nunca estender hard deadline.
- Limites totais: `Infrastructure = 150s`, `Affected = 25s`, `Harness = 150s`.
  Diagnósticos internos aos totais: `Infrastructure = 120s`, `Affected = 12s`,
  `Harness = 120s`; não acrescentam tempo. O deadline de `Infrastructure`
  inclui inicialização MXC e testes do protocolo.
- Reservar até `5s` dentro de cada total para kill/reap/publicação e reconciliação
  da evidência; tempo efetivo do worker não pode exceder deadline total menos
  essa reserva. Nunca estender hard deadline.
- Associar o processo ao Job Object OS antes de liberar sua execução. Se a
  associação não for possível, parar `BLOCKED`. Após kill/cancelamento, exigir
  observação de `ACTIVE_PROCESS_COUNT = 0`; ausência dessa observação ou count
  não zero é `BLOCKED`.
- `PROCESS_TREE = PASS` somente com fronteira OS e ausência observada de
  descendentes/active processes após o término. Documentação MXC não é prova.
- Compatibilidade MXC/Job Object e comportamento de loopback são `UNKNOWN` até
  evidência. Qualquer incompatibilidade MXC/Job Object ou término incerto
  classifica o caso `BLOCKED`.

## 6. Ownership e ordem de execução

| Papel | Ownership exclusivo nesta atividade |
|---|---|
| Root | Orquestração, adjudicação, integração e reconciliação |
| Scribe | Este contrato, relatório de recuperação, `PROJECT_STATE.md` e `CONTINUITY_RECORD.md` |
| Mechanical implementer | `tools/manual_proofs/s6_v2_offline_regression_runner.py`; `tools/manual_proofs/Invoke-S6V2OfflineRegression.ps1`; opcionalmente criar `tools/manual_proofs/s6_v2_mxc_host_executor.py` se necessário |
| Testes de infraestrutura | Criar/alterar somente `tests/manual_proofs/test_s6_v2_mxc_host_executor.py` |

WIP compartilhado permanece preservado. Este contrato não autoriza alterações
fora do ownership listado. A ordem é: implementar transporte/protocolo;
executar primeiro somente os testes do novo protocolo de infraestrutura no
executor novo; fechar todos os gates da seção seguinte; somente após o gate
infra passar, retomar os testes/correções isolados de harness já autorizados
nos respectivos contratos e owners existentes.

## 7. Critérios do gate de infraestrutura

O gate infra só passa quando houver evidência reconciliada de todos os itens:

1. Dois jobs `Infrastructure` em sequência: teste 1 → receipt → retorno ao
   root → teste 2, sem ação manual do usuário entre eles, usando snapshots e
   identidades próprios.
2. Falha sintética de um job `Infrastructure` reportada como falha e isolada
   do outro job, com receipt/JUnit/exit e streams reconciliados.
3. `submit/status/cancel/result` demonstrados para a identidade correta do job.
4. Timeout e cancelamento demonstrados dentro do deadline e grace definidos,
   sem deixar descendentes ativos.
5. Término da árvore aprovado somente após associação prévia ao Job Object OS
   e observação de `ACTIVE_PROCESS_COUNT = 0`; caso contrário, gate bloqueado.
6. Negação de rede demonstrada sob o profile `Infrastructure`; ausência de
   prova de negação de rede bloqueia o gate. Antes do gate, não executar
   `Affected` nem `Harness`.
7. Snapshot e `RunSpec` reconciliados por hash antes/depois; receipt único,
   atômico e válido; JUnit de identidade exata reconciliado; stdout/stderr
   separados e contidos na raiz do run.

Até todos os critérios passarem, registrar infra como `PARTIAL` ou `BLOCKED`,
conforme a evidência, e não executar testes/correções isolados do harness.

## 8. Fora de escopo e preservação

Não executar Telegram, downloads reais/provas reais, nem acessar SQLite de
produção. Manter S6 V1 ativo e V2 global desligado. Preservar WIP amplo; não
fazer staging, commit ou push. Este contrato não declara o gate infra, a
regressão nativa completa, autonomia ou aceitação S6 como PASS.

## 9. Base factual e estado inicial

O comando one-shot host MXC retornou exit 0 e `MXC_HOST_OK`. Uma sessão nativa
persistente também recebeu `ROOT_PING`, devolveu `ACK:ROOT_PING` e exit 0.
Essas evidências comprovam startup e round-trip básico de stdin/stdout em
sessão persistente. Não demonstram JSONL, operações de job, rede negada,
árvore de processos, teste funcional nativo ou autonomia. A falha anterior
`native MXC is unavailable on this executor` ocorreu uma vez e não foi
repetida. O acidente `codex sandbox windows --help` e as lacunas da
pós-checagem estão documentados no relatório de recuperação.

```text
HOST_MXC_AVAILABLE = YES
HOST_TRANSPORT_EVIDENCE = PING_ONLY / ONE-SHOT MXC_HOST_OK AND PERSISTENT ROOT_PING -> ACK:ROOT_PING / EXIT 0
NATIVE_EXECUTION_VERIFIED = STARTUP_AND_BASIC_PERSISTENT_TRANSPORT_ONLY
JSONL_JOB_PROTOCOL = NOT_VERIFIED
NATIVE_FUNCTIONAL_TESTS = NOT_RUN
NETWORK_ISOLATION = NOT_VERIFIED
PROCESS_TREE = NOT_VERIFIED
MXC_JOB_OBJECT_COMPATIBILITY = UNKNOWN
LOOPBACK_COMPATIBILITY = UNKNOWN
JOB_OBJECT_ASSOCIATION = NOT_VERIFIED
ACTIVE_PROCESS_COUNT_ZERO = NOT_VERIFIED
INFRASTRUCTURE_PROFILE = FIXED / NEW PROTOCOL TEST FILE ONLY / 150s TOTAL / 120s DIAGNOSTIC
S6_PROFILES = AFFECTED=25s TOTAL/12s DIAGNOSTIC; HARNESS=150s TOTAL/120s DIAGNOSTIC / UNAVAILABLE UNTIL INFRA GATE PASS
AUTONOMY_GATE = BLOCKED
NEXT_ACTION = IMPLEMENT THE INFRASTRUCTURE CONTRACT, THEN RUN INFRASTRUCTURE GATES
```

## 10. Fontes

- [Relatório de recuperação MXC](../reports/S6_V2_NATIVE_EXECUTION_RECOVERY_2026-10-20.md).
- [PROJECT_STATE](../continuity/PROJECT_STATE.md) e
  [CONTINUITY_RECORD](../continuity/CONTINUITY_RECORD.md).
