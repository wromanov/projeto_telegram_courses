# Registro de continuidade

```text
DOCUMENT_ROLE = CONTINUITY_RECORD
PROJECT_ID = projeto_telegram_courses
RECORDED_AT = 2026-10-08 / America/Sao_Paulo
```

O estado corrente, gates, bloqueios, riscos, autorizações, baseline e safe
resume são mantidos em [PROJECT_STATE.md](PROJECT_STATE.md). O mapa em
[ACTIVE_AUTHORITY_MAP.md](ACTIVE_AUTHORITY_MAP.md) aponta às authorities por
assunto.

Este checkpoint reconcilia o fechamento canônico da S0: SP01-01..10 PASS,
SP01_RESULT PASS e S0_COMPLETION_PERCENT 100%. O replay final de casa está
registrado de forma sanitizada em
[SP01_STACK_WINDOWS](../engineering/evidence/SP01_STACK_WINDOWS.md). O problema
anterior de `ensurepip` é histórico; a causa raiz segue indeterminada e não
bloqueia a validação S0 concluída. PROJECT_COMPLETION_PERCENT permanece
NOT_FORMALLY_DEFINED.

O checkpoint corrente conclui S1-B — Offline Authentication Flow & Telegram
Gateway, após S1-A — Protected Session Foundation. O fluxo, boundary próprio de
autenticação, adapter Telethon e integração CLI foram validados por fakes e
valores sintéticos; pytest completo (50 passed, 8 subtests passed) e Ruff
passaram. A regressão S1-A de DPAPI/ACL também passou. Não houve conexão
Telegram, credencial ou sessão real, nem publicação Git. S1 permanece
IN_PROGRESS; S1-B PASS não fecha a Sprint. O contrato S1-B está congelado em
[S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT](../contracts/S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md).

S1-C e S1-C-OFF-01 estão `PASS`; S1 permanece `IN_PROGRESS`, pois descoberta
e seleção de canais continuam pendentes. A sequência factual, adjudicação das
evidências, segurança e limites de verificação independente estão registrados
uma única vez em [PROJECT_STATE](PROJECT_STATE.md). Esta reconciliação não
repetiu autenticação nem conectou ao Telegram.

O pacote anterior foi publicado em `work/s0-bootstrap`, commit
`2be283f04502ff2b6980831cec6445b0b64da102`. Esse é um marco histórico,
não o HEAD corrente. Branch, HEAD, upstream e worktree devem ser descobertos
em runtime. A correção offline S1-C-OFF-01 passou em focused pytest, full
pytest e Ruff. Após um preflight inicialmente bloqueado por configuração
ausente, o usuário configurou o ambiente local e forneceu evidência de sucesso
na autenticação e reutilização de sessão. S1-C está `PASS`; S1 permanece
`IN_PROGRESS`, pois descoberta/seleção de canais segue pendente. A próxima
candidata é S1-D — Channel Discovery & Selection, limitada nesta retomada à
avaliação de escopo, readiness e contrato, sem autorização de implementação
ou descoberta real. Os contratos
[S1-B](../contracts/S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md) e
[S0_IMPLEMENTATION_CONTRACT](../contracts/S0_IMPLEMENTATION_CONTRACT.md)
permanecem congelados. Veja [LAST_HANDOFF](handoff/LAST_HANDOFF.md) para retomada.

O preflight inicialmente bloqueado de S1-C-A02 e a autorização limitada
exercida são históricos; essa autorização está esgotada. Nenhuma operação Git
foi feita nesta reconciliação.

S1-TEST-01 — Pytest Environment Diagnosis está `BLOCKED`: a collection local
obteve 55 itens, mas o primeiro teste focado do gateway e uma sonda mínima
`asyncio.run` pararam durante a inicialização do Proactor do Windows, em
`socket._fallback_socketpair`/`accept`. O mecanismo imediato foi confirmado; a
causa inferior do host/venv não foi estabelecida. A revalidação permanece
`PENDING`; suíte completa, Ruff e `git diff --check` não foram executados.
Nenhum acesso Telegram, mudança de código ou operação Git ocorreu. Evidência
sanitizada: [S1_TEST_01_PYTEST_ENVIRONMENT_DIAGNOSIS_2026-10-08](../reports/S1_TEST_01_PYTEST_ENVIRONMENT_DIAGNOSIS_2026-10-08.md).
O checkpoint `e947406dbcab8ef593123f079daa279903805d2c` permanece publicado e
inalterado. O safe resume point daquele diagnóstico foi S1-D Architectural Entry
Review, DIRECT / GPT-6 SOL / HIGH; foi sucedido pela atividade documental
abaixo, sem iniciar implementação de S1-D.

