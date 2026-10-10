# S3 — Parser + Catalog CLI Contract

```text
DOCUMENT_ROLE = IMPLEMENTATION_CONTRACT
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
ACTIVITY = S3 Offline Catalog Core Implementation
S3_STATUS = IN_PROGRESS / GENERIC_OFFLINE_CORE_IMPLEMENTED
S3_IMPLEMENTATION_AUTHORIZATION = YES / OFFLINE GENERIC CORE ONLY
S3_ENTRY_REVIEW = PARTIAL
S3_READINESS = CONTRACT_DRAFT_READY / SP-02 AND RASMOO GRAMMAR DECISIONS OPEN
REAL_TELEGRAM_ACCESS = ATTEMPTED / one authorized target; operation result not captured
REAL_USER_SQLITE_ACCESS = NO
CREDENTIALS_OR_SESSION_ACCESS = ATTEMPTED / values not emitted
SP02_MESSAGE_COUNT = UNKNOWN / request cap 30; no result counter captured
SP02_SANITIZED_EVIDENCE = NONE
DOWNLOADS = NONE / LOCAL_PERSISTENCE = NONE
GIT_ACTIONS = NONE
```

## 1. Objetivo e authorities

Definir contratos implementáveis para parsers plugáveis, construção e
persistência idempotente do catálogo, e sua inspeção inicial na CLI. S3 consome
somente mensagens/metadados já persistidos pela S2; não faz nova varredura.
Authorities: [PROJECT_STATE](../continuity/PROJECT_STATE.md),
[ACTIVE_AUTHORITY_MAP](../continuity/ACTIVE_AUTHORITY_MAP.md),
[LAST_HANDOFF](../continuity/handoff/LAST_HANDOFF.md),
[SPRINTS](../continuity/planning/SPRINTS.md), [ROADMAP](../continuity/planning/ROADMAP.md),
[REQUIREMENTS](../product/REQUIREMENTS.md), [ARCHITECTURE](../architecture/ARCHITECTURE.md),
[ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md) e
[S2_MESSAGE_SCANNER_SQLITE_CONTRACT](S2_MESSAGE_SCANNER_SQLITE_CONTRACT.md).

Escopo funcional: FR-04, FR-05 e FR-13; FR-03 é a origem imutável da
identidade e dos dados de entrada. RASMOO é o primeiro parser especializado,
não uma condição para catalogar outros canais.

## 2. Revisão de entrada e limites

| Verificação | Resultado | Evidência/limite |
|---|---|---|
| S2 aceita e encerrada | PASS | PROJECT_STATE registra S2 ACCEPTED / CLOSED. |
| Mensagens e mídia persistidas | PASS, evidência documental | Contrato S2 e implementação/repository presentes. Esta revisão não abriu o SQLite real do usuário nem leu conteúdo. |
| Identidade Telegram preservada | PASS | `channels.telegram_chat_id`, `messages(channel_id, telegram_message_id)` e `media_items(channel_id, telegram_message_id, media_ordinal)`; `channel_id` é o próprio `telegram_chat_id`. |
| Nós e referências iniciais | PASS, com lacuna S3 | `catalog_nodes` e `media_items.catalog_node_id` existem na migration 001; `catalog_nodes` não tem chave natural/constraint para identidade semântica idempotente. |
| Ports/modelos prévios | PARCIAL | `SelectedChannel`, `GatewayMessage`, `GatewayMedia` e `MessageGateway` existem. O núcleo offline agora define modelos, parser genérico, registry, builder e repository de catálogo. |
| Stack | PASS | Python 3.14, Rich, aiosqlite, pytest e Ruff. Suíte completa, Ruff e diff check executados; ver checkpoint abaixo. |
| Semântica dos marcadores RASMOO | OPEN MATERIAL | A documentação lista `=`, `==`, `===`, `#Fxxx` e menciona `#Docxxx`, mas não atribui significado a cada um. |
| Amostra controlada SP-02 | INCOMPLETE / OPEN MATERIAL | O canal autorizado foi identificado. Uma única leitura direcionada foi iniciada com limite de 30 mensagens; a operação não retornou saída sanitizada e foi interrompida dentro do orçamento. A quantidade efetivamente consultada é desconhecida, nenhum conteúdo bruto foi emitido e nenhum resultado estrutural foi capturado. Não repetir dentro do teto original sem redefinir o orçamento considerando esta tentativa. |
| Implementação e DB local | FORA DESTA ATIVIDADE | Só se prepara o contrato; sem parser, migration, testes, CLI ou acesso ao `data/catalog.sqlite3`. |

