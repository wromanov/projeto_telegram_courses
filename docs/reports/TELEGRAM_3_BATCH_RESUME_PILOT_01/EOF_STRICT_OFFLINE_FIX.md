# TELEGRAM-3-BATCH-RESUME-PILOT-01 — Correção offline do EOF estrito

Data: 2026-11-03. Execução: Desktop Commander, host ROMA_CASA.
Escopo: somente engenharia offline e testes, conforme autorização neste chat.

## Evidência original preservada
- Consulta remota anterior (5/5) identificou para o último bloco FileHash remoto um limite declarado de 131072 B que pode exceder o EOF do MP4; em todos os cinco itens, o digest correspondeu a SHA-256 dos bytes existentes da cauda até o EOF, sem padding.
- Fonte local: docs/reports/TELEGRAM_3_BATCH_RESUME_PILOT_01/EOF_DIGEST_COMPARE.json.
- Os cinco arquivos reais continuam como .part com tamanhos declarados, total 73071671 B, sem MP4 finalizados.
- Tentativas originais consumidas: cinco; nenhuma tentativa nova concedida nesta atividade.

## Correção realizada, mantendo o S9 inalterado
1. src/telegram_courses/downloads.py: _remote_hashes tem opção allow_terminal_eof=False como padrão. Somente o modo estrito opt-in permite um único bloco terminal de 128 KiB, alinhado, exceder EOF; o cursor de cobertura é limitado ao comprimento real. Mantém digest remoto bruto sem reescrever o intervalo.
2. _validate_remote_ranges tem allow_terminal_eof=False como padrão. Para o modo estrito, exige comprimento físico correto e compara digest SHA-256 fornecido pelo Telegram com os bytes reais até EOF, sem acrescentar zeros e sem ignorar divergências. Exige cobertura contígua 0..N, sem buracos, sobreposição ou extensões arbitrárias.
3. A verificação de download estrito e a revalidação de arquivos previamente marcados validos no cli.py usam expressamente allow_terminal_eof=True. Caminhos padrao, incluindo o uso S9, permanecem conservadores e rejeitam intervalos estendidos.
4. Nenhuma mudança no contrato S9, no modo de integridade permitido ou nos limites operacionais.

## Testes realizados offline
- 109 testes PASS em unit/test_pilot_eof_strict, unit/test_downloads, unit/test_s9_queue_integration, integration/test_download_flow e integration/test_s5_download_flow.
- Novo teste de ponta a ponta sintético confirma finalização com hash terminal remoto calculado sobre bytes reais e bloqueio quando digest terminal diverge. Nenhum teste usa Telegram real.
- Ruff: All checks passed; compileall sem erros.
- Consulta local read-only posterior: SQLite quick_check=ok; cinco downloads continuam FAILED_RETRYABLE/REMOTE_HASH_RANGE_INVALID, cinco .part presentes e com tamanho esperado, cinco caminhos finais ausentes, nenhuma evidência V2 nova.
- RPC Telegram nesta atividade: 0; bytes remotos transferidos: 0; alterações .part/SQLite/ACL: 0; Git: nenhuma operação.

## Limites e pendências explícitas
- EOF_HASH_RULE_IMPLEMENTED=YES_OFFLINE
- FULL_FILE_REMOTE_INTEGRITY=NOT_YET_PROVEN_REAL
- BATCH_RESULT=FAILED_PREVIOUS_RUN
- FIVE_PARTIAL_FILES=PRESERVED
- REMOTE_PILOT_RETRY=NOT_AUTHORIZED
- S9_ACCEPTANCE=PARTIAL_UNCHANGED
- A correção prepara uma transferência nova sob futuras autorizações, mas NÃO converte os cinco .part antigos em MP4 automaticamente. O launcher do piloto bloqueia partials com tentativas já consumidas; o caminho de retomada atual também passa pela verificação de prefixo original, que pode solicitar payload e reprovar geometria EOF. Não executar novamente.
- Próximo passo técnico para aproveitar os cinco .part sem novo download: desenvolver fluxo separado, autorizado, de revalidação somente por hash remoto de 0..EOF para .part completos, recebendo chamadas getFileHashes limitadas e com metadados/identidade checados. A finalização local e atualização transacional de SQLite, se desejadas, requerem autorização humana distinta após testes. Na ausência de digest remoto integral completo, bloquear.

## Arquivos alterados
- src/telegram_courses/downloads.py
- src/telegram_courses/cli.py
- tests/unit/test_pilot_eof_strict.py (novo)
- tests/integration/test_download_flow.py
