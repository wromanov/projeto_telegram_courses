# S1-D — OPEN-04 Offline Feasibility Proof

## Retomada offline delimitada — 2026-10-08

O precheck confirmou `work/s0-bootstrap` em
`e947406dbcab8ef593123f079daa279903805d2c`, Python 3.14.7 e Telethon
1.45.0. Os deltas documentais preexistentes foram preservados. Em execução local
fora da restrição anterior, uma sonda mínima de `socket.socketpair()` e
`asyncio.run(asyncio.sleep(0))` passou (`LOCAL_CONTEXT_PASS`). Isso confirma a
disponibilidade do contexto funcional para esta atividade, sem reabrir a
investigação do WinError 10013.

Uma única prova sintética foi iniciada no mesmo contexto, sem arquivos de sessão
reais, credenciais reais ou sockets Telegram. O código transitório, enviado por
stdin, criava `StringSession` com chave artificial e estado de updates vazio,
substituía o sender apenas na prova e previa respostas artificiais para
`GetUsers`, `GetState`, `GetDifference` e `GetDialogs`. Seu fluxo previsto era
restaurar, conectar, verificar autorização, iterar diálogos e desconectar.
Nenhum trace ou resultado foi emitido em 30 segundos de execução mais uma
consulta posterior de 5 segundos; o processo foi interrompido, exit 1. A causa
da ausência de saída não foi estabelecida. O limite de uma tentativa impede
repetição ou ajuste do harness nesta atividade.

```text
ACTIVITY = S1-D OPEN-04 Offline Feasibility Resume
STATUS = FAIL / single bounded proof did not return evidence
ACTIVITY_COMPLETION_PERCENT = 88% / partial evidence and reporting
ROOT_RUNTIME_MODEL = GPT-6 SOL target / exact runtime variant and effort not exposed
OFFLINE_EXECUTOR = LOCAL_PRECHECK_PASS / synthetic proof produced no trace
SYNTHETIC_PROOF = FAIL
GET_DIFFERENCE_COUNT = NOT_MEASURED
REQUEST_SEQUENCE = NOT_CAPTURED
SOLUTION_CLASSIFICATION = NOT_DEMONSTRATED
PUBLIC_API_SOLUTION = NOT_DEMONSTRATED
PRIVATE_INTERNALS_REQUIRED = UNDETERMINED / no candidate validated
AUTHENTICATION_COMPATIBILITY = NOT_DEMONSTRATED_FOR_CANDIDATE / baseline preserved
MATERIAL_USER_DECISION_REQUIRED = YES / OPEN-04 architectural disposition
OPEN04_STATUS = NOT_DEMONSTRATED / technical exploration stopped after one attempt
OPEN03_STATUS = PENDING_MEASUREMENT
GOV01_STATUS = UNRESOLVED
FULL_PYTEST = PENDING_REVALIDATION
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
SOURCE_CHANGES = NONE
TEST_CODE_CHANGES = NONE
TELEGRAM_NETWORK_USED = NO
REAL_CREDENTIALS_AND_SESSION_ACCESS = NO
GIT_ACTIONS = NONE / read-only status and identity checks
```

Esta tentativa não substitui validação real no Telegram nem demonstra
impossibilidade universal. A análise estática preservada abaixo segue válida:
`receive_updates=False` não elimina por si só o `GetDifference` inicial no
caminho observado do Telethon 1.45.0. Sem solução pública demonstrada e sem
aprovação do payload de diferenças, OPEN-04 requer decisão humana explícita:
manter a descoberta bloqueada; autorizar revisão arquitetural delimitada de
sessão/lifecycle; ou reavaliar explicitamente o escopo de payload e seus riscos.
Nenhuma dessas alternativas é aprovada por este relatório.

Data: 2026-10-08 / America/Sao_Paulo. Execução DIRECT. Pedido: anexo
`cc1d0b8b-ef65-4b7e-b914-b88c60161178/Texto colado.txt`.

## Tentativa anterior — resultado e limites (histórico)

```text
STATUS = BLOCKED
ACTIVITY_COMPLETION_PERCENT = 76%
PROOF_STATUS = BLOCKED_ENVIRONMENT
ROOT_RUNTIME_MODEL = GPT-6 / variante SOL e effort não verificáveis nesta superfície
OFFLINE_EXECUTOR_STATUS = SYNCHRONOUS_IMPORT_PASS / ASYNCIO_SELECTOR_BLOCKED
GET_DIFFERENCE_AVOIDANCE = NOT_DEMONSTRATED
SOLUTION_CLASSIFICATION = NOT_DEMONSTRATED
PUBLIC_API_SUPPORT = UNDETERMINED / nenhum mecanismo suficiente localizado no fluxo atual
PRIVATE_INTERNALS_REQUIRED = UNDETERMINED / alternativas locais identificadas dependem de internals; não prova impossibilidade universal
REQUEST_TRACE_EVIDENCE = NONE / sequência abaixo é estática, não captura
AUTHENTICATION_COMPATIBILITY = NOT_DEMONSTRATED_FOR_CANDIDATE / baseline preservada
SESSION_SECURITY_IMPACT = NONE_FROM_THIS_ACTIVITY / sessão e credenciais reais não acessadas
IMPLEMENTATION_RISK = HIGH_FOR_PRIVATE_WORKAROUNDS / nenhuma solução aprovada
MATERIAL_USER_DECISION_REQUIRED = YES / escopo de recuperação do executor e eventual revisão arquitetural
OPEN04_STATUS = NOT_DEMONSTRATED / BLOCKED_ENVIRONMENT
OPEN03_STATUS = PENDING_MEASUREMENT
GOV01_STATUS = UNRESOLVED
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
S1D_IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
```

