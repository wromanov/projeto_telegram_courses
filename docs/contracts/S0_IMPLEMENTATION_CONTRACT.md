# Contrato formal de implementação — S0

```text
DOCUMENT_ROLE = IMPLEMENTATION_CONTRACT
PROJECT_ID = projeto_telegram_courses
SPRINT_ID = S0
CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
CONTRACT_VERSION = 1.0
CONTRACT_INITIAL_STATUS = DRAFT
CONTRACT_STATUS = DRAFT_BLOCKED
CONTRACT_APPROVAL = NOT_GRANTED
RECORDED_AT = 2026-10-05 / America/Sao_Paulo
CONTRACT_FIRST_IMPLEMENTATION = REQUIRED
CONTRACT_AUTHOR = SOL
CONTRACT_AUTHOR_ROLE = SOL_CONTRACT_AUTHOR
IMPLEMENTER = LUNA
IMPLEMENTER_ROLE = LUNA_IMPLEMENTER
EXECUTION_MODE = DIRECT
S0_STARTED = NO
S0_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
```

Este documento nasce como DRAFT e permanece na família DRAFT. `DRAFT_BLOCKED` é o resultado da revisão de completude, não aprovação nem autorização. As cláusulas consolidadas e os gaps abaixo são material para revisão; este draft ainda não é authority operacional executável. Somente após aprovação explícita do usuário poderá governar a implementação de S0, subordinado às authorities superiores. Aprovar o contrato e autorizar a sprint são decisões distintas.

## 1. Origem, precedência e estado de entrada

As referências compactas usadas neste contrato são:

| Ref | Fonte / papel | Seções aplicáveis |
|---|---|---|
| U | Card B atual do usuário: criação exclusiva deste contrato | §§1–24; contrato primeiro, limites do implementador, teste, change control e Git |
| REQ | [REQUIREMENTS](../product/REQUIREMENTS.md) / REQUIREMENT | FR-15/FR-16; NFR-01/05/06/08/09/10; escopo e acesso |
| ARC | [ARCHITECTURE](../architecture/ARCHITECTURE.md) / ARCHITECTURE | Product shape; Boundaries; ADR-001/002/003/004/006 |
| ENG | [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md) / ENGINEERING_FOUNDATION | Runtime and toolchain; Configuration contract; Logging contract; Test strategy |
| RM | [ROADMAP](../planning/ROADMAP.md) / ROADMAP | PHASE 0 e sequência S0–S10 |
| SPR | [SPRINTS](../planning/SPRINTS.md) / SPRINT | S0; Future sprint entry conditions; Spikes; Controles transversais |
| STATE | [PROJECT_STATE](../governance/PROJECT_STATE.md) / estado e autorização | Estado, ponto seguro e permissões correntes |
| OPEN | [PROJECT_OPENING_GATE](../governance/PROJECT_OPENING_GATE.md) / gate predecessor | Opening, recuperação e VP-01; fotografia anterior à revisão de prontidão |
| READY | [S0_READINESS_REVIEW_2026-10-05](../governance/S0_READINESS_REVIEW_2026-10-05.md) / READINESS_DECISION | DoR, decisão, classificação dos findings e SP-01 |
| AUD | [AUDITORIA_TECNICA_2026-10-05](../audit/AUDITORIA_TECNICA_2026-10-05.md) / AUDIT_FINDING | Contexto técnico não normativo; findings e spikes |
| GOV | [AUTHORITY_MAP](../governance/AUTHORITY_MAP.md) e [binding](../governance/PROJECT_GOVERNANCE_BINDING.json) | Baseline GOVERNANCE_BASELINE V1 / contract 1; pins e precedência |
| EVID | [OPENING_RECOVERY_VALIDATION](../governance/evidence/OPENING_RECOVERY_VALIDATION.json) | Evidência histórica de schema, pins, Continuity e VP-01 |
| APPROVALS | [APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md) | Aprovações de requisitos, arquitetura, fundação e plano |
| NAV | [START_HERE](../START_HERE.md), [CONTINUITY_RECORD](../governance/CONTINUITY_RECORD.md), [NEW_AGENT_BOOTSTRAP](../governance/NEW_AGENT_BOOTSTRAP.md) | Descoberta e retomada; não substituem STATE |

U é a fonte desta atividade. Sua referência de origem é o anexo `d94b27af-126b-4487-b20b-339d8bf373b5/Texto colado.txt`, recebido nesta sessão; o conteúdo operacional necessário foi materializado neste arquivo e em STATE, sem exigir esse anexo para futura retomada.

GOV resolve PM-00 1.0, PM-01 1.0, PM-02 1.7-R2.6, PM-03 1.7-R2.3, PM-04 1.2, PM-05 v1, VP-01 v2.0 e Continuity 3.0. PM-01 é owner de execução, DoR/DoD, continuidade e handoff; PM-05 rege independência analítica; VP-01 apenas valida. Este contrato especializa S0 e não altera governança externa.

| Fato de entrada | Resultado | Evidência / limite |
|---|---|---|
| Repo root | `C:\Users\walac\desenvolvimento\projeto_telegram_courses` | Git read-only nesta atividade |
| Branch / HEAD | `master` / `a00f325df45f3adad13b3a99d00c3230f913b282` | Git read-only; não é pin permanente da implementação futura |
| Upstream / origin | `origin/master` / `https://github.com/wromanov/projeto_telegram_courses.git` | Git local; nenhum fetch novo, sincronização remota atual não revalidada |
| Worktree / staging | Alterações documentais preexistentes; índice vazio | Inventário inicial preservado; não tratar worktree como limpo |
| PROJECT_OPENING_GATE | PASS | OPEN e EVID |
| PROJECT_GOVERNANCE_BINDING | ACTIVE / VALIDATED | EVID; sete hashes e pin Continuity conferidos novamente nos bytes locais |
| Schema do binding | PASS histórico; bytes do schema inalterados | SHA-256 confere com EVID; checagem focal de estrutura nesta atividade; validador genérico Draft 2020-12 indisponível, sem instalação |
| CONTINUITY_RECOVERY_GATE | PASS registrado | STATE e EVID; não implica autorização |
| VP01_VALIDATION | PASS / VALIDATION_ONLY registrado | OPEN/EVID; recuperação read-only desta sessão resumida no §24 |
| S0_READINESS / S0_BLOCKERS | READY_FOR_AUTHORIZATION / NENHUM na revisão anterior | READY, decisão preservada; não certifica completude deste contrato novo |
| S0_STARTED / S0_AUTHORIZED | NO / NO | STATE e Git/inventário sem produto |
| IMPLEMENTATION_AUTHORIZATION | NOT_GRANTED | STATE; U autoriza somente documentação |

