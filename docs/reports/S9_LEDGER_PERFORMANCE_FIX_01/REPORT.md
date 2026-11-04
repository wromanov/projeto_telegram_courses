# S9 Ledger Performance Fix 01 — relatório final

```text
ACTIVITY_ID = TELEGRAM_S9_LEDGER_PERFORMANCE_FIX_01
RESULT = COMPLETED_OFFLINE_SYNTHETIC
BRANCH = work/s0-bootstrap
HEAD = d36e96055a26556221bc487717f18ed322c76f02
CONTRACT_S9 = APPROVED_FROZEN / UNCHANGED
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
CANONICAL_CHAT_REPORT_DELIVERY = SEND_TOOL_ACCEPTED / READBACK_UNCONFIRMED / após autorização expressa do usuário
TELEGRAM_RPC = 0 / REAL_DOWNLOADS = 0 / LIVE_OPERATIONAL_WRITES = 0
S10 = NOT_AUTHORIZED
```

## Resumo

A correção P0 remove o replay integral do ledger do caminho de cada bloco de
download. O ledger mantém estado incremental dentro de uma época de escrita e
faz replay integral em checkpoints delimitados, sempre em conexão SQLite nova.
O handoff do escritor entre supervisor pai e processo filho é exclusivo, e
nenhum `PASS` ou recibo final é liberado antes da reconciliação completa.

O benchmark sintético de ledger para 1 GiB terminou em **373,02 s**, incluindo
setup e replay final. O fluxo CLI sintético de 1 GiB e os demais gates G0–G9
passaram; o cenário sem mídia M também passou. A regressão dos 11 módulos S9
terminou com **283 aprovados, zero falhas e zero skips em 645,63 s**.

O resultado é apenas offline sintético. Ele não demonstra uma operação
contratual real no Telegram nem autoriza o próximo escopo operacional.

## Causa e correção

Antes da correção, cada bloco de 256 KiB executava reserva e liquidação, e cada
mutação revalidava integralmente o histórico três vezes. Isso produzia seis
replays por bloco e trabalho agregado O(N²); no ensaio anterior de 1 GiB, a
fila M parou em 1809,87 s, com 567,75 MiB liquidados e 0,25 MiB reservados.

A implementação mantém projeções incrementais e as atualiza somente depois de
COMMIT durável. `PRAGMA data_version` é usado como sinal de alteração por outra
conexão; se mudar, o estado incremental é descartado e um replay integral em
conexão nova é obrigatório. O writer lock cobre o uso da conexão e do estado.
Antes de iniciar o filho, o pai libera sua época; o filho só escreve após
admissão e replay; o pai só readquire ownership após contenção e saída
confirmadas. Os checkpoints integrais também preservam os controles de
identidade, caminho, quarentena, integridade, foreign keys e cadeia de auditoria.

`journal_mode=WAL`, `synchronous=FULL`, `BEGIN IMMEDIATE`, contabilidade exata
e a regra de que o ACK depende do commit durável foram preservados. O contrato
S9 v1 permaneceu congelado, sem migração de schema ou alteração dos gates.

## Benchmark ledger-only

Todos os ensaios abaixo são sintéticos e usam o ledger. Eles não são, por si
sós, o gate CLI end-to-end.

| Caso | Hot path | Total com setup/replay final | Throughput | Contabilidade |
|---|---:|---:|---:|---|
| 64 MiB F | 22,82 s | 23,77 s | 2,80 MiB/s | Exata; 0 reservado/incerto |
| 256 MiB F | 92,26 s | 93,27 s | 2,77 MiB/s | Exata; 0 reservado/incerto |
| 1 GiB M | 371,42 s | 373,02 s | 2,76 MiB/s | Exata; 0 reservado/incerto |

Nos três casos, o WAL permaneceu ativo, `synchronous=FULL`,
`integrity_check=ok`, foreign-key check sem linhas e nenhuma quarentena. Para
1 GiB houve 4096 blocos, 8198 eventos e três validações integrais durante o
hot path. O commit medido inclui o comportamento de `synchronous=FULL`; o
harness não expõe duração física de `fsync` separada. A métrica de escrita do
processo cobre todo o processo Python, não somente SQLite. Detalhes completos:
[benchmark-results.json](evidence/benchmark-results.json).

## E2E CLI sintético

Os testes `test_synthetic_g0_through_g9_cli_path_and_recovery` e
`test_synthetic_no_m_scenario_stays_partial_and_g7_g8_not_tested` passaram:
**2 aprovados em 374,08 s**. No cenário com M, os dois passes registraram
1.073.741.824 bytes no primeiro passe e zero no segundo. G6, G7, G8 e G9
terminaram como `OFFLINE_SYNTHETIC_PASS`; o ledger terminou em
`G9 / COMPLETED / OFFLINE_SYNTHETIC_PASS`. O cenário sem M permaneceu parcial,
com G7/G8 não testados conforme esperado.

