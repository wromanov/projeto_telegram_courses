# S2 — Message Scanner & SQLite Persistence

~~~text
DOCUMENT_ROLE = IMPLEMENTATION_CONTRACT
CONTRACT_STATUS = APPROVED / FROZEN
ACTIVITY = S2 — Contract Finalization & Integrated Implementation
S2_STATUS = IMPLEMENTED_OFFLINE / REAL_VALIDATION_PENDING / NOT_CLOSED
IMPLEMENTATION_AUTHORIZATION = EXPLICIT_USER_APPROVAL_2026-10-09
REAL_TELEGRAM_ACCESS_THIS_ACTIVITY = NO
CREDENTIALS_OR_SESSION_ACCESSED_THIS_ACTIVITY = NO
GIT_ACTIONS = NONE
~~~

## 1. Objetivo e authorities

Definir um scanner genérico que percorre o histórico de um canal autorizado,
normaliza as mensagens e metadados de mídia necessários ao catálogo e os
persiste em SQLite. O contrato cobre FR-03 e FR-09. Não implementa parser
RASMOO, catálogo de cursos, download, sincronização incremental completa,
interface, acesso real ao Telegram ou comportamento de sprints posteriores.

Authorities vigentes consultadas:

- [PROJECT_STATE](../continuity/PROJECT_STATE.md): checkpoint anterior registra
  S1 fechada e S2 candidata; a autorização explícita desta atividade o sucede.
- [ACTIVE_AUTHORITY_MAP](../continuity/ACTIVE_AUTHORITY_MAP.md) e
  [PROJECT_GOVERNANCE_BINDING](../continuity/PROJECT_GOVERNANCE_BINDING.json):
  continuidade e baseline de governança adotado.
- [LAST_HANDOFF](../continuity/handoff/LAST_HANDOFF.md): handoff S1-D/GOV-01
  mais recente.
