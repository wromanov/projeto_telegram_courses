# S6 — Remediação Diagnóstica da Janela de Hashes

```text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_HASH_WINDOW_DIAGNOSTIC_REMEDIATION
DATE = 2026-10-17
CONTRACT = S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT / APPROVED / FROZEN
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
```

## Escopo e diagnóstico reutilizado

Esta remediação implementou observabilidade diagnóstica offline no harness de prova S6. Ela reutiliza o diagnóstico concluído em `S6_HASH_RESPONSE_WINDOW_FORENSICS`; não repete nem altera a sondagem real anterior.

A evidência histórica registrava cursor solicitado `1.119.092.736`, EOF esperado `1.119.129.690`, três faixas recebidas, mas apenas uma faixa visível: `[1.118.830.592, 1.118.961.664)`. O predicado anterior `item.offset < cursor` classificava essa faixa como overlap embora seu fim estivesse antes do cursor. A validação fail-fast interrompia na primeira faixa, deixando as duas geometrias seguintes sem observação. A resposta bruta completa não está disponível nesta evidência; portanto, não é possível reconstruir as faixas ausentes nem concluir como elas se relacionavam entre si ou com o EOF.

## Arquivos modificados

- `tools/manual_proofs/s6_resume_harness.py`
- `tools/manual_proofs/s6_controlled_eof_hash_probe.py`
- `tests/manual_proofs/test_s6_real_resume_proof.py`
- `tests/manual_proofs/test_s6_controlled_eof_hash_probe.py`

## Correção diagnóstica

A geometria sanitizada de todas as faixas recebidas é capturada antes do loop de validação fail-fast. O registro inclui, por faixa, índice, offset, limite, comprimento, fim e comprimento do digest. Inclui também contagem recebida/inspecionada, índice da primeira rejeição, cursor anterior/posterior e razão da rejeição. Bytes de digest não são persistidos. Uma falha na captura de telemetria não mascara a rejeição original.

A classificação diagnóstica agora distingue:

- `RANGE_BEFORE_CURSOR`
- `ACTUAL_RANGE_OVERLAP`
- `RANGE_EXTENDS_BEYOND_EOF`
- `INVALID_RANGE`
- `OTHER_CONFIRMED_REASON`

Uma faixa totalmente anterior ao cursor continua rejeitada de forma conservadora; não é chamada de interseção real apenas por começar antes do cursor. As categorias externas e o stop `HASH_COVERAGE_OVERLAP` foram preservados. Quando a resposta remota é recebida, mas rejeitada pela validação local, a classificação passa a `LOCAL_HASH_RESPONSE_VALIDATION_REJECTED`; o campo legado `rejection_classification` permanece. A lógica de aceitação, integridade e fail-closed não foi flexibilizada. Não foram adicionadas chamadas RPC.

## Validações executadas

- Testes direcionados: **8 passed**, cobrindo faixa anterior ao cursor, overlap real, três faixas contíguas, overlap posterior, faixa além do EOF, digest inválido, falha de telemetria e ausência de persistência dos bytes do digest.
- `tests/manual_proofs/test_s6_controlled_eof_hash_probe.py`: **6 passed** em 4,90 s.
- `tests/unit/test_downloads.py`: **10 passed, 1 deselected**.
- Ruff nos quatro arquivos alterados: **PASS**.
- `compileall` em `src`, `tests` e `tools`: **PASS**.
- DryRun via PowerShell: **PASS**; restauração de sessão não ocorreu.
- Parser PowerShell: **PASS**.
- `git diff --check`: exit code **0**, com avisos de line endings.
- Suítes completas S6 (30 casos), regressões S4/S5 e módulos pytest pertinentes: **interrompidas, sem resultado PASS**. Ficaram penduradas ao criar o event loop asyncio do Windows, com traceback em `socket._fallback_socketpair → socket.accept → asyncio.proactor_events._make_self_pipe`, e foram interrompidas.

## Segurança, riscos e limites

Nesta atividade houve **zero chamadas reais ao Telegram**. Não houve restauração de sessão nem transferência de payload. O SQLite original e arquivos `.part` não foram acessados ou modificados.

Os testes sintéticos demonstram o comportamento do avaliador para as geometrias cobertas, não a semântica de segmentação de `GetFileHashes` no servidor. A resposta histórica completa não foi preservada: esta correção melhora diagnósticos futuros, mas não repara nem completa a evidência histórica e não permite inferir as duas faixas então omitidas.

## Decisão seguinte

Manter `NO_GO_FULL_DOWNLOAD` para a mensagem 7603 até revisão e autorização específicas. Esta alteração não autoriza nova consulta, download integral ou aceite formal S6. A próxima decisão necessária é determinar, com authority própria, se uma nova coleta controlada de hashes é autorizada para obter evidência completa; qualquer coleta permanece sujeita a aprovação separada.
