# S6 V2 TRUSTED_REFERENCE preflight — 2026-10-18

```text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_V2_TRUSTED_REFERENCE_PREFLIGHT
RESULT = BLOCKED
EXECUTION_SCOPE = PREFLIGHT_ONLY / PLAN-ONLY
REAL_PROOF_EXECUTION = NOT_AUTHORIZED / NOT_RUN
NATIVE_EXECUTE_CONFIRMATION = NOT_REQUESTED / NOT_OPENED
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
```

## Resultado executivo

A referência local e o manifesto histórico passaram. O DryRun `controlled / TRUSTED_REFERENCE` passou como plano-only em uma raiz nova e isolada, com V1 ativa, V2 inefetiva e zero chamadas Telegram. A prova real permanece bloqueada: o contrato V2 é um rascunho não canônico (somente cinco diretrizes de desenho foram ratificadas), o launcher só permite Execute para `common / OPERATIONAL_ONLY`, o caminho de execução do harness também está restrito ao perfil common, e não há budgets aprovados/efetivos específicos para o alvo controlado.

O cenário `ALIGNED_TWO_PROCESS_RESUME` é compatível com o plano do contrato S6 aprovado. O prefixo proposto de 8 MiB é alinhado a 256 KiB; o harness atual, porém, fixa o alvo controlado em 128 MiB e não expõe parâmetro para selecionar 8 MiB. Nenhum desses valores foi alterado nesta atividade.

## Governança, contrato e histórico

O binding do projeto adota `GOVERNANCE_BASELINE V1`. Os hashes locais de PM-01 a PM-05 coincidem com os pins do binding. O mapa ativo registra como canônico e congelado o contrato S6 V1.

| Artefato | Estado e escopo | SHA-256 |
|---|---|---|
| `docs/contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md` | Aprovado/congelado; contrato S6 canônico | `AA2B4F019F28EC5DB7F0D8CF085B10C274F376271BCC65A0438D8609829F42B2` |
| `docs/contracts/S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT.md` | DRAFT / NOT APPROVED / NOT CANONICAL; houve ratificação de cinco diretrizes de desenho, sem adoção normativa, autorização Telegram ou data efetiva | `C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52` |
| `docs/contracts/S6_UNIFIED_CORRECTION_CONTRACT_V1.md` | Correções adjudicadas e escopo offline; não altera o contrato V1 | `3C0DD08D3CFD7BDC3F35EB788382B92001E538ECB3355DDEE64B544071C1B32F` |
| `docs/contracts/S6_V2_OFFLINE_E2E_AND_SYMLINK_GATES_ADDENDUM_2026-10-18.md` | Gates offline e symlink | `2E10D940D6071BB9065602A582DB54CD32ACA3FF3659996FEE5437B2C136B312` |
| `docs/contracts/S6_V2_PHASE_HANDOFF_CORRECTION_CONTRACT.md` | Handoff de dois processos e evidências | `47113519417AF4AB23C6CF7E9A7F9A75D4906188949AD28B63789550C9C94211` |
| `docs/contracts/S6_V2_PROOF_HARNESS_CORRECTION_CONTRACT.md` | Correção bounded do harness | `10311CA0CB8FA6AC0B6873B689A4B80907D74E6D45E0B96002023067B8C9F018` |
| `docs/contracts/S6_V2_PROOF_HARNESS_LIFECYCLE_FIXTURE_PATH_ADDENDUM_2026-10-18.md` | Fixture de caminho do ciclo de vida | `C5B74F0B04D26D6C15309EEC75EE4E36535528874E4BAFE918EE9F01FC7D74D8` |
| `docs/contracts/S6_V2_PROOF_HARNESS_TIMEOUT_RECEIPT_ADDENDUM_2026-10-18.md` | Recibo de timeout | `1F84AF1FC62CFB6758FE99A1EEC7C77439E0AF3C0991668278E9518E29DE776C` |