O supervisor registrou progresso da fila M em 60, 120, 180, 240 e 300 s; a
fila terminou antes do próximo marco de 360 s. O evento do ledger confirma o
primeiro passe M com 1 GiB observado e estado G5 no acumulado de 310,978 s
desde o início do run. O artefato preserva o acumulado, não uma duração isolada
da fila. Mesmo usando esse acumulado conservador, o gate de 1800 s foi atendido.
Resumo durável dos recibos:
[e2e-synthetic-summary.json](evidence/e2e-synthetic-summary.json).

## Defeitos e ajustes descobertos durante a validação

- A primeira regressão integral usou um `basetemp` longo dentro da raiz de
  visualizações. O nome final de download ultrapassou a política de caminho,
  causando `G6_S5_PATH_POLICY_INVALID`; a falha do cenário sem M foi
  consequência da interrupção anterior antes de criar o recibo G6. A mesma
  execução mostrou que G7/G8 comparavam digests de snapshots diferentes
  (DB+WAL contra somente DB). O digest foi unificado em DB+WAL, excluindo SHM.
- A revisão de segurança encontrou ausência de rejeição do atributo Windows
  `FILE_ATTRIBUTE_REPARSE_POINT` no hash e antes da abertura SQLite de G8. O
  hash agora inspeciona DB, WAL, SHM e journal antes de abrir DB/WAL; a leitura
  operacional e a transição G8 validam a família SQLite e a raiz privada antes
  de conectar.
- Os testes de reparse simulam DB e cada sidecar como arquivo regular com
  atributo `0x400` e confirmam zero aberturas. O digest continua incluindo DB e
  WAL, sem incluir SHM transitório.
- A tentativa de E2E com temporários dentro do checkout foi rejeitada pelo
  guard `LOCALAPPDATA_UNSAFE`; a repetição usou raiz externa curta. Uma rodada
  intermediária foi bloqueada pelo guard de disco com 1,33 GB disponíveis. Os
  artefatos da execução de teste anterior consumiam cerca de 2,17 GB; removi
  somente a pasta temporária criada por aquela execução e repeti com 3,43 GB
  disponíveis. A execução final passou.

## Validação final

| Verificação | Resultado |
|---|---|
| Regressão dos 11 módulos S9 | **283 passed, 0 failed, 0 skipped / 645,63 s** |
| JUnit da regressão | [s9-full-regression-junit.xml](evidence/s9-full-regression-junit.xml) |
| E2E sintético G0–G9 e cenário sem M | **2 passed / 374,08 s** |
| M 1 GiB | **PASS / 1.073.741.824 bytes / limite 1800 s atendido** |
| `ruff check` nos arquivos S9 afetados | **PASS** |
| `python -m compileall -q src tests` | **PASS** |
| Revisão independente de segurança | **PASS_WITH_LIMITS** |

`ruff format --check` reportou que quatro arquivos inteiros seriam
reformatados pelo formatter instalado. Não apliquei uma reformatação ampla:
`ruff check` passou, e a suíte/compilação final passaram. A revisão de segurança
confirmou que não há caminho conhecido de reparse point antes da abertura. Como
limite, a sequência `lstat` seguida de abertura por caminho ainda admite uma
janela de troca concorrente pelo mesmo usuário; o guard existente não cobre
esse adversário.

## Escopo e continuidade

Nenhuma chamada RPC ao Telegram, download real ou escrita operacional em banco
foi realizada. G0–G9 estão comprovados somente por fixtures sintéticas; a
aprovação de código P0 não equivale a uma execução real, a um aceite contratual
real ou à autorização de S10.

Uma primeira tentativa de envio deste relatório ao chat canônico foi recusada
pela revisão automática porque o payload continha detalhes internos do projeto
e caminhos locais para um destino externo. Após autorização expressa do usuário,
a ferramenta aceitou o envio; contudo, o readback e a listagem ainda mostram o
snapshot anterior do chat. Não reenviar até confirmar a visibilidade da mensagem.

O worktree existente foi preservado, sem staging, commit ou push. A próxima
atividade que envolva operação real, S10 ou publicação Git exige autoridade
separada. A continuidade corrente e o safe resume point estão registrados em
[PROJECT_STATE](../../continuity/PROJECT_STATE.md),
[CONTINUITY_RECORD](../../continuity/CONTINUITY_RECORD.md) e
[LAST_HANDOFF](../../continuity/handoff/LAST_HANDOFF.md).
