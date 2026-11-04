# TELEGRAM-3-HASH-RANGE-VALIDATION-CLOSURE-01

EXECUTION_MODE = OFFLINE_VALIDATION_ONLY  
TECHNICAL_GO_NO_GO = GO_WITH_FINDINGS para a correção offline delimitada; adjudicação humana pendente  
PROCESS_COMPLIANCE_STATUS = PASS nesta atividade  
REAL_FOURTH_ATTEMPT_AUTHORIZED = NO

## Matriz de validação

| Verificação no código final | Resultado |
|---|---|
| Suíte unitária e integração completa | 826 PASS / 3 FAIL / 11 subtests PASS, 383,28 s |
| Multi-range, EOF, S5/S6, S9, V2, integridade e orçamento — bateria focada | 354 PASS, 199,31 s |
| Ruff nos quatro arquivos alterados | PASS |
| Ruff global `src tests tools` | FAIL: dois I001 e um F841 em arquivos manual_proofs fora do escopo |
| Compileall `src tests tools` | PASS |
| Revisão independente | ACCEPT_WITH_FINDINGS; sem defeito material aberto no caminho de hashes |

## Causas das três falhas

O teste `test_supervised_scan_reserves_and_reconciles_s9_observation_budget` ativa o contexto de filho supervisionado sem admissão válida no ledger. A instrumentação sintética capturou `LEDGER_CHILD_IDENTITY_INVALID`, convertido pela CLI em `CONFIGURATION`. Referências: `tests/integration/test_cli_scan.py:94`, `src/telegram_courses/s9_operational_ledger.py:1024`, `src/telegram_courses/cli.py:1123`.

Os dois testes `test_synthetic_g0_through_g9_cli_path_and_recovery` e `test_synthetic_no_m_scenario_stays_partial_and_g7_g8_not_tested` usam gateway com título `Synthetic target` e username `synthetic_target`, enquanto o manifesto exige `SYNTHETIC_CHANNEL`. A descoberta retorna `TARGET_CHANNEL_ALIAS_MISMATCH`, que o supervisor apresenta como `G1_SYNTHETIC_TEST_EVIDENCE_INVALID`. Contraprova em memória com alias coerente `SYNTHETIC_TARGET` produziu `OFFLINE_SYNTHETIC_PASS`. Referências: `tests/integration/test_s9_e2e.py:157`, `tests/integration/test_s9_e2e.py:543`, `src/telegram_courses/s9_real_gate_producers.py:435`, `src/telegram_courses/s9_supervisor_cli.py:2437`.

As falhas ocorrem antes do downloader e continuam pendentes. Nenhuma fixture ou guard foi alterado nesta atividade.

## Evidências e findings

A revisão independente confirmou o opt-in restrito ao piloto 585 (`src/telegram_courses/cli.py:255`, `:931`), validação estrutural integral do lote (`src/telegram_courses/downloads.py:1486`), prova com ranges verificados (`:1594`) e `REMOTE_HASH_FULL` antes da finalização (`:652`). Os testes focados incluem os caminhos reais de prefixo e recuperação sintética.

- Médio: suíte global permanece com três falhas de fixtures; Ruff global permanece com três achados fora do escopo.
- Baixo: checkpoints anteriores continuam rotulados “vigente” em `PROJECT_STATE.md:24`, `CONTINUITY_RECORD.md:11` e `handoff/LAST_HANDOFF.md:5`.
- Informativo: a resposta histórica exata do Telegram não foi preservada; a causa real da terceira falha continua não comprovada.

Nenhuma operação Git, RPC Telegram, download real ou acesso a dados operacionais ocorreu nesta atividade. As cinco consultas Git read-only da atividade anterior continuam registradas como não conformidade histórica; não foram normalizadas. Nenhuma quarta tentativa foi autorizada. O parecer técnico limitado não concede aceite global S9 nem autoriza execução real.
