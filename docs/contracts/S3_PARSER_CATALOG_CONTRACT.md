# S3 — Parser + Catalog CLI Contract

```text
DOCUMENT_ROLE = IMPLEMENTATION_CONTRACT
CONTRACT_STATUS = APPROVED / FROZEN_FOR_CONFIRMED_SP02_SCOPE
ACTIVITY = S3 — RasmooParser Integrated Implementation
S3_STATUS = IN_PROGRESS / RASMOO OFFLINE IMPLEMENTATION PASS; FORMAL ACCEPTANCE PENDING
RASMOO_PARSER_IMPLEMENTATION_AUTHORIZATION = GRANTED / OFFLINE_IMPLEMENTATION_AND_VALIDATION
S3_ENTRY_REVIEW = PASS / approved supported grammar and generic offline core available
S3_READINESS = PASS_FOR_CONFIRMED_SCOPE / implementation authorized
REAL_TELEGRAM_ACCESS = NO / this activity uses user-provided samples only
REAL_USER_SQLITE_ACCESS = NO
CREDENTIALS_OR_SESSION_ACCESS = NO
SP02_MESSAGE_COUNT = NOT_APPLICABLE / manual samples
SP02_SANITIZED_EVIDENCE = USER-CONFIRMED INDEX + THREE VIDEO POSTS + GENERAL RAR DOCUMENT POST
RASMOO_GRAMMAR = BASIC / SUPPORTED INDEX + MEDIA-POST FORMATS CONFIRMED
S3_OPEN_01 = BASIC GRAMMAR CONFIRMED
S3_OPEN_02 = DETERMINISTIC IDENTITY AND CONSERVATIVE RECONCILIATION
S3_OPEN_03 = EXPLICIT PARSER SELECTION
DOWNLOADS = NONE / REAL_LOCAL_PERSISTENCE = NONE
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
| Semântica dos marcadores RASMOO | CONFIRMADA PARA FORMATOS SUPORTADOS | Usuário confirmou marcadores de índice, forma de post de mídia, normalização, identidades `#F`/`#Doc` e reconciliação conservadora; ver §5. |
| Amostra controlada SP-02 | SUFICIENTE PARA INDEX + MEDIA_POST SUPORTADOS | Três posts de vídeo e um post RAR fornecidos manualmente; usuário confirmou suficiência para os formatos suportados. A tentativa remota histórica permanece inconclusiva e não foi repetida. |
| Parser, builder, persistência e CLI | EM IMPLEMENTAÇÃO | Implementação exclusivamente offline com fixtures SP-02 e banco SQLite temporário. `data/catalog.sqlite3` real permanece fora de escopo. |

Conclusão: a tentativa SP-02 remota anterior não produziu evidência utilizável
e não foi repetida. O usuário confirmou que as amostras manuais são suficientes
para a gramática suportada de INDEX_MESSAGE + MEDIA_POST, conforme §5. O
contrato está aprovado e congelado somente para o escopo confirmado de índice,
post de mídia e referência documental geral. Formatos não observados permanecem
fora das regras. S2 permanece fechada.

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
explicitamente. A seleção é sempre explícita por configuração: key conhecida
seleciona o parser configurado; configuração ausente seleciona Generic como
fallback. Key desconhecida reporta `UNKNOWN_PARSER_KEY`, sem conversão
silenciosa. Não há autodetecção nem limiar de detecção. Esta decisão resolve
S3-OPEN-03. RASMOO só poderá ser registrado após evidência/decisão de gramática
e autorização específica. Generic não declara correspondência exclusiva.

## 5. RASMOO: gramática básica dos formatos suportados

### Evidência manual recebida

Os exemplos abaixo substituem títulos por identificadores sintéticos; as
quebras de linha, espaços observados, ordem interna e formato dos marcadores
foram preservados. Fragmentos diferentes não são concatenados nem ordenados
entre si sem confirmação da posição original.

Índice hierárquico, fragmento A:

```text
= 04 <TITULO-01>
== 01 <TITULO-02>
=== 01 <TITULO-03>
#F001 #F002 #F003 #F004 #F005 #F006 #F007 #F008 #F009 #F010 #F011 #F012 #F013 #F014 #F015
```

Índice hierárquico, fragmento B:

```text
=== 03 <TITULO-04>
#F016 #F017 #F018 #F019 #F020
```

