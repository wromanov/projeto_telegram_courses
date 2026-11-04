# TELEGRAM-3-RESUME-FINAL-01 — WAVE1 orçamento e arquivo parcial

## Fatos reais observados
- 2026-11-03 02:36 UTC, mensagem 585 / modulo Competencias / RASMOO: uma tentativa com estado FAILED_RETRYABLE.
- SQLite read-only: failure_category=TRANSFER_BUDGET_EXHAUSTED, expected_bytes=6199635, downloaded_bytes=6029312, attempts=1, PRAGMA quick_check=ok.
- O .part existe, com 6029312 bytes (23 blocos de 262144 B); final MP4 ausente.
- Faltam 170323 bytes uteis. Integridade remota de prefixo/arquivo inteiro ainda NAO validada.
- Mensagens 586, 587 seguem PENDING, sem tentativa; cinco videos anteriores 598-602 seguem ALREADY_VALID.

## Causa no codigo
- tools/RUN_TELEGRAM_3_RESUME_FINAL_01.ps1 (versao anterior): MaxTransfer=6199635, exatamente tamanho esperado.
- src/telegram_courses/telethon_gateway.py, reserved_request: reserve_chunk(chunk_bytes) ANTES de cada GetFile; chunk_bytes=262144 inclusive no ultimo request.
- src/telegram_courses/s5_downloads.py reserve_chunk: se budget_consumed+budget_reserved+amount excede max_transfer_bytes, retorna None e causa TRANSFER_BUDGET_EXHAUSTED.
- Apos 6029312 bytes, saldo util 170323 B < proxima reserva de 262144 B. Bloqueio correto pela policy; configuracao de budget de reserva incorreta. Nao confundir payload efetivo com bytes maximos reservados por RPC.

## Correcao offline
- Launcher etapa 1: MaxTransfer 6291456 = 24*262144 B.
- Launcher etapa 2: MaxTransfer 22544384 = 86*262144 B.
- Budget total de requisições (soma do maximo de ambas etapas) = 28835840 B, menor que 256 MiB global.
- Limites de selecao (mensagens 585,586,587), integridade REMOTE_HASH_REQUIRED, 1 worker, 1 tentativa por item, S9 e APIs de download inalterados.
- Verificador de orçamento offline PASS e AST PowerShell PASS.
- A etapa 1 continua intencionalmente BLOQUEADA pelo preflight porque a tentativa 1 da midia 585 JA foi consumida. Nao desativar preflight, nao apagar .part, nao reiniciar sem novo escopo.

## Proximo ato depende de autorizacao nova
- Exigir autorização especifica para 1 tentativa ADICIONAL de recuperacao da mensagem 585 a partir de .part verificado remotamente, sem download integral, 1 worker, no max 262144 B de GetFile solicitado por requisição e limite global de bytes de transfer de 6291456 B para o novo processo (incluindo eventual releitura de prefixo caso necessaria), sem downgrade; definir regime de G0/G4 com o operador.
- Antes de executar, atualizar o guard com caminho de recuperacao para exatamente 585 e testes negativos; nao reaproveitar automaticamente a wave1 one-shot. Se a recuperacao falhar, bloquear e preservar o parcial.
- Somente apos 585 finalizado, emitir recibo de wave1 e iniciar wave2 com 586/587 sob controles e confirmacoes aplicaveis.

## Status
- WAVE1_RESULT=FAILED_RETRYABLE / TRANSFER_BUDGET_EXHAUSTED.
- ROOT_CAUSE=CONFIRMED; LOCAL_BUDGET_FIX=PASS.
- RESTART_AUTHORITY=NOT_GRANTED; TELEGRAM_RPC_AFTER_FAILURE=0.
