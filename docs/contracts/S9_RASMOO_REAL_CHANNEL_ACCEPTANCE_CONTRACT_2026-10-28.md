# S9 — RASMOO Real-Channel Acceptance Contract

~~~text
ACTIVITY_ID = TELEGRAM_S9_CONTRACT_CLOSURE_2026-10-28
DOCUMENT_ROLE = ACCEPTANCE_EXECUTION_CONTRACT
CONTRACT_VERSION = 1.0
CONTRACT_STATUS = APPROVED / FROZEN
CONTRACT_APPROVAL = USER_EXPLICIT_2026-10-28 / RAT-01..RAT-05_APPROVED
TECHNICAL_DECISIONS = APPROVED_BASELINE
S9_IMPLEMENTATION = NOT_STARTED
S9_REAL_OPERATIONS = NOT_EXECUTED
S9_EXECUTION_AUTHORIZATION = NOT_GRANTED
S10_AUTHORIZATION = NOT_GRANTED
~~~

Este documento registra a baseline técnica ratificada para a futura homologação S9. Os limites S9-L01..L16 foram ratificados pelo usuário em 2026-10-28 (RAT-01..RAT-05). Aprovar o contrato não autoriza operações reais no Telegram.

## 1. Identificação e autoridade

A S9 corresponde à validação real prevista no [ROADMAP](../continuity/planning/ROADMAP.md), antes da distribuição S10. As authorities são [REQUIREMENTS](../product/REQUIREMENTS.md), [ARCHITECTURE](../architecture/ARCHITECTURE.md), [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), contratos S1–S8 e decisões humanas em [APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md).

O usuário ratificou o contrato e seus limites em 2026-10-28. Aceite da S9 e autorização real permanecem decisões futuras. O Architect é dono da decisão técnica proposta; o Scribe apenas a registra. Este contrato está aprovado e congelado na versão 1.0 desde 2026-10-28.

Estado factual inicial: branch **work/s0-bootstrap**, HEAD **d36e96055a26556221bc487717f18ed322c76f02**, upstream **origin/work/s0-bootstrap**, worktree dirty com WIP preexistente e sem paths staged. PROJECT_STATE já registra o HEAD factual **d36e96055a26556221bc487717f18ed322c76f02**. A referência histórica divergente foi reconciliada antes do congelamento.

## 2. Objetivo e escopo

Demonstrar em amostra autorizada e limitada o fluxo integrado:

~~~text
CLI Windows → conta própria → canal autorizado → scan/catalogação
→ parser → seleção/plano → fila limitada → arquivo + SQLite
→ segunda execução/dedupe → sync observado → falha/recovery segura
→ evidências e decisão humana
~~~

O aceite é limitado ao conjunto ratificado; não prova compatibilidade universal.

- **Perfil F — funcional controlado:** catálogo representativo, seleção limitada, downloads pequenos, dedupe, sync observado e, quando seguro, uma interrupção controlada.
- **Perfil M — memória real:** transferência inicial de uma mídia grande elegível sob medição do processo, para NFR-02. Não inclui resume do arquivo, V2 nem matriz histórica S6.

Perfis e valores RAT-01..RAT-04 foram ratificados em 2026-10-28.

Fora de escopo: download em massa; alteração no canal; mensagens de teste; busca fora do envelope; novos parsers/famílias de canal; deleção remota; alteração de proteção; V2; Harness S6; provas completas S6; mudança de código/schema; migration no banco original; S10; publicação Git.

## 3. Dependências e pré-requisitos

| Sprint | Base reutilizada | Prova futura e limite |
|---|---|---|
| S1 | Autenticação própria, descoberta e sessão DPAPI CURRENT_USER. | Confirmar lifecycle e seleção legítima; novo login requer autorização específica. |
| S2 | Scanner, identidade, SQLite, transações e runs. | Scan limitado, persistência e reabertura só em cópia isolada. S2 não tem cap numérico aprovado. |
| S3 | RasmooParser, GenericParser e catálogo. | Conferir com amostra observada; gramática só vale para formas comprovadas. |
| S4 | DOCUMENT ligado a Lesson, organização, hash local e finalização sem overwrite. | Transferência inicial e validação em roots isolados. |
| S5 | Planner/fila, seleção, budgets, workers, reservas e dedupe. | Plano igual ao manifesto/caps; segunda fila comprova dedupe. |
| S6 | V1 ativa, REMOTE_HASH_REQUIRED, fail-closed, fsync/checkpoint, no-overwrite. | Um caso pode bloquear com segurança; lacunas históricas preservadas. |
| S7 | High-water confirmado distinto de cursor; checkpoint durável. | G7 exige baseline COMPLETE verificável; mudanças só são avaliadas quando observadas. |
| S8 | Configuração, logs, retry, FloodWait, disco, streaming e workers limitados. | Validação no escopo autorizado; NFR-02 ainda sem limiar aprovado ou medição real. |

