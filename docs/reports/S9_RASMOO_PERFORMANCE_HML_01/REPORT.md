# Homologação real RASMOO + performance — PREFLIGHT_NO_GO

Data: 2026-11-01 (America/Sao_Paulo)

```text
ACTIVITY_ID = TELEGRAM_S9_RASMOO_PERFORMANCE_HML_01
PROJECT_ID = projeto_telegram_courses
ROUTING_MODE_ACTUAL = DIRECT / ROOT_ONLY
AGENTS_USED = ROOT
USER_AUTHORIZATION = BOUNDED_REAL_S9_HOMOLOGATION / CONDITIONAL_ON_G0_AND_G4
PREFLIGHT = NO_GO / BEFORE_G0_AND_BEFORE_ANY_TELEGRAM_RPC
G0_CONFIRMATION = NOT_REQUESTED / NO_PRIVATE_RUN_MANIFEST_OR_ISOLATED_ROOT
G4_CONFIRMATION = NOT_REQUESTED / NO_FRESH_REAL_DOWNLOAD_PLAN
TELEGRAM_RPC = 0
REAL_DOWNLOADS = 0
LIVE_OPERATIONAL_DB_WRITES = 0
S10 = NOT_AUTHORIZED
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
```

## Resultado

A autorização do usuário para a homologação real é explícita e condicionada aos
gates G0 e G4. O preflight parou antes de G0 porque o runtime disponível tem
rede restrita, não há sessão/credenciais DPAPI locais configuradas, o banco e a
pasta de downloads padrão ficam dentro do repositório e o destino Downloads
inspecionado não atende ao requisito de diretório privado. Não foi criado
manifesto, cópia operacional, run ou pasta de saída. Nenhum canal alternativo
foi considerado.

O runtime informa acesso de rede restrito. O caminho padrão `data/catalog.sqlite3`
existe no checkout; não foi aberto para escrita, copiado nem migrado. A
configuração padrão de downloads resolve para `downloads` dentro do checkout,
que também não foi usado. `%LOCALAPPDATA%\telegram_courses` não existe neste
ambiente; os artefatos `session.dpapi` e `credentials.dpapi` não estão presentes.
Nenhum segredo ou conteúdo de sessão foi lido ou impresso.

O destino padrão `%USERPROFILE%\Downloads` existe, mas sua ACL concede
`Modify` ao grupo `CodexSandboxUsers`, além de outras identidades. Ele não foi
aceito como raiz privada. O subdiretório do run não foi criado. O volume tinha
2,97 GiB livres; o teto combinado F+M mais a reserva S9 de 256 MiB exige cerca
de 2,75 GiB, deixando aproximadamente 0,22 GiB de margem. O espaço passaria
apenas o orçamento máximo calculado; isso não resolve a falta de destino
privado.

O venv do projeto está funcional: Python 3.14.7, Telethon 1.45.0, cryptg 0.6.0,
aiosqlite 0.22.1 e Rich 15.0.0; o launcher responde a `--help`. O Python global
3.15.0 está fora da faixa de `pyproject.toml` e não foi usado. A consulta local
não encontrou processos com nome Python ou Telegram.

## Evidência S9/P0 disponível

- O contrato congelado mantém SHA-256
  `BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2` antes e
  depois desta atividade. Nenhuma alteração contratual foi feita.
- O relatório P0 registra ledger incremental ativo, 283 testes S9 aprovados,
  dois E2E sintéticos G0–G9 aprovados e benchmark sintético de ledger de 1 GiB
  em 373,02 s. Isso demonstra apenas execução sintética; não mede rede Telegram.
- A evidência anterior classifica T24 como `PASS_OFFLINE`; o caminho real não
  foi avaliado.
- A revisão de segurança independente do P0 é `PASS_WITH_LIMITS`, sem finding
  bloqueante reportado. A limitação TOCTOU same-account permanece documentada
  e aceita para uso pessoal (`RISK03=ACCEPTED_FOR_PERSONAL_USE`). Nenhuma nova
  revisão de código foi executada nesta atividade.
- O supervisor, contenção, contabilização e deadlines foram exercitados nas
  evidências sintéticas P0. A contenção operacional real segue não avaliada.
- O relatório final P0 e a resposta subsequente do assistente foram observados
  no readback do chat canônico. A mensagem P0 não foi reenviada.

