# S6 — Contrato de Retomada e Recuperação de Downloads Parciais

```text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6-CONTRACT-FORMAL-CLOSURE-01
PREVIOUS_ACTIVITY = S6-CONTRACT-REMEDIATION-01
ORIGIN_ACTIVITY = S6-ENTRY-CONTRACT-01
STATUS = APPROVED / FROZEN
S6_STATUS = PLANNED / NOT_STARTED
USER_CONTRACT_APPROVAL = GRANTED
CONTRACT_FREEZE = APPROVED / FROZEN
IMPLEMENTATION_AUTHORIZATION = NO
F-01 = RESOLVED
S6-OD-01 = APPROVED / ALTERNATIVE_A
S6-OD-02 = APPROVED / ALTERNATIVE_A
ACCEPTANCE_CRITERIA_COUNT = 18
S4_CONTRACT = APPROVED / FROZEN
S5_CONTRACT = APPROVED / FROZEN
CREATED_AT = 2026-10-12 / America/Sao_Paulo
UPDATED_AT = 2026-10-12 / America/Sao_Paulo
```

Este contrato foi aprovado formalmente pelo usuário e congelado para o escopo
S6 descrito aqui. A aprovação não inicia S6 nem autoriza implementação. Não
altera os contratos S4/S5 nem os limites aprovados para esses escopos.

## 1. Authorities e objetivo

- [Estado corrente](../continuity/PROJECT_STATE.md) e [mapa de authorities ativas](../continuity/ACTIVE_AUTHORITY_MAP.md).
- [Roadmap](../continuity/planning/ROADMAP.md) e [plano de sprints](../continuity/planning/SPRINTS.md), em especial S6.
- [Requisitos](../product/REQUIREMENTS.md): FR-12, FR-08, FR-09; NFR-02, NFR-03, NFR-04, NFR-08, NFR-09 e NFR-10.
- [Contrato S4](S4_SINGLE_MEDIA_DOWNLOAD_CONTRACT.md), aprovado e congelado.
- [Contrato S5](S5_COURSE_SELECTION_PLANNER_QUEUE_CONTRACT.md), aprovado e congelado, inclusive os limites de execução.
- [Auditoria técnica histórica](../audit/AUDITORIA_TECNICA_2026-10-05.md), usada somente como contexto não normativo.

**Objetivo:** depois de uma interrupção, reconhecer um `.part` pertencente à mesma mídia, validar identidade e bytes recuperáveis, continuar sem sobrescrever o prefixo, validar o arquivo completo e só então finalizar e persistir `DOWNLOADED`.

**Fora de escopo:** sincronização incremental S7, hardening transversal S8, novo downloader, novo motor de fila, execução distribuída/multi-processo, GUI, novas opções de configuração e qualquer capacidade de produto fora da retomada S6.

## 2. Diagnóstico de entrada

| Campo | Diagnóstico desta revisão |
|---|---|
| `S6_DEPENDENCIES` | S4 e S5 estão `CLOSED / PASS`; S6 permanece `PLANNED / NOT_STARTED`. A entrada documental está autorizada; implementação não. |
| `S4_REUSE` | Reutilizar `SingleMediaDownloadApplication`, identidade canônica, caminho determinístico, guarda de reparse/symlink, SHA-256 local, estados de arquivo e finalização no-overwrite. |
| `S5_REUSE` | Reutilizar `DownloadPlanner → DownloadQueue → workers limitados → SingleMediaDownloadApplication`; manter uma sessão/gateway compartilhada, inicializada uma vez antes do primeiro stream. |
| `SP03_STATUS` | O plano e a auditoria registram a obrigação do SP-03, mas não foi localizado relatório, manifesto, transcript ou commit que prove o experimento de offsets. A prova real S4 documenta um download completo de 6.199.635 bytes, com stream iniciado em offset zero. Isso prova streaming normal daquela mídia, não interrupção, restart ou retomada. |
| `API_COMPATIBILITY` | `pyproject.toml` permite Telethon `>=1.45,<1.46`. A documentação 1.45 expõe `iter_download(offset=...)`; a documentação Telegram impõe alinhamento na chamada wire. O adapter atual não recebe offset. Uso de offset de retomada, `getFileHashes` via Telethon e prova real permanecem `NOT_TESTED` nesta atividade. |
| `DB_SCHEMA_IMPACT` | Recomenda-se nenhuma migration: `downloads` já tem `state`, paths final/parcial, `expected_bytes`, `downloaded_bytes`, `attempts`, `sha256`, `failure_category` e `owner_pid`. São necessárias mudanças de comportamento no repositório para reivindicar uma retomada e persistir checkpoints. |
| `APPROVED_DECISIONS` | S6-OD-01 = `APPROVED / ALTERNATIVE_A`; S6-OD-02 = `APPROVED / ALTERNATIVE_A`. Ver §11. Não resta decisão OD-01/OD-02 em aberto. |
| `REMOTE_HASH_VALIDATION` | A disponibilidade e a cobertura real de `upload.getFileHashes` para cada mídia suportada ainda não foram comprovadas; permanecem validação técnica futura e bloqueio fail-closed se a cobertura não puder ser demonstrada. |
| `F-01` | `RESOLVED` em S6-F01: o preview offline pode encaminhar como candidato condicional um `.part` localmente elegível sem afirmar integridade; ownership, identidade, integridade remota, orçamento runtime e append permanecem gates da execução confirmada. |
| `MATERIAL_RISKS` | O tamanho do `.part` não prova conteúdo íntegro; identidade remota pode mudar ou ficar inacessível; `iter_download` e `getFileHashes` ainda não foram comprovados no adapter para retomada; a estimativa S5 atual não conhece um prefixo S6 validado; a prova anterior SP-03 não está evidenciada no pacote atual. |

**Classificação:** `APPROVED / FROZEN`. Isso não é `READY_FOR_IMPLEMENTATION`: a prova técnica real, inclusive disponibilidade/cobertura de hashes remotos nas mídias suportadas, continua pendente e a autorização de implementação permanece separada.

### 2.1 O que a execução atual demonstra

Fatos registrados nas authorities atuais:

- S4 baixou uma mídia DOCUMENT inteira por streaming e conferiu tamanho/hash local; o fluxo usa `iter_download` a partir do offset padrão zero.
- S5 validou fila, dois workers, orçamento agregado, recuperação de itens completos e deduplicação em cinco mídias observadas. O catálogo dessa prova era parcial.
- S5 corrigiu a inicialização concorrente do gateway: os workers aguardam a mesma tarefa de criação/restauração antes de qualquer stream.
- Há teste offline S4 que interrompe o gateway após alguns bytes e deixa `.part`/`FAILED_RETRYABLE`; ele não reinicia o processo nem retoma bytes.
- Não há evidência localizada de offset não zero, comparação de prefixo, continuação de arquivo grande ou resultado idêntico a uma referência após retomada.

