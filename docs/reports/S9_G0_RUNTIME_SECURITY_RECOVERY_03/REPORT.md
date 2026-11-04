# S9-G0 Runtime & Security Recovery 03

**Data:** 2026-10-29  
**Atividade:** `TELEGRAM_S9_G0_RUNTIME_SECURITY_RECOVERY_03`  
**Resultado:** `S9_G0_BLOCKED`  
**Recomendação:** não recomendar aceite offline integral nem iniciar G0 real.

## Resumo

O preflight local foi repetido em Python 3.15.0 e 3.14.7. Nos dois runtimes,
`socket.socketpair()` e a inicialização do loop asyncio do Windows travaram; a
conexão TCP de loopback falhou com `WinError 10013`. Isso confirma uma restrição
do executor atual, mas não identifica qual política do host a impõe. Como o
preflight funcional não passou, as suítes S9/S8 não foram executadas.

A revisão estática delimitada foi concluída. Ela confirmou controles úteis no
wrapper offline e na supervisão, mas deixou três riscos condicionais em aberto:
resolução de módulo a partir de uma pasta de saída sem ACL privada verificada,
checagem de caminho do ledger vulnerável a troca concorrente nessa pasta, e
cadeia de auditoria SHA-256 sem chave ou âncora externa. A exploração desses
riscos não foi reproduzida, não houve ciclo corretivo e nenhum código de
produção ou teste foi alterado.

O Gate A continua `PASS` apenas conforme evidência histórica; não foi refeito.
Gate B está `BLOCKED` pelo executor. Gate C está `BLOCKED` pelos riscos abertos
e pela impossibilidade de recuperar o contexto do scan nativo anterior.

## Autoridade, escopo e preservação

- O contrato congelado `docs/contracts/S9_RASMOO_REAL_CHANNEL_ACCEPTANCE_CONTRACT_2026-10-28.md`
  foi lido e preservado, sem edição. SHA-256: `bd89eeb0b9c76565fd2780926d50d40ec97255302b2a7da46ce5676828f85ea2`.
- O skill `codex-task-router` e suas referências foram aplicados; modo `DIRECT`,
  sem subagentes. A superfície disponível não expõe confirmação de invocação
  nativa do comando `$codex-task-router`.
- O skill `activity-progress-reporting` foi aplicado. A revisão de segurança
  seguiu o skill `codex-security:security-scan` em modo local, offline e somente
  leitura, respeitando a instrução do card para recuperar o scan anterior em
  vez de iniciar outro scan global.
- Estado factual inicial do Git: branch `work/s0-bootstrap`, `HEAD`
  `d36e96055a26556221bc487717f18ed322c76f02`, upstream
  `origin/work/s0-bootstrap`. Havia 7 arquivos rastreados modificados e 11.225
  arquivos não rastreados antes da criação deste relatório. Esse WIP foi
  preservado; nada foi staged, commitado ou enviado.
- Foram examinados os módulos S9 de supervisão, CLI, handshake, ledger e logging,
  o trecho S9/CLI de `cli.py` e os quatro arquivos de teste S9 correspondentes.
  Os arquivos de teste foram lidos, não executados.
- Nenhuma chamada Telegram/RPC, download, acesso ao banco operacional, instalação
  de pacote ou mudança de configuração do sistema foi feita. Não houve alteração
  de código, teste, contrato, segredo ou artefato histórico.

## Gate A — evidência anterior

`PASS` somente como estado histórico registrado antes desta atividade. Nenhuma
execução de Gate A ocorreu nesta recuperação; esse rótulo não certifica os Gates
B ou C nem autoriza G0 real.

## Gate B — preflight do executor

O executor disponível foi PowerShell 7.6.5 em Windows build 10.0.26200.9711.
Não havia executor alternativo P07 disponível. Foram usados arquivos sintéticos
temporários e limites de tempo; nenhum probe acessou rede externa.

