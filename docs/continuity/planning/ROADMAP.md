# Roadmap — projeto_telegram_courses

**ROADMAP = DEFINED**
**Delivery unit = SPRINT**
**Execution model = INCREMENTAL_VERTICAL_SLICES**
**Maximum active formal activities = 1**

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

Estado de execução, seleção, prontidão e autorização: [PROJECT_STATE.md](../PROJECT_STATE.md). Este roadmap não inicia nenhuma unidade.