Conclusão: a tentativa SP-02 não produziu evidência utilizável. Nenhuma
semântica de marcador foi confirmada. O usuário autorizou separadamente o
núcleo genérico offline; essa autorização não inclui nem implementa RasmooParser
e não resolve os itens em §11. S2 permanece fechada.

## 3. Limites arquiteturais

```text
persisted Channel + Messages + MediaItems
  → ParserRegistry / ParserSelection
  → Parser (pure interpretation)
  → CatalogBuilder (pure hierarchy and ordering)
  → CatalogRepository (SQLite transaction)
  → CatalogQueryService / Catalog CLI (Rich)
```

Parsers recebem modelos de domínio próprios e retornam resultados estruturados.
Não importam Telethon, não leem/escrevem SQL ou filesystem, não iniciam
downloads, retries, rede, scanner ou prompts/CLI. Repository é o único owner de
SQL. Builder e parser são funções determinísticas sobre a mesma entrada e
versão de gramática.

Modelos mínimos (nomes finais podem seguir estilo do código):

```python
SourceMessage(channel_id: int, telegram_message_id: int, date_utc: datetime,
              text: str | None, media: tuple[SourceMedia, ...])
SourceMedia(telegram_message_id: int, media_ordinal: int, kind: str,
            telegram_media_id: str | None, original_filename: str | None,
            mime_type: str | None, file_size_bytes: int | None)
ParserContext(channel_id: int, parser_key: str, grammar_version: str)
ParseResult(nodes: tuple[ParsedNode, ...], media_links: tuple[MediaLink, ...],
            unresolved: tuple[UnclassifiedSource, ...], diagnostics: tuple[SafeDiagnostic, ...])
ParsedNode(node_key: str, kind: str, parent_key: str | None, title: str | None,
           code: str | None, ordinal: int, source_message_id: int | None)
MediaLink(telegram_message_id: int, media_ordinal: int, lesson_node_key: str)
```

`SourceMessage` é uma projeção das linhas S2, não copia nem transforma a
identidade externa. Mensagens sem texto/mídia continuam representáveis.
Diagnósticos guardam categoria, parser e IDs de origem quando úteis, nunca
conteúdo integral, segredo ou exceção de infraestrutura.

## 4. Registry e seleção

```python
class CatalogParser(Protocol):
    key: str
    grammar_version: str
    def detect(self, messages: Sequence[SourceMessage]) -> Detection: ...
    def parse(self, context: ParserContext,
              messages: Sequence[SourceMessage]) -> ParseResult: ...

class ParserRegistry:
    def select(self, configured_key: str | None) -> ParserSelection: ...
```

Registry registra `generic` por padrão; parsers futuros podem ser registrados
explicitamente. Key explícita conhecida no canal seleciona esse parser; key
ausente seleciona Generic. Key desconhecida reporta `UNKNOWN_PARSER_KEY`, sem
conversão silenciosa. Não há autodetecção. RASMOO só poderá ser registrado após
evidência/decisão de gramática e autorização específica. Generic não declara
correspondência exclusiva.

## 5. RASMOO: análise lexical e semântica pendente

Evidência documental existente confirma somente que `=`, `==`, `===` e
`#Fxxx` pertencem a uma convenção suportada, e que `#Docxxx` pode estar
presente. Não confirma a qual nível cada marcador corresponde, se `#F` nomeia
uma aula ou mídia, nem regras de título, repetição ou escopo. Não atribuir esses
significados por convenção presumida.

Contrato lexical preparatório: percorrer texto por linha, preservar texto e
ordem originais; reconhecer como **tokens candidatos** somente linhas cujo
conteúdo estrutural seja exatamente `=`, `==`, `===`, ou um marcador `#F` / `#Doc`
seguido por um código não vazio conforme a amostra aprovada. Texto adicional,
capitalização, espaços, pontuação e formato de código só entram na gramática
após validação SP-02. O lexer deve manter linha e mensagem de origem. Tokens
candidatos ainda não provam o tipo do nó.

