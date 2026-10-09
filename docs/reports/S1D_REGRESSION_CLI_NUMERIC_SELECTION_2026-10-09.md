# S1-D — Regression Fix + CLI Numeric Selection (2026-10-09)

## Resultado

```text
ACTIVITY = S1-D Regression Fix + CLI Numeric Selection
STATUS = PARTIAL / implementation and tests PASS; credential-access restriction breached by pre-fix regression test
PYTHON = 3.14.7
REGRESSION_FAILURE = tests/unit/test_auth.py::test_credentials_are_environment_only_and_validated
FAILURE_MESSAGE = Failed: DID NOT RAISE ConfigurationError
ROOT_CAUSE = TEST_ENVIRONMENT_DEPENDENCY
FOCUSED_REGRESSION = PASS / 3 passed
FOCUSED_CLI = PASS / 15 passed
FULL_PYTEST = PASS / 121 passed, 11 subtests passed in 184.34s
RUFF = PASS / ruff check .
DIFF_CHECK = PASS / git diff --check
REAL_TELEGRAM_ACCESS = NO
CREDENTIALS_ACCESSED = YES / pre-fix regression test read/decrypted configured local credential vault; values not displayed or logged
SESSION_DPAPI_ACCESS = NO
CREDENTIAL_VALUES_DISCLOSED = NO
GIT_ACTIONS = NONE
```

## Falha e correção da regressão

O teste passava um mapeamento de ambiente vazio a
`load_telegram_credentials({})` e esperava `ConfigurationError`. A resolução
atual também consulta o vault DPAPI quando o par de ambiente não existe. Como
havia um vault configurado na máquina, o teste deixou de ser isolado, carregou
credenciais e falhou com `DID NOT RAISE ConfigurationError`.

O teste agora injeta um vault sintético vazio em todas as chamadas. Isso mantém
o caso determinístico, verifica a ausência de credenciais sem consultar storage
local e preserva os testes separados que cobrem a precedência e fallback do
vault com dados sintéticos. Nenhum valor foi exibido ou registrado. A chamada
pré-correção leu/descriptografou o vault local; esse acesso é reportado
explicitamente. O arquivo `session.dpapi` não foi acessado. Como a restrição de
acesso a credenciais reais não foi cumprida, o status geral desta atividade é
`PARTIAL`, embora código, testes focados, regressão completa, Ruff e diff check
tenham passado.

Uma primeira tentativa no executor isolado ficou presa antes da lógica dos
testes: a sonda mínima reproduziu bloqueio do loop Proactor em
`socket._fallback_socketpair → accept`. A suíte completa foi executada no
PowerShell local funcional com Python 3.14.7. Esse bloqueio do sandbox não foi
classificado como defeito do produto.

## Seleção numérica da CLI

A CLI exibe `[1]`, `[2]` e assim por diante, preservando a ordem do snapshot e
mostrando nome, username disponível e tipo `BROADCAST_CHANNEL` ou `MEGAGROUP`.
O número é convertido localmente ao `telegram_chat_id` existente; o modelo de
domínio e a identidade persistida não mudaram. IDs completos continuam aceitos
como compatibilidade exata. IDs parciais, números fora do intervalo, zero e
entradas não numéricas são rejeitados. Entrada vazia ou `Q` cancela.

A seleção continua disponível para discovery `PARTIAL`. A CLI usa o snapshot
retornado, não faz nova chamada Telegram, e solicita a escolha depois do
fechamento do gateway. Lista vazia não solicita entrada. Os testes verificam
índice inicial/final, IDs completos, classificação dos dois tipos, ausência de
nova descoberta, cleanup e ausência do hash sintético na saída.

## Arquivos

- `src/telegram_courses/cli.py`
- `tests/integration/test_cli_channels.py`
- `tests/unit/test_auth.py`
- `docs/continuity/PROJECT_STATE.md`
- `docs/continuity/CONTINUITY_RECORD.md`
- `docs/continuity/handoff/LAST_HANDOFF.md`
- `docs/reports/S1D_REGRESSION_CLI_NUMERIC_SELECTION_2026-10-09.md`

DEC-S1D-01/02/03, OPEN-03 e GOV-01 não foram alterados. S1-D continua
`IMPLEMENTED / REAL_FUNCTIONAL_PASS / FINAL_ACCEPTANCE_PENDING`; esta atividade
não fecha S1-D nem autoriza remediação de credenciais, congelamento do contrato,
nova validação Telegram, publicação Git ou início de S2. A revisão do incidente
e os critérios de aceite de S1-D permanecem pendentes.