Esses fragmentos mostram `=`, `==`, `===` em ordem hierárquica crescente,
seguidos de título numerado; a linha de referências `#F` vem após o título
`===` nos dois fragmentos. A interpretação confirmada pelo usuário é `=` =
Track, `==` = Course e `===` = Module. As referências `#Fxxx` listadas sob
um Module apontam para conteúdo/aulas, não para IDs de mensagens Telegram.

Posts de vídeo (`MEDIA_POST`) têm a forma `#Fxxx <ordinal> <título da aula>`,
seguida pelo caminho Track (sem marcador) → Course (`=`) → Module (`==`). A
mídia anexada ao mesmo post é material daquela Lesson. Três posts com
`#F001`, `#F002`, `#F003` têm títulos de aula distintos sob o mesmo contexto
Track/Course/Module. Além disso, `#F567` aparece sob um Module no índice e no
post correspondente com caminho compatível. Portanto `#Fxxx` é uma referência
de conteúdo que identifica a Lesson/post no domínio; não é `telegram_message_id`.
Para ligar mídia, usar a identidade da mensagem e `media_ordinal` já persistidos
na S2, sem substituir esses identificadores pela referência `#F`.

O formato observado no índice tem linhas iniciadas por `=`, `==`, `===`, com
espaço após o marcador em um exemplo (`= 04 ...`). Nos posts de vídeo, o caminho
começa por um título sem marcador e continua com linhas `=01 ...` e `==01 ...`
sem espaço após os marcadores. Os títulos do post `04 O mercado` → `LinkedIn
Hacks` → `Turbine o seu LinkedIn` correspondem ao índice com um marcador
adicional no primeiro nível (`=`, `==`, `===` no índice; sem marcador, `=`,
`==` no post). Tratar isso como duas formas de origem distintas e normalizar
ambas para a mesma árvore Track → Course → Module → Lesson. O espaço depois do
marcador varia nos exemplos e deve ser preservado na origem; a leitura aceita
as formas observadas. A regra preparatória anterior de tokens isolados está
superada.

Para documentos, a linha `#Doc001` aparece sob o cabeçalho `Documentos` e o
mesmo marcador aparece num post com um arquivo `.rar`. O usuário confirmou que
é referência documental geral, não um vídeo nem anexo específico de `#F001`.
Sem contexto adicional, não atribuir o documento a um curso específico. Usar o
código `#Docxxx` como identidade de referência documental, sem associá-lo à
Lesson de vídeo.

### Regras confirmadas

Classificar a forma da origem como `INDEX_MESSAGE`, `MEDIA_POST` ou
`DOCUMENT_POST`; não tratar todas as mensagens como uma única forma lexical.
Percorrer texto por linha e preservar texto, espaços, ordem da mensagem e
identidade da mensagem S2. Aceitar as formas confirmadas sem assumir que o
comprimento numérico observado (`xxx`) é uma validação universal.

| Forma de origem | Sintaxe/semântica confirmada |
|---|---|
| `INDEX_MESSAGE` | `=` abre/identifica Track; `==` Course sob Track; `===` Module sob Course. Referências `#Fxxx` listadas sob Module apontam para Lessons/conteúdos. |
| `MEDIA_POST` | `#Fxxx <ordinal> <título>` identifica a Lesson. As linhas seguintes identificam Track sem marcador, Course com `=`, Module com `==`. A mídia anexada à postagem é material dessa Lesson. |
| `DOCUMENT_POST` | `#Docxxx` identifica referência documental; a postagem pode conter um arquivo RAR. É documental geral, não vídeo nem material específico de Lesson. Sem contexto explícito, não atribuir curso exato. |
| Normalização | Index e post de mídia convergem para Track → Course → Module → Lesson. O mesmo caminho pode aparecer com níveis de marcador deslocados conforme o formato de origem; preservar o texto original. |

Quando um marcador de índice abre nível igual ou ancestral, substituir apenas o
contexto descendente corrente na projeção; não apagar entidades persistidas.
Um `#Fxxx` de índice associa-se ao MEDIA_POST somente quando a referência é
igual e Track/Course/Module são compatíveis. O `#Fxxx` é uma chave semântica,
nunca `telegram_message_id`. A ordem de aulas/mídias vem da ordem persistida
das mensagens e `media_ordinal`; não ordenar pelo número em `#Fxxx`.

Para cada mídia, preservar a identidade S2 `(channel_id,
telegram_message_id, media_ordinal)`. Referência sem post compatível, contexto
incompatível, duplicata conflitante ou #Doc sem curso explícito permanecem
consultáveis como unresolved/general; não ligar por proximidade, não reparentar
e não apagar estrutura por inferência.