**Reconciliação temporal explícita:** OPEN/EVID preservam `S0_READY = NO` no momento da abertura. READY e STATE v1.2 são posteriores e registram prontidão para autorização. O último parágrafo do bootstrap ainda descreve S0 como não pronta: é texto procedural desatualizado, não uma nova decisão; prevalecem STATE e READY para esse assunto. Não se alteram esses registros históricos nem se presume aprovação de S0. Os gaps descobertos aqui pertencem à exigência adicional de contrato sem decisões pelo implementador, e estão registrados separadamente no §22 e em STATE.

## 2. Regra estrutural e habilitação do implementador

Origem: U; GOV/PM-01 §§6–8; STATE.

```text
PROJECT_SCOPE_LOCK = projeto_telegram_courses
IMPLEMENTATION_WITHOUT_APPROVED_CONTRACT = PROIBIDO
IMPLEMENTER_MAY_REINTERPRET_CONTRACT = NÃO
IMPLEMENTER_MAY_CHANGE_ARCHITECTURE = NÃO
IMPLEMENTER_MAY_FILL_SEMANTIC_GAPS = NÃO
IMPLEMENTER_MAY_EXPAND_SCOPE = NÃO
CONTRACT_GAP_FOUND = PARAR_E_REPORTAR
CONTRACT_CHANGE_REQUIRED = RETORNAR_AO_AUTOR_DO_CONTRATO
EXTERNAL_GOVERNANCE_MUTATION = PROIBIDO
```

Antes de qualquer implementação futura, verificar conjuntamente: contrato aprovado e identificado por versão; zero gaps materiais; DoR predecessor válido; autorização explícita de S0 e escopo de escrita; estado Git factual conhecido. Falhar em qualquer requisito impede bootstrap, instalação ou código. A aprovação futura não pode delegar a Luna os gaps do §22 implicitamente.

O papel `SOL_CONTRACT_AUTHOR` é responsabilidade contratual. O payload solicitou GPT-5.6 Sol/Médio; a sessão identifica o executor como Codex baseado em GPT-6 e não confirma esse tier/esforço solicitado. Não houve troca de modelo, ajuste de esforço ou delegação. O implementador futuro deve verificar seu runtime, sem inferir capability ou authority pelo nome Luna.

## 3. Objetivo canônico e estado de saída de S0

Origem: RM PHASE 0; SPR S0; REQ NFR-01/08/09.

**Repository / Project Bootstrap:** estabelecer o repositório e o ambiente executável de desenvolvimento a partir da abertura aceita. O repositório Git já existe: não há necessidade autorizada de criar, clonar ou substituir o checkout.

S0 cria a estrutura Python/testes que vier a ser fechada neste contrato, `pyproject.toml`, ambiente `venv`, toolchain pytest/Ruff, configuração básica não sensível, entrada mínima da CLI e instruções de desenvolvimento. Preserva os documentos existentes e estabelece exclusões Git antes de qualquer commit de implementação.

S0 valida resolução das dependências-base, imports, package/import do projeto, configuração básica, resposta da entrada CLI em Windows, async, SQLite, pytest/Ruff, boundaries e proteção estrutural de segredos, por SP-01 e pelos testes do §13.

Ao final deve existir uma baseline de desenvolvimento reproduzível e integrada ao fluxo local `ambiente → import/configuração → entrada CLI → testes/lint`, com evidências PASS, documentação e estado reconciliados. Nenhuma capacidade de autenticação, catálogo ou transferência é entregue. O resultado técnico não concede publicação Git, encerramento pelo agente ou início de S1.

## 4. Escopo autorizável e entregáveis

Origem: SPR S0; ENG Runtime and toolchain / Configuration contract; U §§3–4.

| Entregável | Conteúdo mínimo requerido | Limite / fechamento |
|---|---|---|
| Repositório governado | Root, branch, HEAD/upstream verificáveis; documentação preservada | Usar checkout existente; nenhuma mutação Git inferida |
| `pyproject.toml` | Metadados/install do projeto, requisito CPython, dependências-base, pytest/Ruff | Backend, descoberta/instalação e perfil de ferramentas: CG-05; faixas ausentes: CG-01 |
| Ambiente virtual | `venv`, interpretador do ambiente utilizado em todas as validações | `.venv/` é o path protegido já nomeado por SPR; não usar instalações globais como substituto da prova |
| Package Python e estrutura de testes | Import do projeto funcional; testes offline e integração separados | Manifest físico e namespace: CG-02; não criar componentes futuros por antecipação |
| Configuração-base | `config/settings.toml`, carregamento mínimo, segredos separados | Campos e semântica exata de S0: CG-03 |
| Entrada mínima CLI | Resposta local com Rich; integração com configuração básica | Comando, argumentos, saída e códigos: CG-04 |
| `.gitignore` | Todas as exclusões do §10, sem exceção que permita secrets/sessões | Verificar antes de primeiro commit; commit continua sem autorização |
| Instruções de desenvolvimento | Ambiente Windows, instalação aprovada, import, teste, lint, config e CLI | Documento/path e comandos fechados em CG-02/04/05; sem credenciais ou login |
| Evidência SP-01 | Ambiente exato, versões resolvidas, ações/saídas sanitizadas e PASS/FAIL | Formato mínimo no §8; path versionável será fechado em CG-02 |

Não há entrega autônoma obrigatória de logging operacional em arquivos, modelos de domínio, gateways, parsers ou repositórios em S0. Rich e as regras de não exposição aplicam-se à entrada mínima. Um skeleton só poderá ser criado se seu arquivo e responsabilidade constarem do manifest contratual fechado; a mera existência do componente na arquitetura alvo não basta.

`S0_SCOPE_CLOSED = NÃO`: o conjunto funcional acima é fechado, mas o manifest físico e interfaces mínimas ainda não estão definidos. Não há lista de escrita de implementação aprovada nesta versão.

## 5. Fora de escopo

Origem: SPR S0–S10; ARC ADRs; U §4.

São proibidos em S0: autenticação Telegram; sessão Telegram real; listagem/resolução de canais; scanner; parser RASMOO; GenericParser funcional; catálogo persistente de produção; schema/migrations definitivos de S2; download de mídia; resume; sync incremental; workers operacionais; FloodWait/retry operacional; GUI; TDLib; empacotamento final/executável Windows; qualquer funcionalidade de S1+.

Instalar e importar uma biblioteca em SP-01 não autoriza criar cliente, conectar rede Telegram ou implementar seu adapter. O smoke SQLite temporário não entrega persistência de produto. Não criar versões vazias de APIs futuras que congelem assinaturas ainda deferidas, nem comandos de produto simulando sucesso.

## 6. Stack contratual

