# Contrato de implementação — estabilização S6 V2 — 2026-10-20

```text
DOCUMENT_ROLE = ACTIVITY_SCOPED_IMPLEMENTATION_CONTRACT
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_V2_STABILIZATION_IMPLEMENTATION
DELIVERY_UNIT = S6
DATE = 2026-10-20
AUTHORITY = CURRENT_EXPLICIT_USER_INSTRUCTION
CANONICAL_AUTHORITY = NO
CONTRACT_STATUS = MATERIALIZED / ACTIVITY-SCOPED
IMPLEMENTATION_AUTHORIZATION = YES / BOUNDED TO IMPLEMENTER FILES BELOW
TEST_AUTHORING_AND_EXECUTION_AUTHORIZATION = YES / BOUNDED TO TESTER FILES AND SAFE TEST GATES BELOW
V1_ACTIVE = YES
V2_GLOBAL = OFF
S6_FORMAL_ACCEPTANCE = PENDING
S7_S8 = DEFERRED
PRINCIPAL_ARCHITECT = CLOSED / NO_REENTRY
```

## 1. Purpose and authority boundary

Estabilizar as fronteiras entre proof harness, processos filhos, supervisor,
fixtures, launcher e evidências para corrigir os findings delimitados neste
contrato. O contrato registra a autorização explícita atual do usuário para
implementação e autoria/execução de testes nesta sprint. Ele é activity-scoped:
não substitui nem altera requisitos canônicos, arquitetura, integridade
operacional, S6 V1 ou outras authorities do projeto.

Esta autorização supera, somente para esta atividade, o adiamento anterior de
`HARNESS_TEST_CHANGES=DEFERRED` e o limite documental anterior. Ela não remove
gates técnicos do executor e não autoriza chamada ao Telegram, RPC, download,
prova real, adoção global do V2, aceite formal S6, avanço de roadmap/sprint ou
publicação Git.

## 2. Ownership

| Responsável | Ownership autorizado |
|---|---|
| Root | Coordenação, adjudicação, integração dos resultados e reconciliação documental |
| Architect | Parecer de leitura já encerrado; sem reentrada nesta atividade |
| Scriber | Este contrato, `PROJECT_STATE.md` e `CONTINUITY_RECORD.md` |
| Mechanical implementer | `tools/manual_proofs/s6_v2_proof_harness.py`, `tools/manual_proofs/s6_v2_offline_regression_runner.py`, `tools/manual_proofs/Invoke-S6V2OfflineRegression.ps1`, `tools/manual_proofs/Invoke-S6V2Proof.ps1` |
| Luna tester | `tests/manual_proofs/test_s6_v2_proof_harness.py` e `tests/manual_proofs/test_s6_v2_offline_regression_runner.py`; autoria e execução somente nos limites de validação deste contrato |

O checkout contém WIP compartilhado e preexistente. Nenhum responsável deve
reverter, limpar, sobrescrever ou assumir como próprio o trabalho de outro.
Não pode haver escritores concorrentes nos mesmos arquivos; integração e
resolução de conflitos são coordenadas pelo root. Os ownerships acima são
exclusivos para esta atividade.

## 3. Findings e limites de causalidade

1. Dois testes `OPERATIONAL_ONLY` exigem `PASS` na pós-verificação de
   integridade de referência, embora a referência trusted não se aplique a
   esse perfil; a expectativa correta é `NOT_APPLICABLE`.
2. Um processo filho pode falhar antes de produzir resultado funcional. O
   envelope `PROCESS_FAILED`, exit code 5 e `child_result = null` é válido
   quando corresponde à falha observada. Deve permanecer falha e nunca abrir
   phase 2. A ausência de resultado funcional não autoriza sucesso.
3. O supervisor não deve substituir a falha primária por
   `CHILD_REPORT_MISSING_OR_INVALID` quando o envelope válido registra falha
   pré-resultado. Deve validar identidade, schema, fase, alvo, modo, PID
   observado, exit observado, tipos exatos, raízes e artefatos; rejeitar
   conteúdo contraditório, ausente, malformado ou corrompido; e manter
   fail-closed. Em Python, `bool` não satisfaz requisito de tipo `int`.