## S1-D — draft arquitetural, 2026-10-08

O pedido atual informou Entry Review PASS e autorizou somente análise e draft.
Foi entregue [S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md),
DRAFT / NOT_APPROVED / NOT_FROZEN. A análise estática do Telethon 1.45.0
distingue payload incidental recebido pela biblioteca de processamento de
conteúdo pela aplicação. Decisões OPEN, divergência de hashes e ponto seguro
têm estado único em [PROJECT_STATE](PROJECT_STATE.md); o contrato contém os
detalhes/evidências. As alterações e o relatório preexistentes de S1-TEST-01
foram preservados; revalidação continua PENDING. Não houve source/test, pytest,
operação Telegram, correção de policies/pins/binding, stage, commit, push ou
novo checkpoint Git. S1-C permanece PASS, S1 em andamento e implementação
S1-D não iniciada.

## S1-D — fechamento de decisões, 2026-10-08

O fechamento autorizado registrou DEC-S1D-01 (payload incidental de
`getDialogs` aceito nos limites definidos) e DEC-S1D-02 (broadcast + megagroup/
supergroup elegíveis) em [APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md).
A recomendação anterior broadcast-only foi marcada superseded; não existia
registro de `FUT-CHDISC-01`, e nenhum foi criado. O contrato em
[S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md) permanece
DRAFT / NOT_APPROVED / NOT_FROZEN. Completude, resultado parcial, cancelamento,
falhas e restore-only foram reconciliados tecnicamente pelas authorities
existentes. Permanecem OPEN os limites numéricos de descoberta, o perfil de
updates e GOV-01; os cinco hashes divergentes das policies continuam sem
reconciliação. S1-TEST-01 continua PENDING para revalidação. Nenhum código,
teste, policy, pin ou binding foi alterado; pytest, Telegram, sessão/credenciais,
stage, commit e push não foram usados.

## OPEN-04 — prova offline, 2026-10-08

Retomada delimitada em 2026-10-08: Python 3.14.7 e Telethon 1.45.0
confirmados. Fora da restrição anterior, socketpair e asyncio.run passaram.
A única prova sintética subsequente não emitiu trace em 35 segundos de espera
total e foi interrompida. GET_DIFFERENCE_COUNT = NOT_MEASURED; solução pública
= NOT_DEMONSTRATED. O limite MAX_PROOF_ATTEMPTS=1 encerra a exploração técnica
desta atividade. OPEN-04 exige decisão arquitetural humana explícita; contrato
permanece DRAFT / NOT_APPROVED / NOT_FROZEN. Evidência e limites no
[relatório OPEN-04](../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md).
DEC-S1D-01/02, OPEN-03 PENDING_MEASUREMENT, GOV-01 UNRESOLVED e revalidação
pytest PENDING foram preservados.

A prova está BLOCKED_ENVIRONMENT / NOT_DEMONSTRATED: import síncrono passou,
mas a sonda isolada de Selector travou no socketpair/accept interno, encerrada
após 8 s. Não há captura simulada de requests nem solução pública suficiente
identificada para o fluxo atual. A evidência e análise estão no
[relatório OPEN-04](../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md);
estado e retomada têm authority única em [PROJECT_STATE](PROJECT_STATE.md).
O contrato permanece draft; decisões anteriores, deltas, S1-A/B/C e diagnóstico
S1-TEST-01 foram preservados. Nenhum source/test, acesso Telegram, sessão real,
binding ou publicação Git. Recuperação do executor e eventual investigação
arquitetural dependem de escopo próprio; OPEN-03/GOV-01 continuam pendentes.

## S1-D — DEC-S1D-03 Documentation & Reconciliation, 2026-10-08

O usuário aprovou DEC-S1D-03 = D_PLUS_C após a auditoria independente. A decisão
permite o processamento interno incidental de `updates.GetDifference` e
`updates.GetChannelDifference` somente no lifecycle delimitado de descoberta,
incluindo inicialização e loop de updates. A restrição anterior
`PROVE_ZERO_GET_DIFFERENCE` está superseded. A aplicação continua proibida de
usar conteúdo incidental; não há garantia de zero RPC, ausência de mensagens ou
apagamento seguro em memória. A decisão e seus limites estão registrados em
[APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md), e o contrato
reconciliado em [S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).

