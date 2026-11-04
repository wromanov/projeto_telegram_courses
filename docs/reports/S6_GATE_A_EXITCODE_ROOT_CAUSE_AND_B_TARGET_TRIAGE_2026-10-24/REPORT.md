# Diagnóstico dos Gates A e B — S6

- **Data:** 2026-10-24 (America/Sao_Paulo)
- **Atividade:** `S6_GATE_A_EXITCODE_ROOT_CAUSE_AND_B_TARGET_TRIAGE`
- **Execução:** MULTI-AGENT / ROOT integrou as análises
- **Repositório:** `projeto_telegram_courses`
- **Branch / HEAD:** `work/s0-bootstrap` / `98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`

## Resultado integrado

```text
ACTIVITY = S6_GATE_A_EXITCODE_ROOT_CAUSE_AND_B_TARGET_TRIAGE
EXECUTION_MODE = MULTI-AGENT
GATE_A_CONFIRMED_ROOT_CAUSE = NONE
GATE_A_ROOT_CAUSE = UNKNOWN / no confirmed cause; failure localized to Process.ExitCode access before serialization
GATE_A_EVIDENCE = external-process.json records an explicit null and observed=false before serialization; gate-a-evidence-receipt.json has one later fail-closed guard error; external PID 33916 vs worker PID 10696, relationship unverified
GATE_A_FAILURE_POINT = Process.ExitCode read was assigned null before the process receipt; the wrapper then blocked the incomplete result and captured that guard error in the aggregate receipt
GATE_A_SUPPORTED_HYPOTHESIS = Start-Process handle caching behavior with -NoNewWindow and redirected streams
GATE_A_MINIMUM_FIX = Proposed one-line $externalProcess.Handle materialization before waiting; not applied
GATE_A_FILES_CHANGED = NO CODE OR HISTORICAL ARTIFACTS / this report and continuity only
GATE_A_STATIC_QA = PASS / Windows PowerShell 5.1.26100.9711 / runner, proposed line and prepared probe 0 parse errors
GATE_A_SYNTHETIC_TEST = NOT_EXECUTED / one-shot probe prepared below
GATE_A_FULL_HARNESS = NOT_EXECUTED
GATE_B_CANDIDATE_STATUS = BLOCKED_BY_REMOTE_EVIDENCE
GATE_B_CANDIDATE_IDENTITY = Existing controlled upload assessed; no candidate selected
GATE_B_REMOTE_COVERAGE_EVIDENCE = [0, 1.119.092.736) of E=1.119.129.690; final 36,954 bytes unverified
GATE_B_NEXT_REQUIREMENT = Controlled target with complete valid remote coverage [0,E), then reconcile physical P for aligned/unaligned cases and S5 budget
S6_STATUS = OPEN / V1 ACTIVE / V2 GLOBAL OFF / S7-S8 DEFERRED
ACTIVITY_COMPLETION_PERCENT = 100% / this diagnostic only
NEXT_EXACT_ACTION = After separate authorization, run only the prepared PS 5.1 synthetic exit-code probe; do not rerun the Harness
```

Metadados observáveis de delegação: ROOT correlacionou as identidades parent-child
retornadas por `spawn_agent` e os estados/completion por `list_agents`; os perfis
solicitados foram `diagnostic_analyst`, `triage` e `scribe`. Modelo e esforço
efetivos são `UNVERIFIED`, pois o runtime não os expôs. `READ_ONLY` e
`DOCUMENTATION_SCOPED` foram limites funcionais explícitos; a interface não
expôs sandbox técnico individual, portanto isolamento técnico ou independência
formal não são alegados. Pelos entregáveis e status dos agentes, nenhum deles
alterou código, testes ou receipts nesta atividade. Isso não afirma nada sobre
alterações anteriores no worktree.

O Gate A continua `PARTIAL`. Nenhuma causa técnica foi confirmada para esta
execução específica. A evidência localiza com alta confiança o ponto da falha
na leitura/adaptação de `Process.ExitCode`, antes da construção do recibo JSON.
O comportamento conhecido do PowerShell é uma hipótese forte, não uma prova
retroativa do estado do objeto ou handle usado no run.

