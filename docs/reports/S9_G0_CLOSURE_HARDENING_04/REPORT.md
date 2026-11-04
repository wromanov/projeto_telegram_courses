# S9-G0 Closure Hardening 04 — Relatório

**Data:** 2026-10-29
**Atividade:** TELEGRAM_S9_G0_CLOSURE_HARDENING_04
**Resultado:** S9_G0_PARTIAL
**Recomendação:** não recomendar aceite offline integral; G0 real, S9 real e S10 continuam sem autorização.

## Resumo executivo

Foram implementadas mitigações offline para RISK-01 (origem confiável do módulo CLI e execução isolada) e RISK-02 (diretório privado no Windows, validação de DACL/reparse e proteção contra rename enquanto aberto). A revisão estática não identificou vulnerabilidade reportável nos arquivos S9 examinados. Isso não conclui os Gates A ou C: os testes correspondentes não foram executados e não houve revisão independente.

O preflight Windows foi tentado nesta sessão `pwsh` com Python 3.14.7, mas não passou: P01_SOCKETPAIR e P02_ASYNCIO_RUN expiraram em 10 segundos. A limpeza confirmou o encerramento de cada processo raiz, porém `Get-CimInstance Win32_Process` falhou com `Microsoft.Management.Infrastructure.CimException`, impedindo provar o encerramento da árvore. A causa raiz do host permanece não provada. Como os probes não passaram, os testes focados S9/S8 e a regressão offline integral continuam sem execução nesta atividade. O relatório do scan de segurança nativo concluiu com 0 findings reportáveis no escopo analisado, mas cobertura parcial e três itens adiados; o aviso do scan registra mudança da working tree durante a análise. Os arquivos-fonte e testes S9 escaneados não foram alterados depois da captura; as alterações posteriores foram somente documentação e script de preflight.

## Escopo e autoridade

- Contrato base: docs/contracts/S9_RASMOO_REAL_CHANNEL_ACCEPTANCE_CONTRACT_2026-10-28.md — v1.0 APPROVED / FROZEN; não editado.
- Escopo autorizado: correções e verificações offline.
- Roteamento: MULTIAGENT, autorizado pelo card, máximo 2 agentes; funções usadas: backend_engineer (implementação) e validator (preflight do scan).
- Sem chamadas Telegram/RPC, sem escrita no banco operacional, sem stage, commit ou push.
- Nenhum arquivo de credenciais ou sessão foi aberto. Nenhum segredo embutido foi identificado na revisão delimitada.

## Resultado dos gates e riscos

### Gate A — PARTIAL

RISK-01: mitigação presente, teste não executado. O subprocesso parte com Python isolado (-I), valida a origem efetiva do módulo telegram_courses.cli e exige somente o argumento smoke; ambiente filho é allowlist. Evidência: src/telegram_courses/s9_supervisor_cli.py:45-67, 140, 241.

RISK-02: mitigação presente, teste não executado. A criação da pasta privada usa DACL explícita no Windows; a validação verifica proprietário/DACL, unidade local, reparse points e arquivos laterais do ledger. O handle omite FILE_SHARE_DELETE para reduzir a janela de rename. Evidência: src/telegram_courses/s9_operational_ledger.py:119, 306-359.

O código de testes positivos/negativos foi escrito nos quatro módulos unitários S9, mas não foi executado. Por isso o requisito MITIGATED_AND_TESTED não está satisfeito.

### Gate B — BLOCKED

A causa raiz do runtime Windows não foi comprovada além do limite do executor atual. O executor disponível recusou a consulta local de processos WMI/CIM durante a triagem e executa com token de baixa integridade; isso evidencia limitação do executor, sem determinar a política do host responsável.

- SOCKETPAIR_PREFLIGHT: TIMEOUT / 10.071 s / Python 3.14.7 / root encerrado após timeout; árvore não observável por CimException.
- ASYNCIO_PREFLIGHT: TIMEOUT / 10.072 s / Python 3.14.7 / root encerrado após timeout; árvore não observável por CimException.
- Testes focados S9: NOT_RUN.
- Testes S8 afetados: NOT_RUN.
- Regressão offline integral: BLOCKED / NOT_RUN.
- T24: NOT_RUN nesta atividade; resultados anteriores são somente históricos.

Foi preparado um preflight manual que verifica também descendentes do processo e falha fechado quando não consegue confirmar a árvore: docs/reports/S9_G0_CLOSURE_HARDENING_04/RUN_WINDOWS_PREFLIGHT.ps1. Comando exato, a partir da raiz do repositório:
pwsh -NoProfile -File .\docs\reports\S9_G0_CLOSURE_HARDENING_04\RUN_WINDOWS_PREFLIGHT.ps1

### Gate C — BLOCKED / revisão parcial

A revisão estática delimitada pelo root e o scan nativo não são revisão independente. O scan finalizou com 0 findings reportáveis no escopo, cobertura parcial, seis superfícies examinadas e três tarefas adiadas: runtime/regressão, ratificação do RISK-03 e revisão independente. Relatório nativo:
C:\Users\walac\.codex\state\plugins\codex-security\scans\projeto_telegram_courses\d36e96055a26556221bc487717f18ed322c76f02_20261030T013215Z_4xch4cmr\report.md
Scan ID: acb208c2-e16e-436a-a18a-8f78e3b44180.