Coleta automatizada SP-02 não foi realizada nesta atividade. Uma tentativa
remota anterior permanece inconclusiva; as evidências deste checkpoint vieram
somente das amostras manuais fornecidas pelo usuário.

A gramática acima está confirmada para os formatos amostrados; o usuário
aprovou e congelou somente este escopo para a implementação do `RasmooParser`.
Fora de `INDEX_MESSAGE`, `MEDIA_POST` e da referência
`DOCUMENT_POST` observada, conservar o texto de origem e as mensagens/mídias
sem ligação por proximidade especulativa. Marcadores ou formas não observados
ficam `UNKNOWN_MARKER`/unresolved; não encerram contexto nem criam nós. Títulos
originais são preservados e títulos/códigos de exibição não substituem a
identidade semântica.
| mensagens fora de ordem | usar ordem persistida S2 para mensagens; `#Fxxx` não é ordem nem message_id |
| órfãos/edições | preservar origem e referências não resolvidas; contexto incompatível nunca reatribui identidade automaticamente |
| repetição/desconhecidos | reprocessamento idempotente; conflitos/desconhecidos unresolved; ausência não implica deleção |

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
Track opcional → Course → Module opcional → Lesson → MediaItem. Documentos
gerais `#Docxxx` são nós terminais sem associação implícita a Course/Lesson.
`catalog_nodes` representa esses nós, Track/Course/Module/Lesson e Generic
`unclassified`; mídia permanece em `media_items`, associada à Lesson por
`catalog_node_id` somente quando a referência é resolvida. Nós irmãos recebem
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
lógica e FK para o nó. Chaves de Track/Course/Module derivam do tipo e do
caminho numerado de títulos sob o pai lógico. A Lesson usa a referência literal
`#Fxxx` como identidade semântica dentro do escopo
`(channel_id, parser_key, grammar_version)`; `#Fxxx` nunca é convertido em
`telegram_message_id`. Documento usa namespace separado pela referência literal
`#Docxxx`; sem contexto explícito, fica como documento geral/não atribuído.
Títulos são atributos, não identidade de Lesson. Chave Generic continua
derivada do ID de mensagem conforme sua implementação existente. Referência
repetida em contexto incompatível não é movida nem deduplicada por heurística:
preservar a ocorrência como unresolved.

`CatalogRepository` possui todas as queries, aplica migrações SQL, habilita
foreign keys, WAL e busy timeout já definidos, e faz transação única por
reprocessamento completo de um canal. Validar referências de origem contra
`messages(channel_id, telegram_message_id)`; `source_message_id` guarda o ID
Telegram no mesmo canal. Upsert de nó, tabela auxiliar de identidade,
`media_items.catalog_node_id`, key/parser do canal e resultado de catalog run
são atômicos. Falha faz rollback completo e mantém catálogo anterior.

Reprocessar a mesma entrada, parser e versão de gramática produz as mesmas
keys, ordens e links: sem nós/vínculos duplicados e sem timestamps/updates
artificiais quando nada mudou. Posts com o mesmo caminho reutilizam as mesmas
chaves de Track/Course/Module; `#Fxxx` distinto cria Lesson distinta. Alteração
de título em `#Fxxx` atualiza o atributo mantendo a identidade; conflito de
código ou contexto não reparenta a Lesson automaticamente.

Rows de mensagem/mídia S2 nunca são apagadas por parse. Referências/mensagens
não resolvidas são gravadas por execução em `catalog_unresolved_sources` e
expostas em `catalog items`; o motivo e a mensagem de origem permanecem
consultáveis mesmo sem vínculo de Lesson. MediaItem é sempre
endereçado por `(channel_id, telegram_message_id, media_ordinal)` persistido na
S2; `#Fxxx` apenas resolve a Lesson de destino. Referências não resolvidas
permanecem consultáveis com a origem intacta. Nenhuma estrutura é fisicamente
apagada. Ausência, snapshot parcial/falho ou ambiguidade não inativa nem remove
estrutura anterior por inferência. Inativação só ocorre após evidência explícita
e reconciliação autorizada; remoção remota continua fora do escopo S3. CLI
distingue nó atual de obsoleto/inativo. Falha/incompletude de parse não publica
parcialmente um catálogo.

Nota de compatibilidade: o `CatalogRepository` não apaga fisicamente nós.
Desativação e limpeza dos vínculos da identidade selecionada ocorrem somente
após um parse completo sem referências unresolved. Em parse parcial/ambíguo,
preserva nós ativos e vínculos prévios e grava as incertezas aditivamente.

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

