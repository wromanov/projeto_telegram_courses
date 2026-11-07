# Roadmap — projeto_telegram_courses

## Direcao vigente e precedencia — CLI V1 Rich antes de GUI (2026-11-03)

**DECISION = CLI_V1_PYTHON_RICH_FIRST / GUI_AFTER_OPERATIONAL_VALIDATION**
**PRIORITY = P0 / COMPLETE_COURSE_DOWNLOAD_FLOW**
**MIDNIGHT_GLASS_TUI = HISTORICAL_VISUAL_REFERENCE / NO_CURRENT_IMPLEMENTATION_COMMITMENT**
**SUPERSEDES = earlier plan to implement Midnight Glass TUI before functional readiness**

1. **CLI V1, simples:** reutilizar a CLI Python existente e a dependencia Rich 15. Exibir catalogo e arquivos do curso; oferecer (A) selecao individual/multipla e (B) "Baixar tudo" no curso atual, em ordem deterministica. Confirmar plano e limites e executar fila inicialmente sequencial (workers=1), sem interface fullscreen ou framework adicional. Mostrar arquivo atual, bytes e tamanho total, progresso, velocidade real em MB/s, ETA quando confiavel, sucesso/falha, retomada e deduplicacao.
2. **Validar o produto:** auditar primeiro o codigo que ja existe; fechar somente lacunas reais e provar o ciclo completo de um curso elegivel, com autorizacao operacional especifica para escopo e limites. Nao inferir download completo a partir de cinco midias da S5 nem do unico item 585.
3. **GUI apos a CLI comprovada:** somente depois de aceitar o fluxo de download ponta a ponta, definir requisitos e tecnologia de uma interface grafica; reutilizar o backend validado. A aprovacao anterior de Midnight Glass e referencia estetica historica, nao aprovacao automatica de projeto GUI ou obrigacao de TUI.
4. **Distribuicao:** reavaliar S10/empacotamento apos comprovacao do fluxo e escopo de release. Contratos S6-S9 e seus findings historicos permanecem inalterados.

**CURRENT_NEXT_ACTION:** propor `TELEGRAM-3-CLI-V1-OPERATOR-ACCEPTANCE-01` para conferência manual da CLI Python + Rich, inicialmente sem payload e ainda sem autorização de execução. Campanha G4 bounded encerrada em 2026-11-06 com aceite parcial, controles reais essenciais validados, dois roteiros compostos não executados integralmente e `COURSE_DOWNLOAD_E2E_GATE=NOT_PROVEN`. Novos downloads/RPC, prova E2E, GUI e S10 exigem decisão própria. Ver [PROJECT_STATE](../PROJECT_STATE.md) e [checkpoint de 07/11](../checkpoints/TELEGRAM_3_DOC_RECONCILIATION_20261107.md).

---


**ROADMAP = DEFINED**
**Delivery unit = SPRINT**
**Execution model = INCREMENTAL_VERTICAL_SLICES**
**Maximum active formal activities = 1**

Referência histórica das unidades S6–S9: S6, S7 e S8 formalmente CLOSED_WITH_EXCEPTIONS. S6 Gates A=PARTIAL e B=BLOCKED_BY_REMOTE_EVIDENCE continuam sem comprovação integral V1. A S7 foi aceita pela OPTION_B, com critérios A2/A4/A6 ainda parciais e quatro exceções registradas; não há conformidade integral nem homologação de exclusão remota positiva. S8 — Operational Hardening — foi formalmente aceita pelo usuário em 2026-10-28, CLOSED_WITH_EXCEPTIONS, após regressão offline de 366 testes e 11 subtestes aprovados. Permanecem limites documentados da medição de memória NFR-02 e ausência de homologação real Telegram; S9 teve execução real limitada e permanece PARTIAL; o estado vigente e as autorizações constam em PROJECT_STATE. S10 permanece não executado. Ver PROJECT_STATE (authority canônica mantida localmente e omitida da baseline pública), [relatório de fechamento S7](../../reports/S7_FORMAL_CLOSURE_2026-10-26/REPORT.md), [parecer final S7](../../reports/S7_FINAL_ACCEPTANCE_DECISION_2026-10-26/REPORT.md) e aprovações (authority canônica mantida localmente e omitida da baseline pública).

| Phase | Name | Sprint(s) | Outcome |
|---|---|---|---|
| PHASE 0 | PROJECT FOUNDATION | S0 | Repository / Project Bootstrap |
| PHASE 1 | TELEGRAM ACCESS | S1 | Authentication + Channel Discovery |
| PHASE 2 | CATALOG | S2–S3 | Message Scanner + SQLite Persistence; RASMOO Parser + Catalog CLI |
| PHASE 3 | FIRST WORKING DOWNLOAD FLOW | S4 | Single Media Download + Local Organization + Deduplication |
| PHASE 4 | COURSE DOWNLOAD | S5 | Course/Module Selection + Download Planner + Queue |
| PHASE 5 | RESILIENCE | S6–S7 | Partial Download / Resume / Recovery; Incremental Synchronization |
| PHASE 6 | HARDENING | S8 | Errors / Retry / Logging / Disk Safety / Operational Hardening |
| PHASE 7 | REAL VALIDATION | S9 | RASMOO Real-Channel Acceptance |
| PHASE 8 | DISTRIBUTION | S10 | Windows Packaging / Operational Documentation |

## First vertical slice milestone