OPEN-04 arquitetural = RESOLVED; validação técnica = PENDING. OPEN-03 segue
PENDING_MEASUREMENT, GOV-01 segue UNRESOLVED, revalidação de pytest segue
PENDING. DEC-S1D-01/02 preservadas. Contrato segue DRAFT / NOT_APPROVED /
NOT_FROZEN, S1D_DOR = NOT_PASS e implementação NOT_STARTED / NOT_AUTHORIZED.
Próxima atividade: preparar os critérios e evidências restantes para revisão
separada de aprovação/freeze. Nenhum source/test, pytest, Telegram, credencial,
sessão real ou operação Git foi usado. O estado único e safe resume point estão
em [PROJECT_STATE](PROJECT_STATE.md).

## S1-D — implementação e revalidação offline, 2026-10-09

O usuário aprovou o contrato S1-D e seu baseline numérico, e autorizou a
implementação nesta conversa. A implementação e a prova sintética offline
passaram. A revalidação usou PowerShell local independente do executor
restrito: Python 3.14.7 da venv, `socketpair` e `asyncio.run` PASS, collection
96, focused discovery 41 passed e FULL_PYTEST 96 passed + 8 subtests em
158,55 s (exit 0; timeout externo de 180 s não alcançado); Ruff PASS. A falha
anterior com WinError 10013 e o diagnóstico com watchdog de 30 s permanecem
observações históricas do ambiente restrito/diagnóstico, não resultado da
execução final. Não houve rede Telegram, acesso a sessão/credenciais nem ação
Git. O contrato está aprovado, mas não congelado: GOV-01 ainda bloqueia freeze.
O aceite requer calibração operacional e validação real delimitada com
autorização específica. Estado e safe resume únicos em
[PROJECT_STATE](PROJECT_STATE.md); checkpoint de gates no §20 do
[contrato S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).

## S1-D — precheck de validação real, 2026-10-09

O usuário autorizou uma validação real delimitada. O precheck parou antes da
CLI: o artefato de sessão DPAPI esperado não existe e as variáveis de API não
estão configuradas nos escopos Process/User/Machine. Nenhuma credencial ou
conteúdo de sessão foi lido; nenhuma conexão, login ou operação remota ocorreu.
A autorização não congela o contrato nem remove GOV-01, que continua bloqueando
freeze. A atividade fica `BLOCKED_PRECHECK`; retomar a mesma autorização somente
após sessão protegida válida e credenciais locais disponíveis, sem iniciar login.
Evidência sanitizada: [S1D_REAL_DISCOVERY_VALIDATION_2026-10-09](../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md).
O estado e o safe resume point únicos permanecem em [PROJECT_STATE](PROJECT_STATE.md).

## S1-D — correção offline da resposta de 101 diálogos, 2026-10-09

O usuário reportou a primeira execução real: o adapter solicitou 100 e recebeu
101 diálogos, classificando como `ADAPTER_FAILURE` antes de projetar qualquer
candidato. A origem no guard local foi confirmada; não houve exceção original
Telethon. A correção aceita apenas overflow da primeira resposta explicado por
linhas explicitamente marcadas como fixadas, conta todas no teto bruto e
preserva os limites aprovados. Testes unitários e integração CLI foram escritos
com objetos Telethon e transporte falso. Ruff passou; coleta focada/full passou
(24/109 itens), mas execução dos testes bloqueia porque `asyncio.run` mínimo
pendura neste executor. Nenhum acesso real foi repetido. Estado e safe resume
em [PROJECT_STATE](PROJECT_STATE.md); nova tentativa Telegram permanece
`PENDING_RETRY` e requer autorização separada.

## S1-D — Telegram API Credentials Vault, 2026-10-09

O usuário autorizou explicitamente a implementação offline do vault persistente
de credenciais Telegram. O vault reutiliza DPAPI CurrentUser e as verificações
de ACL existentes, grava em `credentials.dpapi` separado de `session.dpapi`,
usa payload versionado e gravação atômica sem sobrescrita. A CLI adiciona
`credentials setup` com API HASH oculto e `credentials status` sem exposição de
valores; auth e channels resolvem um par completo de ambiente antes do vault e
rejeitam variáveis incompletas sem misturar origens.

