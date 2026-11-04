# Operação de fechamento técnico da S6 — 2026-10-20

~~~text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_FINAL_CLOSURE_OPERATION
RESULT = GATE_A_PARTIAL / TRUSTED_REFERENCE_OFFLINE_PREFLIGHT_PASS / S6_OPEN
ACTIVITY_COMPLETION_PERCENT = 100% / deliverables of this operation complete; S6 itself remains open
EXTERNAL_EXIT_EVIDENCE = NOT_PERSISTED
GATE_A_STATUS = PARTIAL
REFERENCE_SIZE_VERIFIED = YES / 1,119,129,690 bytes
REFERENCE_SHA256_VERIFIED = YES / 3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c
REFERENCE_ATTRIBUTES_PRESERVED = YES / Archive before and after; IsReadOnly=False accepted by contract
REFERENCE_ACL_PRESERVED = YES / SDDL SHA-256 unchanged before and after this preflight
TRUSTED_PREFLIGHT_STATUS = PASS / OFFLINE / RPC_CALLS=0
REAL_PROOF_EXECUTED = NO
REAL_PROOF_AUTHORIZATION = PENDING
S6_STATUS = OPEN
V1_ACTIVE = YES
V2_GLOBAL = OFF
S7_S8 = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
~~~

## Estado e limites desta operação

Branch work/s0-bootstrap, HEAD 98d9d6b9ce152b8d2764a4d160fcbdf4722fb257.
O worktree já estava amplamente alterado. Esta operação preservou todos os
artefatos e alterou somente este relatório e os três registros canônicos de
continuidade. Não alterou código, testes, launcher, recibos históricos,
SQLite, downloads parciais ou a referência; não executou testes, prova real,
RPC Telegram, autenticação, download, staging, commit ou push.

Authorities e fontes verificadas: PROJECT_STATE, CONTINUITY_RECORD,
LAST_HANDOFF, ACTIVE_AUTHORITY_MAP, binding de governança, contrato S6 V1,
contrato de regressão Harness, contratos/adendos TRUSTED_REFERENCE, relatório
de reconciliação final, launcher/harness e raízes nativas preservadas
.s6r/e5fca75a3aa7/ e .s6r/bcb2a1158934/.

## Gate A — evidência do processo externo

| Fonte preservada | Resultado funcional | Evidência do processo externo | Leitura |
|---|---|---|---|
| .s6r/e5fca75a3aa7/ — FOCUSED_12 | JUnit 12 casos, 0 falhas/erros/skips; stdout 12 passed in 41.46s | Recibo exit_code=null; não há worker-result.json. A reconciliação registra que o wrapper abortou porque focusedResult.ExitCode ficou nulo e informa orchestrator_exit_code=1. | O 1 é do wrapper que interrompeu a sequência; não é evidência do exit code do pytest. O exit externo continua desconhecido. |
| .s6r/bcb2a1158934/ — FULL_HARNESS | JUnit 196 casos, 0 falhas/erros/skips; stdout 196 passed in 78.60s | worker-result.json: Harness, worker exit_code=0, término reportado, 196 IDs coletados e executados iguais, xfail=xpass=0. Recibo externo exit_code=null. | O worker passou, mas não há exit code persistido para o processo externo. O recibo também registra PID 36236, enquanto a metadata do worker registra PID 18636; a diferença não foi explicada. |

O transcript PowerShell preservado contém o script e os PIDs de início, mas
não contém o valor avaliado de $worker.ExitCode. A saída final foi emitida
depois do encerramento do transcript. JUnit, stdout, metadata do worker e a
ausência posterior de workers Python não substituem o exit code externo
exigido. Não há evidência contraditória de falha dos testes; a classificação é
PARTIAL, não FAIL.

