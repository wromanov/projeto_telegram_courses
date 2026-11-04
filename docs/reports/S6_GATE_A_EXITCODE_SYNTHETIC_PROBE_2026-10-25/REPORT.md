# Relatório — probe sintético de ExitCode do Gate A da S6

- **Data:** 2026-10-25 (America/Sao_Paulo)
- **Atividade:** `S6_GATE_A_EXITCODE_SYNTHETIC_PROBE`
- **Repositório:** `projeto_telegram_courses`
- **Branch / HEAD observados:** `work/s0-bootstrap` / `98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`

## Registro da atividade

```text
ACTIVITY_ID = S6_GATE_A_EXITCODE_SYNTHETIC_PROBE
ACTIVITY_COMPLETION_PERCENT = 100%
EXECUTION_MODE = MULTI-AGENT
ROUTER_INVOCATION = USER_EXPLICIT / codex-task-router applied
AGENTS_USED = scout, mechanical_implementer, scribe
AUTHORIZATION_SCOPE = uma probe sintética; artefatos isolados; relatório e cópia proposta do wrapper
CODEX_LOCAL_STATUS = não apto para a execução exigida: sessão em pwsh 7.6.5 bundled e TEMP sob Packages/sandbox.*
DC_FALLBACK_USED = YES
DC_FALLBACK_JUSTIFICATION = a integração local não atendia ao requisito de PowerShell 5.1 nativo; o host autorizado via DC foi verificado antes da execução
PROBE_EXECUTIONS = 1
FULL_HARNESS_EXECUTIONS = 0
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
GIT_ADD_COMMIT_PUSH = NO
DELIVERY_DESTINATION = Projeto Telegram 3.0
DELIVERY_STATUS = SENT
DELIVERY_CONFIRMATION = relatório completo enviado à conversa existente Projeto Telegram 3.0; a ferramenta confirmou sucesso
PREVIOUS_DELIVERY_ATTEMPT = envio ao chat existente “Projeto Telegram 2.0” rejeitado pelo auto-review
PREVIOUS_DELIVERY_BLOCK_REASON = a ação enviaria ao chat um relatório com caminhos locais, hashes e detalhes internos; não há autorização explícita do usuário para esse destino e payload específicos
DELIVERY_RESTRICTION = não contornar a revisão
```

O handoff histórico `S6_TRANSICAO_NOVO_AGENTE_2026-10-24.md` foi localizado como anexo do chat `Projeto Telegram 3.0` e lido em `C:\Users\walac\AppData\Local\Temp\codex-file-preview-LBwpx8\S6_TRANSICAO_NOVO_AGENTE_2026-10-24.md`. Naquele handoff, a probe constava como não autorizada, com prioridade para `CODEX_LOCAL` e uso de DC somente diante de limitação concreta. A ficha atual, submetida posteriormente, autorizou uma execução sintética única e fallback condicional. A integração local falhou no preflight para execução nativa (PowerShell 7.6.5 bundled e TEMP sob `Packages\sandbox.*`), justificando o fallback; o host DC foi então confirmado como Windows PowerShell 5.1 nativo.

## Preflight e execução

O host de execução foi `ROMA_CASA`, Windows 10.0.26200, com Windows PowerShell `5.1.26100.9711` (`Desktop`) em `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe`. O processo não estava em AppContainer. `$env:TEMP` apontava para `C:\Users\walac\AppData\Local\Temp`; `$env:ComSpec` estava disponível em `C:\WINDOWS\system32\cmd.exe`. `Start-Process` resolveu para o cmdlet do módulo `Microsoft.PowerShell.Management`; o parser do PowerShell 5.1 retornou zero erros.

Foi criado o diretório exclusivo `C:\Users\walac\AppData\Local\Temp\s6-exitcode-probe-8235dd7cad254151903e1d07ad5713d3`. Ele não conflita com o repositório ou com os recibos históricos em `.s6r/d33e020d9dd0/`.

O processo sintético observado foi `System.Diagnostics.Process` (PID `35632`). Imediatamente após `Start-Process`, o tipo do handle era `System.IntPtr` e o handle era válido. `WaitForExit(10000)` retornou `true`, sem timeout; a espera final foi concluída, `Refresh()` foi chamado e `HasExited` retornou `true`. O getter de `ExitCode` não lançou exceção e retornou `37` como `System.Int32`. A duração medida foi `127.6928 ms`.

```text
POWERSHELL_VERSION = 5.1.26100.9711
START_PROCESS_RESOLUTION = Cmdlet / Microsoft.PowerShell.Management
PROCESS_TYPE = System.Diagnostics.Process, System, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089
PROCESS_HANDLE_VALID = YES / System.IntPtr
PROCESS_WAIT_RESULT = WaitForExit(10000)=true; timeout=false; final WaitForExit concluído
PROCESS_HAS_EXITED = true
EXPECTED_EXIT_CODE = 37
OBSERVED_EXIT_CODE = 37 / System.Int32
GETTER_EXCEPTION = nenhuma
PROBE_VERDICT = PASS_SYNTHETIC
```

O verdict segue os critérios explícitos da ficha: host e versão corretos, handle válido, processo terminado, `HasExited=true`, código observado `37` e evidências íntegras. `stdout.log` está vazio. `stderr.log` tem 99 bytes e registra que `timeout /t 2 /nobreak` não suporta a entrada redirecionada e saiu imediatamente. Portanto, o atraso pretendido de dois segundos não ocorreu; a observação demonstra a captura do código para o processo sintético de saída rápida executado, e não valida um cenário com espera efetiva de dois segundos. O arquivo original de stderr permanece preservado, mesmo que sua visualização textual contenha caracteres substituídos.