| Probe | Python 3.15.0 | Python 3.14.7 (`.venv`) | Evidência |
|---|---|---|---|
| P01 — processo mínimo | PASS, exit 0 | PASS, exit 0 | Processo simples concluiu. |
| P02 — import asyncio | PASS, exit 0 | PASS, exit 0 | Import isolado concluiu. |
| P03 — `socketpair()` | TIMEOUT; processo encerrado | TIMEOUT; processo encerrado | Stack em `socket.accept()` dentro do fallback de `socketpair`. |
| P04 — TCP loopback local | FAIL, `WinError 10013` | FAIL, `WinError 10013` | O host negou a operação de socket local. |
| P05 — `asyncio.run(sleep(0))` | TIMEOUT; processo encerrado | TIMEOUT; processo encerrado | Stack no self-pipe do `ProactorEventLoop`, aguardando o mesmo fallback de socket. |
| P06 — subprocesso simples | PASS, exit 0 | PASS, exit 0 | Processo filho encerrou; não restaram processos dos probes. |
| P07 — executor alternativo | NÃO DISPONÍVEL | NÃO DISPONÍVEL | Nenhuma segunda superfície funcional estava disponível. |

**FATO:** a biblioteca padrão usa sockets de loopback para o fallback observado
de `socketpair` no Windows; P03/P05 pararam nesse caminho e P04 foi negado pelo
host.  
**INFERÊNCIA:** a causa operacional é restrição do ambiente/executor (`ENVIRONMENT_RESTRICTION`).  
**NÃO DETERMINADO:** qual controle específico do host nega o loopback; os dados
não permitem atribuir a falha ao Proactor, à versão do Python ou a um defeito
do projeto.

**Gate B = BLOCKED.** Regressão offline completa, testes focados S9 e testes S8
afetados = `NOT RUN`, pois dependem do preflight funcional. Resultados históricos
de outros runs não foram reutilizados como evidência desta atividade.

## Gate C — revisão de segurança delimitada

### Scan nativo anterior

`NATIVE_SECURITY_SCAN = BLOCKED`. O histórico e o chat canônico foram consultados,
mas não foi possível recuperar `scanId`, diretório ou token. A ferramenta nativa
exposta exige um `scanId` e não oferece listagem de scans. Uma tentativa anterior
registrou bloqueio SQLite `database is locked`; não foi repetida nem contornada.
Esta revisão manual de código não substitui o scan nativo.

### Riscos em aberto

**S9-RISK-01 — Importação do módulo filho a partir da pasta de saída**  
**Classificação:** aberto, severidade preliminar média, não reproduzido.

- **FATO/EVIDÊNCIA:** `s9_supervisor_cli.py` cria a pasta indicada pelo chamador
  após verificar forma e ausência de links, mas não verifica DACL/ACL privada ou
  exclusividade do diretório (`_safe_output_directory`, linhas 39–72). Em seguida,
  inicia `python -m telegram_courses.cli smoke` com `cwd=output` (linhas 167–172).
  O ambiente filho não inclui `PYTHONPATH` (`_child_environment`, linhas 75–81),
  mas isso não remove o diretório atual da busca inicial de módulos do Python.
- **INFERÊNCIA:** se um usuário local não confiável puder escrever na pasta de
  saída herdada, poderá tentar plantar `telegram_courses/cli.py` antes da
  importação do filho e executar código com a identidade do operador. A janela
  e a viabilidade no ACL real não foram testadas.
- **Limite:** nenhum payload foi criado ou executado. O risco depende de outro
  principal ter permissão de escrita sobre o diretório filho no instante do
  lançamento.
- **Recomendação:** remover diretórios graváveis da busca de importação e provar
  ACL privada do diretório. Qualquer correção exige revisão e verificação
  próprias; nenhuma foi aplicada nesta atividade.

**S9-RISK-02 — Troca de caminho entre verificação e uso do ledger**  
**Classificação:** aberto, severidade preliminar média, corrida não reproduzida.

- **FATO/EVIDÊNCIA:** `_check_ledger_paths` em
  `s9_operational_ledger.py`, linhas 123–127, declara que não é uma defesa por
  handle contra troca concorrente e exige que o chamador forneça diretório
  isolado. O CLI não comprova isolamento de permissões. A checagem `lstat` e as
  operações SQLite/receipt acontecem em chamadas separadas; handshake também
  valida e depois lê/cria arquivos pelo caminho.
- **INFERÊNCIA:** um escritor concorrente no diretório poderia tentar substituir
  ledger, sidecar, receipt ou marcador entre validação e uso, afetando estado ou
  evidência. Não foi demonstrado que a corrida vence no host atual.
- **Limite:** sem ACL efetiva do caminho escolhido e sem corrida reproduzida,
  impacto e explorabilidade ficam condicionais ao compartilhamento gravável.
