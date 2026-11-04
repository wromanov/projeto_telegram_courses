# TELEGRAM-3-BATCH-RESUME-PILOT-01 — EOF candidate offline proof (2026-11-03)

## Contexto e fonte real preservada
- O diagnostico remoto autorizado anteriormente observou cinco hashes finais com offset/limit de 131072 bytes e end > declared file_size, diferenca de 15453/64194/18455/26192/73283 bytes.
- O metodo Telegram upload.getFileHashes fornece SHA256 para intervalo declarado (offset,limit); a documentacao oficial nao especifica, no material consultado, como proceder quando o ultimo intervalo se estende alem do EOF. Fonte: https://core.telegram.org/api/files.
- Os cinco arquivos permanecem como .part com tamanho completo, mas sem prova remota integral; cinco tentativas de download anteriores foram consumidas.
- O JSON anterior guardou exclusivamente geometria/categoria, nao o digest remoto. Portanto nao e possivel comparar hipoteses com ele offline.

## Hipoteses distintas — nao aprovar automaticamente
1. TRUNCATED_TAIL_DIGEST_MATCH_CANDIDATE: SHA-256 da cauda ate o EOF coincide com hash remoto, embora o limite indicado seja maior.
2. ZERO_PADDED_DIGEST_MATCH_CANDIDATE: SHA-256 da cauda + zeros ate exatamente 131072 bytes coincide com hash remoto.
3. NO_CANDIDATE_DIGEST_MATCH: nenhuma das duas; manter bloqueio.
Um match isolado do bloco final nao equivale a REMOTE_HASH_FULL para o arquivo inteiro.

## Implementacao
- src/telegram_courses/terminal_hash_candidate.py: comparacao criptografica offline, somente leitura; nao integrada automaticamente a finalizacao do downloader.
- tests/unit/test_terminal_hash_candidate.py: testes sinteticos das duas hipoteses e negativas.
- tools/telegram_3_eof_remote_probe.py: por padrao somente preflight offline. O caminho --execute-metadata, com maximo de 5 chamadas remotas, **NAO FOI EXECUTADO**, por falta de nova autorizacao especifica.

## Validacao
- 74 testes PASS: unit/terminal_hash_candidate + unit/downloads + integration/download_flow.
- Ruff PASS em modulo, teste e script diagnostico.
- Preflight real offline: OFFLINE_PRECHECK=PASS; FIVE_PARTIALS_PRESERVED=YES; REMOTE_CALLS=0.
- Nenhum Telegram RPC, nenhum download, nenhuma renomeacao/finalizacao, nenhuma alteracao de banco ou S9 e nenhuma operacao Git nesta atividade.

## Proximo passo e limites
Exigir autorizacao renovada para cinco (5) chamadas exclusivamente upload.getFileHashes no mesmo conjunto MP4 do canal RASMOO e curso Candidato de Ouro, modulo Contagem Regressiva, mais autenticacao/identificacao necessaria. Uma chamada por midia; sem payload, downloads, modificacao de arquivos, ACL, SQLite ou Git. Nunca imprimir os digests.

Se houver coincidencia dos hashes, avaliar validacao da cobertura total do arquivo separadamente; se nao, permanecer BLOCKED. Qualquer mudanca de semantica de aceite/finalizacao ou transferencia de payload requer autorizacao propria.