Origem: ARC Product shape / ADR-001/003/006; ENG Runtime and toolchain; READY SP-01; U §5.

| Dependência | Versão/faixa aprovada | Motivo | OBRIGATÓRIA_EM_S0 | Validação exigida |
|---|---|---|---|---|
| CPython | `3.14.x` | Runtime selecionado | SIM | Implementação CPython, versão exata observada dentro da linha, interpretador do venv |
| Telethon | `1.45.x` | Cliente inicial atrás do gateway | SIM, instalação/import no SP-01 | Versão resolvida dentro da linha; import sem cliente/login |
| cryptg | `0.6.x` | Acelerador selecionado | SIM, instalação/import no SP-01 | Versão resolvida dentro da linha; import no Windows alvo |
| aiosqlite | **Não definida nas authorities** — CG-01 | SQLite async | SIM, SP-01 | Versão aprovada/resolvida, import e smoke local temporário |
| Rich | **Não definida nas authorities** — CG-01 | CLI inicial | SIM | Versão aprovada/resolvida, import e entrada mínima |
| pytest | **Não definida nas authorities** — CG-01 | Testes | SIM | Versão aprovada/resolvida, coleta e suíte com exit code 0 |
| Ruff | **Não definida nas authorities** — CG-01 | Lint | SIM | Versão aprovada/resolvida, execução com exit code 0 |
| asyncio | stdlib do CPython selecionado | Async runtime | SIM | Corrotina local executada com resultado verificável |
| SQLite / `sqlite3` | Runtime fornecido pelo CPython; nenhuma versão independente aprovada | Persistência local futura e prova SP-01 | SIM, disponibilidade/smoke | Versão SQLite observada; conexão temporária e round-trip |
| Backend/build tooling do package | **Não escolhido nas authorities** — CG-05 | Materializar instalação/import reproduzível | Não há ferramenta específica autorizada ainda | Escolher explicitamente antes de fechar comandos de instalação |

As linhas `x` são decisões aprovadas em faixa, não ausência de decisão: não exigir patch inventado. Registrar o patch efetivamente instalado em SP-01 e usá-lo na reprodução documentada. Não substituir CPython, atualizar Telethon para outra linha ou omitir cryptg se não resolver. Os testes dirão se a combinação concreta é compatível; este contrato não afirma compatibilidade já demonstrada.

Para aiosqlite/Rich/pytest/Ruff não se adota implicitamente `latest`, faixa sem limite ou versão extraída da memória do autor. Resolver CG-01 antes de escrever dependências executáveis. Dependências transitivas efetivamente resolvidas devem integrar a evidência de instalação, sem inventar pin aprovado para elas. Política/artefato de reprodução é parte de CG-05; uma lista de versões observadas isoladamente não substitui um procedimento reproduzível.

`STACK_CLOSED = NÃO` até CG-01/05 resolvidos.

## 7. Sequência futura autorizável

Origem: SPR S0; GOV/PM-01 §§3, 6–8, 12; U.

Esta sequência é especificação futura, não comandos autorizados nesta atividade:

1. Confirmar aprovação do contrato sem gaps, DoR, autorização de S0 e permissões separadas de Git.
2. Conferir repo/root/branch/HEAD/upstream/worktree; inventariar e preservar alterações preexistentes.
3. Materializar exclusões antes de manipular artefatos sensíveis e antes de qualquer commit; não produzir sessão/segredo.
4. Criar somente manifest físico aprovado, metadados, configuração e entrada CLI mínima.
5. Selecionar CPython dentro de `3.14.x`, criar `.venv/` e instalar somente o conjunto aprovado pelo procedimento fechado em CG-05.
6. Executar SP-01; registrar versões e resultados. Falha não autoriza troca de stack.
7. Executar testes/lint e fluxo acumulado da CLI/configuração; revisar boundaries/escopo.
8. Registrar aceite/DoD, reconciliar documentação/STATE e preparar handoff para decisão do usuário. Não iniciar S1 nem publicar Git automaticamente.

## 8. SP-01 — Stack Windows

Origem: READY Spikes; SPR Future sprint entry conditions / SP-01; AUD-MED-07; REQ NFR-01.

**Objetivo:** comprovar que a stack selecionada é materializável no ambiente Windows alvo, sem Telegram real. Precondições: contrato completo/aprovado e S0 autorizada; Windows com CPython permitido; dependências/metadados/comandos aprovados. Acesso a repositório de pacotes, se necessário, serve somente à instalação autorizada; o smoke e a suíte não requerem rede Telegram.

| Passo | Ação futura | Resultado binário esperado |
|---|---|---|
| SP01-01 | Identificar Windows, arquitetura, implementação/versão e path do Python | Windows; CPython `3.14.x`; dados exatos registrados |
| SP01-02 | Criar `.venv/` e invocar diretamente seu interpretador | Criação/execução exit 0; `sys.prefix != sys.base_prefix`; path pertence ao venv do projeto |
| SP01-03 | Instalar projeto/dependências por procedimento CG-05 e verificar consistência do ambiente | Exit 0, conjunto aprovado instalado; nenhuma dependência obrigatória omitida |
| SP01-04 | Importar `telethon`, `cryptg`, `aiosqlite`, `rich`, `pytest` e package aprovado | Imports exit 0 sem cliente Telegram ou efeitos de produto |
| SP01-05 | Executar pytest e Ruff usando esse ambiente | Versões registradas; suíte e lint exit 0, sem ignorar falhas |
| SP01-06 | Rodar corrotina local com `asyncio.run`, retornando sentinela definida pelo teste | Resultado igual à sentinela e exit 0; sem rede |
| SP01-07 | Abrir SQLite em memória, ler/escrever sentinela e fechar | Round-trip correto; `sqlite3.sqlite_version` registrado; zero banco de produção |
| SP01-08 | Executar smoke aiosqlite temporário e fechar conexão | Round-trip correto e exit 0; nenhum schema de produto |
| SP01-09 | Executar fluxo mínimo de configuração/CLI fechado em CG-03/04 | Valores, saída e exit codes correspondem ao contrato fechado |
| SP01-10 | Registrar versões completas e repetir procedimento documentado em venv separado | Mesmas versões registradas de projeto/base/transitivas; suite/lint/smoke aprovados |

SQL dos passos 07/08 é um probe de validação isolado, em memória/temporário, não SQL de aplicação. Sua localização de teste deve ser explicitada no manifest CG-02; não abre exceção de SQL no domínio, parser ou CLI.

**Evidência mínima:** Windows/arquitetura; path do interpretador; CPython e SQLite exatos; versões de todas as dependências/base/transitivas e ferramentas de instalação usadas; comandos concretos, exit codes, resultados e data/fuso; nenhum dump de ambiente ou segredo. Evidência versionável descreve o ambiente, sem incluir `.venv/`, banco, logs brutos ou material de sessão.

