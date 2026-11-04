# TELEGRAM-3-585-HASH-RANGE-FIX-01 — relatório de implementação offline

```text
ACTIVITY_ID = TELEGRAM-3-585-HASH-RANGE-FIX-01
EXECUTION_MODE = OFFLINE_IMPLEMENTATION
ROOT_DECISION = NO_GO_STRICT_ACCEPTANCE / CODE_IMPLEMENTED_WITH_LIMITS
IMPLEMENTATION_OFFLINE = PARTIAL
OFFLINE_GO_NO_GO = NO_GO
INDEPENDENT_REVIEW = PASS_WITH_FINDINGS (code) / NO_GO (strict card acceptance)
REAL_FOURTH_ATTEMPT_AUTHORIZED = NO
```

## Arquivos

- `src/telegram_courses/downloads.py`
- `src/telegram_courses/cli.py`
- `tests/unit/test_pilot_eof_strict.py`
- `tests/integration/test_resume_585_budget_once.py`
- `docs/reports/TELEGRAM_3_HASH_RANGE_FIX_01/REPORT.md`
- `docs/continuity/PROJECT_STATE.md`
- `docs/continuity/CONTINUITY_RECORD.md`
- `docs/continuity/handoff/LAST_HANDOFF.md`

## Causa avaliada

O cliente reproduz offline a rejeição `REMOTE_HASH_RANGE_INVALID` quando uma
resposta em lote cobre o prefixo e termina numa faixa nominal de 128 KiB que
passa do EOF real. A causa no caminho do cliente está confirmada por teste
sintético. A resposta exata recebida do Telegram na terceira tentativa não foi
preservada; portanto, não está comprovado que o servidor tenha enviado essa
geometria na falha histórica. Um servidor com resposta realmente inválida
continua sendo hipótese possível.

## Implementação

O caminho permanece estritamente opt-in: a CLI habilita a geometria especial
somente para `--pilot-resume-585-once`; o padrão e as filas estritas gerais
continuam sem o opt-in. Nesse caminho, todos os itens recebidos são validados
quanto a tipo, digest de 32 bytes, continuidade, offset alinhado e tamanho
nominal de 128 KiB. O EOF excedente só é aceito na última faixa alinhada, que
contém o EOF real, com tamanho nominal e excesso menor que 128 KiB.

A validação estrutural cobre o lote inteiro. A prova de prefixo recebe apenas
faixas comparadas com bytes locais, incluindo eventual complemento realmente
obtido para uma faixa que cruza o limite do prefixo. Prefixos que atravessam a
faixa terminal excedente falham fechados. A verificação `REMOTE_HASH_FULL` do
arquivo completo antes da finalização continua obrigatória; digest terminal
com padding zero, divergência na cauda, cobertura incompleta e inconsistência
estrutural são rejeitados.

Os contratos e schemas S9 e V2 não foram editados. A aplicação existente do
validador de prova S9 aceitou a observação sintética verificada e rejeitou
cobertura incompleta. A CLI mantém o novo opt-in falso fora do seletor
one-shot 585.

## Testes e verificações

**Suíte focada final:** 50 testes aprovados em 7,35 s, cobrindo caminho real de
`_verify_prefix`/`_remote_hashes`, lotes de 46/48 faixas e até 10 por página,
prova sem faixas posteriores não verificadas, prefixo desalinhado com
complemento sintético, geometria EOF, recuperação sintética dos 170.323 bytes,
SHA-256/prefixo preexistente, finalização, contabilidade, digest divergente da
cauda, persistência S9 e rejeições negativas.

**Suíte unitária e de integração completa:** 823 aprovados, 3 falhos e 11
subtestes aprovados. A execução ocorreu antes dos dois últimos ajustes locais
que passaram na suíte focada final; não houve nova execução completa depois
deles. As três falhas foram reproduzidas:

1. `test_supervised_scan_reserves_and_reconciles_s9_observation_budget` foi
   rejeitado como `CONFIGURATION` antes de instanciar o downloader.
2. `test_synthetic_g0_through_g9_cli_path_and_recovery` falhou em
   `G1_SYNTHETIC_TEST_EVIDENCE_INVALID` antes do fluxo de download/hash.
3. `test_synthetic_no_m_scenario_stays_partial_and_g7_g8_not_tested` falhou na
   mesma etapa de evidência sintética G1.

As falhas não apontam ao caminho de hash alterado, mas a suíte total não é
PASS e não foi repetida sobre o estado final.

**Ruff:** PASS nos quatro arquivos de código/teste alterados. A execução global
encontrou três problemas em arquivos fora do escopo: imports não ordenados em
`tests/manual_proofs/test_s6_v2_mxc_host_executor.py` e
`tools/manual_proofs/s6_v2_mxc_host_executor.py`, e variável não usada em
`tools/manual_proofs/s6_v2_offline_regression_runner.py`. Esses arquivos não
foram modificados.

**Compileall:** PASS em `src`, `tests` e `tools`.

## Revisão independente

`PASS_WITH_FINDINGS` para o código após revisão read-only. O revisor identificou
dois problemas de implementação durante a revisão; ambos foram corrigidos e
reavaliados. Não restou finding material de código aberto.

Findings de aceite:

- **Alto — processo:** cinco consultas Git somente de leitura foram executadas
  no bootstrap factual, antes da leitura integral do task card. Não houve
  alteração de branch, staging, commit, push ou outra mutação. Ainda assim,
  `GIT_OPERATIONS=0` literal não foi satisfeito.
- **Médio — validação:** três falhas reproduzidas na suíte completa e nenhuma
  execução completa após os ajustes finais impedem declarar regressão global
  PASS.
- **Informativo — evidência histórica:** a causa técnica reproduzida no cliente
  não prova qual resposta o servidor enviou na terceira tentativa.

## Estado operacional e próximo passo

```text
S9_IMPACT = CONTRACT_UNCHANGED / OPT_IN_FALSE_OUTSIDE_PILOT_585
OPERATIONAL_DATA_TOUCHED = NO
TELEGRAM_RPC_COUNT = 0
DOWNLOAD_ATTEMPTS = 0
GIT_OPERATIONS = 5_READ_ONLY_BOOTSTRAP_QUERIES / NO_MUTATION_OR_PUBLICATION
OFFLINE_GO_NO_GO = NO_GO (strict task-card criteria unmet)
REAL_FOURTH_ATTEMPT_AUTHORIZED = NO
NEXT_RECOMMENDED_ACTION = Human adjudication of the strict-gate exceptions; no remote retry implied
```

Não foram executadas RPCs, downloads, autenticação, leitura de credenciais,
alteração do banco operacional, manipulação de `.part`/MP4 ou uso de rede.
Nenhum teste remoto posterior está autorizado por este relatório.