Validação com apenas valores sintéticos: focused 29 passed + 11 subtests;
integração DPAPI CurrentUser Windows 1 passed; regressão final 110 passed + 11
subtests em 169,05 s (exit 0); Ruff PASS. Nenhuma credencial real foi lida ou
configurada, a sessão DPAPI real não foi aberta, e nenhuma rede Telegram foi
usada. Evidência completa em
[S1D_CREDENTIALS_VAULT_2026-10-09](../reports/S1D_CREDENTIALS_VAULT_2026-10-09.md).

O resultado reportado anteriormente continua registrado como
`ADAPTER_FAILURE / PAGES_REQUESTED=1 / PAGES_RECEIVED=1 /
RAW_DIALOGS_RECEIVED=101`; o vault não corrige nem reavalia esse erro. O usuário
deve configurar o vault localmente com `telegram-courses credentials setup`,
verificar com `telegram-courses credentials status` e confirmar a disponibilidade
de uma sessão protegida antes de retomar a validação delimitada já autorizada.
DEC-S1D-01/02/03 e OPEN-03 permanecem inalteradas; GOV-01 ainda bloqueia freeze.
Estado e safe resume point únicos em [PROJECT_STATE](PROJECT_STATE.md).

## Checkpoint consolidado S1-D — 2026-10-09

Conforme instrução direta do usuário nesta atividade, S1-A/B/C e o vault de
credenciais estão PASS. S1-D está `IMPLEMENTED / REAL_FUNCTIONAL_PASS /
FINAL_ACCEPTANCE_PENDING`; descoberta real, descoberta de broadcast e
megagroup, seleção local e correção do adapter em cenário real estão PASS.
DEC-S1D-01/02/03 e OPEN-03 permanecem aprovadas. `CONTRACT_FREEZE` não foi
confirmado; GOV-01 é dependência externa. S1-D não está CLOSED.

A regressão mais recente informada pelo usuário foi 109 passed, 1 failed,
11 subtests passed em 183.63s (`FULL_REGRESSION=NOT_PASS`). As evidências
disponíveis não identificam arquivo, teste ou mensagem da falha nem sua causa;
causa permanece desconhecida. A suíte não foi executada novamente nesta
atividade. A próxima melhoria aprovada para CLI é seleção numérica de canais
por índice, mantendo o `telegram_chat_id` estável internamente, permitindo Q
para cancelar, rejeitando índices inválidos, sem nova consulta Telegram e sem
ações remotas; testes devem ser offline. A melhoria está aprovada e não
implementada. O safe resume é `S1-D — Regression Fix + CLI Numeric Selection`;
detalhes vigentes em [PROJECT_STATE](PROJECT_STATE.md) e
[LAST_HANDOFF](handoff/LAST_HANDOFF.md).

## S1-D — Regression Fix + CLI Numeric Selection, 2026-10-09

A falha foi reproduzida em
`tests/unit/test_auth.py::test_credentials_are_environment_only_and_validated`:
`Failed: DID NOT RAISE ConfigurationError`. O teste fornecia ambiente vazio,
mas o loader usa o vault DPAPI como fallback; um vault configurado na máquina
tornou o teste dependente do ambiente. O teste foi corrigido para injetar vault
sintético vazio. A chamada pré-correção leu/descriptografou o vault local;
nenhum valor foi exibido ou registrado, e `session.dpapi` não foi acessado.
Esta ocorrência está reportada explicitamente na evidência e em
[PROJECT_STATE](PROJECT_STATE.md).

A CLI agora exibe canais numerados em ordem, aceita o índice local ou o ID
completo exato, cancela com entrada vazia/Q e rejeita entradas inválidas. A
identidade de domínio continua `telegram_chat_id`; a seleção usa o snapshot,
inclusive em discovery `PARTIAL`, após o fechamento do gateway e sem nova
chamada de descoberta.

Validação local com Python 3.14.7: focused regression 3 passed; focused CLI 15
passed; full pytest 121 passed e 11 subtests em 184.34s; Ruff PASS; `git diff
--check` PASS. A tentativa inicial no executor isolado bloqueou no socketpair
Proactor antes dos testes; o resultado conclusivo veio do PowerShell local
funcional. Nenhuma conexão Telegram foi feita.