```text
SP01_RESULT = PASS | FAIL
SP01_EXECUTION_IN_THIS_ACTIVITY = NÃO_EXECUTADO
```

PASS exige todos os passos. Qualquer falha resulta FAIL e stop. Falta de evidência não pode ser convertida em PASS. S0 não conclui com SP-01 FAIL ou não executado.

## 9. Estrutura e responsabilidades

Origem: ARC High-level component flow e Boundaries; ENG Configuration contract; SPR S0; U §7.

ARC declara expressamente que seu diagrama lógico **não é layout final de pacotes**. Portanto a árvore sugerida no payload não é promovida a decisão aprovada. CG-02 deve fechar namespace, árvore/arquivos e localização de cada responsabilidade antes da implementação.

| Diretório/local | Responsabilidade | PODE_CONTER | NÃO_PODE_CONTER |
|---|---|---|---|
| Root existente | Metadados e controles do projeto | `pyproject.toml`, `.gitignore`, instruções que forem aprovadas | Secrets/sessões; executável final; mudanças de governança externa |
| Código Python — path pendente CG-02 | Entrada mínima/configuração e package importável | Arquivos expressamente aprovados no manifest | Comportamentos S1+ ou infraestrutura em lógica pura |
| Testes — paths pendentes CG-02 | Unitários offline e integração local separados | Smokes, fixtures sintéticas, probes temporários | Login, sessão/credenciais reais ou download |
| `config/` | Configuração não sensível | `settings.toml` básico fechado em CG-03 | API hash, códigos, senha, session string |
| `docs/` existente | Authorities, instruções e evidências | Documentação de S0; contrato em `docs/contracts/` | Bancos, logs brutos, secrets ou cópia modificada de governança externa |
| `.venv/` local, excluído | Ambiente de desenvolvimento | Runtime/dependências locais autorizados | Arquivos versionados ou prova substitutiva do contrato |
| `data/session/`, `logs/`, `venv/` | Paths de exclusão | Somente futuros artefatos locais quando autorizados | Obrigação de criar agora ou incluir no Git |
| `data/` genérico | Não há entrega de dados de produto em S0 | Nada de produto obrigatório nesta sprint | Catálogo/schema final, sessão ou mídia criada pelo bootstrap |

Nomear um path em `.gitignore` não determina sua criação. Não criar diretórios vazios/placeholders sem necessidade expressa no manifest. Em particular `src/telegram_courses/`, `tests/unit/` e `tests/integration/` são possibilidades de layout, ainda não decisões congeladas.

## 10. Segurança do bootstrap

Origem: REQ NFR-05/06; ENG Configuration/Logging; SPR S0; READY exclusões; U §9; AUD-MED-06.

`.gitignore` deve excluir no mínimo, sem exceções que reincluam conteúdo sensível:

```gitignore
.env
.env.*
*.session
*.session-journal
data/session/
.venv/
venv/
__pycache__/
.pytest_cache/
.ruff_cache/
logs/
*.log
```

`venv/` também vem de U e protege ambiente alternativo; o ambiente de prova permanece `.venv/`. `.env.*` inclui exemplos com esse nome: não abrir exceção silenciosa. O arquivo não cria suporte a dotenv; não adicionar essa dependência por causa da exclusão.

Testar exclusões com paths sintéticos via `git check-ignore --no-index --stdin`, sem criar sessão/segredo. Para cada classe, verificar um path representativo e o pattern aplicável. Inspecionar separadamente `git ls-files`: ignore não remove arquivo já rastreado. Encontrar material sensível real exige stop; não apagar, imprimir, fazer staging ou reescrever histórico automaticamente.

Nenhuma credencial real pode constar em configuração, testes, instruções ou evidência versionável. Não capturar variáveis de ambiente em massa. Não criar sessão, cliente conectado ou autenticação Telegram. A proteção concreta Windows de sessão/ACL/localização é condição antes de sessão real em S1, não comportamento implementável aqui. O catálogo futuro da aplicação deve permanecer sem secrets; não confundir sua SQLite com o formato da futura sessão Telethon.

## 11. Boundaries de implementação

Origem: ARC Boundaries / ADR-002/003/004/006; ENG SQL/Test strategy; REQ NFR-08; U §8.

| Boundary | Regra verificável em S0 |
|---|---|
| DOMAIN | Nenhum import, tipo ou API Telethon; nenhuma construção de infraestrutura |
| PARSERS | Sem dependência de Telegram/Telethon, SQLite, filesystem, download, retry ou CLI; sem parser funcional nesta sprint |
| TELETHON | Código operacional e tipos específicos restritos ao adapter/gateway quando implementado em S1; em S0 apenas import isolado do smoke |
| SQL | SQL de produto restrito à persistência; não criar repositório/schema em S0; probes temporários de SP-01 só no teste autorizado |
| CLI | Somente entrada local, apresentação Rich e configuração-base; sem regra material de domínio ou conexão/persistência de produto |
| TESTES | Suíte normal offline, dados sintéticos; integração local separada; nenhuma integração real Telegram em S0 |

Inspecionar todos os arquivos Python criados e imports/dependências declarados. Se uma camada futura não existe, registrar ausência e inexistência de violações; não criá-la apenas para poder testá-la. Não introduzir dependência reversa por conveniência do skeleton.

## 12. Configuração e logging mínimos

Origem: ENG Configuration contract / Logging contract; REQ FR-15/16; SPR S0/controles transversais; U §10.

Formato/local aprovados: TOML em `config/settings.toml`. Conceitos previstos: diretório de download, workers, limite de retry, opção de hash, path de banco, nível de logging, path da sessão. Workers têm padrão 2 no produto; isso não autoriza executar workers em S0.

Precedência já decidida, onde aplicável: argumento CLI → ambiente/segredo → arquivo de settings → default da aplicação. Secrets futuros `TELEGRAM_API_ID` e `TELEGRAM_API_HASH` vêm de ambiente/provedor próprio, sem fallback hardcoded. Não são obrigatórios para smoke, teste ou início da CLI de S0; a sprint não opera Telegram.

**CG-03:** os documentos não fixam nomes de chaves/seções TOML, subconjunto mínimo carregado em S0, demais defaults, mapeamento não sensível por ambiente/CLI, semântica de paths relativos, chaves desconhecidas, configuração ausente ou validação por campo. Não escolher essas regras implicitamente. Fechar casos nominais, ausência e valores inválidos com entrada/saída/exit code antes de testes executáveis. Ler config não pode criar sessão, diretório de mídia ou catálogo de produto.