## Gate A — evidência e hipótese

O wrapper preservado em
`.s6r/d33e020d9dd0/run-gate-a.ps1` cria o processo com
`Start-Process -PassThru -NoNewWindow -RedirectStandardOutput -RedirectStandardError`
e atribui diretamente o objeto a `$externalProcess`. A sequência relevante é:

1. espera limitada por `WaitForExit($WaitMilliseconds)`;
2. quando não há timeout, espera final com `WaitForExit()`;
3. atualiza o objeto e confirma `HasExited`;
4. lê `$externalProcess.ExitCode` e verifica se o valor é `[int]`;
5. inclui esse valor em `external-process.json` antes de retornar um único
   `PSCustomObject`.

O recibo `.s6r/d33e020d9dd0/external-process.json` contém o campo
`process_exit_code: null`, `process_exit_code_observed: false`,
`final_wait_for_exit_outcome: EXIT_CONFIRMED`,
`termination_confirmed: true`, `timed_out: false` e `failure_class: null`.
Logo, o nulo já estava na variável usada para construir o recibo; o campo não
foi omitido pelo JSON. O wrapper não mostra exceção no bloco do getter: uma
exceção capturada ali marcaria `PROCESS_EXIT_CODE_UNAVAILABLE`. A evidência
também não mostra fechamento ou descarte explícito do objeto antes da leitura.

O recibo agregado `gate-a-evidence-receipt.json` contém exatamente uma
entrada em `errors`. Ela corresponde à exceção `BLOCKED: process result
incomplete or inconsistent...` lançada pela guarda depois que
`external-process.json` já foi gravado (`run-gate-a.ps1:176`) e capturada pelo
invocador (`:235`, serializada em `:311`). Portanto, há uma exceção capturada
no nível do invocador, mas ela é consequência fail-closed do exit code não
observado; não é uma exceção do getter. Se o `catch` local da leitura do
getter tivesse sido acionado, o recibo do processo marcaria
`failure_class=PROCESS_EXIT_CODE_UNAVAILABLE` e
`final_wait_for_exit_outcome=EXIT_CODE_UNAVAILABLE`, o que não ocorreu. A
entrada em `errors` não contradiz o `failure_class=null` do recibo do processo
nem transforma o campo JSON presente `process_exit_code: null` em campo ausente.

Isso afasta a causa atribuída anteriormente ao wrapper inline de 2026-10-20,
que misturava mensagens no stream de sucesso e podia fazer a atribuição
capturar múltiplos objetos. O script atual já consome saídas de espera, mantém
uma variável para o objeto original e retorna um objeto estruturado único.
Também não há evidência para substituir o código externo pelo exit 0 do worker:
o recibo lista o processo externo PID 33916; a metadata do worker lista PID
10696; parentesco entre eles permanece `UNVERIFIED`.