- **Recomendação:** garantir diretório exclusivo por ACL e usar operações
  resistentes a troca de caminho/handles, além de teste de corrida autorizado.

**S9-RISK-03 — Cadeia de auditoria sem autenticação externa**  
**Classificação:** limitação aberta para decisão de threat model; severidade
preliminar média se escritor local adversarial fizer parte do modelo.

- **FATO/EVIDÊNCIA:** `_audit_hash` em `s9_operational_ledger.py`, linhas
  283–291, calcula SHA-256 determinístico sem chave. `_validate_audit` verifica
  sequência e consistência da cadeia (linhas 331–358). O salt armazenado no
  próprio banco é usado para pseudonimização, não para autenticar a cadeia.
- **INFERÊNCIA:** um atacante com escrita no arquivo pode recalcular hashes; não
  existe chave externa nem âncora confiável que prove autoria/integridade frente
  a esse escritor. A possibilidade de forjar um estado completo que passe todas
  as validações cruzadas não foi testada nesta atividade.
- **Recomendação:** decidir explicitamente o threat model e, se adulteração local
  estiver no escopo, usar autenticação com chave protegida externamente ou âncora
  fora do ledger. Não presumir aceitação do risco.

### Controles e dimensões revisadas

| Dimensão | Estado | Observação |
|---|---|---|
| Restrição do wrapper e do comando | DEMONSTRADO em revisão estática | O runner chama apenas o comando offline `smoke`; argv é lista, sem shell. A classificação de Gate S9 exige `limit_check_result=PASS`; `UNKNOWN` bloqueia. |
| V2 / comandos operacionais | DEMONSTRADO em revisão estática | Wrapper não aceita comandos reais/flags de autorização; caminho V2 bloqueia modos diferentes de `REMOTE_HASH_REQUIRED`. Nada disso foi executado nesta atividade. |
| Credenciais no ambiente filho | DEMONSTRADO em revisão estática | Allowlist de variáveis não inclui `TELEGRAM_*`, configuração ou `PYTHONPATH`; define `PYTHONNOUSERSITE=1`. Isso não resolve o cwd de importação descrito em RISK-01. |
| Logging e campos sensíveis | DEMONSTRADO em revisão estática | Formatter usa allowlist, rótulos limitados e omite mensagem/traceback. Nos call sites S9 revistos, eventos usam contagens/estados; nenhum segredo foi emitido nesta atividade. |
| Injeção de comando | DEMONSTRADO em revisão estática | `Popen` recebe lista de argumentos e o wrapper escolhe comando fixo. Nenhum `shell=True` observado no escopo S9. |
| Isolamento de filesystem e TOCTOU | BLOQUEADOR | ACL do output não é verificada e ledger documenta check-then-use sem defesa por handle; RISK-01/RISK-02. |
| Integridade do ledger | LIMITAÇÃO / BLOQUEADOR | SQLite WAL e validações/hash chain existem; autenticação e âncora independente não existem; RISK-03. Testes de corrupção e quarentena não foram executados aqui. |
| Supervisão/árvore de processos | UNPROVEN nesta atividade | Código usa Windows Job Object com kill-on-close e falha fechado se contenção não estiver disponível. Testes específicos não foram executados; há residual de corrida de PID no cancelamento cooperativo. |
| Limites de memória | LIMITAÇÃO | Supervisor amostra memória, mas não configura limite rígido de memória do Job Object; amostragem não é teto preventivo. |
| Deadline persistido | LIMITAÇÃO | Supervisão em execução usa relógio monotônico; ledger persiste/compara deadline por relógio de parede, sujeito a ajuste do relógio entre sessões. |
| Durabilidade após crash/energia | UNPROVEN nesta atividade | SQLite configura WAL e `synchronous=FULL`; testes sintéticos de falha existem, mas não foram executados nem provam queda real de energia. |
| RPC, sessão, fila real e bytes reais | NÃO EXECUTADO | Zero chamadas Telegram, acesso operacional ou download; `settle_bytes` aceita fonte sintética explícita no fluxo revisto. |

**Gate C = BLOCKED.** Há evidência estática suficiente para manter os riscos em
aberto, mas não houve reprodução, teste adversarial, ACL do destino real ou scan
nativo recuperado. `CORRECTIVE_CYCLES = 0` porque nenhum defeito foi reproduzido.

## QA executada

- Ruff nos seis módulos e quatro arquivos de teste S9 delimitados: `PASS` — All
  checks passed.