As authorities de continuidade e políticas locais aplicáveis foram lidas; os
SHA-256 locais de PM-01..PM-05 coincidem com os pins do binding. O router
`codex-task-router` foi invocado conforme solicitado; o cartão fixa
`ROOT_ONLY`, portanto a rota efetiva permaneceu DIRECT sem subagentes.

## Resultado por gate e métricas reais

| Item | Resultado desta atividade |
|---|---|
| Escopo | Canal original RASMOO; sem ID privado registrado |
| G0 | `NOT_EXECUTED`; confirmação TTY não solicitada |
| G1–G9 | `NOT_EXECUTED`; G0 bloqueou a entrada |
| F | 0 itens observados; scan não executado |
| M | 0 itens observados; elegibilidade desconhecida |
| Bytes reais recebidos/liquidados/reservados | 0 / não aplicável |
| Transferência de rede e velocidade média | `NOT_MEASURED` |
| Tempo da fila M, overhead do ledger e verificação | `NOT_MEASURED` |
| L10 real, integridade real e FloodWait | `NOT_TESTED` / `NOT_TESTED` / `NOT_OBSERVED` |
| Peak Working Set/CPU de download | `NOT_MEASURED` |

Os valores sintéticos do ledger não são apresentados como desempenho do
Telegram. Não houve confirmação G0/G4, login, scan, migração, escrita
operacional ou transferência.

```text
CHANNEL_SCOPE = RASMOO_ONLY / NO_ALTERNATE_CHANNEL
MANIFEST_STATUS = NOT_CREATED
OUTPUT_DESTINATION = NO_GO / PRIVATE_ROOT_NOT_AVAILABLE_IN_THIS_RUNTIME
DISK_PREFLIGHT = 2.97 GiB FREE / MAX_F_PLUS_M_AND_RESERVE_APPROX_2.75 GiB
SESSION_STATUS = DPAPI_ARTIFACTS_ABSENT / NO_CREDENTIALS_READ
SECURITY_FINDINGS = P0_REVIEW_PASS_WITH_LIMITS / NO_NEW_REVIEW
RISK03_STATUS = ACCEPTED_FOR_PERSONAL_USE / UNCHANGED
S9_REAL_ACCEPTANCE_RECOMMENDATION = NO_GO / PREFLIGHT_BLOCKED
WIP_PRESERVED = YES / 397 EXISTING STATUS ENTRIES AT START / NO SOURCE EDITS
DELIVERY_STATUS = WAITING_FOR_USER_APPROVAL
SEND_TOOL_RESULT = REJECTED / ONE_ATTEMPT / NO_MESSAGE_ID
AUTO_REVIEW_REASON = relatório inclui detalhes internos, caminhos locais, ACLs e estado operacional; destino externo sem propriedade comprovada; revisão entendeu que a autorização cobre perguntas, não o payload completo.
MESSAGE_OBSERVED = NO
RESPONSE_OBSERVED = NO
APPROVAL_REQUEST = PRESENTED_TO_OPERATOR_IN_SOURCE_CHAT / NO_RETRY_BEFORE_RESPONSE
REPORT_COPY = READY_AT_THIS_LOCAL_PATH
WORK_VALIDATED = PREFLIGHT_AND_REPORT_ONLY / REAL_WORK_NOT_EXECUTED
NEXT_EXACT_ACTION = AWAIT_EXPLICIT_OPERATOR_APPROVAL_FOR_ONE_NEW_SEND_ATTEMPT;
  IF_APPROVED_SEND_THIS_REPORT_ONCE_TO_THE_CANONICAL_CHAT; IF_DENIED_DO_NOT_SEND;
  THEN_CONTINUE_IN_AUTHORIZED_NATIVE_WINDOWS_ENVIRONMENT_WITH_NETWORK,
  LOCAL_DPAPI_SESSION_OR_SECURE_APP_AUTH, ISOLATED_SQLITE_BACKUP AND PRIVATE_ROOT;
  PRESENT_G0_TTY_CONFIRMATION_BEFORE_FIRST_RPC
```

## Encerramento seguro

Este NO_GO é do ambiente/runtime atual, não uma recusa da autorização do
usuário. Retomar somente em sessão nativa autorizada que tenha conectividade,
proteção local de credenciais e caminhos privados fora do repositório. Preservar
o canal RASMOO e todos os caps S9-L01..L16. G0 deve confirmar o manifesto e o
escopo antes da primeira RPC; G4 deve confirmar o plano real fresco antes de
qualquer fila. Se essas condições não forem atendidas, manter `NOT_EXECUTED`.

GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
S10 = NOT_AUTHORIZED