O contrato de regressão do Harness exige recibo válido, resultado de processo
zero, coleção/JUnit coerentes, conclusão normal do supervisor e zero skips e
xfails. Os recibos existentes não cumprem o campo externo obrigatório. Como
esse valor não pode ser reconstruído para processos já encerrados, a menor
remediação que efetivamente fecha o gate é uma única execução nativa,
autorizada separadamente, do perfil Harness completo, com o Process.ExitCode
externo persistido e reconciliado com os artefatos. Essa execução não ocorreu.
Não é necessário repetir a seleção focada para demonstrar os resultados
funcionais já registrados; uma verificação curta ou uma nova consulta de
processos não autenticaria o exit code do Harness histórico. A suíte completa
continua sendo último recurso e não será iniciada automaticamente.

## Gate B — preflight offline TRUSTED_REFERENCE

O preflight status-only do próprio harness retornou status=PASS,
rpc_calls=0, V1=true e V2_global_effective=false, usando o perfil controlado
e a raiz de evidência nativa exata. A referência foi aberta somente para
leitura binária. Tamanho e SHA-256 conferem com a declaração congelada.
O atributo Windows era Archive (IsReadOnly=False) antes e depois; o contrato
aceita ambos os estados e não exige alterar atributo. O digest do SDDL do ACL
foi DD9C123614FB382776BA2B29FC52CAC567E571AAA2FB3E565A162ABB84F21FE9
antes e depois. Caminho, identidade local, arquivo regular sem link/reparse,
integridade do conteúdo e estabilidade da identidade durante o hash passaram
na validação offline do harness. Não houve mutação da referência.

~~~text
CONTROLLED_TARGET = channel=-1002368271467 / message=7603 / media_id=5089068167339181674
MEDIA = DOCUMENT / ordinal=0 / bytes=1119129690
REFERENCE = C:\Users\walac\Downloads\64Gram Desktop\Teste Telegram.rar
REFERENCE_SHA256 = 3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c
REMOTE_IDENTITY = NOT_CHECKED / no RPC before confirmation
PREFIX_PROFILE = 8MiB / PREFIX_BYTES=8388608 / CHUNK_BYTES=262144 / ALIGNED=YES
GETFILE_CAP = 8508 / APPROVED_MAX=8508
GETFILEHASHES_CAP = 8542 / APPROVED_MAX=8542
IDENTITY_GETMESSAGES_CAP = 5 / APPROVED_MAX=5
RESERVED_BYTES_CAP = 2230321152 / APPROVED_MAX=2230321152
~~~

### Budgets, isolamento e salvaguardas confirmados

- Política efetiva TRUSTED_REFERENCE: inicialização 30 s; timeout por
  processo 4.500 s; deadline agregado 4.800 s; inatividade semântica 180 s;
  heartbeat 15 s; grace de cancelamento até 30 s dentro do deadline rígido.
  contract_match=true; hash da política confirmada pelo launcher:
  7bf629ed906f614fd963cdded149a1211af6de450d2a4b1c2559e14d079c2b1a.
- Limites S5 preservados: 1 worker, no máximo 3 tentativas agregadas por
  mídia (fase 1 = 1; fase 2 = 2), FloodWait cumulativo até 120 s. O launcher
  não relança a prova depois de falha/timeout; o teto interno de tentativas
  continua limitado ao contrato S5.
- O EvidenceParent controlado é %TEMP%\s6v2. A árvore nativa observada em
  C:\Users\walac\AppData\Local\Temp\s6v2 existe, seus componentes não são
  reparse points, e ela fica fora do repositório e da pasta da referência. Os
  caminhos planejados medem no máximo 117 caracteres, abaixo da guarda de
  240. O harness cria root novo e exclusivo; modo Execute recusa
  ResumeEvidenceRoot e não reutiliza roots históricos.
- O subprocesso atual desta conversa herda TEMP de AppContainer. Esse caminho
  não foi usado como root de prova. A sequência preparada exige Windows
  PowerShell 5.1 nativo e bloqueia TEMP/LOCALAPPDATA com assinatura de
  sandbox, sem substituí-los; o launcher revalida caminho, alvo, referência,
  status seguro e timeout antes da confirmação.