- [SPRINTS — S2](../continuity/planning/SPRINTS.md#s2--message-scanner--sqlite-persistence)
  e [ROADMAP](../continuity/planning/ROADMAP.md): sequência, escopo e aceite.
- [REQUIREMENTS](../product/REQUIREMENTS.md): FR-03, FR-09, NFR-04, NFR-08,
  NFR-09, NFR-10 e ACCESS_BOUNDARY.
- [ARCHITECTURE](../architecture/ARCHITECTURE.md): ADR-002/003, boundaries e
  ownership de retry.
- [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md):
  schema inicial, SQLite, migrações, transações, logging, erros e testes.
- [Contrato S1-A](S1A_PROTECTED_SESSION_IMPLEMENTATION_CONTRACT.md),
  [S1-B](S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md) e
  [S1-D](S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md): sessão,
  autenticação/gateway, identidade estável do canal e limites de acesso.

Este contrato não altera as authorities listadas. Comportamentos abaixo são
classificados como **DECISÃO EXISTENTE** (já aprovados) ou **DECISÃO S2**
(detalhe finalizado e aprovado com este contrato).

## 2. Revisão de entrada

| Verificação | Resultado | Evidência e limite |
|---|---|---|
| S1 formalmente encerrada | PASS | PROJECT_STATE e LAST_HANDOFF registram S1/S1-D CLOSED. |
| Gateway de autenticação disponível | PASS | TelegramGateway/TelethonGateway oferecem restore, autenticação e descoberta; o scanner não deve reimplementar esses fluxos. |
| Identidade estável de canal | PASS | DEC-S1D-02 e ChannelSummary usam telegram_chat_id; título/username não são chaves. |
| Fronteira Telethon/domínio | PASS | ADR-002 e gateway S1 mantêm objetos/exceções Telethon no adapter. |
| Fundação SQLite aprovada | PASS | ENGINEERING_FOUNDATION e ADR-003 aprovam SQLite + aiosqlite, SQL migrations e SQL confinado ao repository. |
| Dependências para trabalho offline | PASS | pyproject declara aiosqlite 0.22.1 e Telethon 1.45.x; o venv local contém aiosqlite 0.22.1, Telethon 1.45.0, pytest 9.1.1 e Ruff 0.16.10. |
| Implementação existente de scanner/persistência | AUSENTE, conforme escopo S2 | TelegramGateway ainda não oferece iteração de mensagens; não há repository, migrations ou tabelas SQLite da aplicação em src/. |
| Bloqueio material para implementação offline | NONE FOUND | Fakes e banco temporário permitem desenvolver e validar sem Telegram, sessão ou credenciais reais. A retenção requer decisão do usuário antes do freeze/uso de conteúdo real; não bloqueia prova offline com fixtures sintéticas. Ver §12. |

Conclusão da etapa de entrada: **S2_ENTRY_REVIEW = PASS**. A base aprovada e
dependências locais permitem implementação offline. A ausência do scanner e
do repository era o trabalho planejado da S2, não um bloqueio. Naquele ponto,
a conclusão da entrada não aprovava o draft nem autorizava implementação;
esta revisão posterior aprova e congela o contrato. Acesso real e publicação
Git continuam fora da autorização.

## 3. Escopo e limites

### Incluído

- Receber a identidade de um canal que passou pela seleção S1.
- Revalidar a sessão existente e ler somente o histórico desse canal.
- Projetar mensagens para DTOs próprios, sem tipos Telethon acima do adapter.
- Persistir mensagem, metadados pertinentes de mídia, execução e checkpoint.
- Retomar controladamente uma execução interrompida, sem lacunas causadas por
  checkpoint não confirmado.
- Usar migrações SQL, aiosqlite, transações e as regras SQLite da Foundation.
- Testes offline com gateway fake e testes de integração com SQLite temporário.

### Excluído

- Login ou coleta de OTP/2FA dentro do scanner.
- Escolha/interpretação de curso, parser RASMOO, nós de catálogo e CLI de
  catálogo.
- Download, streaming ou armazenamento dos bytes de mídia; persistir um
  file_reference para download posterior.
- Sincronização incremental, detecção completa de remoções ou reconciliação
  reservadas à S7.
- Seleção de canais não descobertos/acessíveis, busca pública, convite, entrada
  em canais, escrita ou qualquer ação administrativa remota.
- Concorrência multi-processo ou varredura paralela.

## 4. Comportamentos existentes e propostas

| Tema | Contrato |
|---|---|
| Acesso legítimo e tipos elegíveis | **DECISÃO EXISTENTE:** somente canal acessível à conta própria e dentro de DEC-S1D-02. |
| Identidade | **DECISÃO EXISTENTE:** telegram_chat_id é identidade externa estável; nunca título ou username. |
| Boundary | **DECISÃO EXISTENTE:** domínio/aplicação usam tipos do projeto; Telethon é privado ao adapter. |
| Persistência | **DECISÃO EXISTENTE:** SQLite + aiosqlite, migrations SQL e repository; sem ORM. |
| Modelo inicial | **DECISÃO EXISTENTE:** schema de schema_migrations, channels, catalog_nodes, messages, media_items, downloads, sync_checkpoints e scan_runs conforme Foundation. A S2 escreve somente nos dados de canal/mensagem/mídia/execução/checkpoint; não entrega operações de catálogo ou download. |
| Ordem da varredura e cursor | **DECISÃO S2:** snapshot de maior ID no início; ler IDs em ordem decrescente; checkpointar o menor ID confirmado do trecho. |
| Edições | **DECISÃO S2:** uma nova observação do mesmo ID atualiza o snapshot atual da mensagem e seus metadados de mídia, sem histórico de versões. |
| Remoções/inacessibilidade | **DECISÃO S2:** ausência no histórico não prova remoção; não apagar nem marcar REMOVED. Uma negação de acesso interrompe a execução sem apagar dados locais. |
| Retry/FloodWait | **DECISÃO EXISTENTE + DECISÃO S2:** a aplicação é dona da política; a S2 não espera nem repete automaticamente. Expõe erro sanitizado e permite retomada explícita a partir do checkpoint. |
| Retenção do texto | **DECISÃO S2-OPEN-01 APPROVED:** persistir o texto integral somente no SQLite local, até exclusão explícita pelo usuário; sem expiração automática. Texto vazio é NULL. Logs não incluem conteúdo. |

## 5. Interfaces e ownership

Assinaturas conceituais. Nomes finais podem seguir o estilo da implementação,
preservando semântica e tipos:

~~~python
class TelegramGateway(Protocol):
    async def latest_message_id(self, telegram_chat_id: int) -> int | None: ...

    def iter_channel_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int,
        before_message_id: int | None,
    ) -> AsyncIterator[GatewayMessage]: ...