- `compileall` dos seis módulos delimitados com Python 3.14.7: `PASS`.
- `git diff --check`: exit 0; somente avisos de normalização LF/CRLF em arquivos
  preexistentes modificados.
- Testes focados e regressão completa: `NOT RUN`, bloqueados pelo Gate B.
- Código fonte, testes e contrato permaneceram sem edição. Os únicos arquivos
  deste pacote são este relatório e os três checkpoints de continuidade.
- Não houve `git add`, commit, push, reset, restore, clean ou stash.

## Snapshot revisado

Hashes SHA-256 dos arquivos observados no escopo, para fixar a revisão estática:

| Arquivo | SHA-256 |
|---|---|
| `src/telegram_courses/s9_supervisor.py` | `88ec44e0eef1801ec5c0f112e9da8486c62e17da3edf9dac201ab4d7237c47f0` |
| `src/telegram_courses/s9_supervisor_cli.py` | `7f5882b0cc91b1f5da177ff641f73064862d8f5071163c810306ed0b167882fd` |
| `src/telegram_courses/s9_supervisor_handshake.py` | `6486246874e3b1553c7ee216bdfc41bdf07b7a6a9a64bb6800561821ddb95cb2` |
| `src/telegram_courses/s9_operational_ledger.py` | `4f1078ae748a5c64d0c73bd985c05274292cb539605f5988299f08caaaefc466` |
| `src/telegram_courses/operational_logging.py` | `766b06fe2e45eb072c3d3dc9092a3fd62434a549cf3d40d62578af76677d4008` |
| `src/telegram_courses/cli.py` | `dfcea2b911387db68a1980e07166ef20c0061928e7d96d7da2b48ac468c9e54d` |
| `tests/unit/test_s9_supervisor.py` | `faae03ca3b5a6d35de58b7a9f1d5509e03c194269bc7dab06a4cd11d89cc45fb` |
| `tests/unit/test_s9_supervisor_cli.py` | `45701d2c63790d4b3814ae2b30416aa1556bb970224ff2b91197e739e7754406` |
| `tests/unit/test_s9_supervisor_handshake.py` | `b403c664345676e575cbe6d558cff7a33431bb394d28b2bc98fdef5a56c21294` |
| `tests/unit/test_s9_operational_ledger.py` | `57a3e96b4b3a787409b91b6f18a8eca29934320d59d85c950a1308ba06934cbb` |

## Fechamento e retomada segura

```text
GATE_A = PASS / HISTÓRICO; NÃO REPETIDO
GATE_B = BLOCKED / RESTRIÇÃO DE SOCKET LOCAL NO EXECUTOR
GATE_C = BLOCKED / 3 RISCOS CONDICIONAIS ABERTOS; SCAN NATIVO SEM CONTEXTO RECUPERÁVEL
FULL_OFFLINE_REGRESSION = NOT RUN
FOCUSED_S9_S8_TESTS = NOT RUN
NATIVE_SECURITY_SCAN = BLOCKED / SCAN ID E DIRETÓRIO AUSENTES
CORRECTIVE_CYCLES = 0
FORMAL_ACCEPTANCE = PENDING / NÃO DECLARADA
S9_G0_REAL = NÃO AUTORIZADO / NÃO EXECUTADO
TELEGRAM_RPC = 0
OPERATIONAL_DATABASE_WRITES = 0
GIT_STAGE_COMMIT_PUSH = NÃO
FINAL_RESULT = S9_G0_BLOCKED
SAFE_RESUME_POINT = Prover executor Windows funcional para P03/P04/P05; recuperar o contexto do scan nativo existente; resolver ou aceitar formalmente os riscos RISK-01..03 sob autoridade do usuário; então executar os testes offline exigidos pelo contrato. Nenhum G0 real, Telegram RPC ou publicação Git decorre deste checkpoint.
```

## Entrega

O relatório sanitizado completo foi enviado ao chat existente **Projeto Telegram
3.0**, no thread `6add6aa9-12e0-83e8-b02f-870f0a0edaf9`; a ferramenta retornou
`isError=false`. O envio não declara aceite formal em nome do usuário.

```text
DELIVERY_STATUS = SENT
DESTINATION = Projeto Telegram 3.0 / 6add6aa9-12e0-83e8-b02f-870f0a0edaf9
MESSAGE_SENT = YES / TOOL_IS_ERROR_FALSE
```
