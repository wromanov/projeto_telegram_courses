# TELEGRAM-3-RESUME-FINAL-01 — terceira tentativa exclusiva do MP4 585

## Status e limites
**READY_FOR_HUMAN_G0_G4.** Nenhuma terceira tentativa de download foi executada durante a preparação deste artefato. A autorização do operador cobre somente mais UMA tentativa do vídeo 585 do canal RASMOO (ID -1002758699600), curso Candidato de Ouro, módulo Competências (44), 1 worker, 1 tentativa da fila, máximo 1.800 s, e orçamento de reservas GetFile de **6.291.456 bytes**. Integridade **REMOTE_HASH_REQUIRED / REMOTE_HASH_FULL** e hashes remotos completos, sem downgrade. Proibidos novos downloads de outros vídeos, mudanças no S9 e operações Git.

Estado prévio comprovado com SQLite local em modo somente leitura: FAILED_RETRYABLE / GATEWAY_FAILURE, attempts=2, downloaded_bytes=6.029.312; o `.part` existe e possui o tamanho esperado. Faltam **170.323 bytes úteis**. O marcador de segunda tentativa permanece; o de terceira não existe antes da aprovação humana. O SQLite está íntegro e os vídeos 586/587 não têm tentativas registradas.

## Entrega local
- `tools/telegram_3_resume_585_third_guard.py`: valida catálogo, identidade, estados das três mídias, DB quick_check, origem e segurança dos caminhos, contagem de tentativas, condição do `.part`, hash local do prefixo, e marcadores. Não acessa Telegram. Pós-sucesso verifica arquivo final, SHA-256 completo, prefixo original, attempts=3, ausência de outros downloads e classificação ALREADY_VALID.
- `tools/RUN_TELEGRAM_3_RECOVER_585_THIRD_ONCE.ps1`: launcher PowerShell 5.1 do operador. Pré-check antes e depois de G0 para detectar mudança do `.part`; G0 simples **SIM**, seguido por plano fresco e G4 **s**. Cria marcador `resume_final_01_recover585_third.started` por CreateNew (sem sobrescrita), após G0 e antes de G4, contendo SHA-256 do prefixo e escopo. Uma recusa do G4 consome o marcador de execução, evitando reexecução automática.
- `tools/telegram_3_resume_final_guard.py`: ajustado somente para reconhecer futuro recibo da wave 1 com total_attempts=3 e os dois marcadores, sem alterar contrato S9. Wave 2 não faz parte desta autorização.
- Em sucesso gera recibo `resume_final_01_stage1.json` com attempts=3 e habilitação futura de wave2 sob nova autorização humana.

## Verificação offline
- Preflight no produto: **PASS**, prefixo 6.029.312, restante 170.323, reserva máxima 6.291.456.
- Pós-condição antes de executar: corretamente **BLOCKED**.
- Dry-run CLI G4=n: SELECTED_MEDIA_COUNT=1, PENDING_MEDIA_COUNT=1, PENDING_BYTES=170323, LIMIT_CHECK_RESULT=PASS, REMOTE_HASH_FULL, nenhuma RPC: **PASS**.
- Regressão: **158 testes PASS**, incluindo S9, hash remoto e simulações de retomada sintética; Ruff/compileall/PowerShell AST **PASS**.
- Durante a preparação: 0 chamadas Telegram; 0 mídia baixada; 0 tentativas adicionais consumidas; nenhum Git.

## Execução manual no ROMA_CASA (PowerShell 5.1)
    Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
    & '.\tools\RUN_TELEGRAM_3_RECOVER_585_THIRD_ONCE.ps1'

O operador deve digitar **SIM** no G0, conferir o plano com **somente mídia 585**, PENDING_BYTES=170323, LIMIT_CHECK_RESULT=PASS, garantia REMOTE_HASH_FULL, e digitar **s** no G4 somente se os dados conferirem. Não existe código aleatório nem re-seleção do módulo. A autorização não permite executar diretamente a CLI sem esse launcher.

Em caso de falha: preservar os marcadores, arquivos e banco, registrar somente evidências sanitizadas, não repetir. Nenhum contrato S9 passa a ser aprovado por este piloto. No sucesso: imprimir `RECOVERY585_THIRD_POST=PASS` e `RECOVERY585_THIRD_PASS`, confirmar que mídia 585 está DOWNLOADED com 3 tentativas, que o MP4 tem 6.199.635 bytes e que mídias 586/587 permanecem não tentadas. 