A regressão S8 histórica foi 366 testes + 11 subtestes PASS, zero falhas. O cenário sintético de 16 MiB registrou pico tracemalloc de 942.996 bytes com payload pré-alocado. Isso não mede RSS total, transferência real ou NFR-02 para mídia grande.

Antes de RPC, autorização futura define canal/escopo, sessão própria, cópia DB, roots isolados, limites ratificados, supervisor validado, evidências, responsáveis e cancelamento.

## 4. Dataset

Selecionar explicitamente a amostra permitida do catálogo RASMOO. O manifesto fica privado, fora do Git; relatório compartilhado usa aliases/contagens, sem IDs, access hashes, payloads ou hashes sensíveis.

A amostra obrigatória S9 deve conter um Track observado, dois Courses e pelo menos dois Modules, conforme ENGINEERING_FOUNDATION.md, seção RASMOO acceptance dataset. A opcionalidade de Track? no modelo genérico não dispensa esse requisito da amostra RASMOO. Se um Track não puder ser demonstrado dentro do escopo e dos limites autorizados, a representatividade fica BLOCKED_DATASET; não ampliar a coleta automaticamente. Qualquer dispensa exige decisão explícita do usuário que revise o escopo de aceite.

Além disso, verificar no envelope autorizado múltiplas referências #Fxxx com Lessons/mídias, um #Docxxx se existir, mensagem sem mídia, mídia não referenciada no índice e nome problemático. Não presumir que esses casos condicionais estejam presentes.

Registrar relação entre mensagem, identidade (channel_id, telegram_message_id, media_ordinal), nó de catálogo, seleção e arquivo esperado. Identificadores ficam no manifesto privado. Registrar itens existentes e, somente se naturalmente observados, novos/editados. Não provocar edição, remoção ou mensagem.

Elegibilidade S4: identidade e tamanho conhecidos, tipo suportado, associação ativa e não ambígua a Lesson e lineage válida. PHOTO, mídia especial, tamanho desconhecido, documento geral sem Lesson ou associação ambígua são excluídos com motivo. #Docxxx é geral sem vínculo explícito; ausência pode ser NOT_APPLICABLE.

Não presumir casos. Sem estrutura central representativa: BLOCKED_DATASET/PARTIAL. Sem item novo/editado: NOT_TESTED. Não truncar Course/Module para pegar as primeiras N mídias; selecionar outro escopo elegível ou bloquear.

## 5. Matriz FR-01..FR-16

Resultados reais começam NOT_TESTED.