## 11. Disposição das decisões materiais

1. **S3-OPEN-01 — gramática básica. RESOLVIDO para INDEX_MESSAGE e MEDIA_POST
   suportados.** Marcadores, níveis, #F, #Doc, normalização comum e associação
   conservadora estão definidos acima. Fora desses formatos, manter conteúdo
   e relações em unresolved; não generalizar regras não amostradas. O escopo
   confirmado está aprovado e congelado para esta implementação.
2. **S3-OPEN-02 — identidade e reconciliação. RESOLVIDO COMO DECISÃO.**
   Identidade composta por canal/parser/versão/chave semântica; Lesson por
   `#Fxxx`, documento por `#Docxxx`, nós estruturais por caminho hierárquico.
   Reprocessamento idempotente, referências ambíguas preservadas, sem
   reparenting por inferência e sem deleção física; snapshot incompleto não
   desativa estruturas.
3. **S3-OPEN-03 — seleção de parser. RESOLVIDO nesta atividade.** Seleção
   explícita pela configuração do canal; configuração ausente usa Generic como
   fallback; key desconhecida é erro. Não há autodetecção e, portanto, não há
   limiar a definir.

### Disposição atual

Tentativa remota anterior de SP-02 capturou zero casos estruturais; a contagem
efetiva permanece desconhecida. Esta atividade não repete coleta remota.
O usuário confirmou que as evidências são suficientes para a gramática
suportada de índice + post de mídia; não solicitar novos exemplos para
reconfirmar. `S3-OPEN-01 = BASIC_GRAMMAR_CONFIRMED`;
`S3-OPEN-02 = DETERMINISTIC_IDENTITY_AND_CONSERVATIVE_RECONCILIATION`;
`S3-OPEN-03 = EXPLICIT_PARSER_SELECTION`. O contrato está aprovado e congelado
somente para o escopo suportado. Entradas ambíguas/fora do formato permanecem
unresolved e não apagam ou reparentam estruturas.

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
GRAMMAR_SCOPE_APPROVAL = GRANTED_BY_USER
CONTRACT_APPROVAL = GRANTED / SUPPORTED_SP02_SCOPE_ONLY
CONTRACT_FREEZE = PASS / SUPPORTED_SP02_SCOPE_ONLY
S3_IMPLEMENTATION_AUTHORIZATION = YES / OFFLINE RASMOO PARSER AND INTEGRATION
S3_STATUS = ACCEPTED / CLOSED
S3_FORMAL_ACCEPTANCE = APPROVED
```

## 13. Checkpoint — núcleo offline genérico — 2026-10-10

Implementados modelos de origem, registry explícito com Generic fallback,
GenericParser sem inferência hierárquica, CatalogBuilder determinístico,
serviço offline, migration aditiva `002_catalog.sql`, repository SQLite com
identity por canal/parser/versão/node key, build transacional, nós obsoletos
inativos e comandos Rich `catalog build/list/show/items`. Nenhum Telegram,
credencial/sessão ou SQLite real foi acessado; nenhum download ocorreu.

Validação do núcleo genérico: pytest completo 157 passed + 11 subtests em
182.02s; Ruff PASS; `git diff --check` PASS. Fixtures sintéticas e SQLite
temporário foram usados. O aceite integrado posterior concluiu S3.

## 14. Aceite formal S3 — S3-CLOSE-01 — 2026-10-10

O escopo S3 está aceito e fechado para a gramática RASMOO comprovada. O parser,
catálogo real com escopo limitado, idempotência, compatibilidade Windows e
regressão completa passaram conforme registrado em
[PROJECT_STATE](../continuity/PROJECT_STATE.md). A coleta real abrangeu 30
mensagens e 26 mídias e terminou em `MESSAGE_LIMIT`; não comprova cobertura do
canal inteiro. Duas referências unresolved foram preservadas. Downloads não
foram validados; a validação integral do produto permanece prevista para S9.

```text
S3_STATUS = ACCEPTED / CLOSED
S3_FORMAL_ACCEPTANCE = APPROVED
S3_GENERIC_CORE = PASS
RASMOO_PARSER = PASS
S3_MAG_01 = PASS
REAL_CATALOG_VALIDATION = PASS_WITH_SCOPE
IDEMPOTENCY = PASS
WINDOWS_CLI_COMPATIBILITY = PASS
FULL_REGRESSION = PASS / 167 passed + 11 subtests
RUFF = PASS
DIFF_CHECK = PASS
S4_STATUS = PLANNED / NOT_STARTED
S4_IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
```