Portanto, S4/S5 não demonstram retomada por byte e não fecham o gate real S6.

## 3. Descoberta do fluxo e pontos de extensão

| Responsabilidade | Ponto atual | Extensão S6 proposta |
|---|---|---|
| Caminhos `.part` e final | `downloads.py`: `destination_paths`; nome determinístico termina em `.part`; valida caminhos e rejeita symlinks/reparse points. | Preservar path e checks. Nunca adotar um `.part` de path divergente nem substituir arquivo final existente. |
| Identidade e elegibilidade local | `DownloadRepository.select_candidate`: canal, mensagem, ordinal, Telegram media ID, tamanho e linhagem Lesson. | Reutilizar a chave única da mídia. Conferir o candidato outra vez antes de reivindicar o `.part`. |
| Conteúdo e stream remoto | `TelethonGateway._iterate_media`: refetch da mensagem, valida canal, id da mensagem, ordinal zero, DOCUMENT, media ID e tamanho; atualmente `iter_download` sem offset. | Expor internamente o offset wire alinhado e leitura dos hashes remotos exigida por S6-OD-01 aprovado. Manter tipos Telethon dentro do adapter. |
| Estado e ownership | `DownloadRepository`: `BEGIN IMMEDIATE`, índice único por `media_item_id`, `owner_pid`; estados `DOWNLOADING`, `VALIDATED`, `FINALIZATION_PENDING`, `DOWNLOADED`, `FAILED_RETRYABLE`, `FAILED`. | Adicionar claim de resume sem zerar `downloaded_bytes` e operação de checkpoint ordenada após `fsync`. Reusar estados/colunas. |
| Append, hash e commit físico | `SingleMediaDownloadApplication`: atualmente `partial.open("wb")` trunca o arquivo; valida tamanho/SHA, faz `flush`/`fsync`, renomeia sem sobrescrever e só depois grava `DOWNLOADED`. | Substituir o truncamento por append controlado após validar prefixo e overlap. Recalcular SHA-256 do arquivo completo antes do commit final. |
| Planejamento, limite de bytes e disco | `s5_downloads.py`: preview read-only; `pending_bytes` soma o tamanho total; margem `MAX(1 GiB, 10% dos bytes pendentes)`; orçamento real reserva até 256 KiB antes de cada GetFile. | Preservar o preview offline e o `plan_id` determinístico; apresentar candidato S6 localmente elegível e estimativas como provisórios. A execução confirmada refaz a validação e o orçamento após prova remota; cada `GetFile`, inclusive leitura de verificação, exige reserva runtime. |
| Workers e gateway compartilhado | `DownloadQueue` usa 1–2 workers; `cli.py` passa um único executor S4 e `_LazyGateway` com tarefa de inicialização compartilhada. | Reutilizar sem fila nova; preservar inicialização concluída antes de streams concorrentes e não reintroduzir a corrida `SESSION_INVALID`. |

### 3.1 SQLite e ownership hoje

- `DOWNLOADING`: transferência reivindicada; `owner_pid` identifica o processo e o registro guarda paths/tamanho esperado.
- `FAILED_RETRYABLE`: S4 grava bytes conhecidos quando uma falha é capturada. Não há checkpoint SQLite por chunk; queda abrupta pode deixar o contador abaixo do `.part` físico.
- `VALIDATED`: tamanho e SHA-256 locais foram calculados para o arquivo completo.
- `FINALIZATION_PENDING`: SQLite registrou validação antes/depois da janela de rename; filesystem e registro precisam ser reconciliados.
- `DOWNLOADED`: só é deduplicável se arquivo final, tamanho e SHA-256 corresponderem ao registro.
- `FAILED`: schema aceita o estado terminal, mas S4 atualmente grava a maioria das falhas capturadas em `FAILED_RETRYABLE`; S5 limita retries dentro da invocação por categoria. S6 deve classificar suas próprias falhas terminais sem ampliar a política S5.
- Exclusão mútua combina lock process-local por `media_item_id`, transação/índice SQLite e verificação do `owner_pid`. O contador persistido não é checkpoint físico a cada chunk.

## 4. Contrato proposto para integridade e offset

### S6-D01 — Autoridade do offset

Seja `P` o tamanho físico atual do `.part`, `D` o `downloaded_bytes` persistido e `E` o tamanho esperado confirmado no refetch remoto.

1. `P` é o único offset lógico candidato: nenhum byte pode ser pulado com base apenas em `D`.
2. `D` é um checkpoint/indício de reconciliação e nunca substitui `P` como offset. `D < P` pode ser resultado de interrupção entre persistência do arquivo e atualização SQLite; `D > P` é uma divergência que deve ser registrada. Em ambos os casos, `P` continua sendo apenas candidato: o prefixo físico só pode ser usado depois da validação de identidade, caminho e conteúdo definida em S6-D02.
3. Se `P > E`, preservar o arquivo e bloquear; não truncar.
4. Se `P = E`, não inferir conclusão pelo tamanho. Para um `.part`, só recuperar/finalizar após a validação remota aprovada comprovar todos os bytes de `[0,E)`; estado `VALIDATED` e SHA-256 local isolados não substituem essa prova. Caso contrário, preservar e bloquear.
5. Se `0 < P < E`, só retomar quando o `.part` estiver ligado ao registro da mesma mídia, o processo proprietário estiver morto e a integridade do prefixo passar. Caso contrário, preservar e bloquear.
6. Se `P = 0`, tratar como início em offset zero apenas se registro/path/ownership forem da aplicação; `.part` vazio estrangeiro permanece bloqueado.
7. `E` deve coincidir com o tamanho informado pela mídia refetchada e com `expected_bytes` persistido. Divergência bloqueia sem anexar bytes.

Persistir checkpoints na ordem `write → flush/fsync do arquivo → atualização SQLite`. O `.part` pode avançar além de `D` por queda entre essas duas últimas operações; a reconciliação não pode descartar esse prefixo só para igualar o contador.

### S6-D02 — Validação do `.part`