| ID | Gates | Critério verificável |
|---|---|---|
| FR-01 | G0/G1 | Sessão própria restaurada com proteção aprovada; falha explícita sem bypass; lifecycle sem segredo. |
| FR-02 | G1 | Canal autorizado descoberto e selecionado inequivocamente; parcial não significa vazio/completo. |
| FR-03 | G2 | Identidades, associações e unicidade persistidas; contagens reconciliadas com SQLite. |
| FR-04 | G3 | O modelo genérico mantém Track? opcional; para o dataset S9, exigir um Track observado, dois Courses e pelo menos dois Modules conforme ENGINEERING_FOUNDATION.md. Unresolved explícitos. |
| FR-05 | G3/G9 | RasmooParser e fronteiras plugáveis; GenericParser coberto offline, sem exigir outro canal real. |
| FR-06 | G4/G5 | Plano contém escopo aprovado, sem irmãos e sem truncamento silencioso. |
| FR-07 | G5/G6 | Arquivos sob root isolado, nomes seguros/determinísticos, sem overwrite. |
| FR-08 | G4/G5 | Tipos elegíveis presentes transferidos; excluídos justificados; sem suporte universal presumido. |
| FR-09 | G2/G6/G8 | Estado persiste após reabertura; SQLite/FK e DB↔filesystem conferidos. |
| FR-10 | G7 | Sync idempotente na janela; high-water/cursor corretos; mudança só PASS se observada. |
| FR-11 | G6 | Segunda fila encontra válidas, sem payload novo; arquivos/estado inalterados. |
| FR-12 | G8 | Cancelamento/reinício preservam dados; append somente após V1. Bloqueio não prova resume em bytes. |
| FR-13 | G3/G4 | Preview mostra escopo, pendentes, válidas, exclusões, tamanhos/caps e catálogo parcial antes da confirmação. |
| FR-14 | G5/G8 | Progresso distingue COMPLETED/PARTIAL/FAILED/CANCELLED/SKIPPED; sem sucesso antes da validação física. |
| FR-15 | G0–G9 | Logs permitem diagnóstico sanitizado, sem credenciais, sessão, payload ou IDs privados. |
| FR-16 | G0/G4/G9 | CLI/configuração e precedência registradas; entradas inválidas falham controladamente; valores respeitam caps ratificados. |

FR-10 pode ser parcial sem mudança observável. FR-12 não promove lacunas S6, mesmo se o escopo S9 passar.

### Matriz NFR-01..NFR-10

| ID | Gates | Critério verificável |
|---|---|---|
| NFR-01 | G0–G9 | Registrar Windows/versões efetivas, CLI, Unicode, paths e códigos observados. Empacotamento é S10. |
| NFR-02 | G0/G5-M/G9 | Medir processo no perfil M contra limiares ratificados. Resultado sintético S8 não os substitui. |
| NFR-03 | G0/G4/G5 | Um worker proposto, dentro de 1..2 aprovados; concorrência observada e limitada. |
| NFR-04 | G0/G5/G8 | Não induzir FloodWait; ocorrência natural é respeitada e encerra o run. Fixtures S8 cobrem tradução/budget offline. |
| NFR-05 | G0/G9 | Config, manifesto exportável e logs sem credenciais; sem evidência sensível candidata ao Git. |
| NFR-06 | G0/G1 | Sessão DPAPI CURRENT_USER fora do repo/logs; verificar lifecycle sem exportar ou ler conteúdo. |
| NFR-07 | G5/G6 | Path e nome problemático, se existir, respeitam limites S4; fixtures cobrem outras classes. |
| NFR-08 | G0/G9 | Fronteiras gateway/parser/application/repository preservadas; sem mudança de código e com regressão offline. |
| NFR-09 | G9 | Regressão normal offline, sem sessão/rede, com inventário e recibo próprio. |
| NFR-10 | G0/G9 | Integração real separada, autorizada e com run/roots próprios; não entra na suíte normal. |

NFR-02 só poderá receber PASS dentro do limiar ratificado e com recibo do processo. Sem mídia M ou medição, fica NOT_TESTED/PARTIAL conforme os critérios da seção 13.

## 6. Arquitetura do fluxo

Usar CLI Windows, gateway Telegram, scanner/SQLite, RasmooParser, catálogo, planner/fila S5 e caminho S4. Não criar CLI, fila ou writer alternativos.

Descoberta precede scan. Scan persiste somente na cópia SQLite isolada. Catálogo é comparado ao manifesto. Preview/plano é revisto antes de confirmação humana. Fila repassa elegíveis ao S4, autoridade de identidade, streaming, caminhos, integridade, estado e finalização. Sync/recovery preservam os mesmos invariantes.

A supervisão futura fica fora da aplicação e controla processo, tempo, memória, cancelamento e recibos. Não foi criada/validada; sua ausência bloqueia G0 antes de RPC. Esta atividade não a implementa.

## 7. Gates G0..G9

Execução futura sequencial; nenhum gate real foi executado nesta atividade.