- Antes da confirmação, o launcher faz apenas verificações locais/status-only
  e imprime os valores efetivos. A identidade remota só é validada depois da
  confirmação e antes de qualquer GetFile/GetFileHashes.
- As fases usam processos distintos. A fase 2 só começa depois da saída da
  fase 1 e valida checkpoint persistido, identidade e prefixo de referência.
  Ao concluir, o child compara tamanho, SHA-256 e bytes com a referência; o
  supervisor repete a comparação byte a byte independentemente e verifica a
  referência novamente. Evidência ausente, mismatch ou timeout não pode ser
  convertido em PASS.
- Em qualquer falha ou timeout: preservar toda a nova raiz, parar e não
  reiniciar a prova automaticamente. O teto S5 interno não autoriza uma
  segunda execução da prova após resultado terminal.

## Procedimento nativo preparado — não executado

A execução real requer autorização explícita separada. Depois de obtida,
abrir uma janela Windows PowerShell 5.1 nativa fora do AppContainer, sem
alterar TEMP ou LOCALAPPDATA, ir à raiz do repositório e executar uma vez:

~~~powershell
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
    throw 'STOP: use Windows PowerShell 5.1.'
}
$sandboxPattern = 'AppData[\\/]+Local[\\/]+Packages[\\/]+sandbox\.'
if ([string]::IsNullOrWhiteSpace($env:TEMP) -or
    [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA) -or
    $env:TEMP -match $sandboxPattern -or
    $env:LOCALAPPDATA -match $sandboxPattern) {
    throw 'STOP: sandbox admission. Do not substitute either environment path.'
}
Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
& .\tools\manual_proofs\Invoke-S6V2Proof.ps1 -Mode Execute -Target controlled -IntegrityMode TRUSTED_REFERENCE -Case aligned -PrefixProfile 8MiB
~~~

O launcher deve exibir o timeout efetivo, identidade declarada, budgets,
estado V1/V2 e preflight da referência antes de abrir Read-Host. Somente após
a autorização separada e a revisão desses valores, a confirmação manual
literal para este perfil é:

~~~text
EXECUTE S6 V2 PROOF controlled TRUSTED_REFERENCE channel=-1002368271467 message=7603 media=5089068167339181674 bytes=1119129690 aligned PREFIX_PROFILE=8MiB PREFIX_BYTES=8388608 GETFILE_CAP=8508 HASHES_CAP=8542 IDENTITY_GETMESSAGES_CAP=5 RESERVED_BYTES=2230321152
~~~

Se qualquer admissão, status, budget, timeout, identidade, saída de processo,
recibo ou reconciliação falhar, não confirmar ou, se já confirmado, preservar
evidência e parar sem repetir.

## Fechamento e próxima ação

~~~text
NATIVE_EXECUTION_PROCEDURE = PREPARED / this report / NOT EXECUTED
BLOCKERS = GATE_A_EXTERNAL_EXIT_NOT_PERSISTED; REAL_PROOF_AUTHORIZATION_PENDING; REMOTE_IDENTITY_NOT_CHECKED
REMAINING_ACCEPTANCE_REQUIREMENTS = VALID_NATIVE_HARNESS_EXIT_RECEIPT; REAL_TRUSTED_REFERENCE_PROOF; EXPLICIT_USER_ACCEPTANCE
S6_STATUS = OPEN
ACTIVITY_COMPLETION_PERCENT = 100% / this reconciliation and preparation only
NEXT_EXACT_USER_ACTION = Separately authorize one corrected native Harness run for Gate A and the controlled real proof for Gate B; after proof evidence is reconciled, decide formal S6 acceptance.
~~~

Nenhum aceite formal é recomendado agora. O Gate A permanece parcial, o
preflight offline do Gate B passou, mas prova real e identidade remota ainda
não existem. S6 permanece aberta; V1 segue ativa, V2 global permanece OFF,
S7/S8 continuam diferidas e o checkpoint de sprint não avança.