O resultado técnico passou, mas a atividade fica `PARTIAL` porque o teste
pré-correção acessou/descriptografou o vault local, contra a restrição do
pedido. Nenhum valor foi exibido ou registrado. A revisão do incidente e o
aceite final permanecem pendentes. S1-D segue `IMPLEMENTED /
REAL_FUNCTIONAL_PASS / FINAL_ACCEPTANCE_PENDING`. DEC-S1D-01/02/03, OPEN-03 e
GOV-01 não foram alterados. Não declarar fechamento, freeze, remediação,
publicação Git ou início de S2. Evidência:
[S1D_REGRESSION_CLI_NUMERIC_SELECTION_2026-10-09](../reports/S1D_REGRESSION_CLI_NUMERIC_SELECTION_2026-10-09.md).

## S1-D — Credential Isolation Review & Final Acceptance, 2026-10-09

### Incidente e isolamento

O caminho acidental foi: `tests/unit/test_auth.py` chamou
`load_telegram_credentials({})`; em `config.py`, ausência do par na mapping
leva ao construtor padrão `CredentialVault`; esse cria
`_ProtectedCredentialsVault`, que herda `_ProtectedSessionVault` e lê
`credentials.dpapi` via `_load`/DPAPI. A fixture antiga não injetava storage
vazio nesse caso. O teste corrigido injeta um vault sintético vazio.

Busca estática dos demais testes não encontrou outra resolução padrão para o
storage do usuário: usos de CredentialVault/TelethonGateway injetam fakes ou
diretórios temporários; os testes Windows criam artefatos sintéticos em
`tmp_path`; o teste do caminho do repositório espera rejeição. Para fechar a
lacuna global, `tests/conftest.py` agora, por teste, remove
`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_COURSES_CONFIG` e
`TELEGRAM_COURSES_LOG_LEVEL`, e define `LOCALAPPDATA` sob `tmp_path`. O
`unittest` que limpa `os.environ` cria seu próprio `LOCALAPPDATA` temporário.
Testes de regressão confirmam que os fallbacks de credential e session
resolvem somente sob o diretório temporário; nenhum vault/session real é aberto.
O fixture afeta pytest, não o runtime normal da CLI.

O resultado capturado da falha foi apenas `DID NOT RAISE ConfigurationError`;
nenhum valor apareceu no output pytest. A implementação observada sanitiza
exceções e não há caminho de log/export nesse teste. O valor descriptografado
foi materializado em memória no processo de teste, que terminou. Não houve
inspeção forense de memória, crash dumps ou telemetria externa; esses pontos
ficam como risco não verificado, não como evidência de divulgação.

### Verificação da aceitação

Critérios offline AC-01..12: cobertos por fakes, fixtures sintéticas e pela
regressão completa. Seleção numérica e legacy ID estão offline PASS. Discovery
real e seleção por ID real permanecem `PASS_USER_REPORTED`; nenhuma conexão foi
feita nesta atividade. A evidência disponível não contém duração de restore,
discovery/cleanup, contadores/cobertura observados nem comparação aos budgets
aprovados (`page_size=100`, `max_raw_dialogs=1000`, `max_pages=20`, operação
120s, cleanup 10s). O relatório existente da tentativa real anterior registra
`OPERATIONAL_CALIBRATION = NOT_MEASURED`; não foi encontrado registro posterior
com essas medições.

```text
ACTIVITY = S1-D Credential Isolation Review & Final Acceptance
INCIDENT_REVIEW = PASS / root cause and test path identified; no repeat vault access
TEST_ISOLATION = PASS / global pytest temp storage/env isolation + credential/session path regression tests
FOCUSED_PYTEST = PASS / 42 passed, 11 subtests passed
FULL_PYTEST = PASS / 123 passed, 11 subtests passed in 165.76s / Python 3.14.7
RUFF = PASS
DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
CREDENTIAL_ACCESS_THIS_ACTIVITY = NO
SECRET_EXPOSURE_EVIDENCE = no values in captured failure/output; external OS telemetry not inspected
RESIDUAL_RISK = prior test process materialized plaintext in memory; external crash/OS telemetry unknown
S1D_OFFLINE_AC01_AC12 = PASS
S1D_REAL_FUNCTIONAL_EVIDENCE = PASS_USER_REPORTED / discovery and ID selection
OPERATIONAL_CALIBRATION = NOT_MEASURED_IN_AVAILABLE_EVIDENCE
S1D_FINAL_VERDICT = NOT_ACCEPTED_YET / operational calibration is an explicit acceptance gate
CONTRACTS_AND_GOVERNANCE = UNCHANGED
GIT_ACTIONS = NONE
```