Não adicionar framework de configuração, dotenv, broker ou web. Logging completo em arquivos não é entregável autônomo de S0; caso o smoke emita diagnóstico, não conter secrets. Preservar shape futuro timestamp/level/component/event/context e proibições de API hash, código, senha 2FA e conteúdo/string de sessão. Não antecipar rotação/retenção ou retry.

## 13. Contrato de testes

Origem: SPR S0; ENG Test strategy; REQ NFR-01/05/08/09/10; U §11.

Todos os testes abaixo são obrigatórios na futura execução, sem login, rede Telegram ou credenciais. Ação/teste pendente de gap não é facultativo: impedir aprovação/executabilidade até fechamento. `<PY_VENV>` designa o interpretador de `.venv/` verificado no SP-01, não um comando global.

| TEST_ID | OBJETIVO | PRECONDIÇÃO | AÇÃO futura | RESULTADO_ESPERADO | EVIDÊNCIA |
|---|---|---|---|---|---|
| S0-T01 | Runtime correto | S0 autorizada; CPython permitido disponível | Obter implementation/version/path, Windows/arquitetura; criar/usá-lo no venv | CPython `3.14.x`, Windows, path do venv, prefix distinto, exit 0 | Metadados e saída sanitizada SP01-01/02 |
| S0-T02 | Imports mínimos | CG-01/05 fechados; instalação SP01-03 concluída | Importar telethon/cryptg/aiosqlite/rich/pytest em processo do venv sem inicializar clientes | Exit 0; versões de distribuições na faixa aprovada | Saída e lista completa de versões |
| S0-T03 | pytest funcional | Manifest CG-02 e descoberta CG-05 definidos; pelo menos um teste real de smoke | Executar `<PY_VENV> -m pytest` pela configuração aprovada | Coleta não vazia; zero falhas/erros; exit 0; sem Telegram | Relatório de coleta/resultado; não aceitar exit de zero testes |
| S0-T04 | Ruff funcional | Perfil CG-05 fechado; código/testes presentes | Executar `<PY_VENV> -m ruff --version` e `<PY_VENV> -m ruff check .` | Versão aprovada; lint exit 0; não excluir código/testes para ocultar erros | Versão, regras/configuração e resultado |
| S0-T05 | Package/import do projeto | Namespace e método instalação CG-02/05 fechados | Instalar pelo procedimento fechado; importar namespace e verificar origem em processo novo | Exit 0; import resolve package deste checkout, sem injeção ad hoc de path | Comando de instalação/import e path de origem |
| S0-T06 | Estrutura/boundaries | CG-02 fechado; implementação disponível | Comparar manifest com arquivos; inspecionar imports/efeitos e dependências conforme §11 | Todos os arquivos autorizados presentes; zero violações/antecipações S1+ | Matriz arquivo → responsabilidade/imports; deltas de escopo |
| S0-T07 | Proteção estrutural | `.gitignore` materializado antes de commit | Conferir todos os patterns do §10 via paths sintéticos; inspecionar arquivos rastreados e superfícies novas | Todas as classes excluídas; zero secrets/sessões versionados ou em fixtures/config/evidência | Pattern/path sintético, resultado e revisão sanitizada, sem imprimir secrets |
| S0-T08 | SP-01 Windows | Todos os gaps fechados; ambiente/meta/base configurados | Executar SP01-01–10 e registrar resultado composto | Todos PASS; SP01_RESULT = PASS; reprodução comprovada | Registro de SP-01 completo |
| S0-T09 | Configuração-base | CG-03 e integração CLI CG-04 fechados | Exercitar arquivo válido, ausência, inválido e precedência para opções realmente previstas em S0 | Valores/saídas/códigos exatamente conforme casos fechados; nenhum efeito de produto | Casos entrada/saída por campo e relatórios |
| S0-T10 | Entrada CLI Windows | CG-04 fechado; package/config integrados | Invocar comando/argumentos mínimos aprovados no venv | Resposta e exit codes contratados; sem exigir credenciais ou conectar Telegram | Comando, saída, exit e estado local observado |
| S0-T11 | Documentação/regressão | Manifest e comandos fechados; entregáveis presentes | Seguir instruções em ambiente separado; comparar documentos preexistentes com baseline e deltas autorizados | Reprodução PASS; documentos preservados salvo reconciliação autorizada; sem produto anterior para regredir | Evidência de reprodução, inventário e diff documental |

Corrotina e round-trip SQLite/aiosqlite de SP-01 devem executar e conferir resultados, não apenas importar stdlib. O critério de boundary pode ser inspeção documentada; não exige introduzir ferramenta extra de arquitetura. Testes da configuração devem distinguir comportamento esperado de mera cópia da implementação.

`TEST_CONTRACT_CLOSED = NÃO`: T02–T06/T08–T11 dependem de decisões CG-01–05, e as lacunas impedem especificar todos os comandos/valores esperados. Os testes não foram executados nesta atividade documental.

## 14. Critérios binários de aceite

Origem: SPR S0 acceptance; READY; U §12. Resultado de cada critério: PASS ou FAIL. Não executado/sem evidência impede PASS, sem alegar que a implementação inexistente foi testada e falhou.

| ACCEPTANCE_ID | PASS somente se | Testes / evidência |
|---|---|---|
| S0-A01 | Root/branch/HEAD/upstream e worktree/staging conhecidos; repo existente preservado | Preflight Git e inventário |
| S0-A02 | `pyproject.toml` existe, usa decisões aprovadas CG-01/05 e instala conjunto aprovado em venv | T01/02/05/08/11 |
| S0-A03 | Todos os arquivos obrigatórios do manifest CG-02 existem e package importa deste checkout | T05/06 |
| S0-A04 | pytest coleta testes de S0 e conclui sem erro, exit 0 | T03 |
| S0-A05 | Ruff aprovado verifica código/testes e retorna exit 0 | T04 |
| S0-A06 | Configuração-base atende cada caso nominal/ausente/inválido/precedência fechado em CG-03 | T09 |
| S0-A07 | Entrada CLI mínima executa em Windows com saída e exit codes fechados em CG-04 | T10 |
| S0-A08 | Todos os passos SP-01 PASS; runtime/SQLite/dependências exatos registrados; reprodução comprovada | T08/11 |
| S0-A09 | Todas as exclusões exigidas aplicam-se; nenhum secret/sessão real é versionado ou incluído em novos artefatos | T07 |
| S0-A10 | Zero violações de boundary; zero funcionalidades S1+ antecipadas | T06 e revisão integral do delta |
| S0-A11 | Instruções/evidências no path fechado; documentação e STATE reconciliados; handoff descobrível | T11, §15 e PM-01 |
| S0-A12 | Contrato aprovado e zero gaps materiais, incluindo CG-01–05; autorização da sprint verificável | Aprovações, STATE e checklist §23 |

