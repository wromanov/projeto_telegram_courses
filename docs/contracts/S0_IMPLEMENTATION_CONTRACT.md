# Contrato formal de implementação — S0

```text
DOCUMENT_ROLE = IMPLEMENTATION_CONTRACT
PROJECT_ID = projeto_telegram_courses
SPRINT_ID = S0
CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
CONTRACT_VERSION = 1.0
CONTRACT_INITIAL_STATUS = DRAFT
CONTRACT_STATUS = APPROVED
CONTRACT_APPROVAL = APPROVED_BY_USER
CONTRACT_SEMANTIC_STATE = FROZEN
CONTRACT_CLOSURE_VERIFICATION = PASS
CONTRACT_APPROVAL_READINESS = READY_FOR_USER_APPROVAL
USER_APPROVAL_DECISION = APPROVED
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

Este contrato v1.0 está APPROVED e semanticamente FROZEN após verificação final focada PASS e aprovação explícita do usuário. CG-01–05 e os nove findings dos §§26–27 estão fechados como especificação. O contrato governa S0 subordinado às authorities superiores; esta aprovação não autoriza a sprint. `S0_AUTHORIZED = NO` e `IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED`. Alteração futura necessária: STOP_AND_REPORT → SOL CONTRACT REVIEW → CONTRACT DELTA → nova aprovação quando material; o implementador não pode editar este contrato silenciosamente.

O cabeçalho e o §28 são o status corrente. Blocos de resultado nos §§24–27 registram checkpoints anteriores; seus status e próximos passos permanecem como fatos históricos e não substituem esta aprovação.

## 1. Origem, precedência e estado de entrada

As referências compactas usadas neste contrato são:

| Ref | Fonte / papel | Seções aplicáveis |
|---|---|---|
| U | Cards B do usuário: autoria inicial, fechamento de CG-01–05 e dois ciclos de correção contratual | Contrato primeiro, limites do implementador, testes, change control e Git; §§26–27 registram as correções |
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

U é a fonte das atividades de autoria: anexo inicial `d94b27af-126b-4487-b20b-339d8bf373b5/Texto colado.txt` e Card B de fechamento `6ba65121-7fd4-4247-9f22-9e79880053f6/Texto colado.txt`. O conteúdo operacional necessário fica neste contrato e em STATE, sem depender dos anexos para futura retomada.

O Card B de correção `16f378d7-565b-4fe9-bbc9-c3c6d6aa9762/Texto colado.txt` fornece os seis findings CONTRACT-HIGH-01 e CONTRACT-MED-01–05 e autoriza exclusivamente corrigi-los. Todos permaneciam aplicáveis no início: ausência de fail-fast executável, oracle parcial, exclusão divergente de pip, executáveis relativos/globais em T10, caches incompatíveis com efeitos nulos e omissão de `.venv-replay/` no §10. As alterações preexistentes de fechamento CG-01–05 foram preservadas; nenhuma dessas regiões já continha a correção dos seis findings. Entrada factual desta correção: `master`, HEAD `71fe536eed4edc81b1e5cd280f71e97d7c7a1160`, upstream `origin/master`, índice vazio e três documentos modificados (contrato, STATE e mapa). A tabela seguinte registra a entrada histórica do fechamento CG-01–05, não um worktree limpo nesta correção.

GOV resolve PM-00 1.0, PM-01 1.0, PM-02 1.7-R2.6, PM-03 1.7-R2.3, PM-04 1.2, PM-05 v1, VP-01 v2.0 e Continuity 3.0. PM-01 é owner de execução, DoR/DoD, continuidade e handoff; PM-05 rege independência analítica; VP-01 apenas valida. Este contrato especializa S0 e não altera governança externa.

| Fato de entrada | Resultado | Evidência / limite |
|---|---|---|
| Repo root | `C:\Users\walac\desenvolvimento\projeto_telegram_courses` | Git read-only nesta atividade |
| Branch / HEAD nesta revisão | `master` / `71fe536eed4edc81b1e5cd280f71e97d7c7a1160` | Git read-only; não é pin permanente da implementação futura |
| Upstream / origin | `origin/master` / `https://github.com/wromanov/projeto_telegram_courses.git` | Git local; nenhum fetch novo, sincronização remota atual não revalidada |
| Worktree / staging nesta revisão | Limpos; branch um commit à frente do upstream | Git read-only no início desta atividade; alterações posteriores são somente documentação autorizada |
| PROJECT_OPENING_GATE | PASS | OPEN e EVID |
| PROJECT_GOVERNANCE_BINDING | ACTIVE / VALIDATED registrado | EVID e STATE; binding lido nesta revisão, sem reexecução dos sete hashes |
| Schema do binding | PASS histórico | EVID; não revalidado nesta atividade documental de CG-01–05 |
| CONTINUITY_RECOVERY_GATE | PASS registrado | STATE e EVID; não implica autorização |
| VP01_VALIDATION | PASS / VALIDATION_ONLY histórico | OPEN/EVID e registro histórico do §24; não reexecutado nesta revisão |
| S0_READINESS / S0_BLOCKERS | READY_FOR_AUTHORIZATION / NENHUM na revisão anterior | READY, decisão preservada; não certifica completude deste contrato novo |
| S0_STARTED / S0_AUTHORIZED | NO / NO | STATE e Git/inventário sem produto |
| IMPLEMENTATION_AUTHORIZATION | NOT_GRANTED | STATE; U autoriza somente documentação |

**Reconciliação temporal explícita:** OPEN/EVID preservam `S0_READY = NO` no momento da abertura. READY e STATE posteriores registram prontidão para autorização. O contrato foi então criado com CG-01–05 abertos e agora recebeu as decisões documentais dos §§6, 9, 12, 13 e 22. Nenhum desses registros históricos é reescrito e não se presume aprovação de S0.

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

Antes de qualquer implementação futura, verificar conjuntamente: contrato aprovado e identificado por versão; zero gaps materiais; DoR predecessor válido; autorização explícita de S0 e escopo de escrita; estado Git factual conhecido. Falhar em qualquer requisito impede bootstrap, instalação ou código. A aprovação futura não pode delegar a Luna eventuais novos gaps implicitamente.

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
| `pyproject.toml` | Metadados/install do projeto, requisito CPython, dependências-base, pytest/Ruff | Valores e seções fechados nos §§6/22.5 |
| Ambiente virtual | `venv`, interpretador do ambiente utilizado em todas as validações | `.venv/` é o path protegido já nomeado por SPR; não usar instalações globais como substituto da prova |
| Package Python e estrutura de testes | Import do projeto funcional; testes offline e integração separados | Manifest físico fechado no §22.2; não criar componentes futuros por antecipação |
| Configuração-base | `config/settings.toml`, carregamento mínimo, segredos separados | Esquema e semântica fechados no §22.3 |
| Entrada mínima CLI | Resposta local com Rich; integração com configuração básica | Comando, argumentos, saída e códigos fechados no §22.4 |
| `.gitignore` | Todas as exclusões do §10, sem exceção que permita secrets/sessões | Verificar antes de primeiro commit; commit continua sem autorização |
| Instruções de desenvolvimento | Ambiente Windows, instalação aprovada, import, teste, lint, config e CLI | `docs/development/S0_SETUP.md` e comandos do §22.5; sem credenciais ou login |
| Evidência SP-01 | Ambiente exato, versões resolvidas, ações/saídas sanitizadas e PASS/FAIL | `docs/engineering/evidence/SP01_STACK_WINDOWS.md`; formato mínimo no §8 |

Não há entrega autônoma obrigatória de logging operacional em arquivos, modelos de domínio, gateways, parsers ou repositórios em S0. Rich e as regras de não exposição aplicam-se à entrada mínima. Um skeleton só poderá ser criado se seu arquivo e responsabilidade constarem do manifest contratual fechado; a mera existência do componente na arquitetura alvo não basta.

`S0_SCOPE_CLOSED = SIM`: o conjunto funcional, manifest físico e interfaces mínimas estão definidos no §22. Isso é especificação para revisão, não autorização de escrita de implementação.

## 5. Fora de escopo

Origem: SPR S0–S10; ARC ADRs; U §4.

São proibidos em S0: autenticação Telegram; sessão Telegram real; listagem/resolução de canais; scanner; parser RASMOO; GenericParser funcional; catálogo persistente de produção; schema/migrations definitivos de S2; download de mídia; resume; sync incremental; workers operacionais; FloodWait/retry operacional; GUI; TDLib; empacotamento final/executável Windows; qualquer funcionalidade de S1+.

Instalar e importar uma biblioteca em SP-01 não autoriza criar cliente, conectar rede Telegram ou implementar seu adapter. O smoke SQLite temporário não entrega persistência de produto. Não criar versões vazias de APIs futuras que congelem assinaturas ainda deferidas, nem comandos de produto simulando sucesso.

## 6. Stack contratual

Origem: ARC Product shape / ADR-001/003/006; ENG Runtime and toolchain; READY SP-01; U §5.

`PYTHON_REQUIRES = >=3.14,<3.15` em metadata; a implementação aceita **somente CPython 3.14.x padrão com GIL no Windows 11 x86-64**. `requires-python` não discrimina implementação/ABI, por isso SP01-01 deve fazê-lo. Política: limites inferior inclusivo e superior exclusivo dentro da linha aprovada; nenhuma resolução `latest` irrestrita. A resolução inicial é registrada com versões exatas e reaplicada por constraints no §22.5. Atualização de linha/faixa requer revisão contratual.

| Nome | Tipo | Faixa contratual | `Requires-Python` publicado | CP314 / Windows 11 x64: base documental | Motivo e obrigatória em S0 |
|---|---|---|---|---|---|
| Telethon | RUNTIME | `>=1.45,<1.46` | `>=3.5` | wheel `py3-none-any`; execução conjunta pendente SP-01 | ADR-001/ENG, instalar/importar; **SIM** |
| cryptg | RUNTIME | `>=0.6,<0.7` | `>=3.11` | wheel `cp314-cp314-win_amd64` publicado; execução pendente SP-01 | ADR-001/ENG, instalar/importar; **SIM** |
| aiosqlite | RUNTIME | `>=0.22.1,<0.23` | `>=3.9` | wheel `py3-none-any`; execução pendente SP-01 | ADR-003/ENG, round-trip local; **SIM** |
| Rich | RUNTIME | `>=15.0,<16` | `>=3.9` | classificador 3.14/Windows e wheel universal; execução pendente SP-01 | ADR-006/ENG, console do smoke; **SIM** |
| pytest | DEVELOPMENT | `>=9.1.1,<9.2` | `>=3.10` | classificador 3.14/Windows e wheel universal; execução pendente SP-01 | ENG/SPR, suíte offline; **SIM** |
| Ruff | DEVELOPMENT | `>=0.16.10,<0.17` | `>=3.7` | wheel Windows x64 e alvo `py314`; execução pendente SP-01 | ENG/SPR, lint; **SIM** |
| setuptools | BUILD | `==84.0.0` | `>=3.10` | wheel universal e backend PEP 517/660; execução pendente SP-01 | backend mínimo; pin exato necessário para repetição do build isolado; **SIM** para build, não é runtime |