class MessageScanner(Protocol):
    async def scan(
        self, channel: SelectedChannel, request: ScanRequest
    ) -> ScanOutcome: ...
~~~

DTOs imutáveis de projeto:

- SelectedChannel(telegram_chat_id: int): somente ID estável da S1.
- GatewayMessage: telegram_message_id, date_utc, edit_date_utc, text,
  grouped_id e zero ou mais GatewayMedia.
- GatewayMedia: media_ordinal, kind, telegram_media_id opaco,
  original_filename, mime_type e file_size_bytes (nullable quando o Telegram
  não fornece).
- ScanRequest: max_messages positivo, timeout_seconds positivo e,
  opcionalmente, resume_run_id. A chamada sempre declara seus limites; o
  contrato não importa budgets numéricos de descoberta S1-D.
- ScanOutcome: run_id, status (COMPLETE, PARTIAL ou FAILED), stop reason,
  contadores e último checkpoint confirmado. Não contém mensagem, mídia bruta,
  tipo/exceção Telethon, credencial ou sessão.

Responsabilidades:

1. **Channel Selection:** entrega telegram_chat_id selecionado pela S1;
   não resolve entidade nem faz chamada de rede.
2. **Telegram Gateway:** restaura apenas sessão já existente, valida acesso ao
   canal, captura o watermark e itera mensagens por uma operação explícita de
   histórico. Só dados retornados por essa operação podem entrar no scanner.
   Respostas de updates/GetDifference/GetChannelDifference não são fonte do
   catálogo; flags de update desativadas não são tratadas como prova de zero
   RPC interno. Resolve internamente a entidade Telethon a partir do ID estável
   ou por atualização limitada da lista de diálogos; mantém access hash e
   objetos Telethon dentro do adapter. Não usa payload incidental de
   GetDifference/GetChannelDifference como entrada de catálogo. Nunca procura
   canal público, faz join ou armazena access hash/file reference.
3. **Message Scanner:** coordena run, deadline, cancelamento, cursor e
   checkpoint; não importa Telethon nem executa SQL.
4. **Message Normalization:** função pura que converte DTOs do gateway para
   modelos persistíveis; classifica tipos conhecidos/desconhecidos sem baixar
   conteúdo. Erro de campo essencial para antes de avançar o cursor.
5. **SQLite Repository:** aplica migrações e owns todas as queries/transações;
   valida integridade e unicidade; não conhece cliente/gateway Telethon.
6. **Scan Run / Checkpoint:** repository guarda estado operacional do run e o
   último trecho duravelmente persistido na mesma transação das mensagens.

O TelegramGateway atual cobre auth e descoberta, mas não histórico. A adição
de iteração e resolução interna do canal é extensão S2 da fronteira aprovada,
não alteração da fronteira arquitetural. Falha ao resolver ou acessar o canal
é controlada; não se contorna com username público ou convite.

## 6. Fluxo operacional e limites

1. A aplicação recebe SelectedChannel e valida ScanRequest. Exatamente um
   canal é varrido por chamada. Cria scan_run e checkpoint inicial juntos em
   transação local, para que também tentativas que falham antes do primeiro
   RPC tenham resultado operacional.