A ratificação de 2026-10-17 restringe a aprovação às cinco diretrizes de desenho e declara expressamente que ela não aprova o contrato V2 como canônico, não efetiva V2 e não autoriza implementação, execução Telegram, aceite S6 nem avanço de sprint. O preflight não resolve essa decisão.

Evidências anteriores consultadas em modo somente leitura: preparação da referência, upload/refetch controlado e provas aligned/nonaligned common. O manifesto de upload/refetch registra `-1002368271467:7603`, media ID `5089068167339181674`, `DOCUMENT`, `1,119,129,690` bytes. Essa é consistência histórica; a identidade e disponibilidade remotas atuais ficaram `NOT_CHECKED`.

## Referência local

```text
PATH = C:\Users\walac\Downloads\64Gram Desktop\Teste Telegram.rar
EXISTS = YES
READABLE = YES
SIZE = 1119129690
SHA256 = 3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c
EXPECTED_SIZE_MATCH = YES
EXPECTED_SHA256_MATCH = YES
LAST_WRITE_UTC_BEFORE = 2026-10-17T05:35:28.9950068Z
LAST_WRITE_UTC_AFTER = 2026-10-17T05:35:28.9950068Z
REFERENCE_VALIDATION = PASS
REFERENCE_MODIFIED = NO
```

O SHA-256 integral foi recalculado por leitura e coincidiu com o manifesto pré-upload e com o manifesto de referência produzido pelo DryRun. Tamanho e timestamp permaneceram iguais. O original não foi copiado, movido, renomeado, recompactado nem usado como destino de escrita. Sua procedência/criador não foi atestado independentemente.

## Cenário e budgets calculados

O contrato S6 pede interrupção em offset alinhado, retomada em processo independente, refetch/validação de identidade, comparação final com a referência e reconciliação do estado. `8,388,608` bytes é múltiplo exato de `262,144` e é adequado como prefixo alinhado no desenho. O harness atual fixa `CONTROLLED_PREFIX_ALIGNED = 134,217,728` bytes (128 MiB); o plano calculado pelo código foi portanto para 128 MiB, não para os 8 MiB propostos.

Valores abaixo são máximos teóricos calculados pelo código atual para `TRUSTED_REFERENCE`, com `E=1,119,129,690`, chunk `C=262,144`, uma tentativa na fase 1 e duas na fase 2. Não são autorização operacional nem observações remotas.

| Métrica | Prefixo do harness: 128 MiB | Prefixo proposto: 8 MiB |
|---|---:|---:|
| Prefixo `P` / wire offset `W` / overlap `O` | 134,217,728 / 134,217,728 / 0 | 8,388,608 / 8,388,608 / 0 |
| Restante `E-P` | 984,911,962 | 1,110,741,082 |
| `GetFile` fase 1 | 512 | 32 |
| `GetFile` por tentativa da fase 2 | 3,758 | 4,238 |
| `GetFile` agregado (1 + 2 tentativas) | 8,028 | 8,508 |
| `GetFileHashes` por tentativa de fase 2 | 4,271 | 4,271 |
| `GetFileHashes` agregado | 8,542 | 8,542 |
| Reserva `GetFile` fase 1 | 134,217,728 | 8,388,608 |
| Reserva por tentativa de retomada | 985,137,152 | 1,110,966,272 |
| Reserva agregada (fase 1 + 2 tentativas fase 2) | 2,104,492,032 | 2,230,321,152 |
| Disco calculado fase 1 | 2,192,871,514 | 2,192,871,514 |
| Disco calculado para retomada | 2,058,653,786 | 2,184,482,906 |

Na transferência final, o último chunk entrega no máximo `36,954` bytes; a reserva continua quantizada em `262,144` bytes antes de cada `GetFile`. A fase 1 permite uma tentativa; fase 2, duas; total S5 máximo três; workers `1`; FloodWait máximo `120` segundos por processo de retomada. No modo `TRUSTED_REFERENCE`, o orçamento calculado não reserva uma releitura de payload `[0,P)`; a comparação byte a byte com a referência e as consultas de hashes remotos são contabilizadas separadamente pelo desenho/código. Nenhuma chamada foi feita nesta atividade.

