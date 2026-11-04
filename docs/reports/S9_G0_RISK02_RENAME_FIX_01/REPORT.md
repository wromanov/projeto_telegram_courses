# S9-G0 RISK-02 — correção offline do guard

ACTIVITY_ID = TELEGRAM_S9_G0_RISK02_RENAME_FIX_01  
DATE = 2026-10-30  
EXECUTION = DIRECT

ROOT_CAUSE = IMPLEMENTATION: o handle era aberto apenas com FILE_READ_ATTRIBUTES. No Windows observado, esse acesso somente a atributos não tornou efetiva a restrição de compartilhamento para o rename. Antes da alteração, o teste reproduziu a falha (1 failed); acrescentar FILE_LIST_DIRECTORY ao acesso, mantendo FILE_SHARE_READ | FILE_SHARE_WRITE e omitindo FILE_SHARE_DELETE, fez o teste passar. A documentação Microsoft distingue acessos a atributos das regras de compartilhamento e informa que DELETE permite rename: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew. A relação causal é sustentada pela mudança isolada e reprodução local; não é uma prova de todos os filesystems.

CreateFileW usa assinatura com retorno de largura de ponteiro e argumentos tipados; OPEN_EXISTING, BACKUP_SEMANTICS e OPEN_REPARSE_POINT permanecem. INVALID_HANDLE_VALUE e NULL levam a erro fechado, embora o código não registre GetLastError e não haja código de erro nativo específico observado. O handle permanece vivo no guard e é fechado em close e nos caminhos de erro de validação. A DACL explícita e sua verificação não foram modificadas. A identidade por caminho final do handle é agora revalidada a cada verify, além da conferência do caminho solicitado. A alteração não estabelece proteção geral contra um adversário da mesma conta ou substituição arbitrária de ancestrais.

FILES_CHANGED = src/telegram_courses/s9_operational_ledger.py; tests/unit/test_s9_operational_ledger.py; este relatório; docs/continuity/PROJECT_STATE.md. Todos os arquivos S9 já eram WIP não rastreado.

RISK02_STATUS = CORRECTION_IMPLEMENTED / FOCUSED_AND_S9_TESTED_IN_CODEX_AND_NATIVE / não é aceite integral G0. Testes sintéticos demonstraram bloqueio de rename com guard ativo, rename após close, rejeição de caminho incompatível e handle trocado, falha fechada antes da criação do ledger, fechamento após falha e verificação de DACL. Não foi demonstrada ausência universal de vazamentos ou resistência a toda troca de ancestrais.

FOCUSED_TESTS = antes: 1 failed, 49 deselected, exit 1; após correção: 1 passed, 49 deselected, exit 0; versão final expandida: 3 passed, 49 deselected, exit 0. A primeira tentativa com python padrão falhou por ausência de pytest; a tentativa inicial com .venv falhou ao criar tmp_path padrão. Os testes efetivos usaram .venv e basetemp sintético no workspace.

FULL_S9_TESTS = versão final: 97 passed in 49.48s, exit 0, nos quatro arquivos S9, no executor Codex Windows. Ruff nos oito arquivos S9: PASS; compileall: PASS; git diff --check: PASS com avisos LF/CRLF em arquivos rastreados existentes. Git diff --check não cobre os arquivos não rastreados.

WINDOWS_NATIVE_VALIDATION = PASS / evidência fornecida pelo usuário: teste focado 1 passed, 51 deselected, 0.54s, exit 0; quatro arquivos S9 97 passed, 35.42s, exit 0. Comandos executados em PowerShell Windows externo, na raiz:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_s9_operational_ledger.py -k private_directory_handle_blocks_concurrent_rename
$LASTEXITCODE
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_s9_operational_ledger.py tests/unit/test_s9_supervisor.py tests/unit/test_s9_supervisor_cli.py tests/unit/test_s9_supervisor_handshake.py
$LASTEXITCODE
```

SECURITY_IMPACT = compartilhamento sem delete efetivo no teste local; DACL preservada; sem alegação de cobertura universal. RISK-01 e RISK-03 não foram reabertos. REAL_TELEGRAM_RPC, login/scan/download reais, escrita em DB operacional, alteração contratual, stage/commit/push, G0 real e S10 não realizados.

WIP_PRESERVED = YES; nenhum WIP anterior descartado ou staged. Diretórios temporários de teste novos foram preservados.

NEXT_ACTION = prosseguir com os demais gates de G0 somente mediante suas authorities. Nenhum aceite integral G0 declarado.

DELIVERY_STATUS = SEND_ACCEPTED / isError=false / destino Projeto Telegram 3.0 / threadId 6add6aa9-12e0-83e8-b02f-870f0a0edaf9  
MESSAGE_OBSERVED = YES para o relatório anterior; resposta do chat confirmou recebimento. Atualização com validação nativa: SEND_ACCEPTED / isError=false; MESSAGE_OBSERVED=NO na leitura imediata, chat ativo.