2. O gateway usa restore() da S1. AUTH_REQUIRED ou SESSION_INVALID
   encerra a operação com orientação para o fluxo de autenticação já existente;
   não solicita telefone/código/senha no scanner. Run e checkpoint terminam
   FAILED, sem cursor.
3. O gateway confirma que a conta atual ainda pode acessar o ID solicitado e
   captura through_message_id uma vez. Falha de acesso termina o run sem apagar
   estado local. Se o canal estiver vazio, conclui run vazio. Mensagens novas
   acima do watermark ficam para outra unidade/execução.
4. A aplicação persiste watermark no run/checkpoint antes de iniciar a
   iteração.
5. O gateway entrega mensagens em ordem estritamente decrescente de
   telegram_message_id, até o watermark. before_message_id é exclusivo;
   não se presume que IDs sejam contíguos.
6. A normalização não retém objetos Telethon. Campos de data são UTC; texto
   vazio ou ausente vira NULL; campos opcionais desconhecidos ficam NULL. Mídia
   suportada tem metadados, não bytes. Tipos não reconhecidos são marcados
   UNSUPPORTED sem bloquear outras mensagens, se identidade/tipo puderem ser
   representados com segurança.
7. O repository grava lotes limitados em uma transação. **Proposta inicial:**
   lote de até 100 mensagens, limitado também ao saldo de max_messages nesta
   chamada; esse número é detalhe interno de batching, não budget S1-D nem
   limite de cobertura do canal.
8. Ao esgotar o histórico até o watermark, run e checkpoint ficam COMPLETE.
   Atingir max_messages, timeout ou cancelamento encerra como PARTIAL,
   preserva o checkpoint e nunca declara cobertura completa.
9. resume_run_id só pode retomar run PARTIAL/INTERRUPTED do mesmo canal,
   com o mesmo watermark e limites válidos. Um run interrompido pode ser
   identificado após reinício e marcado INTERRUPTED. Run concluído não é
   retomado: nova varredura começa no watermark mais recente e reobserva o
   histórico para aplicar upserts.
10. Somente uma varredura ativa por processo/canal. Sem worker paralelo e sem
    garantia multi-processo, conforme a Foundation.

Os limites efetivos por chamada são os valores positivos e obrigatórios em
ScanRequest; o scanner para ao primeiro entre limite de mensagens, deadline,
cancelamento e fim do histórico. Não há valor default ou cap operacional
aprovado nas authorities para a S2. A interface não pode converter limite
atingido em COMPLETE. A escolha de defaults de CLI e validação real fica
pendente da revisão/aprovação do contrato e autorização futura específica.

## 7. Checkpoint e atomicidade

### Cursor

- No início: snapshot_high_water_message_id = through_message_id;
  last_message_id = NULL.
- Para mensagens descendentes, last_message_id é o menor ID do trecho já
  confirmado no banco; a próxima busca usa esse ID como limite exclusivo.
- Resume mantém o watermark original e continua abaixo do cursor. Mensagens
  criadas depois do watermark não entram silenciosamente no run corrente.
- Buracos de IDs não são erro e não se avançam cursores por aritmética.

### Protocolo transacional

Para cada lote:

1. BEGIN IMMEDIATE.
2. Upsert de cada mensagem por identidade canônica
   (telegram_chat_id, telegram_message_id) e upsert/substituição de seus
   metadados de mídia.
3. Atualizar contadores do scan_run.
4. Atualizar sync_checkpoint para o último ID do lote gravado.
5. COMMIT; em qualquer erro, ROLLBACK.