| Gate | Procedimento | PASS futuro | Bloqueio/falha |
|---|---|---|---|
| G0 — preflight/segurança | Autoridade, baseline, cópia/roots, sessão, manifesto, caps, disco, supervisor e recibo antes de RPC. | Controles demonstrados. | Pré-requisito ausente: BLOCKED, sem RPC. |
| G1 — autenticação/descoberta | Sessão autorizada; descoberta dentro dos caps. | Acesso legítimo, canal correto, cleanup seguro. | Sessão/acesso inválidos, canal ausente ou cleanup inseguro: parar. |
| G2 — scanner/persistência | Scan limitado na cópia; conferir identidade, contagem, status/reabertura. | Amostra limitada consistente. PARTIAL/MESSAGE_LIMIT pode ser esperado; não prova completude. | Corrupção, identidade errada ou escrita fora do root: FAIL. |
| G3 — parser/catálogo | Construir RASMOO e comparar ao manifesto. | Estrutura/associações corretas; amostra representativa com Track observado, dois Courses e pelo menos dois Modules; unresolved explícitos. | Sem Track demonstrável no escopo autorizado: BLOCKED_DATASET, sem ampliar coleta. Não corrigir formato não suportado durante homologação. |
| G4 — seleção/plano | Comparar plano fresco, manifesto e caps; confirmação humana. | Escopo exato/determinístico e LIMIT_CHECK_RESULT=PASS. | Cap, exclusão desconhecida ou deriva: bloquear. |
| G5 — download limitado | Perfil F e, se elegível/ratificado, M sob supervisor/um worker. | Só itens aprovados, íntegros e dentro do envelope. | Estouro, timeout, RSS/disco ou erro crítico: cancelar/preservar. |
| G6 — integridade/dedupe | Conferir arquivo, SQLite, hash/tamanho e segunda fila. | DB/arquivo consistentes, sem overwrite/payload novo na segunda fila. | Falso DOWNLOADED, overwrite ou alteração indevida: FAIL crítico. |
| G7 — sync | Baseline COMPLETE; até duas syncs no envelope. | Runs completos, checkpoint correto, idempotência. | Baseline ausente/histórico além do cap: BLOCKED/PARTIAL. |
| G8 — falhas/recovery | Uma interrupção segura e uma tentativa posterior, budgets preservados. | Recovery ou bloqueio V1 correto documentado. | Ambiguidade/claim vivo/mismatch: parar; bloqueio não prova continuação. |
| G9 — evidências/decisão | Reconciliar manifesto, caps, recibos, regressão offline, riscos e resultados. | Conclusões sustentadas, limites apresentados. | Lacuna material mantém gate/aceite parcial. |

G2 pode aprovar catalogação limitada se término PARTIAL/MESSAGE_LIMIT (inclusive exit 4) era esperado, amostra suficiente e persistência correta. Isso não significa scan completo. Em G4, exit 0 de download plan não basta: conferir LIMIT_CHECK_RESULT, manifesto e determinismo.

G4 compara o plano fresco e requer aprovação humana no prompt interativo do terminal TTY. A execução futura deve omitir --confirm: esse argumento pula o prompt. A aprovação do contrato S9 não confirma uma fila de download.

## 8. Limites operacionais

### 8.1 Herdados/aprovados

| Controle | Limite | Fonte |
|---|---|---|
| Workers | 1 ou 2; padrão 2. S9 propõe 1. | S5 |
| Tentativas | Máximo 3 por mídia, inicial incluída. | S5 |
| FloodWait | Até 120 s acumulados por mídia; não resetar em resume. | S5/S6 |
| Reserva GetFile | Até 256 KiB por request, reservados antes do envio. | S5 |
| Margem de disco | max(1 GiB, 10% dos bytes pendentes conhecidos). | S5/S8 |
| Finalização/path | Sem overwrite; componente ≤100; destino absoluto ≤240 caracteres. | S4 |
| Descoberta | Página 100; até 1.000 diálogos; 20 páginas; 120 s e cleanup 10 s. | S1-D |
| Scan S2 | Limites positivos por chamada; nenhum teto numérico aprovado. | S2 |

### 8.2 Limites S9 ratificados — APPROVED / FROZEN em 2026-10-28

Limites de homologação ratificados em RAT-02 e RAT-03; não são benchmarks nem limites universais.

