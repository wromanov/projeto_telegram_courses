# Plano de prontidão técnica — S6 Integrity Contract V2

```text
DOCUMENT_ROLE = NON_AUTHORITATIVE_IMPLEMENTATION_READINESS_PLAN
PROJECT_ID = projeto_telegram_courses
SOURCE_DESIGN = docs/contracts/S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT.md
SOURCE_SHA256 = C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52
DESIGN_RATIFIED = YES / FIVE DIRECTIVES
V1_ACTIVE = YES
V2_EFFECTIVE = NO
IMPLEMENTATION_AUTHORIZED = NO
S6_FORMAL_ACCEPTANCE = PENDING
TELEGRAM_CALLS_IN_THIS_ACTIVITY = 0
```

Este documento organiza o trabalho futuro possível. Não é contrato, autorização, checkpoint, plano de sprint ativo ou instrução para iniciar execução. A sequência só começa após autorização de implementação separada. V1 permanece canônico até adoção posterior expressa, com data efetiva então aprovada.

## 1. Arquivos e fronteiras de impacto previstas

| Área | Arquivos existentes / artefatos previstos | Trabalho futuro delimitado |
|---|---|---|
| Máquina de estados, fluxo e evidência | `src/telegram_courses/downloads.py` | Modelar modos, classes de evidência, precedência de falhas e finalização; distinguir `DOWNLOADED` V1 de `COMPLETED_V2`; garantir que `REFERENCE_MATCH` ocorra antes de persistir qualquer sucesso. |
| Persistência e compatibilidade | `src/telegram_courses/download_repository.py`; migration aditiva prevista em `src/telegram_courses/migrations/005_s6_integrity_v2.sql` (nome provisório) | Acrescentar campos/estado sem reclassificar linhas antigas; versionar evidência; tornar transições e reconciliação crash-safe; manter leitura segura de registros legados como `UNKNOWN_LEGACY`. Não editar banco real durante a implementação sem autorização correspondente. |
| Seleção explícita do modo | `src/telegram_courses/cli.py` | Expor seleção visível por item/operação; usar `REMOTE_HASH_REQUIRED` por padrão; exigir escolha explícita de `OPERATIONAL_ONLY` ou referência antes de RPC/leitura/mutação; nunca fazer downgrade automático. |
| Fila e deduplicação | `src/telegram_courses/s5_downloads.py` | Preservar limites, workers e plan_id S5; não tratar `COMPLETED_V2` como `DOWNLOADED`; impedir consumidores e dedup de elevar a garantia por inferência. |
| Contratos de gateway | `src/telegram_courses/telegram_gateway.py`; `src/telegram_courses/telethon_gateway.py` | Traduzir presença/ausência/resposta inválida/indisponibilidade sem expor tipos Telethon; manter erros estruturados e classificação determinística. Sem probes reais durante esta atividade. |
| Cobertura e testes do downloader | `tests/unit/test_downloads.py`; `tests/unit/test_telethon_gateway.py`; novas provas unitárias de migration/repository | Verificar tabela de transições, precedência, evidências, proteção do estado de sucesso e incompatibilidade legada. |
| Regressão e prova entre processos | `tests/integration/test_download_flow.py`; `tests/integration/test_s5_download_flow.py`; `tests/manual_proofs/test_s6_real_resume_proof.py` e harnesses S6 aplicáveis | Regressões S4/S5/S6 e prova explícita de dois processos com encerramento/reabertura real. A prova Telegram fica atrás de autorização e limites separados; nenhum harness deve ser executado como parte deste plano. |
| CLI e fluxo ponta a ponta | `tests/integration/test_cli_smoke.py` e novos testes CLI/download | Confirmar modo padrão e seleção explícita, persistência da escolha e ausência de fallback em retry/restart. |

Os nomes dos testes novos e da migration são propostas sujeitas à implementação autorizada; nenhum desses arquivos foi criado nesta atividade.

## 2. Ordem recomendada de implementação