Mensagem, associação/metadado de mídia, contadores e checkpoint do lote são
atômicos. Um crash antes do commit deixa todos os quatro no estado anterior; o
lote é lido outra vez na retomada. É proibido persistir checkpoint antes dos
upserts ou em transação separada. Se a transação falhar, o cursor não avança.
Quando o histórico chega ao watermark, uma transação final atualiza o status
COMPLETE do run e checkpoint e o last_scanned_at do canal. Timeout/cancelamento
entre lotes finaliza o run e checkpoint como PARTIAL em transação própria; uma
falha dessa atualização final não converte cursor persistido em sucesso.

Cada conexão liga foreign keys, usa WAL e aplica o busy timeout configurado.
Migrações numeradas atualizam schema_migrations atomicamente. O repository é
o único dono de SQL. Após fechar e reabrir o processo/banco, mensagens,
metadados, runs e checkpoint confirmado permanecem disponíveis.

## 8. Modelo de dados S2

Os nomes abaixo são lógicos e podem virar nomes SQL compatíveis com o estilo
existente; colunas, identidades e restrições são obrigatórias.

| Tabela | Dados e invariantes |
|---|---|
| schema_migrations | version INTEGER PRIMARY KEY; applied_at UTC, conforme Foundation. Migrações numeradas aplicadas uma vez. |
| channels | telegram_chat_id INTEGER PRIMARY KEY; título/username opcionais; parser_key NULL até parser posterior; created_at, updated_at, last_scanned_at. Sem access hash. |
| messages | channel_id, cujo valor é o telegram_chat_id; telegram_message_id; message_date_utc; edit_date_utc NULL; text NULL quando vazio/ausente e íntegro quando presente; grouped_id NULL; created_at; updated_at. PK/UNIQUE em (channel_id, telegram_message_id), equivalente exatamente à identidade externa canônica. Sem sender ID, conteúdo de sessão ou campos Telethon. |
| media_items | FK composta (channel_id, telegram_message_id) para mensagem; media_ordinal; catalog_node_id NULL para S3; kind; telegram_media_id opaco; filename/MIME/bytes opcionais; timestamps. UNIQUE por mensagem/ordinal; conteúdo binário e file_reference não são armazenados. |
| scan_runs | ID; channel_id igual ao telegram_chat_id e FK para channels; status RUNNING/COMPLETE/PARTIAL/FAILED/INTERRUPTED; início/fim; watermark; contadores de mensagens/mídias novas, atualizadas e erros; stop reason/error category sanitizados. Sem conteúdo da mensagem/exceção. |
| sync_checkpoints | Uma linha por scan_run (FK UNIQUE), mais channel_id igual ao telegram_chat_id, watermark, menor last_message_id persistido e data correspondente, status e updated_at. Mantém checkpoints de runs anteriores; é cursor de retomada S2, não checkpoint de sync incremental S7. |

A migração inicial também materializa schema_migrations, catalog_nodes e
downloads conforme os campos/states aprovados na Foundation, mas o scanner S2
não cria nós de catálogo, download tasks, caminhos, arquivos ou transições de
download. Toda tabela usa constraints/foreign keys; mensagens e mídia são
apagáveis somente por política explícita, nunca como efeito implícito de uma
varredura parcial.

Datas remotas são normalizadas para ISO-8601 UTC. telegram_media_id representa
somente identidade estável suficiente para associar a mídia à mensagem. Se o
gateway não puder produzi-la, os metadados disponíveis podem ser nulos e
kind/estado reportam limitação; não se persiste access_hash,
file_reference, objeto serializado ou segredo. Tamanho desconhecido é NULL,
não zero.

## 9. Upsert, idempotência e alterações remotas

- A chave externa não sofre conversão: telegram_chat_id +
  telegram_message_id.
- Primeira observação insere mensagem e suas mídias.
- Reobservação atualiza texto, datas, grouped ID e conjunto de mídias da mesma
  mensagem dentro da transação. updated_at e contador de atualizações só
  mudam quando dados de origem mudaram materialmente.
- Uma execução repetida sem alteração não cria duplicatas nem conta updates
  artificiais.
- Remover mídia de uma mensagem observada substitui suas associações correntes;
  não apaga outras mensagens.