| ID | Limite ratificado | Fundamento/controle |
|---|---|---|
| S9-L01 | Até 200 mensagens/scan; 3 invocações; até 600 observações acumuladas, repetidas incluídas. | Um scan e até duas syncs; ledger limita invocações. |
| S9-L02 | Janela incremental 50 unidades de ID. | Não significa 50 mensagens existentes. |
| S9-L03 | Perfil F: até 8 mídias distintas, cada uma ≤128 MiB. | Conferir manifesto; sem flag CLI por tamanho de item. |
| S9-L04 | Perfil F: 536.870.912 bytes agregados, incluindo retries, overlap e payload de validação. | 512 MiB; caps pré-alocados no ledger. |
| S9-L05 | Perfil M: uma mídia DOCUMENT fresca, 1 GiB ≤ E ≤ 2 GiB, um worker, uma tentativa. | Mídia não presumida; critério grande para NFR-02. |
| S9-L06 | Cap M = ceil(E/262144) × 262144 + 262144; máximo 2.147.745.792 bytes. | Uma transferência inicial, reserva conservadora request/EOF. |
| S9-L07 | Cap F+M máximo 2.684.616.704 bytes. | 2,5 GiB +256 KiB; sem reciclar saldo incerto. |
| S9-L08 | Um worker em S9; attempts-per-media 1 em filas reais. | Mais restrito que S5; G8 debita no mesmo ledger. |
| S9-L09 | Uma interrupção F e uma tentativa recovery; até 3 tentativas por identidade no ledger. | Preserva teto S5. |
| S9-L10 | Timeout: scan 120 s; catálogo/inspeção 60 s; fila F 600 s; fila M 1.800 s; verificação local 300 s. | Novos salvo scan; supervisor cobre flags ausentes. |
| S9-L11 | Deadline global 3.600 s de G1 ao fim G9. | Expiração cancela e classifica parcial. |
| S9-L12 | Cancelamento cooperativo observado em 15 s; contenção da árvore/PID comprovada em 30 s. | Sem controle confiável, G0 bloqueia. |
| S9-L13 | Working Set ≤512 MiB e crescimento ≤128 MiB sobre baseline; coleta 250 ms. | Limiar NFR-02 novo; registrar Peak Working Set e Private Bytes. |
| S9-L14 | Baseline pela mediana de 2 s no prompt antes da confirmação, incluindo o processo CLI completo. | Método novo; validar em ensaio offline. |
| S9-L15 | Reserva adicional de 256 MiB para DB/WAL/evidências. | Além da margem S5; exceder bloqueia próxima operação. |
| S9-L16 | Primeiro FloodWait natural encerra homologação. | Não induzir rate limit nem repetir operação real para retry. |

Sem mídia M: G5-M=BLOCKED_DATASET, NFR-02=NOT_TESTED_REAL e, havendo F, agregado PARTIAL. Não reduzir mínimo silenciosamente.

### 8.3 CLI real

O parser em src/telegram_courses/cli.py aceita, conforme comando, max-messages, timeout-seconds, incremental, reconcile-window, max-media-items, max-transfer-bytes, workers, attempts-per-media e integrity-mode. Timeout-seconds vale para scan, não download. Não existem flags de deadline global, timeout de fila, RSS, tamanho por arquivo, run ID ou resume-run ID.

Max-messages é validado antes de criar gateway e limita mensagens projetadas por invocação; não limita RPC total, refetch ou bytes. Ledger/supervisor externo controla invocações e caps agregados.

### 8.4 Formas de comando futuras

Os comandos abaixo refletem a CLI existente; não foram executados nesta atividade. Variáveis PowerShell devem ser preenchidas a partir do manifesto privado ratificado. São valores do shell, não flags novas.

~~~powershell
telegram-courses credentials status
telegram-courses auth
telegram-courses channels

telegram-courses scan --channel-id $ChannelId --database $IsolatedDb --max-messages 200 --timeout-seconds 120

telegram-courses catalog build --channel-id $ChannelId --database $IsolatedDb --parser-key rasmoo
telegram-courses catalog show --channel-id $ChannelId --database $IsolatedDb
telegram-courses catalog items --channel-id $ChannelId --database $IsolatedDb

telegram-courses download plan --channel-id $ChannelId --database $IsolatedDb --download-dir $IsolatedRoot --scope lesson --workers 1 --attempts-per-media 1 --max-media-items $InvocationMediaCap --max-transfer-bytes $InvocationByteCap --integrity-mode REMOTE_HASH_REQUIRED