4. Exceções específicas podem herdar de `DownloadError`; classificação deve
   percorrer uma allowlist pela classe mais específica. Código desconhecido é
   `OTHER`. Só stage e code sanitizados e allowlisted podem ser reportados; não
   registrar `str`/`repr` da exceção, locals, ambiente, secrets, conteúdo,
   código ou path sensível.
5. A atribuição histórica do trusted E2E a `PATH_TOO_LONG` permanece
   `PROBABLE / HIGH`, não confirmada retrospectivamente, pois o traceback
   direto não foi preservado. Uma reprodução futura pode confirmar apenas a
   causa observada nessa nova execução.
6. O probe trusted deve estar sob o valor efetivo de
   `S6_V2_TEST_ALLOWED_ROOT`; fora dele deve ser rejeitado. Os artefatos
   esperados devem ser demonstrados onde aplicável.
7. O gateway precisa fechar mesmo quando planejamento, plan, fila ou execução
   falham. A garantia de fechamento deve começar imediatamente após adquirir
   o gateway (`try/finally`). Erro no fechamento é secundário e não substitui
   a causa primária.

## 4. Requisitos do proof harness e das fixtures

- Preservar o guard de path de 240 caracteres.
- A fixture negativa deve provar que path final e `.part` acima do limite são
  rejeitados antes de `queue`, sem classificar o caso como sucesso. Cobrir o
  limite considerando o sufixo e incluir fixture curta, contida e válida.
- Colocar probes trusted dentro da raiz allowed efetiva; provar presença do
  artefato esperado e identidade de run/fase/conteúdo conforme o contrato do
  harness. Probes fora da raiz devem ser rejeitados.
- Exigir handshake explícito do filho antes de aceitar evidência de execução.
- Validar phase 1, sua identidade e seus artefatos antes de ler ou validar
  qualquer evidência de phase 2. Evidência negativa ou contraditória de phase 1
  não pode iniciar phase 2.
- Emitir observações `planner.begin/end`, `queue.begin/end` e
  `gateway.close.begin/end` somente quando realmente observadas; não sintetizar
  eventos ausentes.
- Preservar a semântica do trusted reference e seus gates existentes.

## 5. Requisitos do runner e launcher

- Alocar cada execução em `<repo>/.s6r/<12-char-token>/t`, com `basetemp` de
  no máximo 80 caracteres. A alocação deve ser exclusiva, tentar novo token em
  colisão, não reutilizar diretório e preservar o run ID completo no recibo e
  histórico. Preservar artifacts históricos; limpeza não é necessária.
- Proteger contra reparse points, symlinks, traversal e escape. Resolver e
  verificar containment de todos os paths de execução sob a raiz autorizada.
- Manter sandbox admission fail-closed. Não substituir `TEMP`, `LOCALAPPDATA`
  nem outras variáveis herdadas para contornar admission.
- Construir `RunSpec` imutável contendo ID, perfil allowlisted, digest do
  manifesto, intérprete/PowerShell, cwd/entrypoint/seleção/roots/deadlines,
  ambiente e isolamento. Capturar hashes antes/depois; drift invalida a
  execução. Perfis permitidos continuam `Affected` e `Harness`; não aceitar
  comandos, plugins ou paths livres.
- Reconciliar exatamente IDs esperados, coletados, executados, JUnit e receipt,
  incluindo parametrização, skip/xfail/xpass, setup/teardown, exit e artefatos.
  Zero, ausência ou contagens desconhecidas devem refletir somente evidência
  observada; não converter ausência em zero.
- Manter um único writer do receipt terminal: o supervisor Python. PowerShell
  pode registrar observações em arquivo separado. A publicação do receipt deve
  ser atômica.
