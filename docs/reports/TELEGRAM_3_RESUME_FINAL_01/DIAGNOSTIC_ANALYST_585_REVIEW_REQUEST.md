# DIAGNOSTIC ANALYST — análise independente solicitada: falha do MP4 585

**Atividade:** TELEGRAM-3-RESUME-FINAL-01 / 585-HASH-RANGE-CAUSE-01
**Escopo:** diagnóstico somente leitura, sem Telegram RPC novo, sem download, sem mutações em DB/arquivo parcial, sem Git, sem alterações S9. O perfil Diagnostic Analyst deverá confirmar ou refutar a hipótese abaixo independentemente antes de autorizar implementação.

## Evidência confirmada no ROMA_CASA
- Terceira tentativa real de recuperação da mensagem 585 (canal RASMOO -1002758699600, módulo 44 Competências) falhou em ~4 s, zero bytes transferidos.
- Consulta SQLite somente leitura: state=FAILED_RETRYABLE; attempts=3; downloaded_bytes=6029312; failure_category=REMOTE_HASH_RANGE_INVALID; owner_pid=NULL; quick_check=ok; final MP4 não existe.
- .part mantém exatamente 6.029.312 bytes e SHA-256 local idêntico ao digest gravado no marcador da terceira tentativa; nenhuma perda ou alteração do prefixo observada.
- Marcador one-shot da terceira tentativa existe e impede reexecução automática; vídeos 586/587 não envolvidos; S9 não alterado.
- O literal REMOTE_HASH_RANGE_INVALID ocorre na origem do projeto apenas em src/telegram_courses/downloads.py, dentro de _remote_hashes, quando o intervalo do servidor ultrapassa candidate.expected_bytes sem satisfazer allow_terminal_eof.

## Fluxo e hipótese técnica reproduzível
- O tamanho total da mídia 585 é 6.199.635 bytes, o prefixo físico tem 6.029.312 bytes = 46 * 131.072, sobrando 170.323 bytes. O EOF de uma última faixa Telegram de 131.072 bytes pode ser reportado com fim nominal 6.291.456, além do EOF real.
- downloads.py _download_locked chama _verify_prefix(candidate, partial, physical) ANTES de transferir a cauda.
- downloads.py _verify_prefix chama _remote_hashes(candidate, physical) **sem** allow_terminal_eof=True.
- _remote_hashes percorre TODOS os itens da resposta getFileHashes, mesmo se o conjunto já cobriu required_bytes do prefixo. Se o servidor retornar faixas adicionais que alcancem o EOF na mesma resposta, a última pode exceder o tamanho nominal; o parser recusa com REMOTE_HASH_RANGE_INVALID.
- Em contraste, a verificação posterior do arquivo inteiro usa allow_terminal_eof=True, e a recuperação dos cinco vídeos completos já tratou EOF estrito.
- A simulação offline usando resposta sintética com 48 faixas de 128 KiB, incluindo faixa final com fim nominal além de 6.199.635, executada contra a implementação real produziu **BATCH_WITH_EOF_EXTRA_PREFIX_CAUSE=REMOTE_HASH_RANGE_INVALID**; a mesma resposta com required_bytes=full e allow_terminal_eof=True retornou 48 faixas (PASS); somente as primeiras 46 faixas para o prefixo retornaram PASS.
- A regressão sintética anterior tests/integration/test_resume_585_budget_once.py retornava **UMA faixa por get_file_hashes** e não exercitava batching contendo faixas posteriores ao prefixo. Portanto 158 testes PASS não cobriam essa geometria.

**Nível de certeza:** a origem do código que lança a categoria e a reprodução com dados sintéticos estão **confirmadas**. Que o Telegram realmente retornou uma resposta em lote com faixa EOF excedente na terceira tentativa é uma **hipótese forte, mas ainda não comprovada**, pois o conteúdo bruto sanitizado da resposta não foi persistido. O servidor também pode ter enviado efetivamente um intervalo inválido; não presumir automaticamente bug exclusivo do cliente.

## Solicitação de parecer independente ao Diagnostic Analyst
1. Reproduzir offline o caminho exato de _verify_prefix/_remote_hashes para (expected=6199635, physical=6029312), incluindo respostas de getFileHashes com múltiplos ranges, lotes parciais, faixa EOF excedente, resposta malformada, ordem invertida, duplicação, lacuna e sobreposição.
2. Determinar se o parser deve parar de consumir faixas após cobrir required_bytes do prefixo ou validar integralmente lotes excedentes; preservar rejeição de resultados contraditórios e dados incorretos. Não enfraquecer a regra REMOTE_HASH_REQUIRED nem a prova integral antes de finalizar.
3. Distinguir causa-raiz confirmada de hipótese. Se prova real precisar de uma RPC read-only extra, solicitar autorização humana específica; NÃO executar essa RPC na análise inicial.
4. Avaliar isolamento do ajuste (flag estrita opt-in vs default S9), regressões e impacto de EOF em _validate_remote_ranges e _verify_prefix; não alterar S9 nem V2.
5. Entregar correção proposta, plano de testes offline com mocks realistas multi-range, riscos residuais e condições para possível quarta tentativa humana. Nenhum download/codificação/commit sem nova autorização.

## Artefatos de prova
- Reprodução local offline (fora do repo): `%LOCALAPPDATA%\telegram_courses_product\diagnostic585_hashbatch_readonly_repro.py`, resultado: BATCH_WITH_EOF_EXTRA_PREFIX_CAUSE=REMOTE_HASH_RANGE_INVALID; FULL_HASH_EOF_OPTIN_PASS 48; PREFIX_HASH_ONLY_PASS 46.
- Verificador pós-falha fora do repo: `%LOCALAPPDATA%\telegram_courses_product\diagnostic585_verify_prefix_unchanged.py`.
- Fonte: `src/telegram_courses/downloads.py` (_download_locked, _verify_prefix, _remote_hashes), `src/telegram_courses/telethon_gateway.py` (get_file_hashes), `tests/integration/test_resume_585_budget_once.py`, `tests/unit/test_pilot_eof_strict.py`.
- Relatório precedente: `docs/reports/TELEGRAM_3_RESUME_FINAL_01/RECOVERY_585_THIRD_READY.md`.

## Status operativo
`THIRD_ATTEMPT=FAILED`, `ROOT_CAUSE_IN_CODE=CONFIRMED_CATEGORY`, `CLIENT_HASH_BATCH_EDGE=REPRODUCED_OFFLINE`, `ACTUAL_SERVER_BATCH=UNVERIFIED`, `PREFIX_SHA256_UNCHANGED=PASS`, `FOURTH_ATTEMPT_AUTHORIZED=NO`.