## Artefatos e integridade

Os cinco arquivos abaixo foram criados somente no diretório isolado do probe. O manifesto lista os três artefatos primários (`probe-result.json`, `stdout.log` e `stderr.log`); `integrity-verification.json` registra a verificação do manifesto e dos hashes. Todos os itens listados foram conferidos: tamanhos e SHA-256 corresponderam.

| Arquivo | Tamanho | SHA-256 |
|---|---:|---|
| `probe-result.json` | 2691 bytes | `f8c2566ac8b931ae1d544419c114ca73dfaa3f074c3059ff6b82b052a478c160` |
| `stdout.log` | 0 bytes | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `stderr.log` | 99 bytes | `830d0ac59ba9f5f412cc5e57ac3c48040cc2255e9fba5a83494fccb4b40a16f2` |
| `manifest.json` | — | `f6e0d68b45771e4f2d015c75ccb6fdf8f8c9f355abf13fec08b3b166e485f8ec` |
| `integrity-verification.json` | — | `344d64a312e3cc9c8725e6ed4d74342970b8499adbf7578798746f0bd4b98e09` |

Diretório dos artefatos: `C:\Users\walac\AppData\Local\Temp\s6-exitcode-probe-8235dd7cad254151903e1d07ad5713d3`.

## Proposta isolada do wrapper

Como o resultado sintético foi positivo, uma cópia proposta do wrapper foi criada em [run-gate-a.proposed.ps1](run-gate-a.proposed.ps1). A única alteração proposta é inserir `$null = $externalProcess.Handle` imediatamente após a chamada a `Start-Process`. A cópia não foi executada; não houve implementação no wrapper histórico nem em código ativo.

```text
PROPOSED_COPY_SHA256 = c772baa74b1c1800f8064fdbd919b85fd95b3f6ba536829445dba1f3d3268eaf
HISTORICAL_SOURCE_SHA256 = e62730c3f6a6f416443b26c256c1a5cbdfaf16360399ee40a551ae97d0b3283f
SOURCE_PRESERVED = YES
```

## Estado herdado e limites da conclusão

```text
GATE_A_STATUS = PARTIAL
GATE_B_STATUS = BLOCKED_BY_REMOTE_EVIDENCE
S6_STATUS = OPEN
V1_ACTIVE = YES
V2_GLOBAL = OFF
S7_S8 = DEFERRED
ROOT_CAUSE_STATUS = NOT_CONFIRMED
```

O triage histórico registra `196/196 PASS` funcional e um `ExitCode` externo nulo, mas esses testes não foram repetidos. A relação entre o processo externo histórico PID `33916` e o worker não foi comprovada. Esta probe não determina retroativamente o código daquele processo nem confirma a causa raiz histórica; a materialização do handle permanece uma hipótese para investigação separada.

Riscos residuais: o subcomando de atraso terminou imediatamente por não suportar entrada redirecionada; o resultado cobre somente a captura no processo sintético observado; o wrapper proposto ainda precisa de decisão do usuário; nenhuma execução do Harness foi autorizada nesta atividade.

**Próxima ação exata:** revisar a cópia proposta e decidir separadamente se autoriza a implementação dessa linha e qualquer futura execução do Harness. Gate A continua `PARTIAL`; S6 continua `OPEN`.

## Campos de entrega e rastreabilidade

```text
FILES_CREATED =
  docs/reports/S6_GATE_A_EXITCODE_SYNTHETIC_PROBE_2026-10-25/REPORT.md
  docs/reports/S6_GATE_A_EXITCODE_SYNTHETIC_PROBE_2026-10-25/run-gate-a.proposed.ps1
  C:\Users\walac\AppData\Local\Temp\s6-exitcode-probe-8235dd7cad254151903e1d07ad5713d3\probe-result.json
  C:\Users\walac\AppData\Local\Temp\s6-exitcode-probe-8235dd7cad254151903e1d07ad5713d3\stdout.log
  C:\Users\walac\AppData\Local\Temp\s6-exitcode-probe-8235dd7cad254151903e1d07ad5713d3\stderr.log
  C:\Users\walac\AppData\Local\Temp\s6-exitcode-probe-8235dd7cad254151903e1d07ad5713d3\manifest.json
  C:\Users\walac\AppData\Local\Temp\s6-exitcode-probe-8235dd7cad254151903e1d07ad5713d3\integrity-verification.json
EVIDENCE_PATHS = C:\Users\walac\AppData\Local\Temp\s6-exitcode-probe-8235dd7cad254151903e1d07ad5713d3\{probe-result.json, stdout.log, stderr.log, manifest.json, integrity-verification.json}
EVIDENCE_SHA256 =
  probe-result.json = f8c2566ac8b931ae1d544419c114ca73dfaa3f074c3059ff6b82b052a478c160
  stdout.log = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  stderr.log = 830d0ac59ba9f5f412cc5e57ac3c48040cc2255e9fba5a83494fccb4b40a16f2
  manifest.json = f6e0d68b45771e4f2d015c75ccb6fdf8f8c9f355abf13fec08b3b166e485f8ec
  integrity-verification.json = 344d64a312e3cc9c8725e6ed4d74342970b8499adbf7578798746f0bd4b98e09
RESIDUAL_RISKS = timeout /t 2 não produziu o atraso de dois segundos; resultado limitado ao caso observado de saída rápida; causa histórica permanece não confirmada; proposta ainda não aprovada nem executada
NEXT_EXACT_ACTION = revisar a cópia proposta e decidir separadamente se autoriza a implementação e qualquer futura execução do Harness
```