- Mensagem que não aparece mais no Telegram não é inferida como removida.
  Scanner não faz tombstone ou delete por ausência. Remoções, edição retroativa
  não observada e reconciliação incremental são trabalho/decisão S7.
- Se um item é explicitamente retornado como inacessível ou não pode ser
  normalizado nos campos obrigatórios, a execução não avança além dele; registra
  falha sanitizada e permite retomada explícita. Lacunas que o servidor não
  reporta não podem ser classificadas como removidas.

## 10. Falhas e interrupção

| Condição | Resultado S2 |
|---|---|
| FloodWait / rate limit | Adapter traduz para erro de projeto com retry_after_seconds; nenhuma camada dorme ou faz retry automático. Run fica PARTIAL se há cursor confirmado, senão FAILED; checkpoint não avança durante a espera. |
| Timeout/rede transitória | Cancela/fecha iterator; run PARTIAL se o checkpoint avançou, senão FAILED; não repete operação automaticamente. Reexecução/resume é explícita. |
| Auth inválida ou acesso revogado | Run FAILED, erro sanitizado e checkpoint preservado; não reloga, entra ou remove dados locais. |
| Cancelamento do usuário | Fecha iterator em finally, commit somente lotes completos, run PARTIAL/CANCELLED. |
| Processo encerrado abruptamente | Transação não confirmada reverte; após restart, RUNNING obsoleto torna-se INTERRUPTED e pode retomar do checkpoint durável. |
| Erro de normalização de campo essencial | Rollback do lote corrente, sem pular o ID; run FAILED com categoria segura. Tipo opcional desconhecido é preservado como limitação, não erro fatal. |
| SQLite busy/constraint/disk error | Rollback; cursor anterior mantido; erro de banco controlado. Sem loop de retry. |
| Erro no cleanup | Preserva erro primário, não declara COMPLETE; reporta falha de limpeza sanitizada. |
| Mensagem ausente após remoção/ocultação remota | Não existe evento confiável para inferir remoção; mantém o registro local e não escreve tombstone. |

Logs/CLI só podem incluir run ID local, status, contadores, duração e categoria
de erro. Não registrar título/username, channel ID, texto/caption, nome de
arquivo, IDs individuais, dados pessoais, credenciais, sessão, file_reference
ou mensagem/exceção Telethon bruta.

## 11. Plano de testes e aceite

Todos os testes novos são offline salvo a validação futura separada. Não foram
executados nesta revisão.

### Unitários e integração SQLite local

- Scanner depende de gateway fake e repository protocol; domínio não importa
  Telethon nem executa SQL.
- Iteração decrescente, watermark fixo, cursor exclusivo, IDs com lacunas,
  limites, timeout, cancelamento, iterator vazio e retomada no mesmo run.
- Mapper preserva IDs, datas, texto, grupo e metadados pertinentes; omite
  hashes/references/objetos Telethon; mídia sem tamanho tem NULL.
- Mídias desconhecidas não causam download nem abortam quando podem ser
  representadas com segurança.
- Unique (telegram_chat_id, telegram_message_id) impede duplicatas; mensagem
  em canais distintos não colide.
- Reexecução idempotente e reobservação editada atualizam o snapshot atual sem
  criar versões.
- Mensagem removida/ausente não é marcada REMOVED nem apagada.
- FK habilitada, WAL, busy timeout configurado e migration versionada.
- Migration repetida/upgrade, restrições, reopen/restart e persistência em
  arquivo temporário; integridade dos registros e foreign keys verificada.
- Falha injetada antes do commit, durante upsert, update do run ou checkpoint
  demonstra rollback conjunto e cursor anterior intacto.
- Crash simulado após lote commitado e antes do lote seguinte retoma sem perda
  nem duplicata.
- FloodWait transporta a duração sem sleep/replay; timeout, network, access,
  auth, DB, erro inesperado e cleanup mantêm erro primário e cursor seguro.