telegram-courses download queue --channel-id $ChannelId --database $IsolatedDb --download-dir $IsolatedRoot --scope lesson --workers 1 --attempts-per-media 1 --max-media-items $InvocationMediaCap --max-transfer-bytes $InvocationByteCap --integrity-mode REMOTE_HASH_REQUIRED

telegram-courses scan --channel-id $ChannelId --database $IsolatedDb --max-messages 200 --timeout-seconds 120 --incremental --reconcile-window 50
~~~

Os valores 200 e 50 são limites S9 ratificados em 2026-10-28. Course/Module podem substituir Lesson somente se o plano inteiro couber no manifesto/caps. A CLI seleciona scope por menu contextual; não oferece node-id/course-id/lesson-id. --confirm existe apenas para queue e pula o prompt. A operação futura usa prompt humano em TTY, sem --confirm, depois de revisar o plano fresco; a ratificação do contrato não confirma a fila. catalog build/show/items e scan podem executar migrations no banco indicado, portanto usar somente cópia isolada. V2 pode aparecer no parser, mas a execução bloqueia V2_EFFECTIVE=NO; não usar OPERATIONAL_ONLY ou TRUSTED_REFERENCE.

## 9. Segurança de dados e sessões

- Usar a própria conta e canal acessível autorizado.
- Sessão DPAPI CURRENT_USER; nunca exportar StringSession, tokens, API/access hashes ou conteúdo de sessão.
- Credenciais fora do Git, argumentos, configuração, logs e relatório.
- DB, downloads, temporários e evidências fora do repositório e dos originais. Conferir paths, volume e ausência de reparse/symlink.
- Cópia consistente por SQLite Online Backup; não copiar banco ativo ignorando WAL. Migrations/writes só na cópia autorizada.
- Preservar originais; sem exclusão física, cleanup destrutivo ou overwrite.
- Logs brutos/títulos/paths/IDs privados restritos; exportar logs sanitizados, aliases, contagens e igualdade de integridade.
- Não publicar IDs privados, hashes sensíveis, payloads ou conteúdo de mensagens.
- Nenhuma escrita no canal; operação futura limita-se a leitura/download autorizado.

G0 registra integridade/FK da cópia antes/depois e prova de originais inalterados. Sem prova de isolamento/backup, não fazer RPC.

## 10. Integridade, dedupe e recovery

G6 confere identidade; tamanho físico/esperado/SQLite; SHA-256 local independente contra persistido (publicar apenas igualdade); estado terminal; .part; path sob root; ausência de overwrite. Hash local não é digest autenticado pelo Telegram.

Segunda fila usa itens válidos, max-media-items exato e max-transfer-bytes 1, menor valor positivo. Esperado SKIPPED/already-valid, zero payload novo e arquivos/estado inalterados. Cap pode bloquear GetFile, mas não prova ausência de toda RPC se contagem não for observada.

G8 propõe mídia F sem final preexistente e grande o bastante para observar progresso físico. Cancelar uma vez, confirmar saída e conferir .part, P físico, D SQLite e ownership. Novo processo replaneja. Preview não autoriza append.

Sob S6 V1, verificar identidade e prefixo remoto antes do writer. Falta de cobertura/hash, divergência, orçamento ou disco insuficiente preservam .part e bloqueiam. Isso pode provar fail-closed, mas CONTINUATION_COMPLETION=BLOCKED e FR-12 seguem parciais. Não fabricar interrupção/corrupção nem apagar .part.

## 11. Sincronização incremental

O código usa scan_runs status=COMPLETE para baseline. Sem baseline, piso inicia em 1. FULL scan PARTIAL/MESSAGE_LIMIT não cria high-water confirmado.

G7 requer baseline COMPLETE verificável na cópia ou esgotamento natural do histórico dentro do cap. Se exceder, G7 BLOCKED/PARTIAL. Proibidos seed artificial, promoção manual, alteração do piso e ampliação de scan.

Registrar por run high-water anterior, snapshot head, piso/janela, cursor durável, estado e high-water posterior. Runs parciais/interrompidos não promovem high-water. Sem mensagem nova/editada observada, NOT_TESTED. Ausência remota não cria tombstone, remoção ou deleção física; não presumir prova positiva.

## 12. Testes e evidências

A execução futura recebe ID opaco antes de G0, sem IDs privados. Pacote privado fora do Git contém:

- versões, branch/commit e inventário de fonte;
- manifesto e vínculo alias↔identidade;
- recibos G0/supervisor, processo, timeout, memória, cancelamento e término;
- comandos/parâmetros sanitizados e confirmação humana;
- scans/runs, estados, contagens e checkpoints;
- planos, seleção, caps, ledger e bytes observados/incertos/alocados;
- tempos, disco, Working Set/Peak Working Set/Private Bytes;
- SQLite/FS antes/depois, integridade, hash/tamanho e dedupe;
- interrupção/recovery, retries e budgets consumidos;
- logs brutos restritos e exportação sanitizada;
- resultados por gate/FR/NFR, limites, responsável e prova de nenhum dano;
- regressão offline separada, inventariada, com exit externo durável.

Suíte normal segue offline, sem sessão/rede; não substitui integração real. Não repetir Harness S6. Falha nova exige triage, sem rerun automático. Nenhuma evidência operacional foi produzida nesta atividade.

## 13. Critérios de aceite

- **PASS:** critérios aplicáveis ao escopo ratificado executados e satisfeitos com evidência suficiente.
- **PARTIAL:** parte provada e parte obrigatória sem evidência; listar o que falta.
- **FAIL:** violação, inconsistência, corrupção, overwrite, estado falso ou cap excedido.
- **BLOCKED:** pré-requisito ausente impediu execução segura/conclusiva; registrar causa/ação.
- **NOT_TESTED:** cenário não executado ou mudança não observada. Ausência não prova comportamento.
- **NOT_APPLICABLE:** condição explicitamente opcional/fora do escopo ratificado, justificada; não esconder requisito central.

Agregado PASS só para critérios obrigatórios ratificados, sem FAIL/BLOCKED/NOT_TESTED obrigatório. F aprovado sem M ou G7 = PARTIAL. Falha G0 antes de operação = BLOCKED. Violação crítica = FAIL e interrupção.

Publicar resultado do escopo ratificado separado de FULL_FR_NFR_CONFORMANCE. PASS S9 não é conformidade universal nem encerra lacunas históricas.

## 14. Falhas, bloqueios e exceções herdadas

Interromper por identidade divergente; conteúdo inacessível/protegido; erro de sessão; FloodWait; cap/tempo/memória/disco; arquivo estrangeiro/reparse; ownership ambíguo; SQLite/checkpoint inconsistente; perda de supervisor; segredo exposto; plano divergente; escrita fora do root ou dano.

- **S6:** CLOSED_WITH_EXCEPTIONS; Gate A PARTIAL; Gate B BLOCKED_BY_REMOTE_EVIDENCE; V1 ativa/V2 global OFF. Lacunas de prefixo/EOF, alinhamento, crash/ownership, dedupe pós-resume, P/D, budgets, disco, memória e exit externo permanecem.
- **S7:** EX-01 cancelamento/crash; EX-02 prova positiva de exclusão; EX-03 falha global de catálogo; EX-04 rastreabilidade histórica 9 V2 + 9 CLI + 2 migration não reconciliada. A2/A4/A6 parciais.
- **S8:** memória sintética não equivale a RSS/limiar quantitativo; homologação real não executada.

Caso S9 prova somente o que observou. Não altera contratos/decisões S1–S8, recibos ou exceções aceitas.

## 15. Regras de cancelamento

1. Parar agendamento/RPC/payload; cancelar cooperativamente e confirmar término.
2. Preservar DB/WAL, .part, finais, logs/recibos; sem limpeza.
3. Reconciliar filesystem/SQLite offline.
4. Registrar gate seguro, tentativas e cap consumido.
5. Não reiniciar automaticamente; saldo comprovado e autoridade vigente são obrigatórios.
6. Defeito gera reprodução sanitizada; correção exige autorização separada.

Se contenção dura for necessária ou árvore não comprovada, recovery não está demonstrado. Reconciliar antes de novo writer.

## 16. Critérios de encerramento S9

Recomendar aceite humano após G9 reconciliar gates, critérios, manifesto, budgets, regressão, segurança e riscos. FAIL crítico impede recomendação. Escopo incompleto/não observável é PARTIAL/BLOCKED.