1. **Gate de entrada:** receber autorização explícita de implementação; congelar o escopo V2 aprovado; manter V1 como caminho padrão/canônico até rollout aprovado. Registrar baseline offline sem modificar artefatos preexistentes.
2. **Contrato executável e modelo:** definir enums/valores de estado, classes de evidência versionada, chave de identidade/E e matriz de transições. Proibir estado terminal antes dos gates do modo. Explicitar que `DOWNLOADED` preserva V1 e que `COMPLETED_V2` não é sinônimo.
3. **Persistência aditiva:** implementar migration transacional nova, sem reescrever nem promover registros V1; testar abertura antes/depois, rollback, restart e leitura por consumidores. Campos desconhecidos ou incompletos devem falhar fechados como `UNKNOWN_LEGACY`.
4. **Gateway e avaliação remota:** validar resposta, ranges, digests, overflow e EOF; aplicar a precedência contratual; persistir eventos observados sem ocultar divergências. Divergência válida e resposta inválida vetam todos os modos.
5. **Seleção de modo e CLI:** expor e confirmar a seleção por item antes de qualquer RPC, leitura de payload ou mutação do `.part`; persistir vínculo com identidade, E, plan_id e invocação. Default `REMOTE_HASH_REQUIRED`; nenhum caminho implícito para `OPERATIONAL_ONLY`.
6. **Prefixo e orçamento:** revalidar identidade/E/P; para retomada operacional, comparar integralmente `[0,P)` e overlap antes de append; reservar cada `GetFile` antes da chamada. O custo de releitura entra no orçamento agregado S5 já existente, sem teto paralelo, sem exceder 256 KiB reservados por chamada, até 3 tentativas por mídia (inicial inclusa), 120 s cumulativos de FloodWait por mídia, 1–2 workers e os limites agregados aprovados. Reserva insuficiente bloqueia antes do RPC e preserva o `.part`.
7. **Referência e finalização:** validar identidade/proveniência/tamanho/hash da referência e comparar o candidato completo; somente após igualdade persistir `REFERENCE_MATCH` e avançar para finalização. Rename sem overwrite, fsync, evidência e SQLite devem ser reconciliáveis; crash entre filesystem/DB exige revalidação antes de qualquer sucesso.
8. **Consumidores e rollout:** atualizar leitura de estado, CLI, fila e deduplicação; provar que consumidores legados não promovem nem tratam `COMPLETED_V2` como `DOWNLOADED`. Manter V2 atrás de ativação controlada; não fixar data efetiva durante implementação.
9. **Regressão, prova e decisão:** passar testes offline obrigatórios; executar a prova controlada de dois processos e a prova técnica remota somente com autorização, alvo, limites e confirmação próprios. Reconciliar evidências e pedir decisão humana de adoção/aceite formal; sucesso técnico sozinho não ativa V2 nem fecha S6.

## 3. Orçamento de releitura e proteção dos limites S5

Use `C = 256 KiB`, `N = ceil(P/C)`, `R(P) = C × N` para `P > 0`, e `R(0) = 0`. Essa é a reserva conservadora máxima de payload para uma releitura completa do prefixo por tentativa; não é bytes efetivamente recebidos. O custo precisa caber no teto agregado compartilhado da invocação S5, com reserva antes de cada RPC e concorrência corretamente serializada/contabilizada. Cada request, retransmissão, overlap, validação, prefixo e retry entra no mesmo ledger; uma mesma resposta só é debitada uma vez. O máximo teórico do prefixo para três tentativas no mesmo P é `3 × R(P)`, ainda subordinado ao orçamento agregado e sem reserva antecipada desse total. Recalcular P e reserva em cada tentativa. Não aumentar limite S5, não criar exceção por modo e não iniciar chamadas sem saldo reservado para todo o trabalho necessário à tentativa.

A estimativa de preview é informativa. Só a reserva de runtime comprova disponibilidade; a releitura não pode iniciar e depois descobrir que o restante necessário não cabe. A prova deve demonstrar que reservas concorrentes e falhas conservam o limite byte a byte.

## 4. Matriz de testes obrigatórios para futura implementação