| Situação | Comportamento proposto |
|---|---|
| Inexistente | Iniciar no offset zero após claim S4 e refetch/validação da identidade. |
| Vazio e pertencente à aplicação | Tratar como zero bytes e reiniciar do começo, mantendo o path e o ownership. |
| Vazio ou parcial sem registro/path proprietário correspondente | Estrangeiro: preservar e bloquear. |
| Parcial `0 < P < E`, path regular e identidade local correspondente | Usar `P` somente como offset lógico candidato; comprovar remotamente todos os bytes de `[0, P)` e validar o overlap antes de qualquer append. Hash recalculado apenas localmente não prova que o prefixo é válido. |
| Tamanho igual a `E` com `VALIDATED`/`FINALIZATION_PENDING` e SHA confiável | Conferir arquivo físico e a prova remota completa exigida por S6-OD-01; SHA local isolado não substitui cobertura remota. Se ambas passarem, concluir a recuperação S4 sem novo stream. |
| Tamanho igual a `E` sem SHA/estado de validação confiável | Não marcar concluído por tamanho; validar remotamente ou preservar e bloquear. |
| Tamanho maior que `E` | Preservar e bloquear como `PARTIAL_SIZE_EXCEEDED`. |
| Path divergente, symlink/reparse point, arquivo não regular ou registro de outra mídia | Preservar e bloquear; nunca apropriar, substituir ou apagar. |
| Prefixo não confere com hashes remotos | Preservar e bloquear como `PARTIAL_INTEGRITY_MISMATCH`; não anexar, truncar ou apagar automaticamente. |
| Arquivo final já existe e corresponde a estado/hash válidos | Reconciliar como já válido ou recuperar `DOWNLOADED`, sem stream. |
| Arquivo final existe mas está sem prova, divergente ou estrangeiro | Preservar e bloquear; manter no-overwrite. |

O tamanho e o SHA-256 calculados localmente são necessários para validação/deduplicação, mas não provam sozinhos que bytes parciais correspondem ao Telegram. S6-OD-01 exige SHA-256 por faixa informado pelo Telegram quando o mecanismo for tecnicamente aplicável e sua disponibilidade/cobertura estiver comprovada para a mídia suportada. A existência da referência pública do método não comprova essa disponibilidade ou cobertura nesta atividade.

#### Regra obrigatória de prova remota do prefixo

1. Antes de validar bytes, refazer a identidade remota e compará-la integralmente com a identidade canônica persistida no SQLite: `channel_id`, `telegram_message_id`, `media_ordinal`, tipo, `telegram_media_id` e `expected_bytes`. Qualquer divergência bloqueia a retomada.
2. Para cada faixa retornada por `upload.getFileHashes`, validar `offset`, `limit` e o formato/tamanho do hash SHA-256; rejeitar valores inválidos, limites não positivos, estouro de intervalo, resposta incompatível com a solicitação ou hash divergente. Calcular o hash local de cada faixa em streaming, sem carregar o arquivo inteiro em memória.
3. As faixas aceitas devem comprovar, pela união dos intervalos, todos os bytes de `[0, P)`, sem lacuna. Cobertura parcial, ausente, inconsistente ou não verificável não comprova o prefixo.
4. Se uma faixa ultrapassar `P`, o hash da faixa completa não pode ser comparado a um fragmento local nem ser tratado como prova apenas do trecho `[offset, P)`. O contrato deve obter uma faixa válida que não ultrapasse `P`, se isso for suportado e comprovado, ou ler os bytes remotos faltantes por `GetFile` sob reserva de orçamento; se nenhuma opção for segura, bloquear. Toda leitura complementar conta no cap de mídia.
5. Aplicar a mesma validação de offsets, limites, hashes e cobertura aos bytes da continuação antes de declarar o arquivo validado. Se não houver cobertura remota verificável, não finalizar nem persistir `DOWNLOADED`.
6. A região de overlap `[W, P)` deve ser comparada byte a byte com os bytes remotos recebidos antes de qualquer append. Só após igualdade de todo o overlap a escrita pode começar em `P`.
7. Se não for possível comprovar integralmente a integridade exigida, não anexar, não truncar automaticamente, não apagar; preservar o `.part` e registrar bloqueio explícito. Não existe fallback que aceite prefixo não comprovado.

### S6-D03 — Alinhamento do offset e continuidade

Separar quatro valores:

```text
P = offset físico/lógico no fim do .part
C = 256 KiB = CHUNK_BYTES/request_size proposto
W = floor(P / C) * C = início alinhado enviado ao adapter
O = P - W = bytes de sobreposição a comparar antes de append (0 <= O < C)
```

- O adapter S6 aceita `W`, não um offset físico arbitrário. Com `request_size == chunk_size == 256 KiB`, `W` é múltiplo de 4 KiB e cada request de 256 KiB cabe numa unidade de 1 MiB.
- O stream inicia em `W`. Os primeiros `O` bytes são comparados byte a byte com o final já existente do `.part`; eles contam como payload recebido/orçamentado, mas não são escritos de novo.
- Somente após igualdade do overlap o executor escreve a partir do byte `P`. Assim o offset físico pode ser não alinhado sem afirmar que a chamada wire usa offset arbitrário.
- Descontinuidade no overlap interrompe e preserva os dois estados físicos; não tenta “corrigir” por append.
- A documentação pública do Telethon 1.45 descreve `iter_download(offset=...)` em bytes e avisa que alinhamentos não múltiplos podem exigir trabalho extra. A API Telegram exige offset e limit múltiplos de 4 KiB (salvo `precise`) e cada parte dentro da mesma janela de 1 MiB. A estratégia S6 acima evita depender do caminho genérico de offset não alinhado.
- Confirmar no gate futuro que Telethon 1.45.x mantém o caminho direto para `W`, entrega bytes contíguos e que o hook de reserva S5 contabiliza todas as respostas. Caso o comportamento observado divirja, parar e rever o contrato; não contornar erro de offset silenciosamente.