Resolução do alvo SP-02: o usuário forneceu a identidade estável do único canal
broadcast autorizado. Uma leitura limitada solicitou no máximo 30 mensagens e
não usou scanner, download ou persistência local. A operação foi interrompida
antes de retornar contadores/resultados sanitizados; a quantidade efetivamente
consultada e a etapa remota alcançada são desconhecidas. Nenhum texto bruto ou
identificador do canal foi emitido. Isto não é evidência gramatical e não
resolve marcador algum.

Até que a tabela de semântica seja aprovada, `RasmooParser` não deve inferir
Track/Course/Module/Lesson a partir apenas da quantidade de `=`; candidato
ambíguo fica em `unresolved` e sua mensagem/mídia continua consultável. Um
marcador desconhecido, título sem marcador, mensagem órfã ou mídia sem âncora
não é descartado nem ligado por proximidade especulativa. Marcadores sem
reconhecimento ficam como texto de origem e `UNKNOWN_MARKER`; não encerram
contexto nem iniciam um novo nó. A decisão final da gramática deve definir:

| Aspecto | Regra contratual a fechar com evidência |
|---|---|
| `=`, `==`, `===` | tipo de nó/evento de cada token e se abre/substitui contexto ancestral |
| `#Fxxx` e `#Docxxx` | código/identidade e se identifica Lesson, MediaItem ou ambos |
| títulos | linha associada, trimming/normalização, título vazio e preservação do original |
| mensagens fora de ordem | ordenação-fonte e precedência de eventos na mesma mensagem |
| órfãos/edições | associação sem pai, mídia sem índice, alteração de mensagem e reparsing |
| repetição/desconhecidos | duplicata, marcador fora de contexto e continuidade do contexto |

Parser converte apenas regras adjudicadas em `ParsedNode`/`MediaLink`; não
promove casos ambíguos a estrutura válida. A amostra sintética de aceite cobre
um track, dois cursos, ao menos dois módulos, múltiplos `#Fxxx`, `#Docxxx` se
existir no formato, nome problemático, mensagem sem mídia e mídia não listada,
conforme Engineering Foundation, mais órfãos e edições conforme SPRINTS.

## 6. GenericParser

Fallback determinístico e sem inferência de curso/módulo: cria um nó
`unclassified` por mensagem-fonte (incluindo mensagem vazia), com chave da
mensagem sob identidade composta pelo canal (`telegram_chat_id`) e
`telegram_message_id`; texto pode ser título
de exibição, preservando conteúdo original somente na tabela `messages`. Toda
mídia da mensagem é ligada a esse nó para inspeção e aparece com tipo/tamanho
conhecidos/desconhecidos. Não cria Track, Course, Module ou Lesson fictícios.
Mensagem e mídia sem parse especializado ficam contáveis/consultáveis. Esta
forma mínima mantém identidade e origem e permite parser específico futuro sem
alterar a S2.

## 7. CatalogBuilder: hierarquia, associação e ordenação

Entrada é ordenada por `(telegram_message_id ASC, media_ordinal ASC)` antes de
interpretar sequências; IDs Telegram não são recalculados nem assumidos
contíguos. O parser emite chaves/parentes, e o Builder valida que cada pai
existe, é do tipo permitido, pertence ao mesmo canal e não cria ciclos. O
Builder não inventa pais ausentes: nó sem ancestral obrigatório e mensagem ou
mídia não associada viram unresolved.

Árvore permitida: Channel é a linha `channels` (não um `catalog_node`),
Track opcional → Course → Module opcional → Lesson → MediaItem. `catalog_nodes`
representa Track/Course/Module/Lesson e Generic `unclassified`; mídia permanece
em `media_items`, associada à Lesson por `catalog_node_id`. Nós irmãos recebem
ordinal sequencial determinístico derivado da ordem de origem, com desempate
por tipo/código e ID de mensagem. Mensagens com vários itens de mídia preservam
`media_ordinal` da S2. Semântica final de desempate depende da gramática SP-02.

Título de catálogo é projeção de display; não altera `messages.text`, códigos
RASMOO ou filenames originais. Não normalizar/acoplar nome de arquivo ao título.

## 8. Catálogo SQLite e reprocessamento

