# S6 — Proposta de Contrato de Integridade V2

```text
DOCUMENT_ROLE = S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT
PROJECT_ID = projeto_telegram_courses
STATUS = DRAFT / NOT APPROVED / NOT CANONICAL
CURRENT_CONTRACT_V1 = CANONICAL / UNCHANGED
IMPLEMENTATION_AUTHORIZATION = NO
S6_FORMAL_ACCEPTANCE = PENDING
NEXT_ACTION = USER_FINAL_CONTRACT_DECISION
```

> Proposta independente para decisão humana. Não substitui, altera ou descongela [o contrato S6 V1](S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md). Até aprovação normativa expressa e data de adoção definidas pelo usuário, V1 permanece integralmente canônico. Este documento não autoriza implementação, testes, chamadas Telegram, avanço de sprint ou aceite formal.

## 1. Objetivo, vocabulário e princípios

A proposta separa conclusão da operação de evidência de integridade. Os resultados não são equivalentes nem inferíveis uns dos outros.

- **E**: tamanho esperado revalidado da mídia remota.
- **P**: tamanho físico atual do arquivo parcial `.part`.
- **D**: checkpoint anteriormente persistido no SQLite; metadado operacional, não autoridade sobre os bytes.
- **C**: máximo de payload reservado por chamada `GetFile` sob S5: 256 KiB.
- **Referência confiável**: cópia integral capturada antes do upload, preservada e revalidada, com tamanho, SHA-256 e proveniência registrados. Um manifesto local não atestado externamente documenta, mas não prova de forma independente, sua origem.
- **Cobertura remota integral**: faixas remotas válidas e não divergentes cuja união cobre `[0,E)` sem lacunas, com digest correspondente aos bytes de cada faixa.

Estados operacionais descrevem fluxo e finalização. Classes de evidência descrevem exclusivamente provas efetivamente obtidas. SHA-256 local identifica os bytes observados; sem âncora comparativa, não demonstra que eram os bytes pretendidos.

## 2. Modos, seleção e ausência de downgrade

O modo deve ser escolhido por item antes de qualquer RPC, leitura de payload ou mutação do parcial. A escolha persistida fica vinculada à identidade da mídia, E, plan_id e invocação. A escolha de modo V2 só existe após aprovação do contrato V2.

| Modo selecionado | Uso | Resultado de evidência possível |
|---|---|---|
| `REMOTE_HASH_REQUIRED` | Padrão conservador, mantendo semântica V1. | `REMOTE_HASH_FULL` somente com cobertura integral; resultados sem cobertura suficiente bloqueiam. |
| `OPERATIONAL_ONLY` | Download comum sem referência pré-upload; requer escolha explícita e visível antes da execução. | `OPERATIONAL_ONLY / UNVERIFIED_ORIGIN`; não afirma igualdade com referência nem hash remoto integral. |
| `TRUSTED_REFERENCE` | Prova controlada com referência pré-upload explicitamente selecionada. | `REFERENCE_MATCH` somente após igualdade integral e gates de finalização. Hashes remotos permanecem resultado separado. |

Não há downgrade automático por método ausente, erro, indisponibilidade, rate limit, faixa parcial, EOF não verificável, retry ou restart. Se o modo selecionado não puder cumprir seus critérios, interromper a tentativa, preservar `.part` e bloquear. Uma tentativa posterior exige nova decisão explícita antes de qualquer chamada remota. Não é permitido mudar de `REMOTE_HASH_REQUIRED` para `OPERATIONAL_ONLY` depois de observar resposta. Evidência mais forte pode ser registrada adicionalmente, mas não promove estado sem cumprir o critério correspondente.

## 3. Classes de evidência

| Classe | Demonstra | Não demonstra |
|---|---|---|
| `OPERATIONAL_ONLY` | Transferência e retomada consistentes com leituras remotas desta operação, prefixo exigido revalidado, tamanho E, SHA local, durabilidade e finalização coerentes. | Conteúdo originalmente pretendido, snapshot remoto imutável, igualdade com referência ou atestação independente do Telegram. |
| `REFERENCE_MATCH` | Arquivo final byte a byte igual à referência confiável revalidada, com tamanho e SHA-256 iguais. | Cobertura de `GetFileHashes` ou atestação independente do armazenamento remoto. |
| `REMOTE_HASH_PARTIAL` | Digests remotos válidos coincidem nos intervalos registrados. | Bytes fora dos intervalos ou cobertura total. |
| `REMOTE_HASH_FULL` | Digests válidos coincidem em faixas que cobrem `[0,E)` integralmente. | Origem pretendida pelo publisher ou igualdade com referência. |
| `UNKNOWN_LEGACY` | Não há evidência versionada suficiente para atribuir classe moderna. | Qualquer garantia derivada apenas de status `DOWNLOADED`, tamanho, checkpoint ou SHA local legado. |