- Conservar hard limits e waits finitos: `Affected` diagnostic 12s / hard 25s;
  `Harness` diagnostic 120s / hard 150s; relógio monotônico; limites internos
  vencem antes do externo; graça total de término de no máximo 5s. PowerShell
  5.1 é obrigatório.
- `$process.Kill($true)` não é compatível com PowerShell 5.1. `taskkill /T` e
  observação isolada do processo raiz não comprovam término de toda a árvore.
  Exigir uma fronteira verificável, como Windows Job Object sem breakaway ou
  equivalente comprovado. Sem prova disso, manter
  `termination_confirmed = false`, `PROCESS_EXIT_UNCONFIRMED` e `BLOCKED`.

## 6. Executor e classificação de testes

O estado observado neste executor é específico deste ambiente: Windows
26200.9711, Codex CLI 0.163.0. O probe oficial MXC suportado foi executado uma
única vez e terminou com exit 1 e a mensagem
`failed to prepare MXC sandbox: native MXC is unavailable on this executor`.
Não repetir o probe sem mudança material do executor. Isso demonstra a
indisponibilidade neste executor, não incompatibilidade global.

Option A segue bloqueada. Option B segue bloqueada até haver comprovação de
negação de egress no sistema operacional, separação de credenciais, restrição
do filesystem e controle verificável da árvore de processos. O próximo passo
para esses gates é provisionamento ou reconfiguração externa e verificável do
executor. Não alterar admission para contornar o bloqueio.

Podem ser executados neste workspace apenas testes unitários sintéticos,
determinísticos e offline que não precisem de rede, credenciais, dados
protegidos, processos nativos com asserções de árvore, ou controles que o
sandbox atual não consegue demonstrar. Todo resultado desse contexto deve ser
rotulado `SANDBOX EVIDENCE`; não pode ser promovido a native regression,
autonomy ou isolamento `PASS`.

Continuam `BLOCKED` até executor seguro provisionado: regressões funcionais
Harness/child-process, perfis Harness completos, cancelamento/timeout sob
supervisão nativa, dois jobs, terminação da árvore e provas de autonomia. Um
MXC `PASS` futuro demonstraria somente inicialização do sandbox e execução de
comando; por si só não comprova segurança completa ou autonomia. Mocks não
provam isolamento, runtime PowerShell ou término da árvore de processos.

## 7. Matriz de validação contratada

Testes devem cobrir, conforme aplicabilidade e gates do executor:

- envelopes de filho para sucesso, interrupção planejada e
  `PROCESS_FAILED` com resultado nulo;
- relatório ausente, inválido, corrompido, identidade divergente, PID/exit
  incompatíveis, fases/alvo/modo inválidos e outros dados contraditórios;
- falha sempre impedindo phase 2 e falha primária sobrevivendo a erros de
  fechamento ou escrita de relatório;
- fechamento do gateway em falhas de planner/plan/queue/run e no sucesso;
- sanitização/classificação por allowlist e preservação de
  `NOT_APPLICABLE` versus trusted;
- paths acima de 240 para final e `.part`, limite incluindo suffix, rejeição
  anterior a `queue` e path curto válido;
- probe trusted dentro/fora da raiz allowed efetiva e handshake do bootstrap
  do filho;
- alocação exclusiva, colisão, ID completo, preservação de histórico e
  recusa do sandbox;
- reconciliação por IDs exatos até JUnit/receipt/exit/snapshot, escrita única
  e publicação atômica;
- comportamento específico de PowerShell 5.1 em contexto que o suporte;
- timeout/cancelamento/término de árvore e dois jobs somente no executor
  seguro.

Três E2Es sintéticos, o perfil Harness completo e regressão S5/S6 delimitada
dependem dos respectivos gates de runtime e isolamento. Os resultados históricos
de 176 coletados e da coleta de 306 não são contagens esperadas fixas após
mudanças.

## 8. Gates e critérios de resultado