Auxiliares calculados para o perfil atual: `GetMessages` para evidências de hash até `8,542`, mais até `3` chamadas de identidade (`8,545` total no campo agregado); `GetMe` até `2`; teto agregado de RPCs de mídia selecionadas pelo harness `25,117`. O tráfego interno de `Telethon.connect` e o total de requests de transporte não são instrumentados pelo relatório atual. Estimativa de tempo não fornecida: não há base de throughput comparável para este alvo e modo.

Os valores históricos informados pelo usuário (`GetFile=11,786`, `GetFileHashes=12,813`, reserva `3,089,629,184`) foram tratados somente como comparação. O DryRun reutiliza caps common (`GetFile=139 aprovado / 94 efetivo`, `GetFileHashes=138 / 92`, reserva `36,438,016 / 24,641,536`) e não define caps aprovados/efetivos para o alvo controlado. Esses números common não autorizam nem comportam o perfil calculado. Portanto `BUDGET_READY=NO` até existir limite específico aprovado e implementado para este alvo.

## Ambiente, disco, paths e isolamento

```text
WINDOWS_USER = ROMA_CASA\walac
OS = Windows 11 build 10.0.26200
POWERSHELL = 7.6.5
PYTHON = 3.14.7 / project .venv
IS_ADMINISTRATOR = NO
INTEGRITY_LEVEL = LOW
DEVELOPER_MODE = 1
FILESYSTEM_C = NTFS
LONG_PATHS_ENABLED = 1
FREE_DISK_BYTES = 45752987648
APPLICATION_PATH_GUARD = 240 characters
```

O disco C: tem espaço para os máximos calculados: o maior requisito por fase é `2,192,871,514` bytes. O DryRun usou raiz nova `C:\Users\walac\desenvolvimento\projeto_telegram_courses\s6-v2-real-proof-e1d54cd323894f98ab702b8ebd8ff552`, com comprimento de `105` caracteres; ela não é reparse point e contém apenas o SQLite marcador de prova, manifesto e relatório plan-only.

No processo Codex, `TEMP` foi redirecionado ao sandbox e tem `92` caracteres. Uma simulação do caminho final nessa raiz excede a guarda do aplicativo de 240 caracteres (`247`); o mesmo caminho sob `C:\Users\walac\AppData\Local\Temp` tem `188` e sob a raiz do DryRun tem `210`. Para uma futura execução externa, usar um `EvidenceParent` nativo curto explicitamente e confirmar a ACL nesse processo. `LongPathsEnabled=1` não contorna a validação interna de 240 caracteres. O gate real de symlink já consta PASS na continuidade; nenhum novo symlink foi criado aqui.

## Harness, launcher e DryRun

O launcher e harness aceitam `controlled / TRUSTED_REFERENCE` em `DryRun`, e o manifesto criado confere alvo e referência. O DryRun usa SQLite exclusivamente de prova, não restaura sessão e não abre conexão.

O caminho de Execute não está pronto para esse perfil:

- `Invoke-S6V2Proof.ps1` rejeita toda execução real que não seja `common / OPERATIONAL_ONLY`.
- `execute()` no harness também rejeita `controlled / TRUSTED_REFERENCE`; `_case_budget()` valida sempre `common`, e a autorização/validação do processo filho também exige common/operational.
- `CONTROLLED_PREFIX_ALIGNED` não pode ser configurado para 8 MiB.
- O DryRun reporta os caps common como `approved_ceilings` e `effective_proof_caps` mesmo para `controlled`; isso não pode ser interpretado como um gate de budget do alvo.

A primeira tentativa via launcher usou o `TEMP` redirecionado e falhou ao publicar atomicamente o relatório (`PermissionError / WinError 5` no `os.replace`); não houve chamadas externas. A mesma execução foi repetida em raiz gravável do workspace e passou:

```text
DRYRUN = PASS / PLAN-ONLY SQLITE / NO NETWORK / V2 FALSE
REFERENCE_GATE = PASS
REAL_TELEGRAM_CALLS = 0
ORIGINAL_SQLITE_ACCESS = NO
HISTORICAL_PART_ACCESS = NO
V1_ACTIVE = YES
V2_EFFECTIVE = NO
NATIVE_EXECUTE_CONFIRMATION = NOT REQUESTED / NOT OPENED
```

Evidência plan-only: `s6-v2-real-proof-e1d54cd323894f98ab702b8ebd8ff552/s6-v2-dryrun-report.json`. As raízes temporárias das tentativas com falha permaneceram no TEMP isolado do sandbox e não foram reutilizadas. Nenhum arquivo `.part` foi criado e nenhum download, autenticação, acesso a credencial/cofre/sessão ou consulta Telegram foi feito.

## Matriz de prontidão

| Gate | Resultado | Evidência/limite |
|---|---|---|
| G01 — referência íntegra | PASS | Tamanho e SHA-256 integrais correspondem; leitura estável. |
| G02 — manifesto histórico | PASS | Upload/refetch histórico confere canal, mensagem, media ID, tipo e tamanho; identidade remota atual não consultada. |
| G03 — cenário contratualmente válido | BLOCKED para execução | Aligned two-process é compatível com S6 V1 e as diretrizes V2 ratificadas; o rascunho V2 não é contrato canônico aprovado. |
| G04 — harness compatível | BLOCKED | Controlled funciona em DryRun, mas o caminho real é validado como common/operational. |
| G05 — launcher compatível | BLOCKED | Execute está restrito a common/OPERATIONAL_ONLY. |
| G06 — budgets reconciliados | BLOCKED | Cálculo disponível; caps específicos aprovados/efetivos para controlled não existem. |
| G07 — espaço em disco | PASS | `45,752,987,648` livres versus máximo calculado de `2,192,871,514` bytes por fase. |
| G08 — isolamento | PARTIAL | DryRun isolado passou; TEMP do sandbox não serve ao path final, e o caminho de escrita do TEMP nativo não foi exercitado nesta execução. |
| G09 — DryRun | PASS | Plan-only passou; zero RPCs, zero download e V2 permaneceu false. |
| G10 — V1/V2 | PASS | V1 ativa e V2 inefetiva durante o DryRun. |
| G11 — zero chamadas Telegram | PASS | Confirmado no relatório; nenhum preflight de credenciais executado. |
| G12 — nenhum bloqueio crítico | FAIL | G03–G06 e G08 permanecem abertos. |

`TRUSTED_REFERENCE_PREFLIGHT=BLOCKED`. As regressões/offline gates já aprovadas continuam válidas conforme os relatórios anteriores; nenhum teste de regressão foi repetido, pois não houve alteração de código.

## Segurança e próximo passo

```text
SOURCE_CODE_CHANGES = NO
CANONICAL_CONTRACT_CHANGES = NO
REFERENCE_MODIFICATION = NO
HISTORICAL_EVIDENCE = READ_ONLY
OPERATIONAL_SQLITE = NOT ACCESSED
HISTORICAL_PART = NOT ACCESSED
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_UPLOADS = NO
REAL_PROOF_EXECUTION = NOT AUTHORIZED / NOT RUN
GLOBAL_V2_ACTIVATION = NO
GIT_ADD_COMMIT_PUSH = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
```

Finding mínimo: o usuário precisa decidir o basis normativo final para uma futura prova `TRUSTED_REFERENCE` e autorizar separadamente uma correção offline bounded do perfil controlado (prefixo escolhido, budgets específicos, guards do harness e caminho Execute do launcher), seguida de validação offline e novo preflight. Não foi solicitado nem inferido aceite para essas mudanças. Somente se o preflight posterior passar deverá ser apresentada uma autorização separada para a prova real.

```text
NEXT_ACTION = USER_DECISION_ON_TRUSTED_REFERENCE_CONTRACT_AND_BOUNDED_PREFLIGHT_REMEDIATION
```