`ACCEPTANCE_CRITERIA_CLOSED = NÃO` enquanto os critérios ainda referenciam decisões não preenchidas CG-01–05. É proibido declarar os critérios preenchidos apenas por apontar para o registro de gaps.

## 15. Definition of Done e fechamento

Origem: SPR S0 DoD/Gates; GOV/PM-01 §§3, 7, 12; U §13.

S0 somente poderá ser considerada tecnicamente concluída se todos os entregáveis do manifest fechado existirem, T01–T11 e A01–A12 passarem, SP-01 passar, boundaries/segurança/escopo estiverem íntegros, nenhum gap material permanecer e os gates aplicáveis abaixo possuírem evidência:

| Gate | Evidência futura requerida |
|---|---|
| MODULE_GATE | Smokes de runtime, imports, config e package aprovados |
| INTEGRATION_GATE | Entrada CLI usa package/configuração reais do bootstrap no venv |
| ACCUMULATED_FLOW_GATE | Fluxo local completo ambiente → instalação → config/import → CLI → testes/lint PASS |
| REGRESSION_GATE | Documentação/fatos preexistentes preservados; repetição em ambiente separado PASS; baseline de produto anterior inexistente, sem inventar regressão Telegram |
| PROJECT_STATE_RECONCILIATION | Estado factual, evidências, gaps, autorização e próximo passo reconciliados |
| AGENT_HANDOFF_GATE | Campos/artefatos de PM-01 §12.3 descobríveis e atuais, sem estado ativo contraditório |

Docs de S0, estado da unidade e continuidade devem ser atualizados conforme impacto; roadmap somente quando houver alteração material autorizada. Fechamento da sprint/delivery unit e avanço continuam decisões do usuário. Mesmo com aceite técnico, S1 requer seu DoR e autorização próprios.

Commit/push não fazem parte da DoD: SPR e PM-01 distinguem fechamento técnico de publicação. `DOD_CLOSED = NÃO` nesta versão porque manifest e critérios concretos não estão completos; a regra de não concluir com gaps é fechada, mas não substitui o fechamento desses detalhes.

## 16. Findings da auditoria

Origem: AUD findings; READY classificação; SPR Future sprint entry conditions. O relatório de auditoria permanece contexto não normativo.

| Finding | Obrigação em S0 | Condição futura preservada |
|---|---|---|
| AUD-MED-06 | Exclusões e isolamento estrutural do §10; nenhuma sessão real | Proteção Windows concreta antes de sessão em S1; redaction transversal S8–S10 |
| AUD-MED-07 | SP-01 prova stack Windows e registra versões | Formatos/volume/memória/workers: S2/S4/S5/S8/S9 conforme plano; não medir download em S0 |
| AUD-MED-08 | Registrar resolução posterior; não editar auditoria histórica | RESOLVED_BY_LATER_ACTIVITY em READY; não reabrir como blocker da stack |
| AUD-HIGH-01 | Não implementar identidade/revisão, schema ou dedup | Fechar antes de persistência S2; aplicar a S4/S6/S7 |
| AUD-HIGH-02 | Não implementar reconciliação/commit físico | Matriz/ownership antes de finalização e rerun S4; recovery S4/S6 |
| AUD-HIGH-03 | Não criar checkpoint definitivo | Semântica antes de S2; parser S3 e alcance integrado S7 |
| AUD-MED-01/02 | Não criar parser/schema para fechar findings | Cardinalidades/constraints antes de S2–S3 |
| AUD-MED-03/04/05 | Preservar boundaries; não criar máquina/worker/path builder operacional | Retry básico S1; transferências/paths/concurrency S4–S6/S8/S10 |
| AUD-LOW-01 | Fechar somente entrada mínima S0 em CG-04 | CLI de auth/channels/scan/catalog/download/sync/status junto às sprints pertinentes |

SP-02/SP-05 ficam antes de S2; SP-03 antes de congelar adapter em S4 e completo antes do aceite S6; SP-04 em S4. Não são atividades de S0.

## 17. DECISÕES_CONGELADAS

Origem: APPROVALS; ARC ADRs; ENG; REQ; SPR; U regra estrutural atual. Congeladas aqui significa decisões existentes preservadas; não aprovação deste draft.

| Decisão já aprovada/aplicável | Origem |
|---|---|
| S0 é PHASE 0 / Repository / Project Bootstrap sem capacidade Telegram | RM/SPR S0 |
| CPython `3.14.x`; execução fonte/venv; `pyproject.toml`; pytest/Ruff | ENG Runtime and toolchain |
| Telethon `1.45.x` e cryptg `0.6.x`; Telethon atrás de gateway | ARC ADR-001/002; ENG |
| CLI-first com Rich; asyncio stdlib; GUI fora do escopo inicial | ARC ADR-006; REQ interface; ENG |
| SQLite local, aiosqlite, SQL explícito/restrito à persistência | ARC ADR-003; ENG |
| Parsers independentes de infraestrutura e de formato universal RASMOO | ARC ADR-004; REQ FR-05/NFR-08 |
| Sem ORM/Alembic, broker/Redis/Celery, web ou arquitetura distribuída antecipados | ENG Runtime and toolchain |
| TOML em `config/settings.toml`; precedência CLI → ambiente/segredo → arquivo → default, quando aplicável | ENG Configuration contract |
| Segredos fora do versionamento/logs; suíte normal offline; integração Telegram separada | REQ NFR-05/06/09/10; ENG |
| Exclusões de bootstrap; SP-01 obrigatório em S0 | SPR S0; READY; U |
| Contrato primeiro; autoria Sol/execução Luna; nenhum preenchimento de gaps pelo implementador | U regra estrutural |

Não entram nesta lista faixas ausentes, layout proposto, defaults não aprovados ou decisões futuras.

## 18. DECISÕES_DEFERIDAS

Origem: SPR Future sprint entry conditions; READY; ARC/ENG; AUD. Deferidas de S0, não dispensadas.