`asyncio`, `sqlite3` e `tomllib` vêm da stdlib de CPython 3.14 e não são dependências pip. SQLite exato será registrado em SP-01. Os pisos refletem releases oficiais verificadas em 2026-10-05; os tetos evitam avanço de linha sem revisão. Fontes primárias: [Telethon 1.45](https://pypi.org/project/Telethon/1.45.0/), [cryptg 0.6](https://pypi.org/project/cryptg/0.6.0/), [aiosqlite 0.22.1](https://pypi.org/project/aiosqlite/0.22.1/), [Rich 15](https://pypi.org/project/rich/15.0.0/), [pytest 9.1.1](https://pypi.org/project/pytest/9.1.1/), [Ruff 0.16.10](https://pypi.org/project/ruff/0.16.10/), [setuptools 84](https://pypi.org/project/setuptools/84.0.0/). `CONTRACTUAL_COMPATIBILITY = EXPECTED_FROM_METADATA`; `RUNTIME_COMPATIBILITY = NOT_EXECUTED`, sujeita a SP-01.

## 7. Sequência futura autorizável

Origem: SPR S0; GOV/PM-01 §§3, 6–8, 12; U.

Esta sequência é especificação futura, não comandos autorizados nesta atividade:

1. Confirmar aprovação do contrato sem gaps, DoR, autorização de S0 e permissões separadas de Git.
2. Conferir repo/root/branch/HEAD/upstream/worktree; inventariar e preservar alterações preexistentes.
3. Materializar exclusões antes de manipular artefatos sensíveis e antes de qualquer commit; não produzir sessão/segredo.
4. Criar somente manifest físico aprovado, metadados, configuração e entrada CLI mínima.
5. Selecionar CPython dentro de `3.14.x`, criar `.venv/` e instalar somente o conjunto aprovado pelo procedimento do §22.5.
6. Executar SP-01; registrar versões e resultados. Falha não autoriza troca de stack.
7. Executar testes/lint e fluxo acumulado da CLI/configuração; revisar boundaries/escopo.
8. Registrar aceite/DoD, reconciliar documentação/STATE e preparar handoff para decisão do usuário. Não iniciar S1 nem publicar Git automaticamente.

## 8. SP-01 — Stack Windows

Origem: READY Spikes; SPR Future sprint entry conditions / SP-01; AUD-MED-07; REQ NFR-01.

**Objetivo:** comprovar que a stack selecionada é materializável no ambiente Windows alvo, sem Telegram real. Precondições: contrato completo/aprovado e S0 autorizada; Windows com CPython permitido; dependências/metadados/comandos aprovados. Acesso a repositório de pacotes, se necessário, serve somente à instalação autorizada; o smoke e a suíte não requerem rede Telegram.

| Passo | Ação futura | Resultado binário esperado |
|---|---|---|
| SP01-01 | Executar integralmente o oracle do §8.2 no Python selecionado | Windows 11; AMD64/x64 e processo 64 bits; CPython estável `>=3.14,<3.15`, build padrão e GIL habilitado; exit 0 e JSON registrado |
| SP01-02 | Criar `.venv/` e invocar diretamente seu interpretador | Criação/execução exit 0; `sys.prefix != sys.base_prefix`; path pertence ao venv do projeto |
| SP01-03 | Instalar projeto/dependências pelo §22.5 e verificar consistência do ambiente | Exit 0, conjunto aprovado instalado; nenhuma dependência obrigatória omitida |
| SP01-04 | Importar `telethon`, `cryptg`, `aiosqlite`, `rich`, `pytest` e package aprovado | Imports exit 0 sem cliente Telegram ou efeitos de produto |
| SP01-05 | Executar pytest e Ruff usando esse ambiente | Versões registradas; suíte e lint exit 0, sem ignorar falhas |
| SP01-06 | Rodar corrotina local com `asyncio.run`, retornando sentinela definida pelo teste | Resultado igual à sentinela e exit 0; sem rede |
| SP01-07 | Abrir SQLite em memória, ler/escrever sentinela e fechar | Round-trip correto; `sqlite3.sqlite_version` registrado; zero banco de produção |
| SP01-08 | Executar smoke aiosqlite temporário e fechar conexão | Round-trip correto e exit 0; nenhum schema de produto |
| SP01-09 | Executar fluxo mínimo de configuração/CLI dos §§22.3/22.4 | Valores, saída e exit codes correspondem ao contrato fechado |
| SP01-10 | Registrar versões completas e repetir procedimento documentado em venv separado | Mesmas versões registradas de projeto/base/transitivas; suite/lint/smoke aprovados |

SQL dos passos 07/08 é um probe de validação isolado, em memória/temporário, em `tests/integration/test_stack_local.py`, não SQL de aplicação. Não abre exceção de SQL no domínio, parser ou CLI.

**Evidência mínima:** Windows/arquitetura; path do interpretador; CPython e SQLite exatos; versões de todas as dependências/base/transitivas e ferramentas de instalação usadas; comandos concretos, exit codes, resultados e data/fuso; nenhum dump de ambiente ou segredo. Evidência versionável descreve o ambiente, sem incluir `.venv/`, banco, logs brutos ou material de sessão.

```text
SP01_RESULT = PASS | FAIL
SP01_EXECUTION_IN_THIS_ACTIVITY = NÃO_EXECUTADO
```

PASS exige todos os passos. Qualquer falha resulta FAIL e stop. Falta de evidência não pode ser convertida em PASS. S0 não conclui com SP-01 FAIL ou não executado.

### 8.1 SP01_FAIL_FAST — único mecanismo de invocação

`SP01_FAIL_FAST = REQUIRED`. Todo comando externo do SP-01, inclusive launcher, pip, pytest, Ruff, probes, CLI e replay, passa por `Invoke-S0Native`; não executar chamadas nativas avulsas nem pipelines que ocultem seu código. Os comandos resumidos em outras seções designam os mesmos executáveis/argumentos e devem ser envolvidos por este helper. Executar o procedimento inteiro em um único bloco `try/catch`, na ordem contratada. Este código é especificação documental futura, não novo arquivo de implementação:

```powershell
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$Sp01Result = 'PENDING'
$Sp01Step = 'SP01-PREFLIGHT'
$Sp01Failure = $null
$Sp01Events = [System.Collections.Generic.List[object]]::new()
$Sp01NativeResults = [System.Collections.Generic.List[object]]::new()
function Invoke-S0Native {
    param([string]$Step, [string]$Executable, [string[]]$Arguments)
    $script:Sp01Step = $Step
    $script:Sp01Events.Add([pscustomobject]@{step=$Step; event='STEP_START'})
    $Native = (Get-Command -Name $Executable -CommandType Application -ErrorAction Stop).Source
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $Native
    $StartInfo.WorkingDirectory = (Get-Location).ProviderPath
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true
    $StartInfo.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $StartInfo.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
    foreach ($Argument in $Arguments) { $StartInfo.ArgumentList.Add($Argument) }
    $Process = [System.Diagnostics.Process]::new()
    $Process.StartInfo = $StartInfo
    try {
        if (-not $Process.Start()) { throw 'native process did not start' }
        $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
        $StderrTask = $Process.StandardError.ReadToEndAsync()
        $Process.WaitForExit()
        $Code = $Process.ExitCode
        $Stdout = $StdoutTask.GetAwaiter().GetResult()
        $Stderr = $StderrTask.GetAwaiter().GetResult()
    } finally {
        $Process.Dispose()
    }
    $Captured = [pscustomobject]@{exit_code=$Code; stdout=$Stdout; stderr=$Stderr}
    $script:Sp01NativeResults.Add([pscustomobject]@{step=$Step; result=$Captured})
    $script:Sp01Events.Add([pscustomobject]@{step=$Step; event='CAPTURE_EXIT_CODE'; exit_code=$Code})
    if ($null -eq $Code -or $Code -ne 0) {
        $script:Sp01Result = 'FAIL'
        $script:Sp01Failure = [pscustomobject]@{
            step=$Step; kind='NATIVE_EXIT'; exit_code=$Code
        }
        throw 'SP01 native failure'
    }
    return $Captured
}
try {
    # Inserir aqui, em ordem, TODOS os passos dos §§8.2/22.5.
    # Atualizar $Sp01Step antes de ações PowerShell ou validações de oracle.
    # Somente após todos os passos e comparações: $Sp01Result = 'PASS'.
} catch {
    $Sp01Result = 'FAIL'
    if ($null -eq $Sp01Failure) {
        $Sp01Failure = [pscustomobject]@{
            step=$Sp01Step; kind='POWERSHELL_TERMINATING_ERROR'; exit_code=$null
        }
    }
    # Preservar o registro sanitizado definido abaixo antes de encerrar.
    throw 'SP01_RESULT=FAIL; dependent steps not executed'
}
```

Alvo deste procedimento: PowerShell 7, com versão exata registrada. `NATIVE_COMMAND_CAPTURE_STRATEGY = SYSTEM_DIAGNOSTICS_PROCESS_SEPARATE_ASYNC_STREAMS`. Usar exclusivamente o helper acima: argumentos individuais por `ArgumentList`, cwd atual do procedimento e ambiente herdado; nenhuma shell intermediária. Ler os dois streams assincronamente antes de esperar o processo evita bloqueio por buffers cheios. `Process.ExitCode`, capturado após `WaitForExit`, é a authority nativa; `$LASTEXITCODE` e preferências de execução nativa do shell não governam este mecanismo. Capturar UTF-8 sem combinar ou reescrever os streams; JSON contratado contém nomes/versões ASCII. O retorno de sucesso é um único objeto `NATIVE_COMMAND_RESULT = exit_code + stdout + stderr`; toda validação de saída usa exclusivamente `.stdout`. A lista em memória `Sp01NativeResults` preserva os três campos por passo, inclusive em exit não zero; não imprimir nem persistir a lista bruta. Não usar `2>&1` ou concatenação de streams. `exit_code=0` com diagnóstico em stderr é sucesso nativo; parsing/oracle ainda pode falhar. Exit não zero registra `NATIVE_EXIT` e lança `throw`, impedindo passos dependentes. Erro de resolução/início/leitura/parsing/oracle é `POWERSHELL_TERMINATING_ERROR` no catch externo, sem inventar exit code. `Dispose` apenas libera o objeto de processo; não executa etapa dependente. Cmdlets usam `ErrorActionPreference=Stop`; oracle inválido exige `throw`, nunca fallback.

`FAILURE_EVIDENCE`: antes de encerrar, o executor preserva em `docs/engineering/evidence/SP01_STACK_WINDOWS.md` `SP01_RESULT=FAIL`, passo, tipo, código nativo ou `NOT_AVAILABLE`, data/fuso, comando contratual identificado e sequência de eventos até a falha; todos os passos seguintes ficam `NOT_EXECUTED_DEPENDENCY_FAILED`. Usar somente projeções sanitizadas de saídas (oracle esperado/observado e versões); não persistir `$Captured`, exceção/stack trace ou stderr bruto de instalação. Caso a própria gravação falhe, entregar os mesmos campos sanitizados ao usuário e classificar `EVIDENCE_WRITE=FAIL`; o procedimento permanece interrompido. Não executar etapas em `finally`, retomar após `catch` ou sobrescrever FAIL por PASS.

Oracle futuro de fail-fast, parte de S0-T08: com o Python S0, chamar o helper com `Arguments=@('-c','import sys; sys.exit(7)')` e passo sintético `SP01-FAILFAST-NATIVE`; na instrução seguinte do mesmo `try`, atribuir um marcador em memória. Exigir `SP01_RESULT=FAIL`, `kind=NATIVE_EXIT`, `exit_code=7`, marcador não atribuído e nenhum STEP_START posterior. Em execução isolada adicional, `throw 'synthetic PowerShell failure'` antes do marcador deve produzir `kind=POWERSHELL_TERMINATING_ERROR`, código `NOT_AVAILABLE` e marcador não atribuído. São ensaios negativos controlados do mecanismo: suas falhas esperadas não são PASS de um SP-01 real; não incluem instalação nem deixam artefato de produto. Reinicializar os registros antes do SP-01 efetivo.

Oracle positivo adicional obrigatório de S0-T08, em ensaio isolado: `Arguments=@('-c','import sys; print("[{\"name\":\"probe\",\"version\":\"1.0\"}]"); print("s0 diagnostic", file=sys.stderr)')`. Exigir retorno `exit_code=0`, `.stdout` contendo somente o JSON e newline, `.stderr` contendo somente `s0 diagnostic` e newline; `ConvertFrom-Json` aplicado a `.stdout` produz o par probe/1.0 e o marcador seguinte é executado. A lista em memória mantém o diagnóstico separado; a evidência deste ensaio sintético pode registrar o texto conhecido e não sensível. Caso isolado adicional com stdout `not-json`, stderr diagnóstico e exit 0 deve falhar no `ConvertFrom-Json`, cair no catch como `POWERSHELL_TERMINATING_ERROR` e não executar o marcador; não chamar isso de falha nativa. Reinicializar eventos, resultados, falha e status entre ensaios e antes do SP-01 real. SP01-10/T08/T11/A08 e DoD exigem esses oracles e parsing separado nos dois inventários de constraints.

Fontes primárias: [Microsoft — ArgumentList](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.processstartinfo.argumentlist), [Microsoft — leitura dos streams e deadlock](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.standardoutput).

### 8.2 SUPPORTED_ENVIRONMENT_ORACLE

Antes de criar o primeiro venv, resolver `$PyLauncher = (Get-Command py -CommandType Application -ErrorAction Stop).Source`. Usar o helper para `py -3.14 -c 'import sys; print(sys.executable)'`, exigir uma única linha com arquivo absoluto existente e fixar esse path em `$PythonBase`. Não usar novamente a seleção variável do launcher para criar/repetir ambientes: `$PythonBase` cria ambos, garantindo o mesmo patch. Rodar este mesmo oracle no base, `$PyS0` e `$PyReplay`; no base somente a exigência de venv não se aplica:

```powershell
$EnvironmentOracle = @'
import json, platform, struct, sys, sysconfig
gil_check = getattr(sys, '_is_gil_enabled', None)
gil = gil_check() if callable(gil_check) else None
facts = {
    'system': platform.system(), 'windows_release': platform.win32_ver()[0],
    'windows_version': platform.win32_ver()[1],
    'architecture': platform.machine().upper(), 'pointer_bits': struct.calcsize('P') * 8,
    'implementation': platform.python_implementation(),
    'version': platform.python_version(), 'releaselevel': sys.version_info.releaselevel,
    'gil_enabled': gil, 'free_threaded_build': sysconfig.get_config_var('Py_GIL_DISABLED') == 1,
    'executable': sys.executable, 'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
}
print(json.dumps(facts, sort_keys=True))
ok = (facts['system'] == 'Windows' and facts['windows_release'] == '11'
      and facts['architecture'] in ('AMD64', 'X86_64') and facts['pointer_bits'] == 64
      and facts['implementation'] == 'CPython' and (3, 14) <= sys.version_info[:2] < (3, 15)
      and facts['releaselevel'] == 'final' and gil is True and not facts['free_threaded_build'])
sys.exit(0 if ok else 1)
'@
Invoke-S0Native -Step 'SP01-01-BASE' -Executable $PythonBase -Arguments @('-c', $EnvironmentOracle)
```

`EXPECTED_RESULT`: exit 0, uma linha JSON contendo exatamente os campos acima; `system=Windows`, `windows_release=11`, `architecture=AMD64|X86_64`, `pointer_bits=64`, `implementation=CPython`, versão estável `3.14.<patch>`, `gil_enabled=true`, `free_threaded_build=false`; versão Windows e paths reais registrados. API ausente/erro, GIL false/null, build free-threaded, Windows 10/Server, ARM64, processo 32 bits ou qualquer outra divergência = SP-01 FAIL/incompatível, com interrupção pelo §8.1. Não inferir GIL do nome do executável. Não usar `assert` removível por modo otimizado.

`GIL_CHECK_COMMAND = Invoke-S0Native -Step 'SP01-01-GIL' -Executable $PyS0 -Arguments @('-c', 'import sys; print(sys._is_gil_enabled()); sys.exit(0 if sys._is_gil_enabled() is True else 1)')`; `EXPECTED_RESULT = stdout True + newline, exit 0`. Repetir no replay com `$PyReplay`. Ausência da API causa exit não zero e FAIL. O oracle composto também confere o estado antes de importar bibliotecas de terceiros.

Em SP01-02/S0-T01, exigir adicionalmente, por comparação de paths absolutos normalizados Windows sem diferenciar caixa, `executable=$PyS0`, `prefix=$VenvRoot`, `prefix != base_prefix`; no replay, `executable=$PyReplay`, `prefix=$VenvReplayRoot`, base_prefix e versão iguais aos iniciais. Paths divergentes = erro de oracle e stop. Os testes usam os mesmos predicados, sem inventar outro critério de ambiente. Fontes: [CPython — sys._is_gil_enabled](https://docs.python.org/3.14/library/sys.html#sys._is_gil_enabled), [sysconfig](https://docs.python.org/3.14/library/sysconfig.html#sysconfig.get_config_var), [platform](https://docs.python.org/3.14/library/platform.html) e [mapeamento Windows 11 no CPython 3.14](https://github.com/python/cpython/blob/3.14/Lib/platform.py).

## 9. Estrutura e responsabilidades

Origem: ARC High-level component flow e Boundaries; ENG Configuration contract; SPR S0; U §7.

ARC declara expressamente que seu diagrama lógico **não é layout final de pacotes**. O layout mínimo de S0 e as responsabilidades estão fechados no §22.2 como decisão deste contrato, sem criar skeleton dos componentes futuros.

| Diretório/local | Responsabilidade | PODE_CONTER | NÃO_PODE_CONTER |
|---|---|---|---|
| Root existente | Metadados e controles do projeto | `pyproject.toml`, `.gitignore`, instruções que forem aprovadas | Secrets/sessões; executável final; mudanças de governança externa |
| `src/telegram_courses/` | Entrada mínima/configuração e package importável | Arquivos expressamente aprovados no manifest §22.2 | Comportamentos S1+ ou infraestrutura em lógica pura |
| `tests/unit/` e `tests/integration/` | Unitários offline e integração local separados | Smokes, fixtures sintéticas, probes temporários | Login, sessão/credenciais reais ou download |
| `config/` | Configuração não sensível | `settings.toml` básico do §22.3 | API hash, códigos, senha, session string |
| `docs/` existente | Authorities, instruções e evidências | Documentação de S0; contrato em `docs/contracts/` | Bancos, logs brutos, secrets ou cópia modificada de governança externa |
| `.venv/` local, excluído | Ambiente de desenvolvimento | Runtime/dependências locais autorizados | Arquivos versionados ou prova substitutiva do contrato |
| `data/session/`, `logs/`, `venv/` | Paths de exclusão | Somente futuros artefatos locais quando autorizados | Obrigação de criar agora ou incluir no Git |
| `data/` genérico | Não há entrega de dados de produto em S0 | Nada de produto obrigatório nesta sprint | Catálogo/schema final, sessão ou mídia criada pelo bootstrap |

Nomear um path em `.gitignore` não determina sua criação. Não criar diretórios vazios/placeholders sem necessidade expressa no manifest. `src/telegram_courses/`, `tests/unit/` e `tests/integration/` são decisões fechadas somente para os arquivos de S0 expressos no §22.2.

## 10. Segurança do bootstrap

Origem: REQ NFR-05/06; ENG Configuration/Logging; SPR S0; READY exclusões; U §9; AUD-MED-06.

### 10.1 GIT_EXCLUSION_CONTRACT

Esta tabela é a fonte única de patterns obrigatórios de `.gitignore`, do manifest e de S0-T07. Materializar cada pattern abaixo em linha própria, sem regra negativa que reinclua qualquer probe. `.venv-replay/` já era obrigatório pelo replay; os demais patterns são preservados do contrato anterior. A coluna probe define o conjunto exato de entradas sintéticas, sem criar esses arquivos.

| PATTERN obrigatório | PROBE sintético |
|---|---|
| `.env` | `.env` |
| `.env.*` | `.env.s0-probe` |
| `*.session` | `s0-probe.session` |
| `*.session-journal` | `s0-probe.session-journal` |
| `data/session/` | `data/session/s0-probe.txt` |
| `.venv/` | `.venv/s0-probe.txt` |
| `.venv-replay/` | `.venv-replay/s0-probe.txt` |
| `venv/` | `venv/s0-probe.txt` |
| `__pycache__/` | `src/telegram_courses/__pycache__/s0-probe.pyc` |
| `.pytest_cache/` | `.pytest_cache/s0-probe.txt` |
| `.ruff_cache/` | `.ruff_cache/s0-probe.txt` |
| `logs/` | `logs/s0-probe.txt` |
| `*.log` | `s0-probe.log` |
| `*.egg-info/` | `src/projeto_telegram_courses.egg-info/PKG-INFO` |

`venv/` também vem de U e protege ambiente alternativo; o ambiente de prova permanece `.venv/`. `.env.*` inclui exemplos com esse nome: não abrir exceção silenciosa. O arquivo não cria suporte a dotenv; não adicionar essa dependência por causa da exclusão.

S0-T07: primeiro conferir que todas as 14 linhas PATTERN existem literalmente no `.gitignore`. Resolver Git como executável absoluto e, da raiz do checkout, executar `git check-ignore --no-index --verbose --stdin`, passando todas as linhas PROBE acima por stdin, uma por linha, com newline final. Exigir exit 0 e exatamente 14 registros; em cada registro, origem `.gitignore`, pattern e path devem coincidir com a linha correspondente (ordem de saída não importa; nenhuma duplicata ou ausência). Um pattern mais amplo que ignore um probe não substitui a presença e correspondência do pattern obrigatório. Usar `subprocess.run` no teste com `input`, `text=True`, `capture_output=True`, `check=False`, sem depender de shell/ativação. Inspecionar separadamente `git ls-files --cached --ignored --exclude-from=<RepoRoot>/.gitignore`: exigir exit 0 e stdout vazio; nenhuma entrada rastreada pode casar com qualquer pattern obrigatório, pois ignore não remove arquivo já rastreado. Encontrar material sensível real exige stop; não apagar, imprimir, fazer staging ou reescrever histórico automaticamente.

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

**CG-03 fechado no §22.3:** S0 materializa somente `[logging].level`; a política de fontes, ausência, validação e erros está explícita ali. Configurações de download, banco e sessão continuam conceituais para sprints posteriores e não podem ser preenchidas pelo implementador de S0. Ler config não pode criar sessão, diretório de mídia ou catálogo de produto.

Não adicionar framework de configuração, dotenv, broker ou web. Logging completo em arquivos não é entregável autônomo de S0; caso o smoke emita diagnóstico, não conter secrets. Preservar shape futuro timestamp/level/component/event/context e proibições de API hash, código, senha 2FA e conteúdo/string de sessão. Não antecipar rotação/retenção ou retry.

## 13. Contrato de testes

Origem: SPR S0; ENG Test strategy; REQ NFR-01/05/08/09/10; U §11.

Todos os testes abaixo são obrigatórios na futura execução, sem login, rede Telegram ou credenciais. `<PY_VENV>` designa o interpretador de `.venv/` verificado no SP-01, não um comando global. Os cinco gaps de especificação estão fechados no §22; execução e aprovação continuam pendentes.

| TEST_ID | OBJETIVO | PRECONDIÇÃO | AÇÃO futura | RESULTADO_ESPERADO | EVIDÊNCIA |
|---|---|---|---|---|---|
| S0-T01 | Runtime correto | S0 autorizada; CPython permitido disponível | Executar exatamente oracle e comparações de paths do §8.2 no base, S0 e replay | Windows 11, AMD64/x64/64 bits, CPython estável `>=3.14,<3.15`, GIL true e build padrão; paths/prefixes corretos; exit 0 | JSON e probe GIL sanitizados SP01-01/02 |
| S0-T02 | Imports mínimos | CG-01/05 fechados; instalação SP01-03 concluída | Importar telethon/cryptg/aiosqlite/rich/pytest em processo do venv sem inicializar clientes | Exit 0; versões de distribuições na faixa aprovada | Saída e lista completa de versões |
| S0-T03 | pytest funcional | Manifest CG-02 e descoberta CG-05 definidos; pelo menos um teste real de smoke | Executar `<PY_VENV> -m pytest` pela configuração aprovada | Coleta não vazia; zero falhas/erros; exit 0; sem Telegram | Relatório de coleta/resultado; não aceitar exit de zero testes |
| S0-T04 | Ruff funcional | Perfil §22.5 fechado; código/testes presentes | Executar `<PY_VENV> -m ruff --version` e `<PY_VENV> -m ruff check src tests` | Versão aprovada; lint exit 0; não excluir código/testes para ocultar erros | Versão, regras/configuração e resultado |
| S0-T05 | Package/import do projeto | Namespace e método instalação CG-02/05 fechados | Instalar pelo procedimento fechado; importar namespace e verificar origem em processo novo | Exit 0; import resolve package deste checkout, sem injeção ad hoc de path | Comando de instalação/import e path de origem |
| S0-T06 | Estrutura/boundaries | CG-02 fechado; implementação disponível | Comparar EXPECTED_SOURCE_MANIFEST com arquivos; verificar metadata gerado pelo §22.2.1 e inspecionar boundaries §11 | Todos os arquivos autorizados presentes; zero violações/antecipações S1+ | Matriz arquivo → responsabilidade/imports; deltas de escopo |
| S0-T07 | Proteção estrutural | `.gitignore` materializado antes de commit | Verificar integralmente GIT_EXCLUSION_CONTRACT §10.1: 14 patterns/probes, inclusive replay; inspecionar rastreados e superfícies novas | 14/14 correspondências, nenhuma entrada rastreada excluível; zero secrets/sessões em fixtures/config/evidência | Pattern/path/exit e revisão sanitizada, sem imprimir secrets |
| S0-T08 | SP-01 Windows | Todos os gaps fechados; ambiente/meta/base configurados | Conferir ensaios negativos e positivo JSON/stderr §8.1; executar SP01-01–10 e replay §22.5 | Mecanismo interrompe ambos os tipos de falha; SP-01 efetivo todo PASS; constraints e reprodução iguais | Eventos fail-fast e registro completo SP-01 |
| S0-T09 | Configuração-base | CG-03 e integração CLI CG-04 fechados | Exercitar matriz completa e overrides §22.3 no loader e CLI, incluindo vazio/sem seção/sem chave | Valores/saídas/códigos exatamente conforme casos fechados; nenhum efeito de produto | Casos entrada/saída por campo e relatórios |
| S0-T10 | Entrada CLI Windows | CG-04 fechado; package/config integrados | Invocar comando/argumentos mínimos aprovados no venv | Resposta e exit codes contratados; sem exigir credenciais ou conectar Telegram | Comando, saída, exit e estado local observado |
| S0-T11 | Documentação/regressão | Manifest e comandos fechados; entregáveis presentes | Seguir instruções em ambiente separado; comparar documentos preexistentes com baseline e deltas autorizados | Reprodução PASS; documentos preservados salvo reconciliação autorizada; sem produto anterior para regredir | Evidência de reprodução, inventário e diff documental |

Corrotina e round-trip SQLite/aiosqlite de SP-01 devem executar e conferir resultados, não apenas importar stdlib. O critério de boundary pode ser inspeção documentada; não exige introduzir ferramenta extra de arquitetura. Testes da configuração devem distinguir comportamento esperado de mera cópia da implementação.

`TEST_CONTRACT_CLOSED = SIM` como especificação: §22 fixa as entradas e resultados exigidos por T02–T11. Os testes não foram executados nesta atividade documental.

## 14. Critérios binários de aceite

Origem: SPR S0 acceptance; READY; U §12. Resultado de cada critério: PASS ou FAIL. Não executado/sem evidência impede PASS, sem alegar que a implementação inexistente foi testada e falhou.

| ACCEPTANCE_ID | PASS somente se | Testes / evidência |
|---|---|---|
| S0-A01 | Root/branch/HEAD/upstream e worktree/staging conhecidos; repo existente preservado | Preflight Git e inventário |
| S0-A02 | `pyproject.toml` existe, usa decisões aprovadas CG-01/05 e instala conjunto aprovado em venv | T01/02/05/08/11 |
| S0-A03 | Todos os arquivos obrigatórios do manifest CG-02 existem e package importa deste checkout | T05/06 |
| S0-A04 | pytest coleta testes de S0 e conclui sem erro, exit 0 | T03 |
| S0-A05 | Ruff aprovado verifica código/testes e retorna exit 0 | T04 |
| S0-A06 | Configuração-base atende matriz de seis casos e precedência §22.3, com indicador de arquivo carregado estável | T09 |
| S0-A07 | Entrada CLI do venv absoluto executa na raiz e em cwd temporário, com saída/códigos CG-04 e matriz de config §22.3, e zero mutação sob §22.4.1 | T10A–E; oracle de filesystem |
| S0-A08 | Fail-fast e separação stdout/stderr demonstrados; SP01-01–10 PASS; ambiente completo §8.2, SQLite e versões registrados; constraints/replay §22.5 comprovados | T01/08/11 |
| S0-A09 | Todos os 14 patterns/probes de GIT_EXCLUSION_CONTRACT passam, inclusive `.venv-replay/`; nenhum arquivo rastreado casa com as exclusões e nenhum secret/sessão real entra em novos artefatos | T07 |
| S0-A10 | Zero violações de boundary; zero funcionalidades S1+ antecipadas | T06 e revisão integral do delta |
| S0-A11 | Instruções/evidências no path fechado; documentação e STATE reconciliados; handoff descobrível | T11, §15 e PM-01 |
| S0-A12 | Contrato aprovado e zero gaps materiais, incluindo CG-01–05; autorização da sprint verificável | Aprovações, STATE e checklist §23 |

`ACCEPTANCE_CRITERIA_CLOSED = SIM` como especificação após o fechamento verificável de CG-01–05 no §22. Isso não afirma que qualquer critério de implementação já passou.

## 15. Definition of Done e fechamento

Origem: SPR S0 DoD/Gates; GOV/PM-01 §§3, 7, 12; U §13.

S0 somente poderá ser considerada tecnicamente concluída se todos os entregáveis do EXPECTED_SOURCE_MANIFEST existirem e metadata local atender §22.2.1, T01–T11 e A01–A12 passarem, SP-01 passar, boundaries/segurança/escopo estiverem íntegros, nenhum gap material permanecer e os gates aplicáveis abaixo possuírem evidência:

| Gate | Evidência futura requerida |
|---|---|
| MODULE_GATE | Smokes de runtime, imports, config e package aprovados |
| INTEGRATION_GATE | Entrada CLI usa package/configuração reais do bootstrap no venv |
| ACCUMULATED_FLOW_GATE | Fluxo local completo ambiente → instalação → config/import → CLI → testes/lint PASS |
| REGRESSION_GATE | Documentação/fatos preexistentes preservados; repetição em ambiente separado PASS; baseline de produto anterior inexistente, sem inventar regressão Telegram |
| PROJECT_STATE_RECONCILIATION | Estado factual, evidências, gaps, autorização e próximo passo reconciliados |
| AGENT_HANDOFF_GATE | Campos/artefatos de PM-01 §12.3 descobríveis e atuais, sem estado ativo contraditório |

Docs de S0, estado da unidade e continuidade devem ser atualizados conforme impacto; roadmap somente quando houver alteração material autorizada. Fechamento da sprint/delivery unit e avanço continuam decisões do usuário. Mesmo com aceite técnico, S1 requer seu DoR e autorização próprios.

Commit/push não fazem parte da DoD: SPR e PM-01 distinguem fechamento técnico de publicação. `DOD_CLOSED = SIM` como especificação após o manifest e critérios concretos do §22; nenhuma execução ou aceite técnico ocorreu nesta atividade.

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

CG-01–05 eram gaps da própria S0 e foram fechados no §22; não são decisões adiadas para S1+.

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

## 22. Fechamento de CG-01–05

Estas são decisões do **autor do contrato** sob o Card B de fechamento, para revisão do usuário. Não promovem o draft a APPROVED. Valores de runtime continuam hipóteses até SP-01. Em cada gap, `IMPLEMENTER_FREEDOM_REMAINING = NONE` para escolhas materiais; detalhes mecânicos equivalentes continuam permitidos somente após aprovação/autorização.

### 22.1 CG-01 — dependências e política

`CG-01_STATUS = CLOSED`. **DECISION:** tabela e política do §6, runtime separado de development, `PYTHON_REQUIRES = >=3.14,<3.15`, CPython 3.14.x padrão/Windows 11 x64 e faixas fechadas. **RATIONALE:** pisos são versões publicadas verificadas; tetos preservam as linhas selecionadas, com patch exato resolvido e registrado em SP-01. **AUTHORITIES:** ENG Runtime, ARC ADR-001/003/006, SPR SP-01, Card B de fechamento e páginas PyPI oficiais linkadas no §6. Nenhuma dependência extra foi aprovada. `RESOLVED_ENVIRONMENT_VERSIONS = REGISTRAR_EM_SP01`, inclusive transitivas, pip, setuptools, CPython e SQLite.

### 22.2 CG-02 — namespace e manifest de S0

`CG-02_STATUS = CLOSED`. **DECISION:** `PYTHON_PACKAGE_NAME = telegram_courses`, `IMPORT_NAMESPACE = telegram_courses`, `DISTRIBUTION_NAME = projeto-telegram-courses`; `SOURCE_LAYOUT = src/`, `TEST_LAYOUT = tests/unit/ + tests/integration/`, `CONFIG_LAYOUT = config/settings.toml`, `DATA_LAYOUT = nenhuma criação em S0`, `LOG_LAYOUT = nenhuma criação em S0`, `DOC_LAYOUT = docs/development/S0_SETUP.md + docs/engineering/evidence/SP01_STACK_WINDOWS.md`. **RATIONALE:** nome de import curto e estável, distribuição identificável com o projeto, `src` impede importar por acidente um package não instalado. **AUTHORITIES:** SPR S0, ARC boundaries, ENG configuração/testes, STATE e Card B de fechamento. A distribuição usa hífens somente em metadata; comando é `telegram-courses`.

`S0_FILE_MANIFEST = EXPECTED_SOURCE_MANIFEST`: a tabela abaixo é exaustiva para novos paths versionáveis de S0. `SOURCE_ARTIFACTS` são esses arquivos e a documentação preexistente preservada; `PRODUCT_SOURCE` é apenas o package de quatro módulos nomeados. `ALLOWED_GENERATED_LOCAL_ARTIFACTS` é conjunto separado: `BUILD_METADATA` do §22.2.1, `VENV_CONTENT` sob `.venv/` e `.venv-replay/`, e `CACHE` de imports/pytest/Ruff já admitidos abaixo e excluídos pelo §10.1. Metadata, venv e cache não são source obrigatório nem expansão funcional. Diretórios obrigatórios podem conter seus filhos versionáveis e, somente nos paths/condições expressos, artefatos gerados locais; não podem conter S1+, secrets, sessões, mídia, banco operacional ou logs brutos. Para arquivos, “pode conter” significa implementação mecânica da responsabilidade, sem capacidade de S1+ ou segredo real.

| PATH | TIPO / CLASSE | RESPONSABILIDADE e CONTEÚDO_MÍNIMO | PODE_CONTER / NÃO_PODE_CONTER específico |
|---|---|---|---|
| `src/`, `src/telegram_courses/` | DIRECTORY / OBRIGATÓRIO | Raiz de código e package regular com os quatro arquivos abaixo | Só código S0 / sem skeleton de gateway, parser, domínio ou persistência |
| `tests/`, `tests/unit/`, `tests/integration/` | DIRECTORY / OBRIGATÓRIO | Suíte offline; unit e integração local separadas | Somente testes S0 / sem Telegram real, credenciais ou sessão |
| `config/` | DIRECTORY / OBRIGATÓRIO | Arquivo TOML versionado abaixo | Config não sensível / sem `.env`, secrets ou sessão |
| `docs/development/`, `docs/engineering/evidence/`, `requirements/` | DIRECTORY / OBRIGATÓRIO | Instruções, evidência SP-01 e constraints, respectivamente | Somente arquivos nomeados abaixo / sem logs brutos ou dump de ambiente |
| `pyproject.toml` | FILE / OBRIGATÓRIO | Metadata, dependências, backend, console script e pytest/Ruff do §22.5 | Seções contratadas / sem authors/license inventados ou plugins extras |
| `.gitignore` | FILE / OBRIGATÓRIO | Todas as linhas de GIT_EXCLUSION_CONTRACT §10.1 | Sem novo pattern ou exceção não contratada; descoberta de artefato novo retorna ao autor |
| `config/settings.toml` | FILE / OBRIGATÓRIO | `[logging]` e `level = "INFO"`; versionado | Só chave do §22.3 / sem API ID/hash, session path ou valores S1+ |
| `src/telegram_courses/__init__.py` | FILE / OBRIGATÓRIO | Package regular, `__version__ = "0.1.0"` | Exports locais mínimos / sem side effect, cliente ou import operacional Telethon |
| `src/telegram_courses/__main__.py` | FILE / OBRIGATÓRIO | Chamar `cli.main()` e devolver seu código em `SystemExit` | Dispatch mínimo / sem segunda semântica CLI |
| `src/telegram_courses/cli.py` | FILE / OBRIGATÓRIO | `main()`; parser da única subcommand `smoke`; Rich para resposta | Validação de argumentos e apresentação / sem cliente, rede ou produto |
| `src/telegram_courses/config.py` | FILE / OBRIGATÓRIO | Carregar/validar TOML e precedência do §22.3 com `tomllib` | Tipos/erros locais / sem framework, dotenv, persistência ou escrita |
| `tests/unit/test_config.py` | FILE / OBRIGATÓRIO | Casos de defaults, arquivo, overrides e erros do §22.3 | Fixtures temporárias não sensíveis / sem async ou rede |
| `tests/integration/test_cli_smoke.py` | FILE / OBRIGATÓRIO | Subprocesso real do venv nos casos A–D; injeção local de falha no E; códigos do §22.4 | `tmp_path` e ambiente sanitizado / sem autenticação |
| `tests/integration/test_stack_local.py` | FILE / OBRIGATÓRIO | Corrotina, sqlite3 e aiosqlite em memória para SP01-06/08 | SQL sentinela local / sem schema de produto ou banco persistente |
| `docs/development/S0_SETUP.md` | FILE / OBRIGATÓRIO | Comandos do §22.5, entradas/saídas esperadas e reprodução | Instruções sem credenciais / sem login Telegram |
| `docs/engineering/evidence/SP01_STACK_WINDOWS.md` | FILE / OBRIGATÓRIO ao fechar S0 | Resultado por SP01-01–10, versões exatas, comandos, códigos e data/fuso | Evidência sanitizada / sem secrets, env dump ou logs brutos |
| `requirements/s0-resolved-win-cp314.txt` | FILE / OBRIGATÓRIO ao fechar S0 | Constraints `name==version` exclusivamente do CONSTRAINTS_SCOPE §22.5.2, geradas após primeira instalação validada | Runtime/dev/transitivas; exclusões e build definidos uma vez no §22.5.2 / sem path local, URL, secret ou faixa aberta |

`__init__.py` em `tests/` é **PROIBIDO_EM_S0**: pytest descobre os arquivos sem ele. `__main__.py` do package é obrigatório e compartilha `main()` com o console script. **OPCIONAL_CONDICIONAL:** caches de instalação/imports/pytest/Ruff são transitórios, ignorados e nunca versionados, fora da janela do smoke; o smoke segue exclusivamente §22.4.1 e não pode criar/alterar caches. `.venv/` e `.venv-replay/` são **OBRIGATÓRIOS apenas durante SP-01**, locais e ignorados pelo §10.1; não entram no manifest versionável. `data/`, `data/session/` e `logs/` não são criados em S0. São **PROIBIDO_EM_S0** novos módulos/arquivos de scanner, parser funcional, schema/migrations, banco operacional, downloads, sync, autenticação, gateway operacional, fixtures com secrets e documentação que simule aceite de S1+.

### 22.2.1 EDITABLE_INSTALL_METADATA_POLICY

`EDITABLE_INSTALL_METADATA_PATH = src/projeto_telegram_courses.egg-info/`; `EDITABLE_INSTALL_METADATA_POLICY = LOCAL_GENERATED_ARTIFACT`; `VERSION_CONTROL_POLICY = IGNORED`, pelo pattern canônico `*.egg-info/` do §10.1. Path derivado do backend pinado: `egg_base` usa `package_dir[''] = src`; o componente de filename normaliza hífens do nome da distribuição para underscores. O backend cria metadata durante o build editable; não criar, editar ou copiar `.egg-info` manualmente. Existência esperada após SP01-03 e após reinstalação de replay; não obrigatória antes de instalar. Replay usa o mesmo checkout e pode regenerar o mesmo diretório, sem requerer segunda cópia. Essa inferência documental da stack pinada será verificada na futura execução. Fontes: [setuptools 84 — egg_info.finalize_options/run](https://raw.githubusercontent.com/pypa/setuptools/v84.0.0/setuptools/command/egg_info.py) e [normalização de filename no upstream](https://raw.githubusercontent.com/pypa/setuptools/main/setuptools/_normalization.py), lidos em 2026-10-05. O fetch de `_normalization.py` no tag 84 não retornou conteúdo; a regra foi corroborada no upstream, sem afirmar verificação desse arquivo no pin.

S0-T06 deve exigir o diretório esperado e `PKG-INFO` após cada instalação, ler com parser stdlib de metadata e exigir `Name=projeto-telegram-courses`, `Version=0.1.0`. Não congelar todos os filenames internos do backend nem tratá-los como módulos de produto; excluir apenas esse subtree gerado da comparação de source. Demais metadata dentro do venv/build temporário do instalador pertencem a esses ambientes, não ao manifest versionável. Metadata inesperado fora do path contratado no checkout exige stop/reporte, sem inventar exclusão ou apagar. S0-T07 exige presença literal de `*.egg-info/`, correspondência do probe mesmo sem arquivo físico e ausência de metadata rastreado; S0-A03/A09/A10 e DoD incorporam essas verificações. Instalação/replay podem gerar ou alterar metadata antes das snapshots; durante o smoke esse subtree é comparado integralmente e qualquer mutação continua FAIL.

### 22.3 CG-03 — configuração mínima


`CG-03_STATUS = CLOSED`. `CONFIG_FILE = config/settings.toml`; `FORMATO = TOML`; `LOCALIZAÇÃO = relativa à raiz do checkout quando smoke for executado na raiz`; `VERSIONADO = SIM`. O arquivo source obrigatório contém `[logging] level = "INFO"`. Chave `logging.level`: string, valores exatos `DEBUG|INFO|WARNING|ERROR|CRITICAL` (maiúsculas), default `INFO`, não sensível; não ativa arquivo de log. TOML vazio ou `[logging]` vazio são configurações válidas sem valor de arquivo; nenhuma outra seção/chave é admitida.

`CONFIG_INDICATOR_SEMANTICS = CONFIGURATION_FILE_LOAD_ORIGIN`: o campo público `config` informa somente se um arquivo selecionado foi lido e validado integralmente. Arquivo presente e válido produz `file`, inclusive vazio, sem `[logging]` ou sem `logging.level`; ausência apenas do path default produz `defaults`. Não representa origem efetiva do nível: CLI/ambiente podem fornecer o valor sem mudar o indicador. Erro impede emissão do indicador. Distinguir arquivo presente, TOML válido, chave presente, valor válido e origem efetiva; esta última governa `log_level` pela precedência existente, sem adicionar campo público.

Matriz obrigatória S0-T09, também exercitada por subprocesso CLI nos dois venvs sob §22.4.1. Seleção default, sem overrides; `NL` significa newline normalizado pelo modo texto. Na linha 3 o TOML sem `[logging]` é composto apenas de comentários, pois outras seções continuam proibidas. Na linha 6 usar TOML malformado; repetir erro para chave/tipo/valor inválido conforme regras seguintes.

| CASO / fixture | CONFIG_INDICATOR | LOG_LEVEL_EFFECTIVE / origem | EXIT_CODE | STDOUT | STDERR | FALLBACK_ALLOWED |
|---|---|---|---|---|---|---|
| 1: arquivo default ausente | defaults | INFO / default | 0 | `telegram-courses 0.1.0 config=defaults log_level=INFO` + NL | vazio | SIM, ausência default |
| 2: arquivo existente com zero bytes | file | INFO / default | 0 | `telegram-courses 0.1.0 config=file log_level=INFO` + NL | vazio | SIM, chave ausente |
| 3: arquivo existente só com `# s0 fixture` + NL, sem `[logging]` | file | INFO / default | 0 | `telegram-courses 0.1.0 config=file log_level=INFO` + NL | vazio | SIM, chave ausente |
| 4: arquivo contendo `[logging]` + NL, sem `level` | file | INFO / default | 0 | `telegram-courses 0.1.0 config=file log_level=INFO` + NL | vazio | SIM, chave ausente |
| 5: `[logging]` + NL + `level="WARNING"` + NL | file | WARNING / arquivo | 0 | `telegram-courses 0.1.0 config=file log_level=WARNING` + NL | vazio | NÃO necessário; valor do arquivo |
| 6: arquivo contendo `[logging` + NL | NÃO_EMITIDO | NÃO_APLICÁVEL | 2 | vazio | `configuration error` + NL | NÃO |

Repetir casos 2–5 com seleção explícita por CLI e por `TELEGRAM_COURSES_CONFIG`: continuam `file`. Ausência explícita é erro exit 2/stdout vazio/stderr genérico, sem fallback. T09 cobre os overrides isolados e combinados: com arquivo válido, mesmo sem chave, indicador continua `file`; sem default e com override válido, continua `defaults`; nível segue CLI > ambiente > arquivo > INFO. TOML inválido nunca é ocultado por override. A06 exige esta matriz e precedência; A07 exige a mesma saída pública e zero mutação, incorporando a matriz aos casos T10.

`CONFIG_PRECEDENCE = --log-level > TELEGRAM_COURSES_LOG_LEVEL > logging.level no TOML > INFO`. Para selecionar o arquivo: `--config PATH > TELEGRAM_COURSES_CONFIG > config/settings.toml`; os dois primeiros são seleção explícita e ausência do path selecionado é erro, enquanto ausência do path default permite defaults. Nenhuma outra variável/argumento de configuração não sensível é suportada em S0. `--config` e a variável exigem path não vazio de arquivo `.toml`; path relativo é resolvido contra o diretório corrente da invocação. Diretório, path inexistente explícito ou acesso negado são erro. Path explícito pode apontar fora da raiz para fixture local, desde que arquivo regular acessível e sem secrets; nunca é criado ou copiado. O smoke de aceite roda da raiz do checkout. Não expandir `~` ou variáveis dentro do valor; não gravar arquivo. `--log-level`/env sempre são validados e não escondem erro de sintaxe ou chave do arquivo lido.

Validação: TOML malformado, seção/tipo/chave desconhecida, tipo não string, string fora do conjunto, path inválido ou ilegível e qualquer chave sensível (`api_id`, `api_hash`, `password`, `session`, `session_string`, em qualquer nível e caixa) são erro de configuração; não há fallback nesses casos. Valor vazio de override também é erro. Quando o arquivo está presente, a validação percorre todas as suas chaves antes de aplicar precedência; valores inválidos de fonte de menor precedência não são ignorados. O arquivo não recebe valores secretos e `TELEGRAM_API_ID/HASH` não são lidos pelo smoke. A mensagem pública de erro é genérica, sem path/valor/stack trace, pelo exit 2 do §22.4.

### 22.4 CG-04 — CLI e smoke

`CG-04_STATUS = CLOSED`. `CLI_ENTRYPOINT = [project.scripts] telegram-courses = "telegram_courses.cli:main"`; `COMANDO = & $CliS0 smoke`, com resolução absoluta do §22.5.1 e `PYTHONDONTWRITEBYTECODE=1` no processo filho conforme §22.4.1; equivalente `& $PyS0 -B -m telegram_courses smoke`. Argumentos opcionais de S0: `--config PATH` e `--log-level LEVEL`, cada um no máximo uma vez; ordem livre após `smoke`. Sem outros comandos/opções além do `--help` padrão local; argumento/comando inválido retorna exit 2 e diagnóstico genérico `configuration error\n` no stderr.

`EXIT_CODE_SUCCESS = 0`, `EXIT_CODE_CONFIGURATION_ERROR = 2`, `EXIT_CODE_INTERNAL_ERROR = 1`. Saída ASCII sem ANSI, uma linha terminada por newline normalizado, sem timestamp, path ou decoração contratual: `telegram-courses 0.1.0 config=<file|defaults> log_level=<LEVEL>\n` em stdout; stderr vazio. O teste usa modo texto de subprocesso com normalização universal de newline; bytes `CRLF` do console Windows são aceitos, conteúdo e número de linhas não variam. Rich `Console` deve produzir texto simples determinístico no smoke, sem cores nem quebra visual; estilos futuros não são parte do contrato. Falha de configuração ou argumentos: stdout vazio, stderr exatamente `configuration error\n` após normalização; falha inesperada: stdout vazio, stderr exatamente `internal error\n`, sem traceback no console. O smoke importa o package, carrega config, identifica nome/versão e encerra. Efeitos colaterais = NENHUM: sem criar/alterar arquivo, sessão, banco, diretório, log, processo em background ou conexão de rede.

| TEST_ID | PRECONDIÇÃO / AÇÃO | STDOUT_ESPERADO | STDERR_ESPERADO | EXIT_CODE_ESPERADO / EFEITOS |
|---|---|---|---|---|
| S0-T10A | Venv instalado; arquivo válido; `subprocess.run([CliS0, 'smoke'], cwd=RepoRoot, env=SmokeEnv, text=True, capture_output=True, check=False)` | `telegram-courses 0.1.0 config=file log_level=INFO\n` | vazio | 0 / zero mutação conforme §22.4.1 |
| S0-T10B | Cwd temporário vazio criado conforme abaixo; `subprocess.run([CliS0, 'smoke'], cwd=SmokeCwd, env=SmokeEnv, text=True, capture_output=True, check=False)`; caso adicional obrigatório `[PyS0, '-B', '-m', 'telegram_courses', 'smoke']` no mesmo cwd | `telegram-courses 0.1.0 config=defaults log_level=INFO\n` em ambos | vazio em ambos | 0 / zero mutação conforme §22.4.1 |
| S0-T10C | Fixture TOML temporária com `level="WARNING"` selecionada por `--config`; env `TELEGRAM_COURSES_LOG_LEVEL=ERROR`; `--log-level DEBUG` | `telegram-courses 0.1.0 config=file log_level=DEBUG\n` | vazio | 0 / nenhum |
| S0-T10D | `--config` para TOML inválido, ausente ou com chave sensível sintética | vazio | `configuration error\n` | 2 / nenhum |
| S0-T10E | Erro interno sintético isolado em teste, sem expor causa | vazio | `internal error\n` | 1 / nenhum |

`S0-T09` verifica a matriz integral, cada precedência isolada e rejeições da §22.3; `S0-T10` agrega os cinco casos acima e todos os subprocessos da matriz. Sem credenciais. Erro interno sintético é injeção de falha local no teste, não um modo de produção ou argumento CLI adicional.

Em `test_cli_smoke.py`, `RepoRoot = Path(__file__).resolve().parents[2]`; `VenvRoot = Path(sys.prefix).resolve()` deve ser igual a `RepoRoot / '.venv'` na primeira suíte e `RepoRoot / '.venv-replay'` na suíte de replay; qualquer outro prefix impede os testes. `PyS0 = str(VenvRoot / 'Scripts' / 'python.exe')` e `CliS0 = str(VenvRoot / 'Scripts' / 'telegram-courses.exe')`, ambos absolutos e arquivos existentes; no replay os mesmos nomes locais do teste apontam exclusivamente para o replay. Antes de iniciar os subprocessos, comparar `sys.executable` normalizado com `PyS0`. Nenhum teste usa `python`/`telegram-courses` global ou ativação.

`TEMP_DIRECTORY_CREATION = SmokeCwd = tmp_path / 'cwd'; SmokeCwd.mkdir()` antes da primeira snapshot, exigindo ausência prévia e diretório vazio, sem `config/settings.toml`. O processo de teste permanece no seu cwd; a mudança ocorre apenas pelo parâmetro `cwd` do subprocesso. `SmokeEnv` é cópia do ambiente do processo de teste, removendo `TELEGRAM_COURSES_CONFIG`, `TELEGRAM_COURSES_LOG_LEVEL`, `PYTHONPATH` e `PYTHONHOME` e fixando `PYTHONDONTWRITEBYTECODE='1'`; nos casos C/D acrescentar somente os overrides explicitamente contratados. Não imprimir o ambiente. `WORKING_DIRECTORY=SmokeCwd`; `CLI_EXECUTABLE=CliS0 absoluto`; `EXPECTED_RESULT` é a linha T10B. `CLEANUP`: `tmp_path` fica sob o ciclo de retenção/limpeza do pytest, fora do Git; nenhum delete recursivo ou cleanup é realizado pelo smoke, nenhum diretório é removido antes da comparação final. A criação/limpeza pelo harness fica fora da janela medida do comando.

### 22.4.1 SMOKE_FILESYSTEM_SIDE_EFFECT_POLICY

`SMOKE_FILESYSTEM_SIDE_EFFECT_POLICY = ZERO_FILESYSTEM_MUTATION`; `ALLOWED_TRANSIENT_EFFECTS = NENHUM`. A única política é bytecode desabilitado antes de iniciar o interpretador, por `PYTHONDONTWRITEBYTECODE=1` em todas as invocações do console script e por `-B` também na invocação por módulo. Em PowerShell, salvar o valor prévio, definir `$env:PYTHONDONTWRITEBYTECODE='1'` antes do smoke e restaurá-lo após a medição em `finally` (restaurar somente a variável, nunca executar etapa dependente). Isso pertence ao harness/instruções, sem adicionar opção pública da CLI.

`PROHIBITED_EFFECTS = criar, alterar, remover ou renomear arquivos/diretórios, incluindo __pycache__, *.pyc, .pytest_cache, .ruff_cache, logs/ e *.log, configuração, *.session/*.session-journal, bancos e quaisquer data files`. Também não há processo em background, escrita de config nem rede. Caches já presentes antes da chamada são permitidos apenas como estado anterior: não ignorar nenhum deles na comparação. Instalação, outros imports, pytest e Ruff podem produzir os caches transitórios admitidos no manifest fora da janela do smoke; isso não flexibiliza o comando.

Oracle de T10A–D e caso E isolado: preparar fixtures/cwd primeiro; imediatamente antes e depois de cada chamada, colher em memória snapshot recursiva do checkout inteiro (inclusive venvs, caches e `.git`) e de `tmp_path` inteiro (incluindo cwd e fixtures). Não seguir links/reparse points; se encontrados nessas raízes, parar o teste e reportar oracle indisponível. Por entrada registrar path relativo, tipo, atributos, criação/última escrita em UTC; para arquivo regular também tamanho e SHA-256 dos bytes. Ler arquivos em modo binário somente leitura; não persistir snapshots nem valores de arquivos. Exigir mapas idênticos, sem lista de paths ignorados. Horário de último acesso não é comparado, pois a própria leitura do oracle pode atualizá-lo. Divergência, falha de leitura, concorrência ou captura incompleta = FAIL, jamais ajustar baseline ou criar exceção silenciosa. Observadores/harness não escrevem nas raízes durante a janela; caches do pytest anteriores à primeira snapshot permanecem comparados.

Complementar a comparação com inspeção dos quatro módulos do manifest: apenas leitura de configuração pelo loader, sem operação de mutação ou path de escrita fora das raízes observadas. Para T10E, a injeção local em memória ocorre antes da snapshot e não escreve arquivo nem cria um entrypoint alternativo versionado; medir a chamada isolada com os mesmos mapas. Evidência contém igualdade/deltas de paths, resultados e exit codes sanitizados, sem conteúdo de config. Aceite S0-A07 exige saída/código e oracle de filesystem em todos os casos. Fonte: [CPython — bytecode desabilitado](https://docs.python.org/3.14/using/cmdline.html#envvar-PYTHONDONTWRITEBYTECODE).

### 22.5 CG-05 — metadata, ferramentas e instalação

`CG-05_STATUS = CLOSED`. **PROJECT_NAME/DISTRIBUTION_NAME:** `projeto-telegram-courses`; **VERSION:** `0.1.0`; **DESCRIPTION:** `Bootstrap da aplicação CLI para organizar cursos do Telegram`; **REQUIRES_PYTHON:** `>=3.14,<3.15`; **DEPENDENCIES:** quatro linhas RUNTIME do §6; **OPTIONAL_DEPENDENCIES:** grupo `dev` com pytest/Ruff do §6; **ENTRY_POINTS:** `telegram-courses = telegram_courses.cli:main`; **AUTHORS:** omitido por ausência de dado aprovado; **LICENSE_METADATA:** omitido, licença não escolhida; **README_METADATA:** omitido, pois não há README aprovado no manifest. Não declarar classificadores, URL ou maintainers inventados.

`pyproject.toml` conterá exatamente as seções necessárias `[build-system]`, `[project]`, `[project.optional-dependencies]`, `[project.scripts]`, `[tool.setuptools]`, `[tool.setuptools.packages.find]`, `[tool.pytest.ini_options]`, `[tool.ruff]` e `[tool.ruff.lint]`. **BUILD_BACKEND:** `setuptools.build_meta`; `[build-system].requires = ["setuptools==84.0.0"]` por repetibilidade do build isolado; `[tool.setuptools].package-dir = {"" = "src"}`; descoberta `where=["src"]`, `include=["telegram_courses"]`, `namespaces=false`. Nada de `setup.py`, Poetry, Conda ou tool extra. O pin exato do backend é a exceção técnica à política de faixas para garantir a mesma ferramenta de build no replay. [Setuptools oficial](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html).

Conteúdo normativo mínimo de `pyproject.toml` (ordem das chaves não importa):

```toml
[build-system]
requires = ["setuptools==84.0.0"]
build-backend = "setuptools.build_meta"

[project]
name = "projeto-telegram-courses"
version = "0.1.0"
description = "Bootstrap da aplicação CLI para organizar cursos do Telegram"
requires-python = ">=3.14,<3.15"
dependencies = ["Telethon>=1.45,<1.46", "cryptg>=0.6,<0.7", "aiosqlite>=0.22.1,<0.23", "Rich>=15.0,<16"]

[project.optional-dependencies]
dev = ["pytest>=9.1.1,<9.2", "ruff>=0.16.10,<0.17"]

[project.scripts]
telegram-courses = "telegram_courses.cli:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
include = ["telegram_courses"]
namespaces = false

[tool.pytest.ini_options]
testpaths = ["tests/unit", "tests/integration"]
python_files = ["test_*.py"]
addopts = "-ra"

[tool.ruff]
target-version = "py314"
line-length = 88
src = ["src"]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I"]
ignore = []
```

**PYTEST_CONFIGURATION:** `testpaths=["tests/unit", "tests/integration"]`, `python_files=["test_*.py"]`, `addopts="-ra"`; `PYTHONPATH_POLICY = package instalado editable, sem pythonpath/insert em testes`; `ASYNC_TEST_POLICY = asyncio.run em teste síncrono, sem pytest-asyncio`; `NETWORK_TEST_POLICY = offline, sem Telegram/credenciais; nenhum marcador de rede em S0`. **RUFF_CONFIGURATION:** `target-version="py314"`, `line-length=88`, `src=["src"]`, `lint.select=["E4","E7","E9","F","I"]`, `lint.ignore=[]`, `exclude` = defaults oficiais do Ruff, sem override; Ruff percorre `src` e `tests` por `python -m ruff check src tests`. Nada de preview, format gate ou perfil complexo. [Ruff settings](https://docs.astral.sh/ruff/settings/).

### 22.5.1 Resolução de executáveis e instalação

**Procedimento futuro**, PowerShell 7, raiz do checkout, somente após aprovação/autorização. Todas as invocações nativas abaixo passam pelo §8.1. Resolver a raiz factual com Git antes de mudar cwd e fixar os paths uma única vez:

```powershell
$GitS0 = (Get-Command git -CommandType Application -ErrorAction Stop).Source
$RepoRootText = & $GitS0 rev-parse --show-toplevel
$RepoExitCode = $LASTEXITCODE
if ($RepoExitCode -ne 0) { throw 'repository preflight failed' }
$RepoRoot = [IO.Path]::GetFullPath($RepoRootText.Trim())
$VenvRoot = Join-Path $RepoRoot '.venv'
$VenvReplayRoot = Join-Path $RepoRoot '.venv-replay'
$PyS0 = Join-Path $VenvRoot 'Scripts\python.exe'
$CliS0 = Join-Path $VenvRoot 'Scripts\telegram-courses.exe'
$PyReplay = Join-Path $VenvReplayRoot 'Scripts\python.exe'
$CliReplay = Join-Path $VenvReplayRoot 'Scripts\telegram-courses.exe'
$ConstraintsPath = Join-Path $RepoRoot 'requirements\s0-resolved-win-cp314.txt'
```

A chamada Git acima pertence ao preflight, anterior ao SP-01; conferir seu `$LASTEXITCODE` imediatamente e parar se não zero antes de usar seu resultado. `VENV_ROOT=<RepoRoot>\.venv`; `PYTHON_S0=$PyS0 absoluto`; `CLI_S0=$CliS0 absoluto`. Nunca recalcular paths a partir de cwd temporário. Os dois diretórios de venv devem estar ausentes antes de criação; se já existirem, parar e reportar, sem apagar/reutilizar silenciosamente um ambiente contaminado. Não criar por ativação nem usar `python` global.

Dentro do `try` §8.1, executar a seleção/validação do `$PythonBase` §8.2, então `Invoke-S0Native -Step 'SP01-02-CREATE' -Executable $PythonBase -Arguments @('-m','venv',$VenvRoot)`; conferir arquivo `$PyS0`, oracle completo, paths/prefixes e probe GIL. Conferir `Invoke-S0Native -Step 'SP01-03-PIP-VERSION' -Executable $PyS0 -Arguments @('-m','pip','--version')`: uma linha parseável `pip <version> ...`, versão numérica >=21.3; caso contrário `throw`, sem upgrade arbitrário. Registrar versão, sem capturar configuração/URLs do pip.

`DEV_INSTALL_COMMAND = Invoke-S0Native -Step 'SP01-03-INSTALL' -Executable $PyS0 -Arguments @('-m','pip','install','-e',($RepoRoot + '[dev]'))`. Para o aceite, instalar o grupo dev; comando apenas de runtime para uso documental é o mesmo sem `[dev]`, não substitui o SP-01. Depois: helper com `@('-m','pip','check')`; imports SP01-04 por `$PyS0 -c 'import telethon, cryptg, aiosqlite, rich, pytest, telegram_courses'`; versões pytest/Ruff; `TEST_COMMAND` = helper com `@('-m','pytest')`; `RUFF_COMMAND` = helper com `@('-m','ruff','check','src','tests')`, ambos na raiz. SP01-06–08 são os probes com comparação de sentinelas no teste local do manifest; SP01-09 usa os casos T09/T10 e smoke `$CliS0` com bytecode desabilitado/oracle §22.4.1. Atualizar `$Sp01Step` antes de cada comparação PowerShell, sem prosseguir diante de erro. Ativação do venv é opcional para interação humana e não participa de nenhum comando/teste contratual.

### 22.5.2 CONSTRAINTS_SCOPE — definição única e replay

`CONSTRAINTS_FILE_PATH = <RepoRoot>\requirements\s0-resolved-win-cp314.txt`; em comandos, `$ConstraintsPath` absoluto. `CONSTRAINTS_SCOPE = resolução instalada das dependências runtime + development e suas transitivas no venv S0 recém-criado, excluindo gerenciamento do ambiente e distribuição local`. Não é inventário irrestrito nem comando de instalação.

| Classe/distribuição | INCLUDE / EXCLUDE e tratamento |
|---|---|
| PROJECT_RUNTIME_DEPENDENCIES | INCLUDE: quatro distribuições runtime do §6 e todas as transitivas instaladas no venv |
| PROJECT_DEVELOPMENT_DEPENDENCIES | INCLUDE: pytest/Ruff e todas as transitivas instaladas no venv |
| ENVIRONMENT_MANAGEMENT_TOOLS / `pip` | EXCLUDE: única ferramenta de gerenciamento instalada pelo bootstrap; versão exata registrada e igualada separadamente no replay |
| LOCAL_PROJECT_DISTRIBUTION / `projeto-telegram-courses` | EXCLUDE: instalada editable pelo comando explícito; metadata deve ser `0.1.0` nos dois ambientes |
| BUILD_DEPENDENCIES / `setuptools` | Backend isolado `setuptools==84.0.0` controlado exclusivamente por `[build-system].requires`, não instalado deliberadamente no venv-alvo. Se setuptools também for instalado como transitiva runtime/dev no alvo, INCLUDE dessa distribuição na lista; não excluir por nome nem substituir o pin do backend |
| Outra ferramenta de bootstrap (por exemplo `wheel`) | Não instalar ferramenta adicional no alvo. Se presente por resolução transitiva runtime/dev, INCLUDE; build-only isolado não entra nesta lista. Outra instalação manual/contaminação = FAIL, não ampliar exclusões |
| Stdlib e Python/SQLite | Não são distribuições pip: registrar versões separadamente em SP-01, sem linhas nas constraints |

Portanto a única exclusão por nome da lista de distribuições do venv-alvo é `{pip, projeto-telegram-courses}` normalizada. O venv limpo + instalação exclusiva do projeto/dev define seu escopo; nenhuma distribuição manual extra é admissível. Dependências isoladas de build não aparecem na lista do alvo e não são fixadas implicitamente por `-c`; o backend usa o pin aprovado no pyproject. Não acrescentar build-constraint, ferramenta de lock ou dependência para esta correção.

**GERAÇÃO exata**, depois de SP01-01–09 PASS, dentro do mesmo `try`:

```powershell
$Sp01Step = 'SP01-10-GENERATE'
$InitialJson = Invoke-S0Native -Step 'SP01-10-LIST-INITIAL' -Executable $PyS0 -Arguments @('-m','pip','list','--format=json')
$Initial = $InitialJson.stdout | ConvertFrom-Json
function ConvertTo-S0Pairs {
    param($Distributions)
    $Pairs = [string[]]@($Distributions | ForEach-Object {
        $Name = ([regex]::Replace([string]$_.name, '[-_.]+', '-')).ToLowerInvariant()
        $Version = [string]$_.version
        if ($Name -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$' -or
            $Version -notmatch '^[A-Za-z0-9][A-Za-z0-9.!+_-]*$') {
            throw 'invalid distribution pair'
        }
        "$Name==$Version"
    })
    [Array]::Sort($Pairs, [StringComparer]::Ordinal)
    $Names = @($Pairs | ForEach-Object { ($_ -split '==', 2)[0] })
    if (@($Names | Sort-Object -Unique).Count -ne $Names.Count) {
        throw 'duplicate normalized distribution'
    }
    return $Pairs
}
$InitialPairs = @(ConvertTo-S0Pairs $Initial)
$PipRow = @($Initial | Where-Object { $_.name -ieq 'pip' })
if ($PipRow.Count -ne 1) { throw 'pip missing or duplicated' }
$PipVersion = [string]$PipRow[0].version
if ($InitialPairs -notcontains 'projeto-telegram-courses==0.1.0') { throw 'local metadata mismatch' }
$ConstraintsLines = @($InitialPairs | Where-Object { $_ -notmatch '^(pip|projeto-telegram-courses)==' })
if ($ConstraintsLines.Count -eq 0) { throw 'empty constraints' }
$ConstraintsLines | Set-Content -LiteralPath $ConstraintsPath -Encoding ascii
$FilePairs = @(Get-Content -LiteralPath $ConstraintsPath)
if (@(Compare-Object $ConstraintsLines $FilePairs).Count -ne 0 -or
    ($FilePairs -join "`n") -cne ($ConstraintsLines -join "`n")) { throw 'constraints content mismatch' }
```

Antes de gravar, verificar que os seis nomes diretos do §6 runtime/dev estão em `$ConstraintsLines` com versões dentro de suas faixas e que `pip check` passou; lista incompleta = erro de oracle. Nome normalizado em lowercase, linhas ASCII `name==version`, ordem ordinal por nome (as comparações usam os mesmos nomes ASCII), uma por distribuição, sem comentários, URLs, paths ou editable. A lista completa `$InitialPairs`, incluindo pip/projeto, é preservada como evidência sanitizada, sem confundir esse inventário auxiliar com o arquivo de constraints.

**USO e VALIDAÇÃO exatos** no replay, dentro do mesmo `try`, ainda na raiz:

```powershell
Invoke-S0Native -Step 'SP01-10-CREATE-REPLAY' -Executable $PythonBase -Arguments @('-m','venv',$VenvReplayRoot)
Invoke-S0Native -Step 'SP01-10-ENV-REPLAY' -Executable $PyReplay -Arguments @('-c',$EnvironmentOracle)
# Comparar paths/prefixes, patch/base_prefix e GIL pelo §8.2 antes de instalar.
Invoke-S0Native -Step 'SP01-10-PIP-REPLAY' -Executable $PyReplay -Arguments @('-m','pip','install',"pip==$PipVersion")
Invoke-S0Native -Step 'SP01-10-INSTALL-REPLAY' -Executable $PyReplay -Arguments @('-m','pip','install','-c',$ConstraintsPath,'-e',($RepoRoot + '[dev]'))
Invoke-S0Native -Step 'SP01-10-CHECK-REPLAY' -Executable $PyReplay -Arguments @('-m','pip','check')
Invoke-S0Native -Step 'SP01-10-TEST-REPLAY' -Executable $PyReplay -Arguments @('-m','pytest')
Invoke-S0Native -Step 'SP01-10-LINT-REPLAY' -Executable $PyReplay -Arguments @('-m','ruff','check','src','tests')
# Invocar $CliReplay smoke pelo helper, sob política/oracle §22.4.1.
$ReplayJson = Invoke-S0Native -Step 'SP01-10-LIST-REPLAY' -Executable $PyReplay -Arguments @('-m','pip','list','--format=json')
$Sp01Step = 'SP01-10-COMPARE'
$ReplayPairs = @(ConvertTo-S0Pairs ($ReplayJson.stdout | ConvertFrom-Json))
$ReplayConstraints = @($ReplayPairs | Where-Object { $_ -notmatch '^(pip|projeto-telegram-courses)==' })
if (@(Compare-Object $InitialPairs $ReplayPairs).Count -ne 0 -or
    @(Compare-Object $FilePairs $ReplayConstraints).Count -ne 0) {
    throw 'replay distribution mismatch'
}
if ((@(Get-Content -LiteralPath $ConstraintsPath) -join "`n") -cne ($FilePairs -join "`n")) {
    throw 'constraints changed during replay'
}
# Somente após smoke/oracles e todas as verificações: $Sp01Result = 'PASS'.
```

Comparar todos os pares inclui pip e metadata local, além do conjunto das constraints; nenhuma exceção de comparação é permitida. Uma reinstalação no escopo S0 consome explicitamente `-c $ConstraintsPath -e ($RepoRoot + '[dev]')`; o arquivo limita versões das dependências requeridas, não instala sozinho nem fixa Python/SQLite/build isolado. Divergência = SP-01 FAIL; não editar constraints silenciosamente. Constraints fixam versões, não hashes de artefatos: reprodução de versões no mesmo Windows/ABI, sem alegar build bit a bit. `.venv-replay/` permanece local/temporário e proibido no Git pelo §10.1; não apagar automaticamente. `CONTRACTUAL_COMPATIBILITY = DOCUMENTED_EXPECTATION`; `SP01_RUNTIME_VALIDATION = NOT_EXECUTED` nesta atividade. Fontes: [Pip — constraints e build isolado](https://pip.pypa.io/en/stable/user_guide/#constraints-files), [Repeatable Installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/) e [pip list](https://pip.pypa.io/en/stable/cli/pip_list/).

### 22.6 Reconciliação dos gaps

| Gap | STATUS | DECISION / RATIONALE | AUTHORITIES | IMPLEMENTER_FREEDOM_REMAINING |
|---|---|---|---|---|
| CG-01 | CLOSED | §6 e §22.1: faixas estreitas e registro/replay exato | ENG, ARC, SPR, Card B, PyPI oficial | NONE |
| CG-02 | CLOSED | §22.2: namespace e manifest mínimo exaustivo | SPR, ARC, ENG, Card B | NONE |
| CG-03 | CLOSED | §22.3: único campo S0, precedência e rejeições | ENG, REQ FR-16, Card B | NONE |
| CG-04 | CLOSED | §22.4: único comando e oracle determinístico | SPR S0, ARC ADR-006, Card B | NONE |
| CG-05 | CLOSED | §22.5: metadata, backend, install/replay, pytest/Ruff | ENG, SPR S0/SP-01, Card B, documentação oficial Setuptools/pip/Ruff | NONE |

## 23. Verificação de completude do contrato

Origem: U §§21–22; self-review do autor em DIRECT.

```text
S0_OBJECTIVE_CLOSED = SIM
S0_SCOPE_CLOSED = SIM
S0_OUT_OF_SCOPE_CLOSED = SIM
STACK_CLOSED = SIM
LAYOUT_CLOSED = SIM
CONFIGURATION_CLOSED = SIM
CLI_SMOKE_CLOSED = SIM
PACKAGE_METADATA_CLOSED = SIM
REPRODUCIBLE_INSTALL_CLOSED = SIM
BOUNDARIES_CLOSED = SIM
SECURITY_BOOTSTRAP_CLOSED = SIM
TEST_CONTRACT_CLOSED = SIM
ACCEPTANCE_CRITERIA_CLOSED = SIM
DOD_CLOSED = SIM
IMPLEMENTER_STOP_CONDITIONS_CLOSED = SIM
CHANGE_CONTROL_CLOSED = SIM
SEMANTIC_GAPS = NENHUM
HISTORICAL_CONTRACT_STATUS = DRAFT_READY_FOR_REVIEW (AT THIS CHECKPOINT)
IMPLEMENTATION_READY_UNDER_THIS_CONTRACT = NÃO
```

Todos os itens acima estão fechados **como especificação contratual** após §22; nenhum teste de produto, SP-01 ou aceite técnico foi executado. `IMPLEMENTATION_READY_UNDER_THIS_CONTRACT = NÃO` significa que ainda faltam aprovação explícita do contrato e autorização específica de S0, não um gap semântico. Nenhuma aprovação é inferida de READY ou da autorização de editar.

## 24. Registro da atividade documental e recuperação

Origem: U §§23–24; STATE; GOV/Continuity; VP-01; verificações read-only desta sessão.

Esta seção preserva o registro **histórico** da autoria inicial, quando o contrato estava `DRAFT_BLOCKED`, antes do checkpoint documental autorizado depois e antes do fechamento de CG-01–05. Os status correntes estão no cabeçalho, §§22–23 e STATE. O checkpoint Git anterior está em STATE; não aprovou o contrato.

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

## 25. Registro histórico do fechamento de CG-01–05

Este checkpoint registra o fechamento anterior de CG-01–05 e substituiu o status bloqueado histórico do §24. O status corrente após os dois ciclos de correção está no §27. O Card B de fechamento autorizou decisão/documentação de CG-01–05, sem implementação, instalação, bootstrap ou publicação Git. A revisão de completude está no §23 e a reconciliação do estado em [PROJECT_STATE](../governance/PROJECT_STATE.md). Fontes externas do §6 e §22.5 sustentam compatibilidade contratual esperada; não são evidência de execução Windows. `PROJECT_STATE_RECONCILIATION = PASS` foi registrado para ID, versão, status, gaps e próximo passo daquela atividade. `SP01_RUNTIME_VALIDATION = NOT_EXECUTED`.

```text
STATUS = PASS
ACTIVITY_COMPLETION_PERCENT = 100%
COMPLETION_BASIS = CG-01, CG-02, CG-03, CG-04 e CG-05 fechados como especificação; revisão de completude sem novo gap material; estado/mapa reconciliados. Percentual apenas da atividade contratual, não de S0 ou do projeto.
CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
CONTRACT_VERSION = 1.0
CONTRACT_STATUS = DRAFT_READY_FOR_REVIEW
CONTRACT_APPROVAL = NOT_GRANTED
CG-01_STATUS = CLOSED
CG-02_STATUS = CLOSED
CG-03_STATUS = CLOSED
CG-04_STATUS = CLOSED
CG-05_STATUS = CLOSED
SEMANTIC_GAPS = NENHUM
PROJECT_STATE_RECONCILIATION = PASS
SP01_RUNTIME_VALIDATION = NOT_EXECUTED
S0_STARTED = NO
S0_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
GIT_PUBLICATION_AUTHORIZATION = NOT_GRANTED_FOR_CURRENT_ACTIVITY
NEXT_REQUIRED_ACTIVITY = REVISÃO E APROVAÇÃO EXPLÍCITA DO USUÁRIO DO CONTRATO S0
```

## 26. AUDIT_FINDING_CLOSURE — correção do draft 1.0

Registro histórico preservado do fechamento dos seis findings iniciais. Contagens e estratégia de captura abaixo descrevem aquele ciclo; as especializações atuais estão nos §§8.1/10.1/22.2.1/22.3/27. CONTRACT-HIGH-01 e CONTRACT-MED-01–05 permanecem CLOSED, com revalidação de não regressão em §27.2.

Fonte: Card B de correção `16f378d7-565b-4fe9-bbc9-c3c6d6aa9762/Texto colado.txt`, que fornece os seis findings da auditoria independente. Histórico do draft: autoria inicial bloqueada (§24), fechamento de CG-01–05 (§25), correção atual dos seis findings (§26). Versão mantida em 1.0 por ser correção pré-aprovação; nenhum relatório de auditoria, authority de produto ou governança externa foi alterado. `CLOSED` abaixo significa correção documental pelo autor, ainda sujeita à nova auditoria independente.

| FINDING / STATUS | CORREÇÃO / SEÇÃO | TESTE_RELACIONADO / ACEITE | RATIONALE |
|---|---|---|---|
| CONTRACT-HIGH-01 = CLOSED | §8.1: helper único, captura imediata de exit, registro de falha e throw; erro PowerShell distinto | S0-T08, ensaios negativos nativo 7/erro terminante; S0-A08 e DoD §15 | Default do shell não garante interrupção; nenhum passo dependente após falha |
| CONTRACT-MED-01 = CLOSED | §§8.2/13: oracle composto Windows 11/x64/CPython 3.14 padrão/GIL e paths | SP01-01/02, S0-T01/08; S0-A02/08 | Nome/versão de Python isolados não demonstram plataforma, arquitetura nem GIL |
| CONTRACT-MED-02 = CLOSED | §22.5.2 e manifest §22.2: único escopo, geração/replay/validação exatos | SP01-10, S0-T08/11; S0-A08 | Constraints fixam resolução runtime/dev; pip/local separados e build isolado explícito |
| CONTRACT-MED-03 = CLOSED | §§22.5.1/22.4: executáveis absolutos, prefix validado e cwd temporário definido | S0-T10A/B nos dois venvs; S0-A07 | Entrypoint instalado funciona fora da raiz sem depender de PATH/ativação |
| CONTRACT-MED-04 = CLOSED | §22.4.1 e manifest §22.2: zero mutação, bytecode desabilitado, snapshots sem exceções | S0-T10A–E, inspeção dos módulos; S0-A07 | Caches de outras ferramentas não autorizam efeitos do smoke |
| CONTRACT-MED-05 = CLOSED | §10.1: lista única de 13 patterns/probes, inclusive replay; §13/manifest referenciam essa lista | S0-T07; S0-A09 | Ignore e oracle verificam integralmente o mesmo conjunto, incluindo arquivos rastreados |

### 26.1 Revalidação documental cruzada

| PAR revisto | RESULTADO / EVIDÊNCIA |
|---|---|
| MANIFEST ↔ PROCEDIMENTO | PASS: paths de constraints/executáveis/evidência coincidem; caches e venvs seguem §§10.1/22.4.1/22.5 |
| PROCEDIMENTO ↔ TESTES | PASS: T01 usa §8.2; T08 inclui fail-fast e replay; T10 usa paths absolutos e oracle de filesystem |
| TESTES ↔ CRITÉRIOS DE ACEITE | PASS: A07 exige T10A–E/cwd/efeitos, A08 ambiente/fail-fast/replay, A09 exige todos os patterns T07 |
| CRITÉRIOS ↔ DEFINITION OF DONE | PASS: §15 exige todos T01–11/A01–12 e SP-01 PASS; nenhuma correção foi excluída da DoD |
| DEPENDÊNCIAS ↔ CONSTRAINTS | PASS: §6 e metadata preservados; §22.5.2 inclui runtime/dev/transitivas, separa pip/local e backend isolado |
| PYTHON ENVIRONMENT ↔ SP01-01 ↔ S0-T01 | PASS: mesmo oracle de Windows 11, x64/64 bits, CPython estável 3.14, GIL e build padrão |
| CLI ENTRYPOINT ↔ T10A ↔ T10B | PASS: console script contratado, path absoluto por venv, mesmo entrypoint na raiz/cwd temporário; módulo é verificação adicional |
| GIT EXCLUSIONS ↔ S0-T07 | PASS: uma tabela canônica, 13 probes/patterns e rastreados verificados, sem omissão de replay |
| SMOKE SIDE EFFECT POLICY ↔ MANIFEST ↔ TESTE | PASS: política única zero mutação com bytecode desabilitado; caches alheios à janela não são exceção do smoke |

Revalidação por inspeção do texto, rastreabilidade, parse estático dos blocos PowerShell e simulação do executor, sem executar os comandos do contrato. A simulação fixa a ordem e interrupção, condições completas de ambiente, escopo/exclusões/build das constraints, executáveis/cwd/ambiente do processo, janela e campos do oracle de filesystem, retenção do temporário e lista Git integral; nenhuma decisão material desses seis pontos ficou para o implementador. Sintaxe/oracles previstos não constituem evidência de compatibilidade runtime. A nova auditoria deverá reavaliar esta conclusão de autoria.

Recuperação desta correção: binding validado contra schema canônico por `Test-Json`; sete pins e protocolo Continuity conferidos por SHA-256 (8/8), mantendo baseline adotado. Git factual verificado. O bootstrap contém a descrição antiga de draft bloqueado; ela foi identificada como divergência procedural e limitada pelo status corrente do contrato/STATE, sem mudar esse arquivo nem conceder implementação. A autorização atual é exclusivamente documental. Gates históricos de VP-01/abertura não foram convertidos em autorização, aprovação ou validação runtime nesta atividade.

```text
STATUS = PASS
ACTIVITY_COMPLETION_PERCENT = 100%
COMPLETION_BASIS = Seis findings fechados como especificação; nove pares cruzados revisados; oracles e critérios rastreáveis; estado reconciliado para nova auditoria. Percentual somente desta correção contratual.
CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
CONTRACT_VERSION = 1.0
CONTRACT_STATUS = DRAFT_READY_FOR_REVIEW
CONTRACT_APPROVAL = NOT_GRANTED
SP01_FAIL_FAST = CLOSED
SUPPORTED_ENVIRONMENT_ORACLE = CLOSED
CONSTRAINTS_CONTRACT = CLOSED
CLI_EXECUTABLE_RESOLUTION = CLOSED
SMOKE_SIDE_EFFECT_POLICY = CLOSED
GIT_EXCLUSION_TEST = CLOSED
TRACEABILITY = PASS
INTERNAL_CONSISTENCY = PASS
TESTABILITY = PASS
IMPLEMENTER_SEMANTIC_FREEDOM = ZERO
HIDDEN_IMPLEMENTATION_DECISIONS = 0
MATERIAL_SEMANTIC_GAPS = NENHUM
PROJECT_STATE_RECONCILIATION = PASS
SP01_RUNTIME_VALIDATION = NOT_EXECUTED
S0_STARTED = NO
S0_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
HISTORICAL_NEXT_REQUIRED_ACTIVITY = REPETIR AUDITORIA INDEPENDENTE DO CONTRATO S0 (SUPERSEDED BY FINAL_FOCUSED_VERIFICATION)
```

## 27. AUDIT_FINDING_CLOSURE — segundo ciclo, CONTRACT-MED-06–08

Fonte/autorização: Card B do usuário, anexo `148726eb-ea91-4690-8e1b-e838c31afb41/Texto colado.txt`. Os três findings da segunda auditoria foram fornecidos no payload; nenhum relatório independente desse ciclo foi localizado como authority adicional, nem alterado. Entrada: contrato 1.0 DRAFT_READY_FOR_REVIEW com CHANGES_REQUIRED informado pelo usuário; seis findings anteriores CLOSED; Git master/HEAD `71fe536eed4edc81b1e5cd280f71e97d7c7a1160`, upstream origin/master, índice vazio, contrato/STATE/mapa já modificados. Escrita desta atividade somente no contrato e PROJECT_STATE; alterações preexistentes preservadas. O status DRAFT_READY_FOR_REVIEW continua sem aprovação. A execução é DIRECT; o runtime não foi trocado para o modelo/esforço alvo do payload.

### 27.1 Fechamento e decisões explícitas

| FINDING / STATUS | CAUSA | DECISÃO | SEÇÃO_CORRIGIDA | TESTE/ORACLE | ACEITE | RATIONALE |
|---|---|---|---|---|---|---|
| CONTRACT-MED-06 = CLOSED; HID-01 = CLOSED | Fusão de stderr e JSON por redirecionamento nativo | System.Diagnostics.Process; stdout/stderr lidos separadamente e assincronamente; ExitCode independente; retorno objeto | §8.1; parsing inicial/replay §22.5.2; §§13–15 | T08: positivo JSON + diagnóstico + exit 0; negativos exit 7, erro PowerShell e JSON inválido; T11/SP01-10 parsing somente stdout | A08 e DoD | Preservar formato machine-readable e fail-fast sem dependência nova |
| CONTRACT-MED-07 = CLOSED; HID-02 = CLOSED | Metadata do editable não classificado nem excluído/testado | src/projeto_telegram_courses.egg-info/ é metadata gerado local e ignorado; manifest de source distinto | §§10.1/22.2/22.2.1; §§13–15 | T06: metadata após instalação/replay, Name/Version exatos, sem expansão source; T07: 14 patterns/probes, incluindo egg-info, nenhum rastreado excluível | A03/A09/A10 e DoD | Prever artefato da stack selecionada sem versionar build metadata ou flexibilizar smoke |
| CONTRACT-MED-08 = CLOSED; HID-03 = CLOSED | config podia significar arquivo carregado ou origem efetiva de level | config representa exclusivamente arquivo lido e validado; file mesmo sem valor, defaults somente sem arquivo default | §22.3 matriz; §22.4/T09/T10; §§13–15 | Seis casos completos com indicador/nível/exit/stdout/stderr/fallback; seleção explícita e overrides em loader/CLI dos dois venvs | A06/A07 e DoD | Compatível com T10C e precedência existente; separar presença/validade/chave/valor/origem efetiva |

### 27.2 Revalidação das correções anteriores

| Finding anterior | STATUS / evidência documental de não regressão |
|---|---|
| CONTRACT-HIGH-01 | CLOSED: §8.1 conserva NATIVE_EXIT/throw em exit não zero, catch externo e marcador negativo não executado; ExitCode do processo substitui LASTEXITCODE por causa diretamente ligada a MED-06 |
| CONTRACT-MED-01 | CLOSED: oracle completo §8.2 e seus predicados de plataforma/ABI/GIL/paths não alterados; consumo da saída usa stdout do resultado §8.1 |
| CONTRACT-MED-02 | CLOSED: escopo/pin do backend, exclusões pip/local, geração e comparação de pares/constraints §22.5.2 preservados; somente parsing dos dois inventários usa stdout separado |
| CONTRACT-MED-03 | CLOSED: executáveis absolutos por venv e cwd temporário §§22.4/22.5.1 preservados |
| CONTRACT-MED-04 | CLOSED: zero mutação §22.4.1 permanece integral; metadata prévio à janela também é observado, sem nova exceção |
| CONTRACT-MED-05 | CLOSED: tabela única §10.1 conserva os 13 patterns/probes anteriores e acrescenta egg-info; oracles/aceite ativos passam a 14, sem regra negativa |

### 27.3 Revalidação dos eixos afetados

| EIXO | RESULTADO | EVIDÊNCIA DOCUMENTAL |
|---|---|---|
| INTERNAL_CONSISTENCY | PASS | Resultado nativo único §8.1 consumido em §22.5.2; source/metadata separados §22.2; indicador único §22.3 usado em CLI/testes/aceite |
| MANIFEST_CONTRACT | COMPLETE | EXPECTED_SOURCE_MANIFEST e ALLOWED_GENERATED_LOCAL_ARTIFACTS têm classes/paths/condições próprios; metadata esperado e tratamento T06/T07 fechados |
| CONFIGURATION_CONTRACT | COMPLETE | Matriz §22.3 cobre seis casos e cada dimensão exigida, seleção explícita, invalidez e overrides sem alterar precedência |
| CLI_CONTRACT | COMPLETE | §22.4 conserva formato e códigos; T09/T10 exercitam a mesma matriz com file/defaults e zero mutação |
| SP01_CONTRACT | COMPLETE | SP01-10, T08/T11 e A08 exigem captura independente, oracles positivo/negativos, parsing e comparação dos dois inventários |
| POWERSHELL_CONTRACT | PASS | Cinco blocos PowerShell parseados estaticamente pelo Parser do runtime, zero erros; helper usa API .NET disponível no PowerShell 7, sem shell/quoting manual |
| REPRODUCIBILITY | PASS | Como especificação: constraints/replay preservados e stdout JSON protegido de diagnósticos; não é resultado de execução de instalação |
| TESTABILITY | PASS | Oracles futuros fixam entradas/saídas/códigos/interrupção; T06/T07 distinguem metadata de source; seis casos de config verificáveis no loader/CLI |
| TRACEABILITY | PASS | MED-06 → SP01-10/T08/T11/A08/DoD; MED-07 → T06/T07/A03/A09/A10/DoD; MED-08 → T09/T10/A06/A07/DoD |

Revisão estática limitada aos três findings e seus efeitos diretos: conferidos cinco blocos PowerShell, 14 linhas da tabela de exclusões, ausência de fusão em comandos de captura e uso de .stdout nos dois parsers de constraints. Simulação documental de exit 0 + JSON + diagnóstico mantém sucesso e parsing; exit não zero ou oracle inválido impede a próxima instrução. Revisadas as relações manifest → procedimento → testes → aceite → DoD e as seis correções anteriores. Fontes primárias da API e backend estão junto às decisões. Nenhum teste de produto, helper nativo, smoke real, pip, instalação, venv, egg-info ou SP-01 foi executado/criado nesta autoria. Expectativa documental de metadata não é validação do build Windows.

Binding/schema conferido por Test-Json; oito pins (sete authorities + Continuity) íntegros por SHA-256. Baseline adotado preservado. Divergência procedural já conhecida do bootstrap (draft bloqueado antigo) permanece explicitamente limitada pelo contrato/STATE atuais; não se declara novo handoff global ou nova execução VP-01. STATE é reconciliado somente para o segundo ciclo e terceira auditoria. Authority alignment, pyproject, security bootstrap, boundaries e ausência de overengineering previamente aceitos foram preservados; não reabertos como auditoria nova.

```text
STATUS = PASS
ACTIVITY_COMPLETION_PERCENT = 100%
COMPLETION_BASIS = Três findings fechados documentalmente; decisões/oracles/aceite rastreáveis; seis correções anteriores preservadas; oito eixos afetados revalidados por inspeção e parse estático; PROJECT_STATE reconciliado. Percentual somente desta correção contratual.
CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
CONTRACT_VERSION = 1.0
CONTRACT_STATUS = DRAFT_READY_FOR_REVIEW
CONTRACT_APPROVAL = NOT_GRANTED
IMPLEMENTER_SEMANTIC_FREEDOM = ZERO
HIDDEN_IMPLEMENTATION_DECISIONS = 0
MATERIAL_SEMANTIC_GAPS = NENHUM
CORRECTION_REGRESSIONS = NENHUMA
PROJECT_STATE_RECONCILIATION = PASS
FILES_CREATED = NENHUM
FILES_UPDATED = docs/contracts/S0_IMPLEMENTATION_CONTRACT.md; docs/governance/PROJECT_STATE.md
GIT_DIFF_CHECK = PASS
SP01_RUNTIME_VALIDATION = NOT_EXECUTED
S0_STARTED = NO
S0_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
git add = NÃO_EXECUTADO
git commit = NÃO_EXECUTADO
git push = NÃO_EXECUTADO
HISTORICAL_NEXT_REQUIRED_ACTIVITY = TERCEIRA AUDITORIA INDEPENDENTE DO CONTRATO S0 (SUPERSEDED BY FINAL_FOCUSED_VERIFICATION)
```

CLOSED/PASS nesta seção era conclusão de autoria documental no checkpoint histórico; não representava então aprovação do usuário. A verificação final focada e a aprovação posteriores constam no §28. Nenhuma auditoria adicional foi executada nesta reconciliação.

## 28. VERIFICAÇÃO FINAL FOCADA E APROVAÇÃO DO USUÁRIO

Fonte: Card B do usuário para reconciliação documental, que informa como concluída fora deste checkout a verificação final focada (PASS, 100%) e registra a decisão explícita `APPROVE S0_IMPLEMENTATION_CONTRACT v1.0`. Esta seção materializa esses fatos; não declara nova auditoria nem validação runtime.

```text
CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
CONTRACT_VERSION = 1.0
FINAL_FOCUSED_VERIFICATION = PASS
CONTRACT_CLOSURE_VERIFICATION = PASS
CONTRACT_APPROVAL_READINESS = READY_FOR_USER_APPROVAL
CONTRACT-MED-06 = CLOSED_CONFIRMED
CONTRACT-MED-07 = CLOSED_CONFIRMED
CONTRACT-MED-08 = CLOSED_CONFIRMED
PREVIOUS_FINDINGS_REGRESSION = NONE
CONTRACT-HIGH-01 = PRESERVED
CONTRACT-MED-01 = PRESERVED
CONTRACT-MED-02 = PRESERVED
CONTRACT-MED-03 = PRESERVED
CONTRACT-MED-04 = PRESERVED
CONTRACT-MED-05 = PRESERVED
HIDDEN_IMPLEMENTATION_DECISIONS = 0
IMPLEMENTER_SEMANTIC_FREEDOM = ZERO
MATERIAL_SEMANTIC_GAPS = NENHUM
OUT_OF_SCOPE_STRUCTURAL_ISSUE = NENHUM
USER_APPROVAL_DECISION = APPROVED
APPROVED_BY = USER
CONTRACT_STATUS = APPROVED
CONTRACT_SEMANTIC_STATE = FROZEN
IMPLEMENTER_CAN_EDIT_CONTRACT = NO
S0_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
S0_STARTED = NO
SP01_RUNTIME_VALIDATION = NOT_EXECUTED
NEXT_REQUIRED_ACTIVITY = DECISÃO EXPLÍCITA DO USUÁRIO SOBRE AUTORIZAÇÃO PARA IMPLEMENTAR S0
```

A aprovação congela semanticamente a versão 1.0 e preserva integralmente suas decisões técnicas, comandos, testes, critérios de aceite, DoD e findings fechados. Se surgir gap durante implementação futura: `STOP_AND_REPORT` → revisão do contrato por SOL → `CONTRACT DELTA` → nova aprovação quando material → somente então continuar. Aprovação do contrato e autorização de S0 são gates separados.