Classes podem coexistir somente quando cada prova foi realmente executada e registrada. Não existe equivalência entre integridade operacional, igualdade com referência e hashes remotos.

## 4. Estado `DOWNLOADED`, versionamento e compatibilidade

**Recomendação normativa:** preservar `DOWNLOADED` e sua semântica V1 para resultados aceitos por V1, incluindo `REMOTE_HASH_FULL` conforme o contrato vigente. Não reutilizar `DOWNLOADED` para conclusão com garantia mais fraca. Para conclusão V2 operacional ou por referência que não satisfaça V1, introduzir estado terminal distinto, por exemplo `COMPLETED_V2`, associado a evidência versionada. O nome final requer aprovação humana.

Todo registro novo deve carregar `schema_version`, `contract_version`, `selected_mode`, classe(s) de evidência, estado remoto de hashes, identidade da mídia, E, SHA-256 final e vínculo ao artefato final. Evidência é invalidada se identidade, E ou bytes finais mudarem. Registro antigo sem proveniência/evidência compatível classifica como `UNKNOWN_LEGACY`; migration jamais retroatribui `REMOTE_HASH_FULL` ou `REFERENCE_MATCH` com base em status ou campos antigos.

Consumidores, CLI e deduplicação devem ler e preservar versões, modo, classe de evidência, identidade, E e SHA final. Consumidor legado que não entende `COMPLETED_V2` ou a evidência associada deve falhar fechado: não rotular como verificado, não promover e não deduplicar como sucesso equivalente a `DOWNLOADED`. Migration deve ser aditiva e rollout só pode expor `COMPLETED_V2` depois que consumidores necessários reconheçam a diferença. Linhas V1 e comportamento legado ficam preservados.

**Decisão humana necessária:** autorizar novo estado, schema/migration e tratamento dos consumidores. Recomendação: estado separado `COMPLETED_V2`, evidência versionada aditiva, `DOWNLOADED` preservado, consumidores desconhecidos fail-closed.

## 5. Semântica e precedência de `GetFileHashes`

