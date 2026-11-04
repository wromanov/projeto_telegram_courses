# TELEGRAM-3-BATCH-RESUME-PILOT-01 — RECUPERAÇÃO REAL DOS 5 MP4

Data: 2026-11-03. Host: ROMA_CASA. Executado pelo Desktop Commander neste chat, autorizado pelo operador para as ações necessárias de recuperação.

## Contexto
O piloto anterior transferiu integralmente 73071671 bytes de 5 MP4 do canal RASMOO (-1002758699600), curso Candidato de Ouro, módulo Contagem Regressiva, mas resultou em FAILED por REMOTE_HASH_RANGE_INVALID. Os cinco .part tinham tamanhos completos, 1 tentativa por mídia. Consultas posteriores (5/5) comprovaram que o hash do último bloco de 128 KiB era calculado sobre os bytes reais até o EOF sem zeros.

## Recuperação realizada
- Implementado fluxo separado tools/telegram_3_recover_full_partials.py, com bloqueio estrito por canal/módulo/quantidade/identidade/estado/paths, limite de 640 chamadas hash e de 3600 s.
- A operação NÃO chama stream_media, não executa downloads, não repete tentativas e não altera contratos S9.
- Todas as faixas de hash remoto retornadas pela API foram verificadas contra os bytes locais, em sequência, exigindo cobertura contínua do primeiro byte até EOF. Para a geometria terminal Telegram de 128 KiB sobre o EOF, o digest é comparado com a cauda real, sem padding nem truncamento de hash. Lacunas, inconsistências, sobreposições parciais e divergências bloqueiam.
- getFileHashes é chamado pelo gateway Telethon existente, que revalida identidade antes de cada chamada; houve revalidação adicional por mídia. Sem respostas salvas com digests ou credenciais.
- Resultado observado: MEDIA_1..5_FULL_REMOTE_HASH=PASS. Total: 73 solicitações getFileHashes, sem payload.
- Somente APÓS prova integral dos cinco arquivos, foi realizado backup SQLite privado consistente, seguida de recuperação local de cinco .part para seus MP4 finais mediante renomeação sem overwrite, com atualização VALIDATED -> FINALIZATION_PENDING -> DOWNLOADED e sem aumentar attempts.
- Resultado do executável: files=5, finalized=5, hash_requests=73, payload_download_bytes=0, original_attempts_preserved=true, status=COMPLETED.

## Auditoria independente após a operação
- Banco SQLite da área privada do produto: PRAGMA quick_check=ok.
- Cópia SQLite privada pre-recovery: quick_check=ok.
- Cinco MP4 finais existentes; cinco .part originais ausentes por finalização normal.
- Cada arquivo com tamanho esperado e SHA-256 local calculado novamente igual ao digest registrado no banco.
- Cinco registros DOWNLOADED, owner_pid nulo, attempts=1, downloaded_bytes=expected_bytes.
- Soma final: 73071671 bytes.
- Planejador offline da fila: 5 selecionados, 5 ALREADY_VALID, 0 PENDING, 0 BLOCKED, 0 EXCLUDED, pending_bytes=0. Segunda execução futura não exige baixar esses arquivos.
- Evidência sanitizada do processo em docs/reports/TELEGRAM_3_BATCH_RESUME_PILOT_01/RECOVERY_RESULT.json.
- Sem Git, publicação, download amplo do canal, manipulação de outros cursos ou contrato S9.

## Limites do aceite
- PILOT_EXISTING_FIVE_FILES_RECOVERY=PASS.
- FULL_REMOTE_HASH_CHECK=PASS para os cinco arquivos nesta execução.
- LOCAL_SQLITE_AND_SHA256_POSTVERIFY=PASS.
- BATCH_TRANSFER_ORIGINAL=FAILED e foi recuperado sem repetir payload.
- REAL_INTERRUPTION_AND_PARTIAL_MEDIA_RESUME=NOT_TESTED nesta atividade.
- S9_ACCEPTANCE=PARTIAL, G6-G9 e evidência M não foram demonstrados aqui.
- PRODUCT_READINESS geral permanece PARTIAL: operação diária e download de cursos inteiros exigem aceite independente.
- O fluxo de recuperação é exclusivo do piloto e não substitui a fila normal.

## Caminho de uso dos MP4
%LOCALAPPDATA%\telegram_courses_product\downloads

## Arquivos técnicos adicionados
- tools/telegram_3_recover_full_partials.py
- tests/unit/test_pilot_full_partial_recovery.py
- Scripts de auditoria locais em %LOCALAPPDATA%\telegram_courses_product\pilot_postverify_readonly.py e pilot_plan_verify.py.

## O que falta para fechar o produto inteiro
Validar fluxo real de interrupção e retomada (outro escopo controlado), revisar proteção de EOF no modo de uso cotidiano e empacotar/documentar Windows sob decisão do operador. Nao elevar escopo para 196 MP4 automaticamente.
