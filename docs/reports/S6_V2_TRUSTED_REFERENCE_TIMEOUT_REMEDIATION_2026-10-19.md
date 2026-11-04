# S6 V2 TRUSTED_REFERENCE — relatório de remediação de timeout

```text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION
REPORT_DATE = 2026-10-19
RESULT = OFFLINE_VALIDATION_PASS
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_RETRY = NO
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
NEXT_ACTION = USER_CONTROLLED_REAL_REPROOF_AUTHORIZATION
```

## Resultado executivo

A remediação do timeout do harness `TRUSTED_REFERENCE` foi implementada e
validada offline, conforme os resultados verificados pelo root. Os testes
abrangeram a suíte específica do harness, regressões S5/S6/download, duas
E2Es sintéticas com processos separados no Windows e o E2E sintético
`TRUSTED_REFERENCE` incluído na suíte do harness. Os DryRuns common e
controlled também passaram.

Não houve chamada real ao Telegram, download real ou retry. V1 permanece
ativa e V2 continua não efetiva. Este resultado offline não altera o status
de aceite formal S6 nem o checkpoint da sprint e não autoriza uma nova prova
real.

## Causa registrada

A causa do bloqueio anterior foi a aplicação global do deadline agregado de
900 segundos, cuja origem R7.2 era o cenário `common / OPERATIONAL_ONLY` com
envelope de 11.649.955 bytes. No recibo histórico, o timeout de processo
solicitado era 3.600 segundos, mas o efetivo foi aproximadamente 899,947
segundos porque prevaleceu o tempo restante do deadline agregado.

Na execução controlada observada, a transferência ainda avançava quando o
deadline expirou: 833.617.920 bytes em 863,160 segundos; bucket completo de
60 segundos mais lento a 688.052 bytes/segundo; última progressão semântica
de bytes 0,254 segundos antes do timeout e maior intervalo observado entre
avanços de 1,152 segundos. Esses dados não sustentam atribuir a interrupção a
inatividade, ao Telegram ou à integridade.

O terminal repetia `semantic_events=12`, valor que corresponde a
`len(seen_stages)`, a quantidade de tipos de estágio distintos observados. O
valor não conta eventos nem bytes. O progresso de bytes continuava renovando
`last_semantic`; a exibição repetida era visualmente enganosa e não indicava
transferência parada.

A fase 2 ficou sem relatório individual porque o filho só o grava após o
retorno normal do estágio, enquanto o supervisor podia encerrá-lo antes
desse ponto. O recibo do supervisor é a evidência autoritativa obrigatória e
deve identificar o relatório filho ausente como evidência incompleta, sem
fabricar fatos do filho.

No caso observado, `budget.within_caps=false` indicava contadores incompletos
e avaliação fail-closed: os contadores numéricos observados de `GetFile`
estavam abaixo dos limites, mas valores de identidade/GetMe eram nulos porque
faltava o relatório do filho. Isso não demonstra estouro numérico de cap.
Novos relatórios distinguem estouro numérico, reserva não resolvida,
contadores/evidência ausentes e corrupção do ledger.

## Contrato de timeout e progresso aplicado

Os parâmetros adjudicados constam no [adendo técnico de timeout e
reconciliação](../contracts/S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION_ADDENDUM_2026-10-19.md):

| Cenário | Limite solicitado por processo | Deadline agregado |
|---|---:|---:|
| `common / OPERATIONAL_ONLY` | 3.600 s | 900 s |
| `controlled / TRUSTED_REFERENCE` | 4.500 s | 4.800 s |

Para o caso controlado, a reserva autorizada de 2.230.321.152 bytes dividida
pelo bucket mínimo medido de 688.052 bytes/s resulta em aproximadamente
3.241,5 segundos. O dimensionamento acrescenta 10% de reserva temporal, até
120 segundos de FloodWait e 300 segundos de inicialização/finalização,
totalizando aproximadamente 3.985,7 segundos; os limites foram arredondados
e ampliados para 4.500/4.800 segundos. O limite efetivo do processo é o menor
entre o cap por processo e o tempo restante do deadline agregado. O grace de
cancelamento de até 30 segundos permanece dentro do deadline.

O monitoramento usa heartbeat de bytes recebidos e persistidos e taxa
observada pelo menos a cada 15 segundos. O heartbeat, polling, eventos
duplicados e valores inalterados não reiniciam o timeout de inatividade
semântica de 180 segundos. O progresso semântico evidenciado reinicia o
marcador; o deadline agregado continua obrigatório. Não havia throughput
histórico de consultas remotas de hash para reivindicar uma taxa medida
separada.

## Interrupção e reconciliação segura

Após confirmar a saída do filho, a reconciliação transacional e idempotente
fica restrita ao root de prova e às evidências observadas de PID, estado,
checkpoint, arquivo físico e ledger. Para a fase que expirou, o estado de
prova `DOWNLOADING` e a tentativa `SELECTED` transitam para
`FAILED_RETRYABLE`, classificados como `SUPERVISOR_TIMEOUT`. O checkpoint e
arquivo parcial são preservados; não se cria evidência de conclusão. Cada
reserva do ledger é liquidada por `reservation_id`; reserva pendente muda para
`UNCERTAIN` uma única vez. Se a saída não puder ser confirmada, não ocorre
escrita de recuperação e o resultado é `BLOCKED`. Evidência ausente ou
inconsistente nunca produz `PASS`.

## Resultados de validação

Os comandos e execuções abaixo foram realizados e verificados pelo root; não
foram repetidos durante a preparação deste relatório.

| Gate | Resultado observado |
|---|---|
| `tests/manual_proofs/test_s6_v2_proof_harness.py` | `PASS — 157 passed in 73.99s` |
| Regressões S5/S6/download | `PASS — 129 passed in 32.39s` |
| Duas E2Es sintéticas com processos separados no Windows | `PASS` |
| Cancelamento Windows nativo durante espera sintética de `GetFile` após chunk persistido | `PASS — saída confirmada; recibo filho ausente permaneceu incompleto; reconciliação bloqueada sem falso PASS` |
| E2E sintético `TRUSTED_REFERENCE` | `PASS — incluído na suíte do harness` |
| Ruff: `ruff check src tests tools` | `PASS` |
| Compilação: `compileall -q src tests tools` | `PASS` |
| Parser PowerShell de `Invoke-S6V2Proof.ps1` | `PASS` |
| DryRun `common / OPERATIONAL_ONLY` | `PASS` |
| DryRun `controlled / TRUSTED_REFERENCE`, prefixo de 8 MiB | `PASS` |
| `git diff --check` | `PASS`, com avisos LF/CRLF em arquivos pré-existentes |

```text
TIMEOUT_POLICY = PASS / OFFLINE
TRANSFER_PROGRESS_MONITORING = PASS / OFFLINE
SAFE_TIMEOUT_RECONCILIATION = PASS / OFFLINE
TRUSTED_REFERENCE_SYNTHETIC_E2E = PASS
S5_S6_REGRESSION = PASS
SAFETY_GATE = PASS / OFFLINE
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_RETRY = NO
```

## Autoridade e próximo passo

Os resultados são limitados aos gates offline listados. V1 permanece ativa;
V2 não foi promovida nem está efetiva. A referência e evidências históricas
permanecem somente leitura. O aceite formal S6 segue pendente, o checkpoint
da sprint segue diferido e nenhuma mutação Git foi autorizada ou executada.
Uma prova real requer decisão e autorização explícitas do usuário após
apresentação do estado offline validado.