Estimativa de conclusão: recuperação, sonda e inspeção/adjudicação estática
concluídas; captura simulada e validação dos cenários A–E não concluídas.
Reconciliação documental registra o bloqueio, sem fechar a prova.

## Executor offline

`.venv/Scripts/python.exe -B` importou Telethon em processo isolado: Python
3.14.7, Telethon 1.45.0, exit 0. O aviso de localização do executável base
persistiu; sua causalidade com o travamento não foi estabelecida.

Uma única sonda diagnóstica criou `asyncio.SelectorEventLoop()`, tentou executar
`asyncio.sleep(0)` e fechar o loop. `faulthandler.dump_traceback_later(8,
exit=True)` encerrou o processo com exit 1 durante o construtor do loop:

```text
socket.py:298 accept
socket.py:633 _fallback_socketpair
asyncio/selector_events.py:120 _make_self_pipe
asyncio/selector_events.py:66 __init__
<string>:1 <module>
```

`SELECTOR_PROBE_BEGIN` apareceu; `SELECTOR_PROBE_PASS` não apareceu. Nenhuma
política global de asyncio foi alterada. A sonda usa o socketpair local interno
do próprio asyncio; não abriu conexão Telegram. Não repetimos Proactor nem a
sonda bloqueada. O diagnóstico anterior de Proactor e a revalidação pytest
PENDING permanecem em S1-TEST-01. A causa inferior do host/venv permanece
NOT_ESTABLISHED; Selector não é solução demonstrada neste host.

## Evidência estática do Telethon instalado

Referências relativas à instalação `.venv/Lib/site-packages/telethon/`:

| Local | Fato observado |
|---|---|
| `sessions/string.py:11–53`, `sessions/memory.py:13–90` | StringSession restaura DC/endereço/porta/auth key; não serializa estado de updates. MemorySession inicia `_update_states={}`. |
| `client/telegrambaseclient.py:583–597` | `catch_up=True` carrega estados da sessão no MessageBox; uma StringSession recém-restaurada não possui esses estados. |
| `client/telegrambaseclient.py:605–619` | Envia inicialização/GetConfig, opcionalmente encapsulada; MessageBox vazio leva a get_me e, se autorizado, `_on_login`; cria tarefas de updates/keepalive. |
| `client/users.py:144–179` | get_me consulta GetUsers(InputUserSelf), cacheia identidade e retorna None em UnauthorizedError; não é o método que chama `_on_login`. |
| `client/auth.py:385–407` | `_on_login` solicita GetState e GetDifference sem condição baseada em receive_updates/catch_up. |
| `client/users.py:59–65` | receive_updates=False encapsula requests em InvokeWithoutUpdates; o request interno continua existindo. |
| `client/users.py:207–227` | is_user_authorized usa GetState se necessário; chamá-lo depois de connect não desfaz o GetDifference já disparado. |
| `client/updates.py:54–63,248–280,313` | set_receive_updates(False) desabilita recebimento; catch_up enfileira UpdatesTooLong; loop interno pode consultar diferenças. Não há opção pública aqui para suprimir a inicialização de `_on_login`. |
| `client/dialogs.py:27–110` | iter_dialogs constrói GetDialogsRequest; processa mensagens incidentais da resposta na biblioteca e pagina. Não controla a inicialização anterior de connect. |
| `client/telegrambaseclient.py:702–750` | disconnect cancela tarefas e salva estado via session; StringSession.save não persiste esse estado no valor protegido existente. |

Sequência derivada, **não executada/capturada**:

```text
restore StringSession → connect → InvokeWithLayer(initConnection(GetConfig))
→ GetUsers(InputUserSelf) → _on_login → GetState → GetDifference
→ tarefas internas → get_me do gateway → descoberta/GetDialogs → disconnect
```

Com receive_updates=False, os requests correspondentes usam
InvokeWithoutUpdates; isso não elimina GetDifference. A sonda bloqueou antes
da criação de um client, fake, credencial sintética ou sessão sintética.

Hashes SHA-256 dos arquivos inspecionados:

```text
client/telegrambaseclient.py = a25de6b17facbdf6888f4c12aae8d0d9a5aaaa45d7219ebf7399f4523fb9814e
client/auth.py = 955c6da74f697a9d923fb7f7eb5a9217b715a6a4839c6d0d3d10701b4f354592
sessions/string.py = 1185fb0a82cae97e87575cde676f7ca16f9791d3eefab221cad970d843208ebd
```

A [referência oficial do client 1.45.0](https://docs.telethon.dev/en/stable/modules/client.html)
documenta receive_updates e APIs de ciclo de vida. A descrição de connect
afirma apenas inicialização de baixo nível, mas o código instalado inclui o
caminho adicional acima. Essa divergência impede usar a descrição como prova
de zero GetDifference. A [documentação de sessões](https://docs.telethon.dev/en/stable/concepts/sessions.html)
apresenta StringSession e implementações customizadas; não demonstra uma
opção pública de supressão desse caminho com o storage/gateway atuais.

## Alternativas e adjudicação

| Alternativa | Avaliação nas restrições atuais |
|---|---|
| receive_updates=False + catch_up=False | Perfil público útil para reduzir updates, insuficiente para eliminar GetDifference inicial. Custo baixo, sem garantia exigida. |
| catch_up=True com StringSession restaurada | Sem estados persistidos, não soluciona o caso vazio; solicita catch-up no loop. Não recomendado. |
| get_me/is_user_authorized ou GetDialogs direto após connect | Autorização legítima e descoberta pública, mas a chamada problemática ocorre antes. |
| Session customizada com estado genuíno persistido | API de sessão extensível, mas exigiria novo contrato de storage/lifecycle e avaliar diferenças futuras; estado não existe no blob atual. Decisão arquitetural material, sem prova de zero diferenças. |
| Pré-carregar estado inventado | Viola a restrição de não falsificar updates; rejeitado. |
| Sobrescrever `_on_login`, MessageBox ou sender; filtrar RPC em produção | Dependência privada, custo alto de revisão a cada atualização e risco de ocultar erros/desalinhar lifecycle. Não aprovado. |
| Fazer get_me retornar None para evitar inicialização | Altera o significado da verificação de autorização e depende do comportamento interno de connect; não é mecanismo suportado de supressão. Rejeitado. |
| Reescrever connect/usar transporte MTProto próprio ou outra versão | Amplia arquitetura/manutenção e validação; fora deste escopo, sem viabilidade demonstrada. |

INFERÊNCIA limitada: não há solução pública suficiente identificada para o
gateway atual, a StringSession restaurada sem estado e Telethon 1.45.0.
Não classificar isso como impossibilidade universal nem como workaround
privado demonstrado. A classificação final da prova é NOT_DEMONSTRATED,
pois o executor falhou e nenhum candidato sustentável foi validado.

S1-A/B/C não sofrem alteração. Qualquer mudança futura no adapter compartilhado
exigirá autorização explícita e regressão de auth/sessão; nova Session exigirá
revisão da proteção/persistência de S1-A. O perfil de descoberta deve preservar
a semântica dos comandos de autenticação existentes. Não duplicar login nem
ampliar DEC-S1D-01 para diferenças.

## Cenários e assertions

```text
A_VALID_RESTORED_SESSION = NOT_RUN
B_EMPTY_UPDATE_STATE = STATIC_ANALYSIS_ONLY
C_CONNECT_AUTHORIZATION = NOT_RUN
D_SIMULATED_DIALOG_DISCOVERY = NOT_RUN
E_CONTROLLED_DISCONNECT = NOT_RUN
GET_DIFFERENCE_REQUEST_COUNT = NOT_MEASURED / zero não demonstrado
GET_DIALOGS_REQUEST = EXPECTED_STATICALLY / não observado
NO_UNAUTHORIZED_RPC = PASS_FOR_ACTIVITY / nenhum RPC executado; não valida candidato
NO_MESSAGE_CONTENT_EXPOSURE = PASS_FOR_ACTIVITY / nenhum payload recebido; canário não executado
PYTEST_REVALIDATION = PENDING / pytest não executado
TELEGRAM_NETWORK_USED = NO
REAL_CREDENTIALS_AND_SESSION_ACCESS = NO
SOURCE_CHANGES = NONE
TEST_FILE_WRITES = NONE
GOVERNANCE_BINDING_CHANGES = NONE
GIT_PUBLICATION_ACTIONS = NONE / somente consultas Git
HEAD = e947406dbcab8ef593123f079daa279903805d2c
```

Recomendação: manter OPEN-04 aberto. A menor decisão imediata é autorizar uma
atividade delimitada de recuperação do executor offline, com encerramento por
timeout e sem alteração global de asyncio. Recuperar o executor permite medir
o fluxo, mas não torna o perfil público suficiente. Para preparar aprovação do
contrato, será necessária evidência de um mecanismo sustentável ou uma revisão
arquitetural explicitamente autorizada. OPEN-03/GOV-01 e revalidação pytest
continuam com gates próprios. Simulação futura não substituirá validação real
separadamente autorizada. Não congelar nem implementar o contrato.