| Decisão / trabalho | Sprint ou condição antes de implementar |
|---|---|
| Storage/ACL de sessão, falhas auth e ownership básico FloodWait/retry | Antes de acesso/sessão real em S1 |
| Identidade/revisão da mídia e invalidação | Antes de schema S2; fluxos S4/S6/S7 |
| Semântica checkpoint, paginação, progresso confirmado | Antes de persistência definitiva S2; validação S3/S7 |
| Schema definitivo, PK/FK/constraints/índices/transações | Antes da primeira migration S2 |
| Cardinalidades, parser associations, órfãos e fallback | Amostra SP-02 antes de S2–S3 |
| Máquina de estados final e separação remoto/transferência | Antes dos fluxos de S4–S7 |
| Filesystem/SQLite reconciliation, ownership de parcial/final e destino existente | Antes da finalização/rerun S4; SP-04 em S4 |
| Paths Windows completos, containment e colisões | Antes de escrever mídia S4; pacote S10 |
| Streaming, offsets e resume | SP-03 antes do adapter S4; teste real completo antes de aceite S6 |
| Queue, backpressure, cancelamento e concorrência operacional | Antes de operações S4–S6; thresholds com evidência S8/S9 |
| Alcance sync de edições/substituições/remoções | Definições SP-05 antes de S2; validação integrada S7 |
| Medições de memória, formatos, catálogo e máximo de workers | Antes dos aceites afetados S2/S4/S5/S8/S9 |
| Logging operacional/retention e hardening transversal | Desde primeiro uso; consolidação S8, sem exigir serviço em S0 |
| GUI, TDLib, novos frameworks e distribuição final | GUI/TDLib futuros; distribuição Windows somente S10 |

CG-01–05 são gaps da própria S0, não decisões legitimamente adiadas para S1+.

## 19. Comportamentos proibidos ao implementador

Origem: U §17; ARC/ENG; GOV/PM-01.

É proibido alterar arquitetura, trocar stack, adicionar framework, ORM, broker, web server, GUI ou abstrações não exigidas; resolver decisões deferidas; implementar funcionalidades S1+; mudar aceite; editar contrato; reinterpretar requisito ambíguo; omitir teste/dependência obrigatório; declarar reprodução/compatibilidade sem evidência; promover draft/aprovar contrato; iniciar sprint ou publicar Git sem autorização pertinente.

Detalhes puramente mecânicos que preservem cada regra fechada podem ser executados. Escolher namespace, interfaces CLI/config, versão sem faixa, backend ou comportamento ausente não é detalhe mecânico neste contrato.

## 20. IMPLEMENTER_STOP_CONDITIONS

Origem: U §18; GOV/PM-01 §8; ENG boundaries.

Parar em limite seguro se: contrato contraditório ou incompleto; authority superior contradiz cláusula; contrato não aprovado; sprint não autorizada; dependência obrigatória não resolve; versão exigida indisponível; teste requer decisão não documentada; boundary impossível de cumprir; mudança extrapola S0; aceite impossível de demonstrar; segredo real aparece nas superfícies afetadas do workspace; arquitetura precisaria mudar; falha SP-01; estado Git/documental materialmente divergente ou alteração concorrente afeta o trabalho.

```text
STOP_ACTION = PARAR
IMPROVISATION = PROIBIDA
GAP_REPORT = OBRIGATÓRIO
```

Preservar alterações e evidências sanitizadas. Reportar cláusula, comportamento esperado/observado, impacto e decisão necessária. Não descartar mudanças, trocar biblioteca, remover proteção ou buscar workaround que transforme falha em PASS.

## 21. CONTRACT_CHANGE_CONTROL

Origem: U §19; GOV/PM-01/PM-05.

```text
IMPLEMENTER_CAN_EDIT_CONTRACT_AFTER_APPROVED = NÃO
SILENT_CONTRACT_CHANGE = PROIBIDO
```

Se implementação revelar gap: (1) parar no limite seguro; (2) identificar cláusula/versão; (3) registrar evidência sanitizada; (4) classificar impacto em escopo, arquitetura, semântica, testes, segurança e compatibilidade; (5) retornar ao autor Sol; (6) autor preparar delta contratual rastreável; (7) obter nova aprovação explícita do usuário quando material; (8) confirmar permissões/estado antes de continuar. Luna não altera mesmo um gap aparentemente simples.

Revisão deve identificar versão revisada, cláusulas alteradas, origem/decisão e testes afetados. Mudança não autoriza implementação/publicação por si. Nesta versão DRAFT, o autor pode revisar dentro do escopo documental autorizado, sem fingir que novas decisões já foram aprovadas. Promoção para APPROVED é exclusiva do usuário.

## 22. SEMANTIC_GAPS e decisão necessária

Origem: confronto U §§3/5/7/10/11/12 com ARC/ENG/SPR/READY; PM-05. Classificação: **FATO** documental nas colunas evidência; **INFERÊNCIA** de bloqueio do contrato quando implementação exigiria escolha proibida; nenhuma dessas lacunas é resultado FAIL de runtime.

| GAP_ID | Evidência de ausência | Impacto / cláusulas | O que deve ficar decidido e materializado pelo autor antes de aprovação |
|---|---|---|---|
| CG-01 | ENG nomeia aiosqlite/Rich/pytest/Ruff sem versões/faixas | Stack e instalação; §§4/6/8/13/14 | Versão/faixa de cada dependência; origem da seleção e política de resolução compatível; não inventar versões |
| CG-02 | ARC diz que fluxo lógico não finaliza package layout; SPR requer estrutura válida sem manifest de paths | Escopo de escrita/import/testes/evidências; §§4/9/11/13 | Árvore mínima, namespace, arquivos e responsabilidades, path de instruções/evidência, separação unit/integration; somente componentes necessários a S0 |
| CG-03 | ENG fixa conceitos/local/precedência, sem chaves/defaults/ausência/validação exatos | Config e smoke; §§4/8/12/13/14 | Subconjunto de S0, chaves/seções/tipos/defaults, overrides realmente suportados, paths relativos, ausência/inválido/desconhecido e casos com resultados/códigos |
| CG-04 | SPR requer entrada mínima responsiva; AUD-LOW-01 registra CLI sem contrato completo | Integração/smoke Windows; §§4/8/13/14 | Invocação exata de S0, argumentos, stdout/stderr, exit codes e efeitos permitidos; uso de Rich/config sem operação de produto |
| CG-05 | ENG define pyproject/venv/ferramentas, sem backend, install command, reprodução ou perfil concreto | Ambiente reproduzível/package/pytest/Ruff; §§4/6/8/13/14 | Metadados mínimos, backend/faixa se requerido, instalação e artefato/procedimento de versões reproduzíveis, configuração de descoberta pytest/perfil Ruff, comandos Windows completos |

Todas as cinco linhas bloqueiam a executabilidade deste contrato. O autor precisa fechar esses dados com authority/decisão rastreável e submeter revisão; não delegar escolhas à implementação. Não se exige aqui contratar auth, schema, parser, download ou sync para resolvê-las.

**RECOMENDAÇÃO:** uma única revisão contratual focada em CG-01–05; pesquisar/validar versões apenas quando autorizado para essa atividade, decidir o mínimo de bootstrap, sem reabrir a arquitetura aprovada. `DEFERRED_NO_AUTHORITY` aplica-se a qualquer seleção ainda sem decisão válida, não a mudanças que o implementador possa tomar livremente.

## 23. Verificação de completude do contrato