Fontes primárias: [Telethon 1.45 — `iter_download`](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.downloads.DownloadMethods.iter_download), [Telegram — download de arquivos e alinhamento](https://core.telegram.org/api/files#downloading-files), [Telegram — `upload.getFile`](https://core.telegram.org/method/upload.getFile), [Telegram — `upload.getFileHashes`](https://core.telegram.org/method/upload.getFileHashes).

### S6-D04 — Identidade remota

Antes de qualquer uso do prefixo, o gateway deve refetch da mensagem indicada e validar:

```text
channel_id
telegram_message_id
media_ordinal
media kind = DOCUMENT
telegram_media_id
expected_bytes
```

Para o fluxo S4 atual, `media_ordinal` aceito é zero. O peer da mensagem, id da mensagem, identidade do documento e tamanho precisam coincidir com o candidato SQLite. Filename/nome de exibição participa do path determinístico, mas não substitui identidade de mídia.

Mensagem removida, acesso revogado, peer diferente, mídia ausente/substituída, ordinal/tipo divergente ou tamanho alterado: não anexar nada, preservar `.part`, retornar categoria estável e exigir nova decisão/seleção. Não fazer scan de canal nem adotar uma mídia nova sob a identidade antiga.

Uma nova tentativa que requeira referência atual deve entrar pelo limite normal S5 e refazer a mensagem antes de GetFile. Reaquisição não aumenta as três tentativas ou o orçamento FloodWait aprovados.

### S6-D05 — Finalização durável

1. Manter o `.part` e o final no mesmo volume.
2. Fechar o stream, confirmar tamanho físico exato `E`, fazer `flush` e `fsync`, calcular SHA-256 local do arquivo inteiro e validar remotamente as faixas da continuação conforme S6-OD-01.
3. Persistir `VALIDATED` com tamanho/hash; depois `FINALIZATION_PENDING`.
4. Finalizar atomicamente sem sobrescrever o destino (reusar a política S4). Reabrir/validar o final por tamanho e SHA-256.
5. Só depois persistir `DOWNLOADED`. Um flag/linha SQLite sem arquivo final comprovado nunca conta como sucesso.
6. Em colisão de destino, divergência de hash ou path, preservar os arquivos e bloquear.
7. Reutilizar reconciliação S4 após rename. Um final válido em `FINALIZATION_PENDING` pode ser confirmado como `DOWNLOADED` sem nova transferência.

`SHA256` SQLite continua sendo o digest do arquivo completo. Não persistir um digest local recém-calculado como prova remota do prefixo.

O contrato exige recuperação consistente após interrupção do processo, falha de conexão, encerramento/reinício normal e falhas entre filesystem e transações SQLite. Após queda súbita de energia, nunca presumir que bytes em cache foram persistidos: revalidar o estado físico e o estado SQLite; recuperar somente quando a consistência puder ser provada, caso contrário bloquear e preservar. `flush`/`fsync` e rename atômico não são promessa de persistência absoluta em hardware/cache. Teste destrutivo de perda de energia não é gate obrigatório S6.

## 5. Recovery e concorrência

### S6-D06 — Janelas de interrupção

| Janela | Reconciliação proposta |
|---|---|
| Processo termina durante stream | Detectar PID morto; ler o `.part` físico; refetch identidade e validar prefixo antes de continuar. |
| Conexão cai e aplicação captura erro | Persistir `FAILED_RETRYABLE`/bytes observados após fechar e sincronizar `.part`; preservar prefixo. Nova tentativa usa as cotas S5. |
| Windows reinicia e owner PID não existe | Mesmo caminho de recuperação de processo morto. Não confiar em checkpoint SQLite isoladamente. |
| Arquivo foi gravado/fsync, DB ainda não recebeu checkpoint | `P > D` pode ser reconciliado; usar `P` só após verificação de identidade e integridade. |
| DB checkpoint foi gravado, mas arquivo físico está menor | Nunca pular para `D`; verificar o prefixo físico real e retomar a partir dele apenas se válido. Registrar a divergência. |
| Falha antes de `VALIDATED` | Preservar `.part`; refetch/hash remoto antes de qualquer append. |
| Falha depois de `VALIDATED`, antes/depois de `FINALIZATION_PENDING` | Revalidar `.part` fisicamente e comprovar remotamente todos os bytes existentes conforme S6-OD-01; SHA local registrado isoladamente não substitui a prova. Só então finalizar sem novo stream. |
| Falha depois do rename, antes de persistir `DOWNLOADED` | Validar o arquivo final contra tamanho/SHA confiáveis e persistir `DOWNLOADED`; sem retransmissão. |
| Falha depois de `DOWNLOADED` | Segunda execução confere final e deduplica; zero bytes novos. Se arquivo divergir, não o substituir. |

Recuperações válidas são idempotentes. Se row/path/owner/identity/hash não resolverem a janela sem ambiguidade, parar, preservar `.part` e final e reportar bloqueio.

### S6-D07 — Ownership e workers

- Reusar o lock process-local por `media_item_id`, o índice único SQLite e a reivindicação transacional/`owner_pid` S4. O claim precisa acontecer antes de escrever ou anexar.
- Só reclaim quando o owner anterior estiver comprovadamente morto; owner vivo bloqueia a segunda escrita no mesmo destino. Considerar reutilização de PID após restart: se os dados de ownership existentes não distinguirem com segurança o processo anterior de um processo diferente com o mesmo PID, ownership é ambíguo, então preservar e bloquear sem iniciar outro writer. Não criar outro modelo de ownership ou migration nesta atividade.
- Reusar os workers S5: default 2, valores 1–2, limitado aos itens pendentes. Não criar workers por chunk nem execução multi-processo.
- Todos os workers aguardam uma única inicialização/restauração compartilhada do gateway antes de stream. Preservar a correção S5 de `SESSION_INVALID`.
- A prova de concorrência deve incluir a mesma mídia sob disputa e comprovar no máximo um escritor/stream por identidade.

## 6. Orçamento e espaço — S6-D08

Manter separados os contadores:

| Medida | Definição S6 proposta | Efeito |
|---|---|---|
| Bytes já presentes | `P` observado fisicamente no `.part` candidato | Não são payload transferido desta execução. A observação offline não comprova integridade; serve à estimativa condicional e não autoriza append. |
| Bytes adicionais em disco | `E - P` como estimativa para candidato localmente elegível; valor autoritativo após revalidação na execução | O `.part` existente já ocupa o volume e não deve ser contado novamente. O preview rotula a estimativa como provisória; conflitos locais impeditivos permanecem bloqueados. |
| Payload de continuação | `E - P` bytes teóricos para preencher a região ausente `[P,E)` | Estimativa condicional no preview; após revalidação, payload recebido por `GetFile` é debitado no cap agregado. É separado do overlap e de qualquer leitura extra de verificação. |
| Overlap de rede | `O = P - W`, provisório no preview e recalculado após prova/ownership | Payload novo recebido do Telegram e debitado no cap; é comparado e não regravado no `.part`. |
| Leituras extras de integridade | `V` = bytes adicionais de mídia lidos por `GetFile` para completar/verificar uma faixa remota, quando necessários | Payload recebido por `GetFile`, debitado no cap; deve ser estimado no preflight ou a execução bloqueia sem reserva suficiente. |
| Retransmissões após falhas/retries | `R` = payload novamente recebido por `GetFile` após falha/retry, incluindo bytes de continuação e overlap repetidos | Continua debitado no mesmo cap agregado; tentativa/retry não zera consumo nem cria orçamento. |
| Payload total recebido | Soma dos bytes de mídia em cada resposta real de `GetFile`, em todos os workers e tentativas; retries de bytes já vistos continuam sendo payload novo recebido nesta execução | Debitado integralmente no orçamento global S5 compartilhado. A classificação de finalidade/retransmissão não reduz nem duplica o débito; in-flight incerto continua cobrado pela reserva inteira, conforme S5. |
| Bytes gravados no destino | Bytes de `P` até `E`, sem overlap | Usados para progresso em disco e validação de tamanho, não substituem payload recebido. |
| Hash metadata | Respostas `getFileHashes` | Não são mídia/payload. Chamadas continuam sujeitas a rate limits, cancelamento, erros e FloodWait; esperas contam no teto cumulativo existente de 120 s por mídia. |

Para um candidato localmente elegível, o preview pode mostrar provisoriamente `E - W = (E - P) + O` como continuação mais overlap previsto (`W = floor(P / C) * C`); isso não prova o prefixo nem valida o orçamento runtime. Leituras adicionais `GetFile` previstas para completar/verificar faixas remotas têm custo separado `V`. Após confirmação, prova e revalidação, recalcular os valores e o custo total; se `V` não puder ser calculado/reservado ou não houver reserva suficiente para qualquer `GetFile`, bloquear antes da chamada. Todo payload de mídia efetivamente recebido por `GetFile`, inclusive retransmissões `R`, consome o orçamento agregado autorizado da execução. O runtime é a autoridade final: reservar até 256 KiB antes de cada `GetFile`, debitar resposta efetiva/uncertain e nunca enviar chamada sem reserva.

Hashes metadata não são bytes de mídia e não entram no cap de payload; suas chamadas devem respeitar rate limits, cancelamento, tratamento de erros e o teto FloodWait cumulativo de 120 s por mídia, compartilhado com a execução. Candidato condicional pode exibir `E-W` e `E-P` como estimativas provisórias antes da prova, sem autorização de transferência. Conflito local impeditivo permanece bloqueado; falha na prova remota bloqueia a execução e preserva `.part`, sem append ou descarte automático.

No preview, `E - P` e a margem S5 preservada `MAX(1 GiB, 10% dos bytes adicionais conhecidos)` são estimativas provisórias para candidato localmente elegível. Após confirmação, ownership e prova remota, recalcular necessidade e margem, revalidar espaço antes de cada item e subtrair a necessidade dos demais itens em espera; contar que `.part` existentes já ocupam o volume. Tamanho desconhecido continua excluído/fail-closed em execução com cap.

Não criar limite configurável por mídia. A contabilização por mídia é informativa e soma respostas reais de suas tentativas; o limite autorizado continua sendo o orçamento agregado S5 e suas reservas. Preservar `MAX_ATTEMPTS_PER_MEDIA = 3`, FloodWait cumulativo máximo de 120 segundos por mídia, 1–2 workers e demais limites S5. A retomada não zera contadores nem cria orçamento extra.

### 6.1 Integração mínima necessária com S5

O preflight S5 atual é offline e calcula `pending_bytes` sem prova remota. O contrato S6 não altera os contratos S5 congelados nem seus limites. Para F-01, o planner pode expor estimativas condicionais para `.part` localmente elegível antes de qualquer validação remota; essas estimativas não são `VALIDATED_RUNTIME_BUDGET = PASS` nem autorização de transferência. Depois da confirmação, a execução refaz identidade/integridade e calcula orçamento e espaço com o estado revalidado. Candidato localmente inseguro/ambíguo permanece bloqueado; a ausência de prova remota, por si só, não deve bloquear circularmente um candidato condicional.

```text
NECESSITY = O preview S5 é read-only/offline, portanto não pode comprovar a integridade remota exigida por S6; bloquear todo prefixo ainda não provado impede a execução que realizaria essa prova.
ALTERNATIVES = (1) bloquear prefixos até haver prova remota, criando dependência circular; (2) tratar o prefixo como validado no preview offline, permitindo append inseguro; (3) classificar localmente elegíveis como condicionais, sem aprovação de append, e exigir prova e reorçamento durante execução confirmada.
RISK = O plano read-only pode ficar obsoleto entre preview e execução e as estimativas não incluem fatos remotos ainda desconhecidos; refazer filesystem/SQLite sob ownership, separar estimativa provisória de orçamento runtime PASS e reservar cada GetFile antes do request.
MINIMUM_CHANGE = Preservar um único planner/plan_id/fila S5; expor classificação condicional transitória e estimativas provisórias para candidatos localmente elegíveis; após confirmação, claim S4, refetch e prova remota, recalcular limites e usar as reservas agregadas S5 em runtime. Prefixos inseguros ou ambíguos continuam bloqueados.
```

Isso é uma extensão comportamental mínima do fluxo S6 no planner/queue existentes. Não exige alterar o contrato S5 congelado, os valores de limite, o determinismo de `plan_id`, criar segunda fila ou adicionar configuração.

### S6-F01 — Preview condicional e gate remoto de execução

#### Etapa A — Preview offline

O `DownloadPlanner` pode classificar um `.part` como `CONDITIONAL_RESUME_CANDIDATE` somente para fins de planejamento quando leituras locais de SQLite/filesystem confirmarem identidade canônica conhecida, mídia elegível, path esperado e seguro, arquivo regular, ownership local admissível, `0 < P < E` e ausência de conflito local impeditivo. `E` nesta etapa é o tamanho esperado local persistido, ainda sujeito à confirmação remota. Arquivo estrangeiro, path inseguro, identidade local inconsistente, ownership ambíguo ou conflito conhecido permanece `BLOCKED`.

Essa classificação é conceitual/transitória do preview; não é novo estado SQLite nem estado canônico de download. O preview deve:

- continuar read-only e determinístico, sem gateway Telegram, autenticação, chamadas remotas, claim de ownership ou mutação de SQLite/filesystem;
- preservar o `plan_id` e o contrato determinístico S5;
- apresentar `E`, `P`, restante teórico `E-P`, overlap teórico `O`, estimativa condicional de payload (`E-W` mais leituras extras conhecidas/estimadas), estimativa condicional de disco (`E-P`) e a indicação de que validação remota é obrigatória antes da retomada;
- rotular `ESTIMATE = PROVISIONAL` e nunca elevar isso a `VALIDATED_RUNTIME_BUDGET = PASS`;
- não marcar o item como `ALREADY_VALID`, `RESUME_VALIDATED` ou como autorização para append.

Não bloquear um candidato localmente elegível somente porque a prova remota ainda não ocorreu; isso recriaria F-01. A elegibilidade local tampouco prova integridade ou garante que o limite runtime será suficiente.

#### Etapa B — Execução após confirmação

Somente após a confirmação do usuário e aprovação dos limites preliminares aplicáveis, o fluxo existente deve:

1. Reavaliar o candidato, obter ownership exclusivo pelos mecanismos S4 existentes e revalidar filesystem e SQLite. Não reutilizar cegamente `P`, `E` ou estimativas do preview.
2. Inicializar o gateway compartilhado pelos mecanismos S5 aprovados, refazer a referência remota e conferir identidade canônica e tamanho.
3. Comprovar a integridade remota completa do prefixo segundo S6-OD-01 antes de append. Chamadas `getFileHashes` continuam sob rate limit/cancelamento/FloodWait. Qualquer payload `GetFile` usado para concluir uma faixa de verificação deve consumir o cap agregado e ter reserva runtime aprovada antes do request.
4. Se a prova passar, recalcular com filesystem e DB revalidados `P`, `W`, `O`, restante, payload de continuação, leituras extras previstas e espaço adicional. Revalidar orçamento agregado e disco; só então autorizar a continuação, mantendo reserva antes de cada `GetFile`.
5. Não considerar a classificação condicional como `ALREADY_VALID`, ownership, resultado da prova, orçamento validado ou permissão de append.

Se a prova falhar, a resposta for insuficiente, o estado divergir, ou orçamento/espaço/reserva não couberem, não fazer append, não truncar nem apagar `.part`, não declarar `DOWNLOADED`; preservar os arquivos e o estado recuperável ou registrar bloqueio explícito. A validação remota continua obrigatória e precede todo append, sem dependência circular no preview.

## 7. Falhas — S6-D09

| Classe | Exemplos | Ação proposta |
|---|---|---|
| Transitória | `NETWORK`, timeout, conexão interrompida | Preservar `.part`; `FAILED_RETRYABLE`; retry/resume somente dentro das três tentativas S5. |
| Rate limit | FloodWait | Honrar duração recebida, espera cancelável e teto cumulativo S5 de 120 s por mídia; sem retry após o orçamento. |
| Requer nova referência | file reference expirada/inválida | Próxima tentativa S5 refaz a mensagem; só continua se identidade completa e tamanho coincidirem. A tentativa conta no limite existente. Sem nova tentativa fora dele. |
| Terminal remoto | Mensagem removida, acesso perdido, mídia substituída ou tamanho diferente | Preservar `.part`, registrar categoria e não anexar/repetir cegamente. Requer nova seleção/estado remoto confirmado pelo usuário. |
| Terminal local/integridade | arquivo estrangeiro, hash remoto divergente, path divergente, final conflitante, `.part > E` | Preservar os arquivos, estado terminal (`FAILED`) e bloquear overwrite/append automático. |
| Espaço/limite | disco insuficiente, cap sem reserva completa, size desconhecido sob cap | Bloquear antes do próximo payload; preservar itens e arquivos já concluídos. |
| Persistência/estado | SQLite indisponível/corrompido, claim/checkpoint falha | Não abrir escritor concorrente; manter `.part`; não declarar conclusão. Reconciliar sem ignorar estado DB nem físico. |
| Configuração/autenticação/permissão | sessão inválida, configuração ausente, acesso negado | Sem retry automático de categoria terminal; não iniciar stream. A inicialização compartilhada S5 continua obrigatória. |

Uma tentativa futura iniciada pelo usuário continua sujeita ao preflight S5 e refetch antes do payload. Não ampliar silenciosamente retries, FloodWait, limites S5 ou fallback que descarte `.part`.

## 8. Impacto de schema e escopo

**Schema:** nenhuma migration faz parte deste contrato. Reutilizar `downloaded_bytes` como checkpoint não autoritativo, `expected_bytes`, caminhos, `attempts`, `sha256`, `failure_category`, `state` e `owner_pid`. `getFileHashes` pode ser consultado novamente a cada retomada; não precisa persistir hash remoto no banco.

**Pontos de implementação futuros:** `downloads.py`, `telegram_gateway.py`, `telethon_gateway.py`, `download_repository.py` e integração mínima em `s5_downloads.py`. `cli.py` deve continuar usando o mesmo executor, fila e inicialização compartilhada.

Se durante a implementação surgir necessidade de coluna/migration ou mudança maior:

```text
NECESSITY = demonstrar qual informação não pode ser derivada/reconciliada dos campos existentes
ALTERNATIVES = checkpoint físico/SQLite existente, leitura read-only, estado transitório
RISK = compatibilidade de banco e recuperação após atualização
MINIMUM_CHANGE = menor alteração aditiva possível, fora desta autorização e após revisão do contrato
```

Proibido dentro do escopo deste contrato: downloader paralelo, motor de recuperação genérico, sync S7, recursos S8, GUI, novo setting ou alteração dos contracts aprovados S4/S5.

## 9. Matriz de aceite — 18 critérios

`ACCEPTANCE_CRITERIA_COUNT = 18`. Os dez cenários adicionais definidos nesta remediação complementam os critérios existentes; a matriz continua com 18 critérios observáveis, cada um com condição explícita de PASS.

| CRITERION | EXPECTED_BEHAVIOR | TEST_LAYER | EVIDENCE_REQUIRED | PASS_CONDITION |
|---|---|---|---|---|
| Resume após interrupção | Preview offline reconhece `.part` localmente elegível como condicional; após confirmação, execução reivindica e revalida sem exigir prova remota no preview. | `OFFLINE_UNIT` + `OFFLINE_INTEGRATION` | Preview, mesmo `plan_id`, filesystem/SQLite antes/depois, confirmação e chamadas do fake gateway. | Preview permanece read-only/provisório; não há bloqueio circular; só continua após identidade e cobertura remota integral comprovadas. |
| Identidade remota | Mensagem, peer e identidade remota coincidem com a identidade canônica SQLite: canal, message ID, ordinal, tipo, Telegram media ID e tamanho. | `OFFLINE_UNIT` + `REAL_TELEGRAM_TECHNICAL_PROOF` | Casos de mismatch; valores SQLite/remotos e transcript sanitizado do refetch real. | Qualquer mismatch bloqueia antes do payload; não altera `.part` nem marca `DOWNLOADED`. |
| Matriz física do `.part` | Inexistente, vazio, parcial, completo, maior, estrangeiro e path divergente seguem §4; inclui `D < P` e `D > P` e a classificação local condicional. | `OFFLINE_UNIT` + `OFFLINE_INTEGRATION` | Matriz de estados, `D`, `P`, hashes, ownership e paths antes/depois do preview/execução. | Apenas candidato localmente seguro pode ser condicional; divergências/arquivo estrangeiro/path inseguro permanecem `BLOCKED`; preview não reivindica ownership nem usa prefixo não comprovado. |
| Integridade do prefixo | Todos os bytes antigos, inclusive corrupção fora do overlap final, são comprovados por hashes remotos; faixas incompletas, inválidas ou indisponíveis falham fechado. | `OFFLINE_INTEGRATION` + `REAL_TELEGRAM_TECHNICAL_PROOF` | Bytes/hash antes e depois; offsets, limites e hashes retornados; gaps; disponibilidade observada para a mídia. | Cobertura remota de `[0,P)` sem lacunas e hashes correspondentes; corrupção antiga, API indisponível, gap ou resposta inválida não permite append, truncamento ou exclusão e preserva `.part` com bloqueio explícito. |
| Offset físico alinhado | `P=W`, overlap zero; comprovar requests/offsets próximos à fronteira de 1 MiB. | `OFFLINE_INTEGRATION` + `REAL_TELEGRAM_TECHNICAL_PROOF` | Captura dos offsets, limites/respostas, incluindo fronteira 1 MiB, e bytes gravados. | Sem lacuna, duplicação ou request fora das regras confirmadas. |
| Offset físico não alinhado | `W=floor(P/256KiB)*256KiB`; overlap `<256KiB` comparado integralmente com bytes remotos antes de escrever. | `OFFLINE_INTEGRATION` + `REAL_TELEGRAM_TECHNICAL_PROOF` | `P`, `W`, `O`, bytes remotos e locais comparados, destino antes/depois. | Nenhum append antes da igualdade de todo overlap; append inicia exatamente em `P`; overlap é debitado, não regravado. |
| Offset aceito pelo adapter | O adapter rejeita offset wire inválido e não declara suporte arbitrário sem prova. | `OFFLINE_UNIT` + `REAL_TELEGRAM_TECHNICAL_PROOF` | Argumentos e requests reais Telethon 1.45.x. | `W` e limites passam; sem `OFFSET_INVALID` ou fallback escondido. |
| Arquivo final idêntico à referência | Resultado retomado corresponde byte a byte a download de referência do mesmo documento. | `REAL_TELEGRAM_TECHNICAL_PROOF` | Dois arquivos, tamanhos, comparação binária e SHA-256. | Bytes e SHA-256 coincidem integralmente. |
| SHA-256 e tamanho | SHA local cobre arquivo completo; tamanho é exatamente `E`. | `OFFLINE_INTEGRATION` + `REAL_TELEGRAM_TECHNICAL_PROOF` | Hash independente do final e valor persistido. | Hashes coincidem e tamanho físico/DB é `E`. |
| Persistência após restart | Claim/checkpoint e arquivo sobrevivem à saída/reabertura; avaliar PID reutilizado e ownership potencialmente ambíguo. | `OFFLINE_INTEGRATION` + `REAL_TELEGRAM_TECHNICAL_PROOF` | Antes/depois SQLite, PID/ownership disponível, estados e filesystem após restart. | Reabertura recupera estado consistente; PID ambíguo bloqueia sem segundo writer; contador isolado nunca comprova sucesso. |
| Janelas de crash | Falhas injetadas antes/depois de fsync, antes do checkpoint SQLite, em VALIDATED/rename e após finalização física antes de persistir DOWNLOADED. | `OFFLINE_INTEGRATION` | Matriz de fault injection e inspeção independente do estado SQLite/filesystem em cada janela. | Após `fsync` antes do checkpoint, `P` é revalidado; após finalização física, só arquivo final comprovado permite reconciliação; inconsistência bloqueia e nenhum estado falso `DOWNLOADED` aparece. |
| Deduplicação posterior | Segunda execução de item final válido não faz stream. | `OFFLINE_INTEGRATION` + `REAL_TELEGRAM_TECHNICAL_PROOF` | Estado inicial/final, bytes de payload e contador de stream. | `ALREADY_DOWNLOADED/ALREADY_VALID`, zero payload novo, arquivos/hashes inalterados. |
| Concorrência sem corrupção | Dois workers não escrevem a mesma identidade ao mesmo tempo; gateway restaura uma vez. | `OFFLINE_UNIT` + `OFFLINE_INTEGRATION` | Linha do tempo de ownership, restore e stream. | Um writer por mídia; até dois workers distintos; nenhum `SESSION_INVALID` por inicialização. |
| Orçamento S5 | Distingue estimativa provisória do preview e orçamento runtime validado; inclui overlap, leituras GetFile de integridade, falhas/retries e retransmissões. | `OFFLINE_UNIT` + `OFFLINE_INTEGRATION` | Preview com `ESTIMATE = PROVISIONAL`; limites confirmados; reservas/respostas/saldo por worker, tentativa e tipo; recálculo após prova. | Estimativa nunca vira PASS runtime; todo `GetFile`, inclusive validação, tem reserva prévia; orçamento agregado e disco são revalidados após prova e nunca excedidos. |
| Disco e margem | Necessidade adicional usa `E-P`; margem mantém fórmula S5 e `.part` já consome espaço. | `OFFLINE_UNIT` + `OFFLINE_INTEGRATION` | Valores de free-space, `.part`, bytes restantes e margem. | Falha de espaço acontece antes de write/request; nenhum arquivo é removido. |
| Sem falso `DOWNLOADED` | Falha na prova remota, limite ou reserva preserva `.part`; estado só persiste depois de final validado por tamanho/hash e rename. | `OFFLINE_INTEGRATION` | Fault injection, estado/hash do `.part` antes/depois, bloqueio e leitura independente SQLite/filesystem. | Falha não apaga/trunca/anexa nem declara `DOWNLOADED`; item só finaliza após prova e arquivo final comprovados. |
| Regressão S4/S5 | Download inicial, rename recovery, dedup, fila, limites, retries, FloodWait, workers e `plan_id` determinístico permanecem válidos; sem segunda fila. | `OFFLINE_INTEGRATION` | Preview repetido determinístico, mesmos IDs, evidências da fila única e checagens existentes fornecidas pelo executor autorizado. | S4/S5 continuam PASS; preview segue read-only/determinístico e S6 usa o fluxo existente sem alterar os contratos congelados. |
| Memória limitada | Streaming e verificação usam memória limitada, sem carregar arquivo inteiro. | `OFFLINE_INTEGRATION` + `REAL_TELEGRAM_TECHNICAL_PROOF` | Medição de pico em arquivo grande e buffers limitados. | Memória é limitada ao desenho por chunks/hash ranges, sem crescimento proporcional ao arquivo. |

As camadas são independentes: `OFFLINE_UNIT` e `OFFLINE_INTEGRATION` não autenticam nem acessam Telegram; `REAL_TELEGRAM_TECHNICAL_PROOF` é um gate separado e obrigatório para aceitar resume. Nenhuma camada offline comprova disponibilidade/cobertura de `upload.getFileHashes` em mídias suportadas. Essa confirmação permanece futura; não foi executada nesta atividade.

## 10. Plano futuro da prova técnica real

Este plano não é autorização para executar a prova agora.

1. Obter uma mídia DOCUMENT legítima, estável e suficientemente grande; recomendação inicial: pelo menos 1 GiB. Definir previamente um arquivo de referência byte-idêntico ao mesmo `channel_id/message_id/media_id`, com SHA-256 registrado.
2. Usar root e SQLite de prova isolados e `max_media_items=1`, `workers=1`. Definir limites S5 explícitos por invocação e um teto agregado autorizado que inclua referência, bytes da interrupção, restante, overlap e eventuais retries. Não usar o SQLite ou diretório original.
3. Iniciar uma execução real, interromper deliberadamente após um offset alinhado, confirmar `.part` físico persistido e processo encerrado; não inferir persistência apenas da barra de progresso.
4. Abrir novo processo, refazer a mensagem, validar identidade e hashes do prefixo, continuar no offset alinhado, finalizar e verificar DB/filesystem.
5. Repetir em execução isolada com `P` não alinhado a 256 KiB (por exemplo, prefixo válido seguido de um pequeno sufixo de bytes da referência). O adaptador deve normalizar `W`, comparar `O` e não duplicar bytes. Registrar claramente a preparação do caso, sem chamá-la de interrupção espontânea.
6. Comparar o final de cada execução byte a byte com a referência, verificar SHA-256/tamanho/SQLite, executar uma segunda fila e comprovar zero payload novo.
7. Reconciliar todos os limites S5: workers, tentativas, espera FloodWait, contagem de mídia, bytes agregados e espaço livre. Registrar chamadas não observáveis como não observáveis.

O aceite real exige uma prova de arquivo grande com processo reiniciado e refetch, cobrindo offset alinhado e não alinhado. Se o orçamento aprovado não comportar o arquivo e a referência, o gate não passa; não reduzir o critério silenciosamente.

## 11. Decisões aprovadas pelo usuário

### S6-OD-01 — Prova de integridade do prefixo

**Decisão:** `S6-OD-01 = APPROVED / ALTERNATIVE_A`.

Exigir prova SHA-256 por faixa remota para o prefixo completo `[0,P)` e verificar remotamente a continuação antes da validação final. Se mecanismo, identidade, offset, limit, hash ou cobertura integral não puderem ser comprovados para mídia suportada, preservar o `.part`, registrar bloqueio explícito e não retomar. Hash local isolado não é fallback. A existência/documentação do método não constitui prova técnica de disponibilidade ou cobertura nesta atividade.

### S6-OD-02 — Limite de durabilidade

**Decisão:** `S6-OD-02 = APPROVED / ALTERNATIVE_A`.

Exigir recuperação consistente após interrupção do processo, falha de conexão, encerramento/reinício normal e falhas entre operações filesystem e transações SQLite. Manter `write → flush/fsync → checkpoint DB`, validação do final, finalização atômica no-overwrite e reconciliação filesystem/SQLite. Em queda súbita de energia, revalidar estado físico e SQLite, recuperar só quando seguro e bloquear/preservar em caso de ambiguidade. Não prometer persistência absoluta em hardware/cache e não exigir teste destrutivo de perda de energia no gate obrigatório S6.

## 12. Fechamento e autorização

```text
ACTIVITY = S6-CONTRACT-FORMAL-CLOSURE-01
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = COMPLETED / PASS
USER_CONTRACT_APPROVAL = GRANTED / FORMAL ACCEPTANCE
S6_CONTRACT_STATUS = APPROVED / FROZEN
CONTRACT_FREEZE = APPROVED / FROZEN
C-01 = INCORPORATED
C-02 = INCORPORATED
C-03 = INCORPORATED
F-01 = RESOLVED
F01_STATUS = RESOLVED
S6_CONTRACT_REMEDIATION = PASS / C-01, C-02, C-03 INCORPORATED; F-01 RESOLVED
S6_CONTRACT_READINESS = FORMAL APPROVAL GRANTED
CONTRACT_APPROVAL = APPROVED / USER
S6_IMPLEMENTATION_READINESS = NOT_ASSESSED
S6_IMPLEMENTATION_AUTHORIZATION = NO
S6_STATUS = PLANNED / NOT_STARTED
S6-OD-01 = APPROVED / ALTERNATIVE_A
S6-OD-02 = APPROVED / ALTERNATIVE_A
ACCEPTANCE_CRITERIA_COUNT = 18
SP03_REAL_RESUME_PROOF = NOT_TESTED
REAL_TELEGRAM_TECHNICAL_PROOF = NOT_PERFORMED
UPLOAD_GETFILEHASHES_AVAILABILITY_AND_COVERAGE = NOT_VALIDATED / FUTURE TECHNICAL GATE
SOURCE_CODE_CHANGES = NONE
TEST_EXECUTIONS = 0
TELEGRAM_OPERATIONS = 0
SQLITE_MODIFICATIONS = NONE
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
PREVIEW_OFFLINE = PASS
CONDITIONAL_RESUME_FLOW = PASS / CANDIDATE CLASSIFICATION IS TRANSITORY; REMOTE GATE STILL REQUIRED
REMOTE_VALIDATION_GATE = REQUIRED BEFORE APPEND / FAIL-CLOSED
BUDGET_REVALIDATION = PASS / PROVISIONAL PREVIEW SEPARATED FROM RUNTIME RESERVATIONS
NEXT_ACTION = AWAIT_SEPARATE_S6_IMPLEMENTATION_AUTHORIZATION
```

O aceite formal do usuário aprova e congela este contrato para o escopo S6.
O preview S5 permanece offline; candidato condicional pode chegar à validação
remota somente após confirmação, e a validação remota precede qualquer append.
Todo `GetFile`, inclusive payload usado para validação, exige reserva de
orçamento antes da chamada. Os limites S5 permanecem preservados. A matriz
contém 18 critérios de aceite. A prova técnica real continua futura e não foi
executada. S6 permanece PLANNED / NOT_STARTED; implementação não está
autorizada.