Os resultados são independentes: materialização contratual; implementação;
autoria de testes; validação focada; integração; autonomia; regressão nativa;
reconciliação de `PROJECT_STATE`; e aceite do usuário. Um gate concluído não
implica conclusão dos demais. A sprint inteira não é declarada concluída por
este contrato.

- `PASS`: critérios do gate satisfeitos com evidências completas, snapshot e
  processos reconciliados.
- `FAIL`: violação contratual observada.
- `BLOCKED`: precondição insegura ou indisponível impede execução válida.
- `INCOMPLETE`: evidência ou execução insuficiente para decidir.

`PROJECT_STATE_RECONCILIATION` é obrigatório antes de declarar conclusão
formal. No máximo quatro ciclos corretivos por finding. Não repetir a mesma
assinatura sem nova evidência, entrada ou mudança de ambiente. Interromper
diante de vazamento, drift de snapshot, escape de path, terminação não
confirmada, contradição, escopo protegido ou limite de ciclos.

Não é prescrita microsequência de aprovações ou ciclos; os owners e os critérios
de aceite formam uma unidade de entrega e devem respeitar dependências reais
entre contrato, código, testes e gates do executor.

## 9. Exclusões e proteções

Não alterar `src/telegram_courses` (incluindo downloader/gateway), schema ou
migrations, S6 V1 canônico/integridade operacional, credenciais, sessão,
`.env` operacional, SQLite de produção, referência original, `.part`
históricos, proof roots/receipts existentes, configuração global do usuário,
policies ou o sandbox do host. Não executar Telegram/RPC, download ou prova
real. Não ativar V2 globalmente, aceitar S6 formalmente, avançar roadmap/sprint,
fazer stage, commit ou push. Preservar WIP seletivamente; não usar reset, clean,
stash ou restore amplo.

## 10. Evidências de entrada e lacunas

- [Auditoria profunda do principal architect](../audit/S6_V2_PRINCIPAL_ARCHITECT_DEEP_AUDIT_2026-10-19.md): findings e limites de causalidade.
- [Relatório de estratégia e continuidade S6 V2](../reports/S6_V2_STABILIZATION_STRATEGY_DOCUMENTATION_AND_CONTINUITY_2026-10-19.md): baseline, escopo anterior e findings.
- [Gate de execução nativa de 2026-10-20](../reports/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20.md): snapshot P0 `FCA1CB93D83C07E80B2150777905077D13F0B31631D6252D87ADC07B3663C547`, 306 itens coletados sem execução funcional, limitações de Option A/B e recibos históricos distintos `163/163` e `176/173/3`.
- [Contrato de correção do runner Harness](S6_V2_NATIVE_HARNESS_REGRESSION_FIX_CONTRACT_2026-10-19.md) e [contrato do runner offline](S6_V2_OFFLINE_REGRESSION_RUNNER_CONTRACT_2026-10-19.md): limites de alocação, admissão e evidência preservados.
- Diagnóstico do executor repassado pelo root: uma tentativa do probe oficial MXC neste host, exit 1, mensagem exata registrada na seção 6. O pacote recebido para materialização não inclui transcript nem digest independente do probe; esse detalhe permanece lacuna documental.

```text
HISTORICAL_PATH_TOO_LONG_CAUSE = PROBABLE / HIGH / NOT RETROSPECTIVELY CONFIRMED
CURRENT_EXECUTOR_MXC_PROBE = FAILED / EXIT 1 / ONE ATTEMPT / DO NOT REPEAT WITHOUT MATERIAL CHANGE
SAFE_LOCAL_TESTS = DETERMINISTIC SYNTHETIC UNIT ONLY / SANDBOX EVIDENCE
FUNCTIONAL_HARNESS_AND_NATIVE_AUTONOMY = BLOCKED PENDING VERIFIED SECURE EXECUTOR
CONTRACT_MATERIALIZATION = COMPLETE
IMPLEMENTATION = AUTHORIZED / NOT CLAIMED COMPLETE
TEST_AUTHORING = AUTHORIZED / NOT CLAIMED COMPLETE
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_COMPLETION = NOT ESTABLISHED
```