`FIRST_VERTICAL_SLICE_GATE` é avaliado em S4. Seus nove critérios têm authority única em [SPRINTS.md — S4](SPRINTS.md#s4--single-media-download--local-organization--deduplication).

The user-approved definition of the first working value is end-to-end: authenticate, discover the RASMOO channel, build its course/module/lesson catalog, select one lesson, download and organize its media, persist state, rerun, and avoid downloading the same item again. Isolated components do not pass this milestone.

## Dependências, aceite e riscos

As fases seguem a ordem acima; cada fase depende do aceite das unidades predecessoras e da baseline integrada acumulada. O gate S4 é o primeiro valor completo, seguido de seleção em lote S5, recuperação S6, sync S7, hardening S8 e aceitação real S9 antes da distribuição S10. Detalhes de escopo, testes, gates e entrada/saída estão em [SPRINTS.md](SPRINTS.md).

Riscos a validar nas unidades pertinentes: compatibilidade CPython/Telethon/cryptg, memória limitada em arquivo grande, retomada em bytes condicional, proteção de sessão Windows, FloodWait, variações de estrutura e semântica de edições/remoções no sync. Datas/durações/capacidade não foram aprovadas. RASMOO é a primeira validação real, sem limitar o produto a um canal.

DOCUMENT_ROLE = ROADMAP
ROADMAP_VERSION = 1.1 / 2026-10-05
ROADMAP_STATUS = DEFINED_USER_BASELINE_RECONCILED

Estado de execução, seleção, prontidão e autorização: PROJECT_STATE.md (authority canônica mantida localmente e omitida da baseline pública). Este roadmap não inicia nenhuma unidade.

## Direcao de interface aprovada — 2026-11-03

Para a experiencia final do operador, esta aprovada a CLI/TUI navegavel no estilo **Midnight Glass (Direcao 1)**; a interface esta **NOT_IMPLEMENTED**. O proximo passo de produto e a apresentacao de mockups completos das telas antes do inicio de implementacao, sem alterar retroativamente o aceite ou a sequencia historica das sprints. Ver [especificacao visual](../../design/TELEGRAM_COURSES_TUI_MIDNIGHT_GLASS_V1.md).

## Prioridade corrigida — fluxo de download utilizável (2026-11-03)

DECISION = USER_EXPLICIT / COURSE_CLI_DOWNLOAD_FIRST
DESIGN = MIDNIGHT_GLASS_V1_APPROVED_BUT_DEFERRED
PRODUCT_READY = NOT_DEMONSTRATED_FOR_COMPLETE_COURSE
NEXT_GATE = COURSE_DOWNLOAD_E2E_GATE
GATE_SCOPE = VERIFICAR_FLUXO_EXISTENTE_ANTES_DE_IMPLEMENTAR_TUI

O resultado pretendido pelo operador e simples: na CLI, navegar pelo catalogo, selecionar um curso e **marcar arquivos individualmente** ou escolher **Baixar tudo** (todos os arquivos catalogados daquele curso, na ordem correta). Em ambos os modos, revisar uma vez o plano, confirmar e acompanhar a fila, sem criar fluxos tecnicos paralelos. A selecao de arquivos nao se limita necessariamente a um unico modulo ou a uma unica aula.

Sequencia obrigatoria:
1. **Verificar o fluxo existente** em modo offline/read-only: catalogo do curso, navegacao/selecao individual de multiplos arquivos, selecao total do curso, ordenacao deterministica, planner, fila, estados, retomada, validacao e persistencia. Marcar cada capacidade como PROVEN, IMPLEMENTED_NOT_PROVEN ou MISSING. Reaproveitar a infraestrutura S1-S9, sem novo backend por preferencia estetica.
2. **Corrigir apenas as lacunas funcionais** que impedem selecionar arquivos arbitrarios, selecionar todos e baixar sequencialmente. Documentar ordem canonica curso > modulo > aula > arquivo (ordem observada no catalogo, desempate por identidade), total de midias, total em bytes conhecidos e itens com tamanho desconhecido. Nao alegar catalogo completo quando o scan for parcial.
3. **Comprovar o ciclo ponta a ponta**, em curso de escopo explicitamente aprovado: catalogar, escolher modo de selecao, gerar plano, revisar limites, executar fila em ordem, registrar sucesso/falha, validar organizacao, reiniciar e verificar deduplicacao/retomada. Integracao real exige autorizacao separada de canal, curso e limites; nao e concedida por este plano.
4. **Somente apos gate operacional**, desenhar telas definitivas Midnight Glass e implementar TUI sem alterar semantica do downloader.
5. **Depois** avaliar S10/distribuicao. S9 continua PARTIAL, S10 NOT_STARTED; nao reabrir nem alterar retrospectivamente contratos e aceites S5-S9.

ACEITE = operador consegue escolher arquivos especificos OU todos os arquivos de um curso em ordem, confirma um plano claro e os arquivos terminam corretamente organizados/validados ou com falhas explicitas; reinicio mantem estado e evita redownload de arquivos validos. Testes unitarios sinteticos isolados e piloto de uma unica midia nao bastam como prova desse aceite.

Ver [criterios verificaveis](SPRINTS.md#gate-de-prontidao-do-produto--course_download_e2e_gate--2026-11-03) e [requisitos](../../product/REQUIREMENTS.md#refinamento-de-uso-da-cli--2026-11-03).
