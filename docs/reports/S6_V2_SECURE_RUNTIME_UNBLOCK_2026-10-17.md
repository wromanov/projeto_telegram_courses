# S6 V2 secure runtime unblock — 2026-10-17

```text
ACTIVITY = S6_V2_SECURE_RUNTIME_UNBLOCK
ENVIRONMENT_ROOT_CAUSE = CODEX_EXECUTION_SANDBOX_REDIRECTED_LOCALAPPDATA
SECURE_VAULT_AVAILABLE = YES / WINDOWS_CURRENTUSER_DPAPI / STATUS_ONLY
PROTECTED_SESSION_AVAILABLE = YES / DECRYPTED_IN_MEMORY_ONLY
CORRECT_WINDOWS_CONTEXT = YES / ROMA_CASA\walac / C:\Users\walac
SAFE_RECOVERY_STATUS = PASS / PROCESS_SCOPED_LOCALAPPDATA_OVERRIDE / NO_COPY_EXPORT_OR_NEW_AUTH
DRYRUN = PASS / PLAN_ONLY_SQLITE / NO_NETWORK / V2_FALSE
PREFLIGHT_READY = YES / NATIVE_CONFIRMATION_AND_PHASE_1_IDENTITY_GATE_STILL_REQUIRED
LIVE_TELEGRAM_IDENTITY = NOT_CHECKED
SECRETS_EXPOSED = NO
REAL_TELEGRAM_CALLS = 0
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
```

## Diagnóstico

O processo usado pelo Codex era PowerShell Core nativo no Windows, sob a
identidade `ROMA_CASA\walac` e o perfil `C:\Users\walac`; não havia marcador de
WSL, container ou sessão remota. O runtime de execução, porém, redirecionava
`LOCALAPPDATA` para uma pasta `Packages\sandbox.*\AC` isolada e variável por
invocação. O projeto resolve os caminhos de `credentials.dpapi` e
`session.dpapi` relativamente a `LOCALAPPDATA`. Assim, os dois artefatos
pareciam ausentes naquele sandbox, embora existam no caminho padrão do perfil
Windows.

O código do provedor confirma uso da API nativa Windows DPAPI
`CryptUnprotectData` no contexto CurrentUser; a dependência é `ctypes` da
biblioteca padrão do Python e as bibliotecas Win32 do sistema. Não foi
identificada dependência de segurança ausente nem diferença de identidade do
usuário Windows. Nenhum conteúdo protegido foi impresso.

## Recuperação segura e validação

Para uma única invocação, `LOCALAPPDATA` foi apontado temporariamente para
`C:\Users\walac\AppData\Local` e o valor anterior foi restaurado no bloco
`finally`. Não houve alteração persistente do ambiente, código, cofre ou
permissões; nenhum arquivo foi copiado, exportado ou convertido; nenhuma
autenticação nova foi criada.

No contexto corrigido, o status não sensível do CLI confirmou o cofre
configurado e disponível. A sessão protegida foi descriptografada somente em
memória; o objeto foi descartado sem emitir conteúdo. O DryRun passou no root
isolado abaixo, apenas com SQLite de prova e relatório:

`C:\Users\walac\desenvolvimento\projeto_telegram_courses\.s6-v2-secure-unblock-8aa41b77\s6-v2-real-proof-10e9c9b8fe954bb79a11e7c19508ce64`

```text
DRYRUN = PASS / PLAN-ONLY SQLITE / NO NETWORK / V2 FALSE
REAL_TELEGRAM_CALLS = 0
ORIGINAL_SQLITE_ACCESS = NO
HISTORICAL_PART_ACCESS = NO
NATIVE_EXECUTE_CONFIRMATION = NOT_REQUESTED_OR_USED
PHASE_1 = NOT_STARTED
PHASE_2 = NOT_STARTED
```

Disponibilidade local da sessão não confirma a identidade remota do Telegram.
Essa identidade deve ser revalidada pelo gate da fase 1 durante a prova já
autorizada. Antes de qualquer chamada real, o launcher deve receber a
confirmação nativa exata; esta atividade não acionou `Execute`.

## Próxima ação

Retomar somente a prova alinhada única já autorizada, usando o contexto Windows
que lê o perfil padrão e mantendo `LOCALAPPDATA` process-scoped no launcher.
Exigir a confirmação nativa antes de qualquer chamada real e parar se a
validação de identidade da fase 1 não corresponder ao alvo autorizado. Não
iniciar prova adicional, aceite S6, avanço de sprint ou publicação Git.