Origem: U §§21–22; self-review do autor em DIRECT.

```text
S0_OBJECTIVE_CLOSED = SIM
S0_SCOPE_CLOSED = NÃO
S0_OUT_OF_SCOPE_CLOSED = SIM
STACK_CLOSED = NÃO
BOUNDARIES_CLOSED = SIM
SECURITY_BOOTSTRAP_CLOSED = SIM
TEST_CONTRACT_CLOSED = NÃO
ACCEPTANCE_CRITERIA_CLOSED = NÃO
DOD_CLOSED = NÃO
IMPLEMENTER_STOP_CONDITIONS_CLOSED = SIM
CHANGE_CONTROL_CLOSED = SIM
SEMANTIC_GAPS = CG-01, CG-02, CG-03, CG-04, CG-05
CONTRACT_STATUS = DRAFT_BLOCKED
IMPLEMENTATION_READY_UNDER_THIS_CONTRACT = NÃO
```

Objective/out-of-scope/boundaries/segurança/stops/change control estão explicitamente delimitados. Escopo físico, stack completa, comandos/testes/aceite e DoD concretos ainda dependem das cinco decisões identificadas. A presença de seções e tabelas não equivale a completude semântica. Nenhuma aprovação é inferida de READY ou de U autorizar a edição.

## 24. Registro da atividade documental e recuperação

Origem: U §§23–24; STATE; GOV/Continuity; VP-01; verificações read-only desta sessão.

Este é o registro histórico da autoria antes da autorização posterior de stage/commit. O checkpoint Git autorizado depois, com inclusão do pacote documental pendente, é registrado em STATE; não altera o status bloqueado ou aprova este contrato. A referência a texto procedural desatualizado nos §§1/24 descreve o estado encontrado durante a autoria; o bootstrap foi posteriormente reconciliado no checkpoint documental.

Escrita desta atividade: somente este contrato e registros estritamente necessários em `docs/governance/PROJECT_STATE.md` e `docs/governance/AUTHORITY_MAP.md`. Alterações preexistentes nos demais documentos devem permanecer byte a byte; nenhum código/dependência/ambiente de produto foi criado. Nada de governança externa foi escrito.

**Recuperação:** raiz `docs/`, Git factual verificado, sete pins e Continuity 3.0 conferidos por SHA-256; Registry global corresponde às versões adotadas, `GLOBAL_BASELINE_RELATION = CURRENT`; sem migração. A validação genérica Draft 2020-12 histórica é preservada em EVID; nesta sessão schema/hash e estrutura focal do binding foram conferidos, sem alegar reexecução genérica. O Python empacotado do aplicativo serviu somente a verificações documentais read-only; não comprova o CPython de produto nem SP-01.

**VP-01 aplicável read-only antes das edições:** PM-00/Registry e policies aplicáveis resolvidos; distinção draft/authority, readiness/autorização e estado/histórico demonstrada nas cláusulas anteriores. Cenários adversariais e justificativas:

| Cenário | Decisão validada |
|---|---|
| A/B | Volume/criticidade isolados não justificam tier superior ou agentes |
| C/D | Capability de subagente e falha localizada não autorizam spawn; execução permanece DIRECT |
| E/F | Ferramenta opcional não é obrigação; efeito externo exige autorização específica |
| G/H | Authority canônica prevalece sobre candidate; evidência prevalece sobre concordância automática |
| I/J | Escopo/Git capability não permitem expansão, staging, commit ou push |
| K/L | Módulo isolado não é DONE; integração incremental, sem big-bang no fim |
| M/N | Checkpoint exige estado descobrível; chat não substitui artifacts |
| O/P | Insuficiência do root exige reconfiguração autorizada; subagente forte não é workaround |
| Q/R | Se frontend exigido, backend desconectado não conclui capability; aqui frontend-first gráfico é NOT_APPLICABLE à CLI |

18/18 decisões adversariais acima aderem às authorities, sem executar as ações hipotéticas. Dry-run simples: mensagem de erro já contratada → edição bounded, DIRECT, menor capability suficiente, testes existentes, nenhum plugin/publicação. Dry-run S0: DoR/contrato/autorização → bootstrap → módulo → CLI/config integrada → fluxo local/regressão → reconciliação → handoff → decisão de fechamento. Nesta sessão o fluxo para antes de implementar devido aos gaps, comprovando aplicação fail-closed. Self-check: nenhum draft promovido, authority inventada, modelo trocado, subagente criado, produto implementado ou Git publicado. Validação não concede autorização e precedeu a escrita documental distinta autorizada por U.

```text
STATUS = BLOCKED
ACTIVITY_COMPLETION_PERCENT = 80%
COMPLETION_BASIS = 4 de 5 etapas documentais concluídas: recuperação; rastreabilidade; materialização do draft; self-review e registro do estado. A quinta etapa, fechamento semântico sem gaps e prontidão para revisão de aprovação, permanece bloqueada por CG-01–05. Percentual somente desta atividade, não de S0/projeto.
PROJECT_COMPLETION_PERCENT = 0% / 0 de 11 sprints aceitas; documentação fundacional não é medida por esse indicador.
DOCUMENT_STRUCTURE_AND_TRACEABILITY = PASS
LOCAL_LINKS = PASS
NEW_FILE_WHITESPACE = PASS
PROJECT_STATE_RECONCILIATION = PASS
PREEXISTING_DOCUMENT_PRESERVATION = PASS / 17 de 19 arquivos preexistentes idênticos por SHA-256; somente STATE e AUTHORITY_MAP atualizados nesta atividade.
FILES_CREATED = docs/contracts/S0_IMPLEMENTATION_CONTRACT.md
FILES_UPDATED = docs/governance/PROJECT_STATE.md; docs/governance/AUTHORITY_MAP.md
GIT_DIFF_CHECK = PASS / tracked; contrato novo também verificado separadamente, pois git diff padrão não inclui untracked.
S0_STARTED = NO
S0_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
git add = NÃO_EXECUTADO
git commit = NÃO_EXECUTADO
git push = NÃO_EXECUTADO
NEXT_REQUIRED_ACTIVITY = FECHAMENTO DE CG-01–05 PELO AUTOR SOL COM DECISÕES RASTREÁVEIS DO USUÁRIO; DEPOIS, REVISÃO E APROVAÇÃO EXPLÍCITA DO CONTRATO.
```

A reconciliação deste checkpoint significa tornar draft/gaps/ponto seguro descobríveis, não declarar a atividade integralmente concluída nem o handoff global PASS com texto procedural ainda desatualizado. A execução futura deverá recuperar STATE/mapa e resolver divergência documental material antes de implementar. O ponto seguro é revisar este draft bloqueado e fechar gaps; não executar S0.