| Gate | Cenários mínimos | Evidência para PASS |
|---|---|---|
| Estados e sucesso | Transições válidas/inválidas; V1 `DOWNLOADED`; `COMPLETED_V2`; crash antes/depois do rename e transação; referência mismatch | Nenhum sucesso antes de todos os gates; `REFERENCE_MATCH` anterior a qualquer estado persistido de sucesso; recovery revalida bytes e prova. |
| Modos e default | Nenhuma flag; modo explicitamente selecionado; mudança de tentativa/restart; hash API ausente/indisponível/EOF | `REMOTE_HASH_REQUIRED` é padrão; seleção precede RPC; sem downgrade automático; modo escolhido e identidade/E/plan_id/invocação persistidos. |
| Precedência | Divergente, inválido, ambos, indisponível, ausente, parcial e EOF em combinações | Agregado primário determinístico, eventos completos preservados, vetos de divergente/inválido sem fallback. |
| Prefixo/orçamento | P=0, alinhado, não alinhado, maior que E, divergente; saldo abaixo/igual/acima de R; concorrência, retries e resposta incerta | Comparação completa antes do append; reservas por chamada ≤256 KiB; orçamento agregado nunca excedido; bloqueio antes da chamada sem saldo. |
| Migration/legado | DB novo, V1 existente, migration repetida/rollback, campos ausentes, consumidor antigo | Aditividade, idempotência conforme estratégia, linhas legadas intactas/`UNKNOWN_LEGACY`, nenhuma promoção implícita. |
| Compatibilidade e dedup | `DOWNLOADED` válido/mismatch; `COMPLETED_V2` com cada evidência; consumidor desconhecido | Dedup só para garantia reconhecida; status/evidência distintos; nenhum rótulo verificado sem prova. |
| Regressão S4/S5/S6 | Download inicial, rename recovery, dedup, fila, `plan_id`, workers, tentativas, FloodWait, disco, reserva e cancelamento | Suítes focadas integralmente PASS com testes explícitos para novos ramos; sem regressão nem violação dos limites aprovados. |
| Dois processos | Processo A grava prefixo e encerra; processo B abre de novo, reivindica sem concorrência e retoma; alinhado e não alinhado; falha em janelas críticas | Evidência independente de PID/processo distinto, SQLite e bytes antes/depois, zero writer concorrente, revalidação, final e dedup posterior. |
| Cobertura remota | Respostas reais por range incluindo cobertura `[0,E)`, gaps e EOF, em alvo autorizado | Resultado separado `REMOTE_HASH_ACCEPTANCE`; faixas e geometria verificadas; ausência de prova não se converte em PASS nem em referência. |

## 5. Rollout e ativação futura

- Implementar somente após autorização de implementação separada; primeiro em testes/fixtures isolados e banco descartável.
- Migration deve ser aditiva; backup/rollback documentado e consumidores precisam reconhecer estado/evidência antes de qualquer linha `COMPLETED_V2` ser exposta.
- Manter `REMOTE_HASH_REQUIRED` padrão e comportamento V1 enquanto rollout estiver em preparação; qualquer execução V2 deve estar explicitamente selecionada e permitida por futura decisão.
- Ativar V2 apenas depois de regressões offline e provas requeridas PASS, revisão das evidências e nova autorização humana que defina data efetiva, escopo de rollout e aceite S6. A ratificação de desenho atual não atende essa condição.
- Prova real de dois processos que use Telegram exige autorização separada, mídia/identidade definida, sessão protegida e limites S5 aprovados. Na ausência disso, a prova permanece não executada e S6 formalmente pendente.

## 6. Riscos residuais e decisões futuras

- `OPERATIONAL_ONLY` não atesta origem pretendida; o risco de garantia reduzida foi aprovado como desenho, mas sua implementação e uso ainda requerem autorização própria.
- `TRUSTED_REFERENCE` depende de proveniência da referência que pode não ter atestação independente; `REFERENCE_MATCH` não equivale a hash remoto.
- `GetFileHashes` pode estar ausente, indisponível, retornar cobertura parcial ou ter semântica de EOF não verificável; nesses casos não existe cobertura total.
- Consumidores externos ou scripts que assumam lista fechada de estados podem rejeitar ou interpretar mal `COMPLETED_V2`; compatibilidade precisa ser auditada antes do rollout.
- Migration aditiva reduz risco, mas não resolve automaticamente backups, leitores antigos concorrentes ou rollback após novos estados serem gravados.
- Releitura de prefixo pode consumir parcela relevante do orçamento e tornar uma tentativa inelegível; não reduzir a prova para caber no orçamento.
- Hash local, igualdade de referência e cobertura remota permanecem garantias distintas.

Decisões humanas futuras efetivamente necessárias: (a) autorização de implementação com escopo e ambiente; (b) autorização separada para prova Telegram real e seus limites; (c) após implementação/validação, adoção V2, data efetiva, rollout e aceite formal S6. Alterações de esquema/compatibilidade fora do desenho ratificado ou qualquer redução adicional de garantia exigem retorno à decisão humana.

```text
PLAN_READY = YES / NON-AUTHORITATIVE
PLAN_EXECUTED = NO
SOURCE_CODE_CHANGES = NO
SQLITE_CHANGES = NO
PART_CHANGES = NO
REAL_TELEGRAM_CALLS = 0
GIT_ADD_COMMIT_PUSH = NO
IMPLEMENTATION_AUTHORIZED = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
NEXT_ACTION = USER_IMPLEMENTATION_AUTHORIZATION
```