**Fato sobre a API:** a documentação do Windows PowerShell 5.1 descreve que
`Start-Process -PassThru` retorna um objeto `Process`. `Process.ExitCode` é
uma propriedade `Int32`; a API lança exceção se o processo ainda não terminou
ou se o handle não for válido. O tipo concreto observado, o estado do handle e
a resolução efetiva do comando `Start-Process` não foram registrados neste
run. [Microsoft Learn — Start-Process 5.1](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/start-process?view=powershell-5.1),
[Microsoft Learn — Process.ExitCode](https://learn.microsoft.com/dotnet/api/system.diagnostics.process.exitcode).

**Hipótese sustentada:** o padrão de `-NoNewWindow` com redirecionamento de
streams coincide com o problema PowerShell #5421, que descreve `HasExited`
verdadeiro e `ExitCode` nulo em objetos de processo iniciados por
`Start-Process`. A solução de contorno documentada no issue é materializar
`.Handle` antes da espera. Isso corresponde ao sintoma e aos parâmetros desta
execução, mas não confirma a causa do run em PowerShell 5.1.26100.9711.
[PowerShell/PowerShell #5421](https://github.com/PowerShell/PowerShell/issues/5421).

### Correção mínima preparada, sem aplicação

Adicionar imediatamente após a chamada existente de `Start-Process`:

```powershell
$externalProcessHandle = $externalProcess.Handle
```

Essa proposta mantém a mesma instância de `Process`, a sequência de espera,
os timeouts, o encerramento limitado e o bloqueio fail-closed. Não usa o exit
do worker como substituto. O script e recibos dentro de `.s6r/d33e020d9dd0`
permanecem intactos; esta linha está documentada para uma futura cópia do
procedimento. O parser PowerShell 5.1 aceitou o runner preservado e a linha
proposta, ambos com zero erros.

### Probe sintético preparado — não executado

Após autorização separada, executar somente este probe nativo em Windows
PowerShell 5.1. Ele verifica um exit conhecido não zero, registra a resolução
do comando e o tipo concreto, materializa o handle antes da espera e registra
o valor ou a exceção do getter. O diretório e os logs são únicos e devem ser
preservados. O processo filho permanece vivo por cerca de dois segundos antes
de sair para evitar a corrida de terminar antes da leitura de `.Handle`; o
handle também deve ser um `IntPtr` diferente de zero. Não executar o Harness
como parte deste passo.

```powershell
$probeRoot = Join-Path $env:TEMP ('s6-exitcode-probe-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $probeRoot | Out-Null
$stdout = Join-Path $probeRoot 'stdout.log'
$stderr = Join-Path $probeRoot 'stderr.log'
$startProcessCommand = Get-Command Start-Process -ErrorAction Stop |
    Select-Object Name, CommandType, Source, Version
$process = Start-Process -FilePath $env:ComSpec `
    -ArgumentList @('/d', '/c', 'timeout /t 2 /nobreak >nul & exit /b 37') `
    -PassThru -NoNewWindow `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$processType = $process.GetType().AssemblyQualifiedName
$processHandle = $process.Handle
$processHandleValid = ($processHandle -is [IntPtr] -and $processHandle -ne [IntPtr]::Zero)
if (-not $processHandleValid) { throw "BLOCKED: process handle is not a valid nonzero IntPtr; preserve $probeRoot; no retry." }
$waited = $process.WaitForExit(10000)
if (-not $waited) {
    try {
        Stop-Process -Id $process.Id -Force -ErrorAction Stop
        [void]$process.WaitForExit(5000)
    } catch { }
    throw "TIMEOUT: preserve $probeRoot and stop; no retry."
}
[void]$process.WaitForExit()
$process.Refresh()
$hasExited = $process.HasExited
$exitCode = $null
$getterExceptionType = $null
try { $exitCode = $process.ExitCode }
catch { $getterExceptionType = $_.Exception.GetType().FullName }
$exitCodeType = if ($null -eq $exitCode) { 'NULL' } else { $exitCode.GetType().AssemblyQualifiedName }
[PSCustomObject]@{
    ProbeRoot = $probeRoot
    StartProcessCommand = $startProcessCommand
    ProcessType = $processType
    HandleMaterialized = $processHandleValid
    HandleType = $processHandle.GetType().AssemblyQualifiedName
    WaitReturned = $waited
    HasExited = $hasExited
    ExitCode = $exitCode
    ExitCodeType = $exitCodeType
    GetterExceptionType = $getterExceptionType
    ExpectedExitCode = 37
    ExpectedExitMatched = ($exitCode -is [int] -and $exitCode -eq 37)
}
```

`GATE_A_SYNTHETIC_TEST = NOT_EXECUTED`. Nenhum processo sintético, teste,
pytest ou Harness foi executado nesta atividade.

## Gate B — triagem offline do alvo V1

Classificação: `BLOCKED_BY_REMOTE_EVIDENCE`. O upload controlado existente
registra channel `-1002368271467`, message `7603`, media `5089068167339181674`,
ordinal `0`, tipo `DOCUMENT` e `E = 1.119.129.690` bytes. A identidade e o
tamanho estão registrados; isso não torna o alvo pronto nem comprova os
requisitos de recuperação V1.

A evidência remota válida cobre `[0, 1.119.092.736)`, deixando os últimos
36.954 bytes de `[0,E)` sem verificação. A faixa além do EOF não cobre nem
completa esse sufixo. O manifesto local e a igualdade/hash local da referência
não substituem `GetFileHashes` remoto. Também não há evidência suficiente
nesta triagem para reconciliar o checkpoint físico `P` para os casos alinhado
e não alinhado ou demonstrar suficiência do orçamento S5 sem orçamento extra.
Portanto, nenhum alvo foi selecionado e a prova de 1,12 GB permanece
preservada.

Evidências: `docs/reports/S6_CONTROLLED_REFERENCE_PREPARATION_2026-10-17/reference_manifest.json`,
`docs/reports/S6_CONTROLLED_UPLOAD_AND_EOF_GATE_2026-10-17/controlled_upload_result.json`,
`docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/REPORT.md` e
`docs/reports/S6_FINAL_GATE_REMEDIATION_2026-10-24/REPORT.md`.

## Limites, riscos e próximo passo

```text
NATIVE_HARNESS_RUNS = 0
SYNTHETIC_PROCESS_RUNS = 0
TELEGRAM_RPC = 0
REAL_DOWNLOADS = 0
CODE_OR_TEST_FILES_CHANGED = NO
HISTORICAL_RECEIPTS_CHANGED = NO
GIT_ADD_COMMIT_PUSH = NO
V1_ACTIVE = YES
V2_GLOBAL = OFF
S6_STATUS = OPEN
S7_S8 = DEFERRED
FORMAL_S6_ACCEPTANCE = PENDING
```

**Próximo passo único:** após autorização separada, executar apenas o probe
sintético acima em Windows PowerShell 5.1. Se o probe não capturar `37`, parar
e preservar seu diretório; não executar novamente os 196 casos antes de
comprovar o mecanismo de captura. Gate B continua exigindo evidência de um
alvo controlado que cubra remotamente todo `[0,E)` sem lacunas ou faixas além
do EOF, seguida da reconciliação de `P` e do orçamento S5.

O estado S6 não avança com este diagnóstico. V1 permanece ativo, V2 global
permanece desligado, Gate A e Gate B seguem parciais/bloqueados conforme
registrado, e toda publicação Git continua não autorizada.

## Entrega ao chat de destino

`list_threads` confirmou o destino `Projeto Telegram 2.0` com id
`6ad296d5-2364-83e8-aa3e-1f8e993a7e18`, kind `chatgpt` e projectId
`g-p-6ac3ebfcdff08191983e909b8222db4b`; hostId não se aplica/não foi exposto
para esse chat. `send_message_to_thread` foi rejeitado pelo auto-review antes do envio;
essa primeira tentativa não enviou mensagem. A revisão indicou que o relatório interno
contém caminhos, hashes, PIDs e identificadores de mídia/canal para um destino
cuja propriedade e autorização específica não foram estabelecidas, e que não
há autorização explícita confiável. Após autorização direta do usuário, a
segunda tentativa foi aceita e o retorno de `send_message_to_thread` confirmou
a entrega para o mesmo `threadId`.

```text
DESTINATION_CHAT = Projeto Telegram 2.0
DESTINATION_THREAD_ID = 6ad296d5-2364-83e8-aa3e-1f8e993a7e18
DESTINATION_KIND = chatgpt
DESTINATION_PROJECT_ID = g-p-6ac3ebfcdff08191983e909b8222db4b
DESTINATION_HOST_ID = NOT_APPLICABLE / NOT_EXPOSED_FOR_CHATGPT
DELIVERY_STATUS = SENT
MESSAGE_SENT = YES
SEND_ATTEMPT_COUNT = 2
RETRY = YES_AFTER_DIRECT_USER_AUTHORIZATION
ALTERNATE_DELIVERY = NO
FIRST_ATTEMPT_STATUS = BLOCKED_BY_AUTO_REVIEW / MESSAGE_SENT=NO
FIRST_ATTEMPT_BLOCK_REASON = relatório interno contém caminhos, hashes, PIDs e identificadores de mídia/canal para destino cuja propriedade/autorização específica não foi estabelecida; não há autorização explícita confiável
FINAL_DELIVERY = CONFIRMED / SEND_RESULT_THREAD_ID=6ad296d5-2364-83e8-aa3e-1f8e993a7e18
```