Conclusão: não declarar S1-D formalmente aceita ainda. Os resultados reais
fornecidos pelo usuário cobrem discovery e seleção por ID, e todos os gates
offline passaram. O aceite do contrato também exige calibração operacional;
ela não está comprovada nos registros disponíveis. Primeiro procurar métricas
sanitizadas da validação já realizada. Só se não existirem, considerar nova
calibração após autorização específica; esta atividade não autoriza conexão.
S1-D não está CLOSED e S2 não foi iniciado. Estado único em
[PROJECT_STATE](PROJECT_STATE.md); handoff em [LAST_HANDOFF](handoff/LAST_HANDOFF.md).

### Checkpoint — calibração operacional S1-D

Revisão dos registros disponíveis confirmou que a primeira descoberta real
falhou no adapter após 1 página solicitada/recebida e 101 diálogos brutos. A
descoberta funcional posterior e a seleção por ID foram reportadas como
aprovadas, mas sem durações, contagens ou resultado COMPLETE/PARTIAL. A causa
específica do overflow de 101 não é demonstrável a partir dos registros.

Telemetria offline foi adicionada ao workflow S1-D. Ela mede com relógio
monotônico operação, restore, descoberta e cleanup, e registra contadores,
budgets, resultado e razão de parada em uma linha sanitizada. Testes verificam
COMPLETE/PARTIAL, sanitização de erro e ausência de identificadores. Focados:
43 passed; suíte completa: 126 passed, 11 subtests; Ruff e diff check: PASS.
Nenhum acesso real foi feito.

```text
METRICS_SUFFICIENT = NO
INSTRUMENTATION_READY = YES
S1D_ACCEPTANCE = PENDING_REAL_OPERATIONAL_MEASUREMENTS
NEXT_ACTION = after separate authorization, run .\.venv\Scripts\telegram-courses.exe channels and retain only S1D_CALIBRATION
REAL_TELEGRAM_ACCESS = NO
```

Relatório atualizado: [S1D real discovery validation](../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md).

## S1-D — aceite funcional e checkpoint final, 2026-10-09

Evidência sanitizada da calibração recebida nesta atividade: operação 2.809485s,
restore 0.957923s, discovery 1.315603s e cleanup 0.001170s; cleanup COMPLETE;
4/4 páginas; 313 diálogos brutos. Limites aprovados: página 100, total bruto
1000, páginas 20, operação 120s e cleanup 10s. Resultado/outcome COMPLETE,
sem stop reason ou failure category. Discovery real, broadcast, megagroup e
seleção local PASS; a opção `69` resolveu para o `telegram_chat_id` esperado.
Nenhum download ou scanner foi iniciado.

```text
FUNCTIONAL_ACCEPTANCE = PASS
CONTRACT_FREEZE = BLOCKED_BY_GOV01
FORMAL_CLOSURE = BLOCKED_BY_GOV01 / S1-D NOT CLOSED
DEC-S1D-01/02/03 = APPROVED / PRESERVED
OPEN-03 = APPROVED / limits measured within budget
AC-01..12_OFFLINE = PASS
FULL_PYTEST = PASS / 126 passed, 11 subtests, 167.64s
RUFF = PASS / GIT_DIFF_CHECK = PASS
CREDENTIAL_VAULT = PASS / PYTEST_CREDENTIAL_ISOLATION = PASS
INCIDENT = prior accidental vault read and residual risk preserved; not reopened
REAL_TELEGRAM_ACCESS_FOR_VALIDATION = YES / user-provided evidence
CREDENTIALS_ACCESSED_DURING_THIS_RECONCILIATION = NO
GIT_ACTIONS = NONE
NEXT_PHASE_CANDIDATE = S2 — Message Scanner & SQLite Persistence / not started
```

O aceite funcional satisfaz os critérios registrados no contrato. O contrato
separa aceite de freeze; contudo, GOV-01 continua sem adjudicação e é o requisito
externo que bloqueia freeze e encerramento formal. Não declarar `CLOSED`, não
alterar governança e não iniciar S2. Ver [relatório final S1-D](../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md).