Reutilizar a migration S2 `001_initial.sql`; não editá-la nem mudar a chave
Telegram. Nova migration numerada é aditiva e contém as constraints/índices
necessários. Como `catalog_nodes.id` é substituto e não há chave natural única,
introduzir tabela auxiliar de identidade com `channel_id`, `parser_key`,
`grammar_version`, `node_key` e `catalog_node_id`, chave única para a identidade
lógica e FK para o nó. `node_key` de nó ancorado em mensagem deriva de parser,
tipo, pai lógico e ID de mensagem/código validado; não deriva de título. Chave
Generic deriva do ID de mensagem. Mudança de título/ordem atualiza a mesma
entidade; mudança real de âncora não pode ser deduplicada por heurística.

`CatalogRepository` possui todas as queries, aplica migrações SQL, habilita
foreign keys, WAL e busy timeout já definidos, e faz transação única por
reprocessamento completo de um canal. Validar referências de origem contra
`messages(channel_id, telegram_message_id)`; `source_message_id` guarda o ID
Telegram no mesmo canal. Upsert de nó, tabela auxiliar de identidade,
`media_items.catalog_node_id`, key/parser do canal e resultado de catalog run
são atômicos. Falha faz rollback completo e mantém catálogo anterior.

Reprocessar mesma entrada, parser e versão de gramática produz as mesmas keys,
ordens e links: sem nós ou vínculos duplicados e sem timestamps/updates
artificiais quando nada mudou. Alterações de origem atualizam nós existentes.
Rows de mensagem/mídia S2 nunca são apagadas por parse. Nós antigos que não
aparecem em reparsing não são fisicamente removidos; ficam inativos por estado
de reconciliação aditivo, e associações históricas não são silenciosamente
destruídas. CLI distingue nó atual de obsoleto/inativo. Falha/incompletude de
parse não publica parcialmente um catálogo.

Cada associação de mídia tem no máximo um nó terminal por mensagem/ordinal;
conflito ou duplicata material falha o lote e reporta categoria segura. Foreign
keys e integridade são verificáveis em SQLite temporário. Qualquer mudança
necessária à forma exata da tabela auxiliar/estado inativo deve ser fechada na
migration de implementação, preservando essas invariantes e sem alterar schema
S2 existente.

## 9. Catalog CLI (Rich)

CLI consulta apenas o repository e oferece `catalog build`, `list`, `show` e
`items`. Build é explícito, exige `--channel-id` e consome somente dados S2
persistidos; `--parser-key` configura explicitamente o parser. `show`/`items`
aceitam `--channel-id` ou seleção numérica entre canais já catalogados:

1. listar canais catalogados, com título e `telegram_chat_id` para distinguir
   homônimos;
2. selecionar canal e mostrar parser, status/versão do catálogo e contagens;
3. listar Track/Course (incluindo curso sem Track), depois Module (incluindo
   aula sem Module), aulas e mídias;
4. exibir título/código, mensagem de origem, mídia, tipo, tamanho ou
   “desconhecido”; itens ambíguos, órfãos, genéricos e obsoletos têm seção
   explícita de não classificados;
5. inspeção é somente leitura. Build é a única ação que grava catálogo e só
   começa pelo comando explícito. Sem download, autenticação, Telegram ou
   reparse implícito em consultas.

Entradas vazias/Q cancelam o nível atual; índice inválido é rejeitado sem
efeito colateral; paginação pode ser simples, sem GUI. FR-13 exige tornar
visíveis os itens com tamanho desconhecido e o que não foi classificado. Não
expor IDs internos SQLite como identidade de usuário.

## 10. Falhas e limites

| Condição | Comportamento |
|---|---|
| parser key desconhecida | não substituir silenciosamente; preservar dados e reportar canal sem parser resolvido |
| marcador/caso não suportado ou ambíguo | preservar mensagem/mídias em unresolved, com categoria segura |
| pai ausente, ciclo, tipo/link inválido | abortar parse do canal; catálogo anterior permanece íntegro |
| mídia ou mensagem sem classificador | Generic/unresolved consultável, sem descarte |
| falha SQLite/FK/migration | rollback; erro `DatabaseError` sanitizado; sem sucesso parcial |
| reparse após edição/remoção | atualizar snapshot das relações numa transação completa; manter mensagens, mídias e nós obsoletos sem deleção física implícita |
| canal sem mensagens | resultado vazio válido, selecionável e consultável |