### RISK-03 — decisão proposta, sem ratificação

O ledger encadeia eventos por SHA-256 sem chave autenticadora (src/telegram_courses/s9_operational_ledger.py:618). Isso permite detectar inconsistências acidentais, mas não autentica alterações feitas por quem consegue escrever diretamente no banco e recomputar a cadeia; também não impede rollback integral coerente sem âncora externa.

Recomendação para ratificação humana: opção C, âncora monotônica append-only em domínio de confiança separado. Ela mitiga adulteração/rollback após ancoragem, mas não prova a veracidade de eventos antes da âncora nem omissões anteriores. Exige disponibilidade, retenção e recuperação fora do ledger e pode alterar a premissa offline se depender de serviço remoto. Nenhuma opção foi implementada ou aceita nesta atividade.

## Diagnóstico e QA

- WINDOWS_RUNTIME_ROOT_CAUSE = NOT_PROVEN; process visibility failed in Codex pwsh and Windows PowerShell sessions.
- P01 socketpair e P02 asyncio: TIMEOUT / 10s; root processes ended after cleanup, process-tree termination unproven.
- S9_FOCUSED_TESTS = NOT_RUN.
- S8_AFFECTED_TESTS = NOT_RUN.
- FULL_OFFLINE_REGRESSION = BLOCKED / NOT_RUN.
- WORK_VALIDATED = NO / FINAL_TEST_EVIDENCE_PENDING.
- SCOPED_SECURITY_REVIEW = PARTIAL; sem reviewer independente.
- CONFIRMED_FINDINGS = 0 findings reportáveis no scan delimitado; cobertura parcial, não equivale a ausência universal de vulnerabilidades.
- POTENTIAL_RISKS = RISK-03, decisões de confiança/rollback do ledger.
- RESIDUAL_RISKS = runtime e regressão não validados; DACL requer execução real Windows; cadeia SHA-256 sem autenticação/âncora externa.
- RUFF = PASS nos 8 arquivos S9 selecionados.
- COMPILEALL = PASS nos mesmos 8 arquivos.
- GIT_DIFF_CHECK = PASS, exit 0; somente avisos LF→CRLF em arquivos rastreados previamente modificados.
- UNTRACKED_QA = PASS para whitespace/final newline nos arquivos novos desta atividade e nos 8 arquivos S9 selecionados.
- O parser PowerShell aceitou o script. Execução em `pwsh` retornou exit 1; probes expiraram e a verificação de árvore não ficou provada.

## Arquivos e preservação

Implementação/testes S9: quatro módulos em src/telegram_courses (s9_supervisor_cli.py, s9_operational_ledger.py, s9_supervisor_handshake.py, s9_supervisor.py) e quatro módulos em tests/unit (test_s9_supervisor_cli.py, test_s9_operational_ledger.py, test_s9_supervisor_handshake.py, test_s9_supervisor.py). Artefatos: este relatório e RUN_WINDOWS_PREFLIGHT.ps1. Continuidade atualizada em PROJECT_STATE.md, CONTINUITY_RECORD.md e handoff/LAST_HANDOFF.md.

WIP_PRESERVED = YES; baseline da atividade: 7 arquivos rastreados modificados e 11.225 não rastreados; nenhum foi descartado. Nenhum arquivo foi staged.

## Fechamento e próxima ação

- ACCEPTANCE_RECOMMENDATION = não aceitar offline integral ainda.
- G0_REAL_EXECUTION = NOT_AUTHORIZED.
- NEXT_EXACT_ACTION = usuário executar o comando pwsh em sessão Windows externa ao runtime atual, com `Get-CimInstance Win32_Process` funcional; usar saída JSON e exit code como evidência. Só após PASS nos dois probes e na árvore, executar a sequência de testes offline prevista no contrato e obter revisão independente; depois submeter a decisão de RISK-03 ao usuário.
- DELIVERY_STATUS_PREVIOUS_VERSION = SENT / DESTINATION=Projeto Telegram 3.0 / THREAD_ID=6add6aa9-12e0-83e8-b02f-870f0a0edaf9 / MESSAGE_SENT=YES / CHAT_RESPONSE=RECEIVED
- CURRENT_REPORT_VERSION = UPDATED_AFTER_WINDOWS_PREFLIGHT / DELIVERY_PENDING

A prontidão técnica não ratifica aceite, não autoriza G0 real nem inicia S10.

## Retorno do chat sobre a versão anterior

O chat confirmou recebimento, concordou com S9_G0_PARTIAL e não apontou
divergência material na classificação dos gates. Reforçou que RISK-01/02
continuam pendentes dos testes negativos; a execução em console Windows
nativo é o próximo experimento para o Gate B; e a opção C para RISK-03 é
condicional ao modelo de ameaça e requer um domínio de confiança separado,
verificação fail-closed e processo de recuperação. O próprio retorno registra
RISK-03 como PENDING_USER_RATIFICATION. Essa análise não é aceite formal nem
autorização de implementação ou G0 real.