O contrato foi ratificado com os caps aprovados em 2026-10-28. Esta atividade não executa gates nem aceita S9 em nome do usuário.

## 17. Condições para entrada futura na S10

S10 pode ser recomendada com aceite humano S9 no escopo definido; bloqueios aplicáveis resolvidos ou aceitos; limitações FR-10/FR-12/NFR-02 e exceções herdadas documentadas; inputs Windows/configuração/paths/sessão conhecidos; e autorização S10 separada. Aceite S9 não inicia S10.

## 18. Autorizações e restrições

Autorizado: definição técnica e documentação do contrato/relatório.

Não autorizado: implementação S9/S10; login/Telegram/RPC; scan/download real; alteração canal; SQLite operacional; migration; mudança de código/teste/config; Git stage/commit/push; publicação; resolução retroativa de exceções S6/S7/S8.

~~~text
CONTRACT_APPROVAL = APPROVED / USER_2026-10-28
S9_IMPLEMENTATION = NOT_STARTED
S9_REAL_OPERATIONS = NOT_EXECUTED
S9_EXECUTION_AUTHORIZATION = NOT_GRANTED
S10_AUTHORIZATION = NOT_GRANTED
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
NEXT_EXACT_ACTION = SEPARATE_AUTHORIZATION_FOR_OFFLINE_SUPERVISOR_AND_LEDGER
~~~

## 19. Matriz de rastreabilidade

| Authority | Conteúdo |
|---|---|
| REQUIREMENTS | FR-01..FR-16 e NFR-01..NFR-10 |
| ARCHITECTURE | Gateway, parser, aplicação, persistência e CLI |
| ENGINEERING_FOUNDATION | Dataset RASMOO e invariantes |
| S1-D | Descoberta, sessão e caps aprovados |
| S2/S3 | Scanner, SQLite, parser e limites da gramática |
| S4/S5 | Download, seleção/planner/fila, retry, budgets e paths |
| S6 | Resume, V1, hash remoto, fail-closed, fsync/checkpoint/no-overwrite |
| S7/S8 | High-water, sem inferir deleção, hardening e limites NFR-02 |
| APPROVALS_AND_DECISIONS | Aceites/exceções S6/S7/S8 |
| Relatórios S6/S7/S8 | Evidência histórica e limites |

Matriz detalhada: seção 5; gates/decisão: seções 7, 8 e 13.

## 20. Checklist operacional futuro

1. Confirmar RAT-01..RAT-05 ratificadas em 2026-10-28 e seus valores S9-L01..L16.
2. Obter autorização real separada com canal, sessão, roots, caps e escopo.
3. Confirmar baseline Git, cópia SQLite e manifesto privado.
4. Preparar supervisor/ledger e demonstrar timeout, medição, cancelamento e recibo offline; sem isso G0 BLOCKED.
5. Confirmar representatividade sem expandir busca.
6. Passar G0 antes de RPC.
7. Executar G1–G9 sequencialmente; comparar plano ao manifesto; parar no primeiro limite/erro.
8. Preservar dados/WIP, sanitizar exportação e reconciliar por gate/FR/NFR.
9. Apresentar recomendação; aguardar aceite humano S9.
10. Não iniciar S10 sem autorização separada.

### Ratificações aprovadas (2026-10-28)

| ID | Decisão concreta | Impacto |
|---|---|---|
| RAT-01 | Dataset com Track observado, dois Courses e pelo menos dois Modules, perfis F/M e elegibilidade. Qualquer dispensa exige decisão explícita revisando o escopo. | Define universo do aceite; sem Track demonstrável, representatividade BLOCKED_DATASET sem ampliação automática da coleta. |
| RAT-02 | S9-L01..L12 e L15..L16. | Define volume, custo, tempos, cancelamento e orçamento. |
| RAT-03 | S9-L13/L14 e mídia M 1–2 GiB. | Define critério quantitativo NFR-02. |
| RAT-04 | Supervisor/ledger e ensaio offline antes de RPC. | Sem controle demonstrado, G0 bloqueia. |
| RAT-05 | Semântica de cobertura/resultados e restrições herdadas. | Evita tratar amostra como conformidade universal. |

O contrato foi ratificado em 2026-10-28; a autorização de operações reais permanece separada. Próxima ação: preparar e validar offline o supervisor/ledger após autorização específica.