- Verificação de logs confirma ausência de textos, metadata pessoal
  desnecessária, secrets, IDs remotos individuais e exceções brutas.
- Nenhum teste normal autentica, abre sessão/vault real, cria conexão Telegram
  ou baixa mídia.

### Validação Telegram futura, separada

Antes de qualquer teste de histórico real, exigir autorização explícita própria
do usuário, sessão local já configurada e canal de teste autorizado. Limitar a
uma leitura controlada, registrar somente métricas sanitizadas e não baixar
mídia. Isso não foi autorizado nem executado por esta atividade; os testes reais
de aceitação devem ocorrer antes do fechamento S2, com escopo aprovado.

### Critérios de aceite S2

1. Mensagens e metadados são associados ao canal correto e sobrevivem ao
   restart.
2. A identidade (telegram_chat_id, telegram_message_id) é única e
   reexecução não duplica dados.
3. Transações mantêm mensagem, mídia, run, contadores e checkpoint consistentes.
4. Nenhum checkpoint indica progresso além de mensagem/metadado commitado.
5. Runs completos, parciais, falhos e interrompidos são distinguíveis e
   recuperáveis dentro do cursor confirmado.
6. Edição observada atualiza o snapshot; ausência não é tratada como remoção.
7. FloodWait e falhas respeitam retry ownership; não há sleep/retry ilimitado.
8. FK/WAL/busy timeout/migrations funcionam em SQLite temporário e o estado
   persiste após reabrir.
9. Boundary não vaza tipos Telethon, access hashes, session ou conteúdo para
   logs; scanner não baixa bytes.
10. Testes offline, integração local e regressão da baseline passam. Qualquer
    teste real de histórico depende da autorização separada acima.

## 12. Decisão S2-OPEN-01 — aprovada

| ID | Tema | Situação e proposta |
|---|---|---|
| S2-OPEN-01 | Retenção e exclusão de texto de mensagens | **APPROVED:** persistir o texto integral das mensagens selecionadas no SQLite local até exclusão explícita pelo usuário; não expirar automaticamente. Edições observadas atualizam os dados preservando a identidade. Texto vazio pode ser NULL. Logs nunca contêm conteúdo. Remoção remota e reconciliação ficam fora da S2, para etapa apropriada de sincronização. |

Limites numéricos de varredura são fornecidos explicitamente em cada
ScanRequest; não há default/cap S2 aprovado. O batching de 100 mensagens e o
busy timeout são detalhes técnicos de implementação congelados neste contrato.
O trabalho offline valida os mecanismos com limites e conteúdo sintéticos.
Nenhuma decisão desta atividade autoriza leitura real.

## 13. Veredito desta atividade

~~~text
S1_ACCEPTANCE = PASS / S1 CLOSED
S2_ENTRY_REVIEW = PASS
S2_READINESS = CONTRACT_REVIEW_PASS
FOUNDATION_COMPATIBILITY = PASS
SCANNER_CONTRACT = APPROVED / FROZEN
SQLITE_CONTRACT = APPROVED / FROZEN
CHECKPOINT_SEMANTICS = APPROVED / ATOMIC_WITH_MESSAGE_AND_MEDIA_BATCH
ACCEPTANCE_CRITERIA_DEFINED = YES
MATERIAL_OPEN_DECISIONS = NONE
S2-OPEN-01 = APPROVED
S2_IMPLEMENTATION_AUTHORIZATION = EXPLICIT_USER_APPROVAL_2026-10-09
S2_STATUS = IMPLEMENTED_OFFLINE / REAL_VALIDATION_PENDING / NOT_CLOSED
S2_ACCEPTANCE_STATUS = PENDING_SEPARATELY_AUTHORIZED_REAL_TELEGRAM_VALIDATION
REAL_TELEGRAM_ACCESS = NO
CREDENTIALS_ACCESSED = NO
GIT_ACTIONS = NONE
~~~