Sem retry automático nesta unidade. Logs não incluem texto de mensagem, nomes
de credenciais, sessão, corpo de exceção ou conteúdo de mídia. Escopo não
inclui sincronização de remoções remotas (S7).

## 11. Decisões materiais pendentes

1. **S3-OPEN-01 — semântica da gramática RASMOO.** Obter/validar amostra SP-02
   controlada e sanitizada sob autorização e orçamento reconciliados; adjudicar papel de
   `=`, `==`, `===`, `#Fxxx` e `#Docxxx`, título, contexto, órfãos, edição,
   duplicatas e ordem. Sem resolução: `RASMOO_GRAMMAR = NOT_FROZEN` e não
   implementar RasmooParser funcional.
2. **S3-OPEN-02 — reconciliação e identidade.** Implementados identity por
   canal/parser/versão/node key, IDs estáveis e nós ausentes inativos sem
   deleção. Falta adjudicar estabilidade das âncoras especializadas sob
   edição/reordenação com fixtures RASMOO.
3. **S3-OPEN-03 — limiar de detecção automática.** Autodetecção não está
   implementada. Decidir se será necessária e, se sim, definir limiar com
   evidência; até lá há configuração explícita ou fallback Generic.

### Disposição possível com a evidência atual

SP-02 capturou zero casos estruturais; a contagem remota efetiva é desconhecida.
S3-OPEN-01 permanece sem resolução. S3-OPEN-02 tem implementação provisória
validada para Generic, sem evidência de estabilidade das âncoras RASMOO.
S3-OPEN-03 permanece decisão aberta; não há autodetecção no código.
`RASMOO_GRAMMAR = NOT_FROZEN`; a validação offline não confirma a gramática
nem fecha S3.

## 12. Critérios de aceite propostos

- Contratos e seleção demonstram Rasmoo/Generic sem dependência de Telegram,
  Rich, SQL ou filesystem dentro dos parsers.
- Fixtures validam gramática aprovada, hierarquia, títulos, órfãos, mídia
  indexada/não indexada, mensagens sem mídia, desconhecidos, edições e ordem
  fora da sequência de chegada.
- Generic mantém todas as mensagens/mídias e identidade original sem criar
  curso/módulo/aula fictícios.
- Builder rejeita pais inválidos/ciclos e gera ordenação determinística.
- SQLite temporário: migration aditiva, FKs, rollback, referências de origem,
  upsert e reprocessamento idempotente; mesma entrada duas vezes não duplica
  nós/links nem altera estado quando a origem não mudou.
- Múltiplos canais com IDs/mensagens coincidentes permanecem isolados;
  identidade continua `telegram_chat_id` + `telegram_message_id` da S2.
- CLI Rich navega canais→trilhas/cursos→módulos→aulas/mídias e permite ver
  itens não classificados, tamanhos desconhecidos e canais/cursos sem nível
  opcional, rejeitando índices inválidos e cancelando sem mutação.
- Testes são offline, com fixtures sintéticas e SQLite temporário; cobrem que
  nenhum download, cliente Telegram, credencial ou banco real é acessado.
- Contrato aprovado, grammar open decisions resolvidas ou delimitadas, testes
  correspondentes e integração no fluxo S2 aceitos antes do fechamento S3.

```text
CONTRACT_APPROVAL = NOT_GRANTED
CONTRACT_FREEZE = NO
S3_IMPLEMENTATION_AUTHORIZATION = YES / OFFLINE GENERIC CORE ONLY
S3_STATUS = IN_PROGRESS / RASMOO AND FORMAL ACCEPTANCE PENDING
```

## 13. Checkpoint — núcleo offline genérico — 2026-10-10

Implementados modelos de origem, registry explícito com Generic fallback,
GenericParser sem inferência hierárquica, CatalogBuilder determinístico,
serviço offline, migration aditiva `002_catalog.sql`, repository SQLite com
identity por canal/parser/versão/node key, build transacional, nós obsoletos
inativos e comandos Rich `catalog build/list/show/items`. RASMOO não está
registrado nem implementado. Nenhum Telegram, credencial/sessão ou SQLite real
foi acessado; nenhum download ocorreu.

Validação: pytest completo 157 passed + 11 subtests em 182.02s; Ruff PASS;
`git diff --check` PASS. Fixtures sintéticas e SQLite temporário foram usados.
O contrato permanece DRAFT e S3 não está encerrada.