A descrição de [FileHash](https://core.telegram.org/constructor/fileHash) associa digest a offset/limit; [upload.getFileHashes](https://core.telegram.org/method/upload.getFileHashes) e [documentação de downloads](https://core.telegram.org/api/files#downloading-files) são referências para implementação futura. Esta proposta não inventa clamp, padding ou truncamento do digest no EOF. Faixas anteriores ao cursor podem ser retrospectivas; sua contribuição depende do intervalo real, não do cursor.

Aplicar a precedência em camadas, conservando todos os eventos observados e uma classificação agregada primária:

1. **Vetores globais**, em qualquer modo: conflito de identidade/E, arquivo/path/ownership/SQLite ambíguos, P/D ou prefixo/overlap divergente, orçamento insuficiente e falha de finalização/persistência bloqueiam operação e sucesso.
2. **Vetores de resposta remota**, em qualquer modo: qualquer faixa válida, integralmente verificável e divergente resulta em `REMOTE_HASH_DIVERGENT`; qualquer resposta malformada, overflow ou resposta internamente inconsistente resulta em `REMOTE_HASH_INVALID_RESPONSE`. Ambos bloqueiam todos os modos e proíbem fallback. Se ambos ocorrerem, preservar ambos os eventos e usar `BLOCKED_CONTRADICTORY_REMOTE_EVIDENCE` como agregado primário.
3. **Vetores de referência**, no modo `TRUSTED_REFERENCE`: referência ausente, alterada, identidade/proveniência exigida não satisfeita ou mismatch resulta respectivamente em `REFERENCE_ABSENT`, `REFERENCE_INVALID`/`REFERENCE_PROVENANCE_UNVERIFIED` ou `REFERENCE_MISMATCH`; bloqueia a operação sem fallback.
4. **Indisponibilidade transitória** depois de aplicar limites S5 de retries/FloodWait resulta em `REMOTE_HASH_UNAVAILABLE`; bloqueia esta tentativa, não é ausência e não permite downgrade.
5. **EOF**: faixa que cruza E recebe `REMOTE_HASH_UNVERIFIABLE_EOF`. Pode-se registrar outras faixas válidas; não cortar, completar ou comparar digest parcial presumido. Se houver lacuna na cobertura, registrar também `REMOTE_HASH_PARTIAL`.
6. **Lacuna** sem veto superior: `REMOTE_HASH_PARTIAL`.
7. **Ausência explícita**: método não exposto/ausente ou resposta vazia resulta em `REMOTE_HASH_ABSENT`.
8. **Cobertura integral**: `REMOTE_HASH_FULL` somente se todas as respostas forem bem formadas, não houver veto e a união verificada cobrir `[0,E)` sem lacunas.

`EOF`, `PARTIAL` e `ABSENT` podem seguir somente o modo V2 já pré-selecionado e aprovado. Divergente e inválido sempre bloqueiam. Registro de eventos guarda todos os resultados, faixas, motivos e classificação primária, sem ocultar evidência contraditória.

## 6. Modelo de operação sem referência pré-upload

Para `OPERATIONAL_ONLY`, revalidar identidade remota, E, caminho, arquivo regular, ownership, estado SQLite, limites de disco e orçamento. Para P>0, reler do remoto todo o prefixo `[0,P)` e comparar byte a byte com `.part` antes de qualquer append. Depois verificar integralmente o overlap alinhado e contíguo requerido pelo protocolo e continuar exatamente a partir de P. D não substitui comparação de bytes. P>E, divergência, leitura incompleta ou conflito bloqueia sem truncar/apagar.

Essa prova demonstra coerência operacional com os bytes remotos lidos na execução. Não demonstra o conteúdo pretendido originalmente e não converte ausência de hash remoto em cobertura. Mesmo se a operação concluir, a classificação fica `OPERATIONAL_ONLY / UNVERIFIED_ORIGIN`.

## 7. Modelo de prova controlada com referência

Antes da execução, selecionar explicitamente `TRUSTED_REFERENCE`. Validar imutabilidade, proveniência registrada, tamanho e hash local da referência antes e depois do uso. Baixar o candidato para `.part`/estado não autoritativo. Comparar o arquivo integral, byte a byte, com a referência e verificar E e SHA-256 antes de persistir qualquer sucesso.

Antes do match, só são permitidos estados `DOWNLOADING`, `FAILED_RETRYABLE` ou `BLOCKED`; trabalho de prova fica em memória ou evidência temporária não autoritativa. Antes de `REFERENCE_MATCH`, é proibido persistir `VALIDATED`, `FINALIZATION_PENDING`, `DOWNLOADED` ou `COMPLETED_V2`. Após match, finalizar com rename atômico sem sobrescrita e publicar estado final/evidência versionada em uma transação SQLite ou handshake recuperável equivalente. Se houver crash após rename e antes da transação, recovery precisa revalidar o arquivo final byte a byte contra a referência antes de qualquer sucesso. Mismatch não persiste sucesso e mantém arquivos recuperáveis.

`REFERENCE_MATCH` não atesta o armazenamento do Telegram; os resultados remotos são registrados separadamente. Essa prova controlada, sozinha, não demonstra capacidade geral para mídias sem referência.

## 8. Orçamento da releitura de prefixo sem alterar S5

Com `C = 256 KiB`, para cada tentativa e P revalidado, número de blocos `N = ceil(P/C)`. Se P=0: `Q_actual = R_reserve = 0`. Para P>0, limite conservador de payload `Q = min(E, C*N)` e reserva máxima `R = C*N`; a última resposta pode ser menor, mas a reserva por chamada é feita integralmente antes do RPC e R pode exceder E pelo bloco final.

Antes da primeira leitura de prefixo, exigir capacidade R dentro do limite agregado compartilhado S5: reservar suborçamento dentro do limite existente ou serializar para impedir workers de consumirem capacidade concorrente. Não aumentar o teto agregado. Cada `GetFile` continua reservando no máximo C antes da chamada; debitar bytes recebidos e tratar reserva incerta em voo conforme S5. Resposta reutilizada como overlap é contada uma vez; requests separados, retries, overlap, continuação, releituras de integridade e retransmissões contam no mesmo orçamento.

S5 já permite no máximo três tentativas. Para o mesmo P, limite teórico de releitura é `3R(P)` por item, ainda subordinado ao orçamento agregado; não criar teto independente adicional nem reservar `3R` antecipadamente. Em cada tentativa, recalcular R a partir do P revalidado e revalidar a reserva restante para prefixo e transferência. Se não couber tudo, bloquear antes da chamada remota e preservar `.part`. Preview Q/R é provisório. Manter retries máximos 3, FloodWait máximo de 120 s por mídia, 1–2 workers, reservas por `GetFile` até 256 KiB e teto agregado S5. `GetFileHashes` não carrega payload, mas continua sob rate limit/FloodWait existente e sem retries ilimitados.

## 9. Finalização e persistência de sucesso

Estado terminal V2 só pode ser persistido depois dos gates do modo selecionado, verificação de E e SHA final, flush/fsync, rename atômico sem overwrite, revalidação do arquivo final e persistência coerente. Para referência, o gate de igualdade precede qualquer estado que indique sucesso conforme §7. Para modo operacional, os gates de releitura e overlap precedem finalização. Falhas entre filesystem e SQLite exigem recovery que revalide bytes e evidências; não inferir garantia a partir do nome do arquivo ou estado incompleto.

`REMOTE_HASH_FULL` pode sustentar semântica V1 de `DOWNLOADED` sob o contrato vigente. `OPERATIONAL_ONLY` e `REFERENCE_MATCH` sem cobertura remota total, se autorizados por V2, usam estado V2 distinto. Evidência ou status não é promovido por deduplicação. Falha de qualquer gate impede estado terminal de sucesso.

## 10. Matriz fechada de decisão

| Condição observada | Classificação/decisão primária | Ação determinística | Evidências obrigatórias |
|---|---|---|---|
| Identidade remota ou E conflitante | `REMOTE_IDENTITY_CONFLICT` / `BLOCKED` | Bloquear todos modos; sem append/finalização. | Identidade registrada e reobservada, E e motivo. |
| Path, ownership, arquivo ou SQLite ambíguo | `LOCAL_STATE_CONFLICT` / `BLOCKED` | Bloquear todos modos; preservar artefatos. | Path, tipo/owner, claim, estado DB. |
| P>E, D/arquivo incompatíveis, prefixo ou overlap divergente | `PREFIX_CONFLICT` / `BLOCKED` | Sem append; sem truncar/apagar. | P, D, offsets, bytes comparados e resultado. |
| Reserva/orçamento/disco não comporta leitura e operação | `BUDGET_BLOCK` / `BLOCKED` | Bloquear antes da próxima chamada; preservar `.part`. | Cap agregado, reservas, custo, bytes e requests. |
| Hash remoto válido, faixa integralmente verificável diverge | `REMOTE_HASH_DIVERGENT` / `BLOCKED` | Veto todos modos. | Faixa, offset/limit, hashes declarado/computado, identidade. |
| Resposta remota malformada, overflow ou inconsistente | `REMOTE_HASH_INVALID_RESPONSE` / `BLOCKED` | Veto todos modos; não reinterpretar. | Resposta bruta normalizada, validações e motivo. |
| Ambos inválido e divergente | `BLOCKED_CONTRADICTORY_REMOTE_EVIDENCE` | Preservar os dois eventos; nenhum fallback. | Eventos completos e precedência aplicada. |
| Referência ausente, inválida, proveniência insuficiente ou bytes diferentes | `REFERENCE_ABSENT`, `REFERENCE_INVALID`/`REFERENCE_PROVENANCE_UNVERIFIED`, ou `REFERENCE_MISMATCH` | Veto modo referência; sem fallback/sucesso. | Identificador da referência, tamanho/hash, proveniência e comparação. |
| Hash remoto falha transitoriamente após orçamento de retries/FloodWait S5 | `REMOTE_HASH_UNAVAILABLE` | Bloquear tentativa; sem fallback. | Chamadas, códigos, waits, tentativas e limite atingido. |
| Faixa cruza E, semântica além EOF desconhecida | `REMOTE_HASH_UNVERIFIABLE_EOF` | Não clamp/pad/truncar; não contribui para full. | Range, E, bytes verificáveis e resultado das outras faixas. |
| Cobertura tem lacuna | `REMOTE_HASH_PARTIAL` | Nunca full; modo selecionado decide apenas se modo alternativo aprovado é elegível. | União de intervalos e lacunas. |
| Método explicitamente ausente ou resposta vazia | `REMOTE_HASH_ABSENT` | Nunca full; sem fallback; modo alternativo só se pré-selecionado/aprovado. | Método/resultado e contexto. |
| Respostas válidas, coincidentes e cobrem `[0,E)` | `REMOTE_HASH_FULL` | Elegível após gates operacionais e finalização. | Todas faixas/digests, versão avaliador, identidade/E/SHA final. |
| Todos os gates do modo passam | Sucesso apenas do modo selecionado | Persistir estado/evidência versionada; nunca elevar classe por inferência. | Eventos, modo, versão contrato/schema, final, SHA, E e identidade. |

Todos os eventos observados permanecem no registro; a coluna agregada primária segue precedência acima. Ausência, EOF, parcial e indisponibilidade nunca se confundem; nenhuma permite downgrade implícito.

## 11. Regra proposta para aceite formal S6

Manter quatro resultados independentes: `OPERATIONAL_ACCEPTANCE`, `RESUME_ACCEPTANCE`, `REFERENCE_ACCEPTANCE` e `REMOTE_HASH_ACCEPTANCE`, cada qual `PASS`, `FAIL`, `NOT_TESTED` ou `NOT_APPLICABLE`, com razão e evidência própria. Não converter `NOT_TESTED` ou `NOT_APPLICABLE` em PASS.

Recomendação para declarar `S6_READY_FOR_FORMAL_DECISION` após eventual adoção V2:

1. `OPERATIONAL_ACCEPTANCE=PASS` e `RESUME_ACCEPTANCE=PASS`, demonstrados em mídia comum sem referência sob `OPERATIONAL_ONLY` pré-selecionado e aprovado; cobrir restart alinhado e não alinhado, releitura `[0,P)`, overlap e orçamento S5.
2. `REFERENCE_ACCEPTANCE=PASS` demonstrado separadamente em caso controlado com referência confiável.
3. Regressões e gates de segurança S4/S5 passam: download inicial, rename recovery, dedup, fila, reservas/limites, tentativas, FloodWait, workers e plan_id.
4. `REMOTE_HASH_ACCEPTANCE` é explicitamente `PASS`, `FAIL`, `NOT_TESTED` ou `NOT_APPLICABLE`, com motivo. `REMOTE_HASH_DIVERGENT` ou `REMOTE_HASH_INVALID_RESPONSE` em qualquer observação bloqueia a prontidão.

Esses critérios podem demonstrar uma capacidade geral operacional e uma capacidade controlada de referência; não alegam cobertura remota quando ausente. Prova controlada sozinha nunca satisfaz capacidade geral. Hash remoto integral é resultado de capacidade separada. Se os três primeiros grupos passarem e não houver veto, a proposta recomenda encaminhar para decisão formal humana, mantendo o resultado remoto explícito. O usuário decide se essa composição é suficiente; aceite formal da S6 permanece humano e exige aprovação explícita da redução de garantia aplicável.

## 12. Texto candidato para alterações do contrato

Texto normativo abaixo é candidato de substituição/adendo; não está vigente.

### S6-OD-01 — modos e eixos de integridade

> O estado operacional e a evidência de integridade são resultados distintos. O modo padrão é `REMOTE_HASH_REQUIRED`, preservando a semântica fail-closed V1. Antes de qualquer RPC ou leitura de payload, registrar por item o modo selecionado, vinculado a identidade, E, plan_id e invocação. `OPERATIONAL_ONLY` exige seleção explícita e visível anterior à execução; nenhuma ausência, indisponibilidade, resposta inválida, EOF não verificável, retry ou restart permite downgrade automático. Um modo sem cobertura remota pode registrar somente `OPERATIONAL_ONLY / UNVERIFIED_ORIGIN`, ou `REFERENCE_MATCH` após prova própria, sem implicar `REMOTE_HASH_FULL`. Divergência válida ou resposta inválida bloqueia todos modos. `REMOTE_HASH_FULL` requer cobertura válida e coincidente de `[0,E)`.

### S6-D02 — seleção, candidato, retomada e custo

> A escolha entre `REMOTE_HASH_REQUIRED`, `OPERATIONAL_ONLY` e `TRUSTED_REFERENCE` é anterior a qualquer operação remota e persistida por item, identidade/E/plan_id/invocação. Falha no modo selecionado bloqueia a tentativa e preserva `.part`; retry/restart exige nova seleção explícita antes de qualquer nova RPC. Não se permite trocar modo após observar resposta. Reconciliar P físico e D sem atribuir autoridade de conteúdo a D. Exigir identidade, caminho, ownership, SQLite, `P≤E`, prefixo integral `[0,P)` e overlap requerido antes de append. Para releitura de prefixo, com `C=256 KiB`, `R=C*ceil(P/C)` se P>0 e zero se P=0; reservar dentro do orçamento agregado S5 antes da primeira requisição, recalcular por tentativa, contar todas as requisições e bloquear antes da chamada se a reserva completa restante não couber. Não aumentar limites S5 nem reservar três tentativas antecipadamente. Contradição bloqueia sem fallback.

### S6-F01 — preview, execução, referência e finalização

> Preview offline/read-only informa modo, garantia pretendida e custo Q/R provisório, sem provar identidade, ownership ou orçamento runtime. Antes da execução, selecionar/persistir modo e revalidar item. Falha de gate bloqueia e preserva arquivos. No modo `TRUSTED_REFERENCE`, validar referência e obter candidato em estado não autoritativo; comparar integralmente bytes, tamanho E e SHA-256 antes de persistir `VALIDATED`, `FINALIZATION_PENDING` ou estado terminal de sucesso. Após match, finalizar por rename atômico sem overwrite e publicar estado/evidência versionados em transação SQLite ou handshake recuperável. Recovery de rename sem transação revalida final contra referência antes de sucesso. Sem referência, manter requisitos específicos do modo pré-selecionado; não reclassificar resultados remotos. `DOWNLOADED` preserva semântica V1; estado V2 operacional/referência sem remote full usa estado terminal distinto aprovado.

### §9 — resultados e regra de aceite

> Registrar independentemente `OPERATIONAL_ACCEPTANCE`, `RESUME_ACCEPTANCE`, `REFERENCE_ACCEPTANCE` e `REMOTE_HASH_ACCEPTANCE` em `PASS/FAIL/NOT_TESTED/NOT_APPLICABLE`, com evidência e motivo. Prontidão recomendada para decisão humana requer operação e retomada PASS em mídia comum sem referência sob modo operacional explicitamente selecionado e aprovado, referência PASS em prova controlada, regressões/gates S4/S5 PASS e resultado remoto declarado sem promoção. Resultado remoto divergente ou inválido bloqueia prontidão. A prova de referência não substitui capacidade geral; nenhuma classe implica outra. A combinação final para aceite formal e qualquer redução de garantia requer aprovação humana explícita.

## 13. Impactos propostos (sem implementação)

| Área | Impacto para decisão/planejamento |
|---|---|
| SQLite | Migration aditiva para schema/contract version, modo e consentimento, identidade/E/plan_id/invocação, classes e eventos remotos, ranges, referência, SHA final, estado terminal e motivo. Transição estado/evidência atômica ou handshake recuperável. Legados ficam `UNKNOWN_LEGACY`; sem retroatribuição. |
| Checkpoints | Preservar durabilidade write/flush/fsync antes do checkpoint atual. D continua operacional. Evidência vinculada a identidade/E/bytes e invalidada quando qualquer um muda. |
| Downloader | Seleção explícita antes de RPC; releitura integral do prefixo e overlap sob orçamento compartilhado; nenhum downgrade; gate da referência antes de persistir sucesso; rename sem overwrite e recovery com revalidação. |
| Gateway | Distinguir absent, unavailable, invalid, EOF-unverifiable, partial, full e divergent; preservar ranges e erros do Telethon sem trimming ou semântica inventada. |
| CLI/planner/consumidores | Preview mostra seleção e custo provisório; execução mostra estado operacional, evidência, versão e motivo. Consumidores legados desconhecidos falham fechado para V2 e não deduplicam como `DOWNLOADED` verificado. |
| Testes/evidência futura | Cobrir matriz de precedência, modos, estados/versões, migrations, consumidores antigos, falhas e crash windows, igualdade de referência, retomada alinhada/não alinhada, custos/retries e regressões S4/S5. Nenhum teste foi executado ou autorizado por este documento. |

## 14. Riscos residuais

- `OPERATIONAL_ONLY` não oferece âncora para conteúdo originalmente pretendido e depende da estabilidade dos bytes remotos durante leitura.
- Referência ou manifesto pode ser comprometido; proveniência local não verificada externamente limita `REFERENCE_MATCH` à referência adotada.
- Sem cobertura remota e sem referência, hash local sozinho não prova origem. O modo operacional reduz garantia em relação à regra V1.
- Releitura completa pode consumir até o limite agregado, tempo e disco; cap insuficiente bloqueia e preserva parcial.
- Crash entre filesystem e SQLite exige recovery cuidadoso para não sinalizar sucesso falso.
- Consumidores desconhecidos podem interpretar incorretamente novo estado/evidência; rollout precisa de compatibilidade fail-closed.
- Geometria EOF de `GetFileHashes` permanece semanticamente não especificada; faixa excedente não tem digest verificável pela proposta.

## 15. Itens que exigem aprovação humana

1. **Autorizar capacidade `OPERATIONAL_ONLY` e redução explícita de garantia.** Recomendação: aprovar somente com escolha explícita antes de cada execução, rótulo visível `UNVERIFIED_ORIGIN`, gates de releitura e limites S5 preservados.
2. **Autorizar `COMPLETED_V2`, migration aditiva e rollout de consumidores.** Recomendação: sim, estado distinto; preservar `DOWNLOADED` V1 e consumidores desconhecidos fail-closed.
3. **Aprovar composição do aceite formal.** Recomendação: exigir três grupos PASS (operação, retomada geral e prova controlada), gates S4/S5 PASS e status remoto explícito; permitir encaminhar à decisão formal só sem veto inválido/divergente. O usuário decide se isso basta para aceite.
4. **Aceitar custo de releitura.** Recomendação: permitir somente quando preflight garante reserva dentro do orçamento agregado S5 existente; nunca aumentar cap nem chamar sem reserva.
5. **Aprovar texto normativo V2, adoção e data efetiva.** Recomendação: manter V1 até aprovação expressa e rollout compatível. Implementação e prova LIVE requerem authority futura separada.

Não há outras escolhas semânticas técnicas pendentes nesta proposta. Aprovação de qualquer item não autoriza automaticamente implementação, testes, operação Telegram, mudança de sprint ou publicação Git.

## 16. Evidências preexistentes referenciadas

As geometrias abaixo foram fornecidas em atividade anterior. Não foram reexecutadas nesta revisão e não atribuem falha ao servidor:

| Caso | Valores fornecidos | Limite da evidência |
|---|---|---|
| RASMOO / message 598 | E=`11,649,955`; faixa `[11,534,336, 11,665,408)` excede EOF em `15,453` bytes. | Digest da faixa excedente não pode ser validado com apenas bytes anteriores ao EOF; sem conclusão sobre semântica do servidor. |
| Mídia 7603 | E=`1,119,129,690`; cursor=`1,119,092,736`; faixas `[1,118,830,592, 1,118,961,664)`, `[1,118,961,664, 1,119,092,736)`, `[1,119,092,736, 1,119,223,808)`; a última excede EOF em `94,118` bytes. | As faixas anteriores são observações de intervalos; a última não prova cobertura verificável até EOF. Nenhuma alegação de falha do servidor. |

```text
PROPOSAL_CREATED = YES
PROPOSAL_STATUS = DRAFT / NOT APPROVED / NOT CANONICAL
CANONICAL_CONTRACT_MODIFIED = NO
IMPLEMENTATION = NO
TELEGRAM_OPERATIONS = 0
TESTS_EXECUTED = 0
SQLITE_OR_PART_MODIFIED = NO
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
S6_FORMAL_ACCEPTANCE = PENDING
NEXT_ACTION = USER_FINAL_CONTRACT_DECISION
```
