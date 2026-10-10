# S1-D — Channel Discovery & Selection

```text
DOCUMENT_ROLE = IMPLEMENTATION_CONTRACT
CONTRACT_STATUS = FROZEN / ACCEPTED
CONTRACT_APPROVAL = APPROVED_BY_USER_2026-10-09
CONTRACT_FREEZE = PASS / GOV-01 RESOLVED
RECORDED_AT = 2026-10-08 / America/Sao_Paulo
ACTIVITY = S1-D implementation and offline validation checkpoint
EXECUTION_MODE = DIRECT
ROOT_MODEL_TARGET = GPT-6 SOL / MEDIUM
ROOT_RUNTIME_MODEL = GPT-6 / variante e effort não verificáveis nesta superfície
CONTRACT_DRAFT_AUTHORIZATION = HISTORICAL / 2026-10-08
S1D_IMPLEMENTATION_AUTHORIZATION = EXPLICIT_USER_APPROVAL_2026-10-09 / IMPLEMENTED_OFFLINE
S1D_STATUS = CLOSED / functional acceptance and formal closure PASS
S1D_ENTRY_REVIEW = PASS / informado pelo usuário; relatório local não localizado
S1D_DOR = PASS / implementation, acceptance, freeze, and formal closure complete
PYTEST_REVALIDATION = PASS / section 20
ACTIVE_ARCHITECTURAL_DECISION = DEC-S1D-03 / APPROVED / D_PLUS_C
PROVE_ZERO_GET_DIFFERENCE = SUPERSEDED
CONTRACT_REVIEW_STATUS = APPROVED_BY_USER_2026-10-09 / FROZEN
OPEN-03 = NUMERIC_BASELINE_APPROVED / operational calibration PASS
GOV-01 = RESOLVED / KEEP_PINNED_BASELINE
```

O registro arquitetural vigente é [DEC-S1D-03](../governance/APPROVALS_AND_DECISIONS.md#dec-s1d-03--lifecycle-de-diferenças-internas), aprovada após a auditoria independente. As seções 1–10, 12 e 19 compõem a proposta consolidada atual; 13–17 são snapshots históricos, e 18 preserva a decisão aprovada (seu antigo snapshot de pendências é sucedido pela seção 19). A seção 11 preserva evidência prévia de GOV-01, sem nova investigação. As conclusões e ressalvas da auditoria Astra permanecem intactas no [relatório independente](../audit/S1D_INDEPENDENT_ARCHITECTURE_REVIEW_2026-10-08.md). Aprovação contratual, freeze, implementação e aceite têm gates separados.

## 1. Objetivo, authority e escopo

Definir a descoberta de canais e seleção local por identidade estável, para
FR-02, sobre o gateway autenticado existente. O contrato foi aprovado pelo
usuário, implementado e aceito; as seções 20 e 21 registram aprovação,
calibração, freeze e encerramento formal. S1-A/B/C permanecem PASS; S1-D e S1
estão CLOSED.

Authorities de produto e arquitetura:

- [REQUIREMENTS](../product/REQUIREMENTS.md): FR-01/02/15/16 e NFR-04/05/06/08/09/10; acesso legítimo.
- [ARCHITECTURE](../architecture/ARCHITECTURE.md): gateway, ADR-002/006/008, modelos próprios, CLI e ownership de retry.
- [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md): identidade de canal, taxonomy, proteção, logging e testes separados.
- [SPRINTS — S1/S2](../continuity/planning/SPRINTS.md): descoberta antes do scanner; identidade como saída para S2.
- [APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md): decisões humanas já registradas, especialmente sessão e retry.
- [S1-A](S1A_PROTECTED_SESSION_IMPLEMENTATION_CONTRACT.md) e [S1-B](S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md): contratos frozen, dependências por referência, sem cópia ou nova implementação de login/vault.
- [ACTIVE_AUTHORITY_MAP](../continuity/ACTIVE_AUTHORITY_MAP.md) e [binding](../continuity/PROJECT_GOVERNANCE_BINDING.json): resolução e ressalva de integridade na seção 11.

As cópias locais PM-01 v1.0, PM-02 v1.7-R2.6 e PM-03 v1.7-R2.3 foram
consultadas nos trechos materialmente aplicáveis: condução, DoR, continuidade,
DIRECT, autoridade humana, runtime e revisão final. PM-05 local orienta a
separação de fato, inferência e recomendação. A identidade por hash dessas
cópias não foi validada contra a adoção; não tratá-las como pins verificados.

Escopo proposto: enumerar candidatos, projetar metadados mínimos, apresentar
uma lista na CLI e selecionar um canal em memória. Não implementar catálogo,
SQLite, scanner, parsers, downloads, busca pública, convite/join, escrita remota,
mark-as-read, exportação, persistência da escolha, nova dependência ou mudança
de governança. Não usar conteúdo de mensagem para detectar canais de cursos.

## 2. Decisões aprovadas e decisões técnicas

FECHADA_POR_AUTHORITY significa obrigação já sustentada; DETALHE_TECNICO_PROPOSTO
significa solução do draft, ainda sujeita à aprovação do contrato inteiro.
Nenhum desses estados significa aprovação humana deste documento.

| Tema | Proposta / conclusão | Estado e base |
|---|---|---|
| A. Descoberta | `TelegramGateway.discover_channels` com paginação direta sequencial de `messages.GetDialogsRequest` | Proposta consolidada da seção 4; DEC-S1D-01 preservada; valores dependem de aprovação OPEN-03 |
| B. Tipos próprios | `ChannelSummary`, `DiscoveryResult`, `SelectedChannel` e erros próprios | FECHADA_POR_AUTHORITY: ADR-002; detalhes na seção 3 |
| C. Identidade | `telegram_chat_id` inteiro marcado, nunca título/username | FECHADA_POR_AUTHORITY: identidade Telegram na Foundation; representação proposta na seção 3 |
| D. Elegibilidade | Broadcast channels e megagroups/supergroups; excluir basic groups, diálogos de usuários/bots e secret chats | DECISÃO APROVADA: DEC-S1D-02; classificação própria e explícita |
| E. Seleção | Escolha em snapshot local por ID exato; sem nova chamada Telegram | DETALHE_TECNICO_PROPOSTO compatível com FR-02 |
| F. Falhas | Vazio é resultado; escolha ausente/ambígua é inválida; acesso não garantido no futuro | DETALHE_TECNICO_PROPOSTO; não contornar falhas de acesso |
| G. Auth/sessão | Reusar sessão válida via `restore`; se ausente/inválida, encerrar com orientação ao comando `auth` existente e exigir nova invocação de descoberta | DECISÃO TÉCNICA FECHADA pelas authorities S1-A/B e ADR-008; sem login duplicado ou inline |
| H. Exceções/FloodWait | Erros próprios; espera/retry na aplicação; sem sleep no adapter | FECHADA_POR_AUTHORITY: ADR-008; taxonomy de descoberta é proposta |
| I. Ownership | CLI apresenta; aplicação coordena; adapter é único dono de operações Telegram | FECHADA_POR_AUTHORITY: Architecture/Foundation |
| J. Boundary | Projetar tipos próprios antes de retornar; TL types e access hash privados | FECHADA_POR_AUTHORITY: ADR-002 |

| ID | Decisão material OPEN | Recomendação e alternativa |
|---|---|---|
| OPEN-03 / GAP-01 | Aprovação do orçamento operacional inicial | OPTION_1 preservada; proposta explícita na seção 4, implementação posterior e calibração durante implementação/aceite com autorização real própria; não exigir medição real prévia ao contrato. OPEN-03 não fechado. |
| OPEN-04 | Decisão arquitetural sobre RPCs internos de diferenças | RESOLVED_BY_DEC-S1D-03 = APPROVED / D_PLUS_C. Validação técnica do comportamento e isolamento da aplicação permanece PENDING; ver seção 18. Não exigir `GET_DIFFERENCE_COUNT = 0`. |

OPEN-03 exige aprovação dos valores; GOV-01 permanece bloqueio externo de freeze. Revalidação pytest é baseline necessária no gate de implementação; validação do novo comportamento pertence ao aceite. As
decisões DEC-S1D-01/02/03 estão aprovadas e registradas; não aprovam o contrato inteiro.
Nomes públicos e layout de arquivos podem ser ajustados no freeze sem alterar
a semântica aqui descrita.

## 3. Interfaces, modelos próprios e identidade

Assinaturas conceituais propostas, sem implementação:

```text
TelegramGateway.discover_channels(request: DiscoveryRequest) -> DiscoveryResult  [async]
ChannelDiscoveryApplication.discover_and_select(...) -> SelectionOutcome        [async]
select_channel(snapshot: DiscoveryResult, telegram_chat_id: int) -> SelectedChannel [local]
```

`DiscoveryRequest` transporta somente limites aprovados e política de cobertura;
não recebe username, telefone, sessão, TL object ou segredo. Valores/defaults
numéricos propostos estão na seção 4 e dependem de aprovação OPEN-03. A aplicação controla deadline/cancelamento; o
adapter controla paginação e valida os limites antes do primeiro RPC.

Modelos imutáveis próprios propostos:

- `ChannelSummary(telegram_chat_id: int, title: str, username: str | None,
  kind: ChannelKind)`. Metadados servem à apresentação; username pode faltar.
  Sem message, last_message, text, media, draft, access_hash ou client.
- `ChannelKind`: BROADCAST_CHANNEL ou MEGAGROUP; classificação própria explícita
  antes do retorno. Não inferir tipo por título; peers fora da elegibilidade
  aprovada não aparecem na lista.
- `DiscoveryResult(channels: tuple[ChannelSummary, ...], complete: bool,
  stop_reason: DiscoveryStopReason | None, stats: DiscoveryStats)`. `DiscoveryStats`
  contém páginas solicitadas/recebidas, diálogos brutos recebidos/projetados,
  candidatos únicos, tempo monotônico decorrido e orçamento efetivo, sem cursores,
  IDs de mensagem, conteúdo ou TL objects. `complete` significa esgotamento
  da enumeração dentro da cobertura aprovada, nunca todos os canais acessíveis
  do Telegram. Limite atingido produz PARTIAL/LIMIT_REACHED, não EMPTY completo.
- `SelectedChannel(telegram_chat_id: int)` como identidade de saída para S2;
  sem garantia de acesso futuro, sem carregar TL objects. Metadados de exibição
  podem ser consultados no snapshot enquanto ele existir.
- `SelectionOutcome`: SELECTED, EMPTY, CANCELLED, AUTH_REQUIRED,
  SESSION_INVALID, INCOMPLETE_EMPTY (parcial sem candidatos), ou falha controlada.
  Nenhum estado não selecionado fornece ID. `DiscoveryStopReason` distingue
  RAW_DIALOG_LIMIT, PAGE_LIMIT e TIME_BUDGET; COMPLETE usa `stop_reason=None`.

Proposta de representação: para um peer de canal com ID positivo `n`, usar
`telegram_chat_id = -(1_000_000_000_000 + n)`, conforme
`telethon.utils.get_peer_id` instalado. Isso NÃO é concatenação textual de
`-100` ao decimal. Exemplo sintético: `n=123` → `-1000000000123`.
Megagroups usam o mesmo namespace PeerChannel; chats básicos usam `-n`, usuários
`+n`. Não aceitar um inteiro positivo de canal como identidade canônica nem
converter um ID arbitrário só porque tem prefixo visual parecido.

No adapter, calcular/verificar o ID a partir de PeerChannel/Channel e conferir
round-trip com `resolve_id`; fora dele só há inteiro próprio validado. Rejeitar
bool, zero, texto inválido e ID ausente no snapshot. A CLI pode interpretar
uma string decimal estrita para inteiro, mas a aplicação valida a identidade.
O título/username muda sem alterar a escolha. Unicidade/deduplicação é por ID;
colisões incompatíveis falham de forma controlada. Migração de chat básico
para supergrupo pode mudar identidade; S1-D não inventa equivalência/migração.
S2 deve usar a mesma identidade canônica na integração futura, sem definir
migrations/banco neste draft.

## 4. Elegibilidade, cobertura e seleção

DEC-S1D-02: aceitar `types.Channel` como BROADCAST_CHANNEL somente quando
`broadcast=True` e `megagroup=False`, ou MEGAGROUP somente quando
`broadcast=False` e `megagroup=True`, sem `left`/restrição impeditiva conhecida.
Excluir ChannelForbidden, ChatForbidden, usuários/bots, chats básicos, secret
chats, Channel sem classificação elegível e tipos desconhecidos. Flags
ambíguas/inconsistentes não são aceitas por adivinhação.
`is_channel` isoladamente é insuficiente: Telethon também o define para
megagroups. Um megagroup pode ser supergroup/forum conforme flags conhecidos;
classificá-lo explicitamente como MEGAGROUP não atribui permissões administrativas.
Não realizar RPC adicional para classificar cada item; usar metadados recebidos.
Proteção de conteúdo nunca é contornada; esta lista não prova permissão para
baixar e não adjudica suporte de download de um canal protegido.

A enumeração candidata consulta `getDialogs` com cobertura de todas as pastas
(`folder=None`), fixados incluídos e chats básicos migrados excluídos da lista.
`iter_dialogs(ignore_migrated=True, folder=None, ignore_pinned=False)` é uma
alternativa histórica de menor código, mas a API escolhida nesta proposta é GetDialogsRequest direto, conforme OPEN-03 abaixo.
Cobertura significa diálogos da conta autenticada enumeráveis nessa operação;
não implica todos os canais existentes ou acessíveis por outros caminhos.
`complete=True` somente quando a enumeração termina normalmente; uma enumeração
limitada/interrompida é explicitamente `PARTIAL` e nunca `EMPTY` completo apenas
porque não encontrou candidato antes do corte. Snapshot parcial pode ser
apresentado como parcial e selecionado localmente por ID, com a limitação visível.
Cancelamento resulta em `CANCELLED`, sem seleção/ID; falha de rede/rate limit
resulta em erro controlado e não vira resultado bem-sucedido. Não usar `limit=0`
como consulta sem conteúdo: a biblioteca ainda faz getDialogs com limit=1. Os
valores propostos de diálogos/páginas/prazo aguardam aprovação OPEN-03; nenhum corte pode
ser silencioso. Ao atingir um limite sem prova de exaustão, marcar PARTIAL,
inclusive quando o último item coincide com o limite; uma sonda adicional só
pode ocorrer se estiver dentro de todos os orçamentos aprovados.

A CLI mostra ID, título e username opcional; escapes de terminal/markup devem
ser tratados como texto sem executar sequências. Não mostrar previews, drafts,
mensagens, mídia ou IDs de mensagem. Um ordinal visual, se existir, resolve
para ID naquele snapshot; não é chave de seleção/persistência. Escolha inválida
não dispara busca, resolve_username, auto-select, fallback ao primeiro item ou
novo RPC. Lista completa sem elegíveis retorna EMPTY; cancelamento retorna
CANCELLED. Snapshot parcial deve ser rotulado como parcial e a seleção vale
apenas para seus candidatos. Falha RPC/FloodWait interrompe a operação e não
expõe um resultado parcial como se tivesse sucesso.

Acessibilidade observada na descoberta é temporal. Selecionar localmente não
consulta o canal e não garante leitura futura; uma falha de acesso durante a
enumeração torna a operação controladamente falha. Um peer forbidden recebido
é excluído, não contornado. Revalidação remota antes de scanner pertence a S2
e exige seu contrato/autorização; não ler história para verificar seleção.

### OPEN-03 — orçamento inicial proposto, algoritmo e aprovação pendente

FATO: a instalação Telethon 1.45.0, inspecionada estaticamente em
`.venv-replay/Lib/site-packages/telethon/client/dialogs.py`,
`_DialogsIter._init/_load_next_chunk`, usa chunks de até 100. Seu limite conta
itens emitidos após filtros; não prova limite bruto nem de páginas. O método
oficial [messages.getDialogs](https://core.telegram.org/method/messages.getDialogs)
define offsets e inclui mensagens/entidades. A [documentação de paginação](https://core.telegram.org/api/offsets)
descreve limites e offsets. Consulta pública em 2026-10-08, sem Telegram RPC,
conta ou sessão; o código da versão instalada é a referência de compatibilidade.

RECOMENDAÇÃO (não medição nem decisão aprovada): adotar o orçamento abaixo
para a primeira implementação. Não existe amostra real de volume/latência
suficiente para afirmar que os números cobrem a conta. Por isso
`OPEN-03 = PENDING_USER_APPROVAL`, sem fechamento nesta atividade.

| Parâmetro configurável | Proposta inicial | Fundamentação e incerteza |
|---|---:|---|
| `page_size` | 100 diálogos | Chunk da versão instalada; menos viagens para a mesma cobertura. Redutível para 1..100; não é promessa de tamanho de payload em bytes. |
| `max_raw_dialogs` | 1.000 | Envelope inicial de dez chunks cheios, sem filtro de tipo; mantém lista e trabalho finitos. Escolha operacional proposta, sem evidência de volume da conta ou de suficiência universal. |
| `max_pages` | 20 | Permite configurar páginas de 50 para o mesmo envelope de 1.000, com teto independente para chamadas de continuação/sonda. Com páginas de 100, o teto bruto normalmente é atingido antes. Não aumenta o teto bruto nem autoriza loops sem progresso. Não é limite oficial do Telegram. |
| `operation_timeout_seconds` | 120 | Premissa de planejamento: 20 s para configuração/restore + até 20 páginas a 5 s = 120 s. Não são latências medidas nem reserva garantida por etapa; é um deadline único. |
| `cleanup_timeout_seconds` | 10 | Janela separada proposta para disconnect/cancelamento de tarefas; evita espera indefinida. Não há medição do pior caso; máximo cooperativo planejado da fase conectada + cleanup = 130 s. |

Todos os valores devem ser finitos, positivos, explícitos e configuráveis na
configuração da aplicação; contagens inteiras rejeitam bool, zero, negativos,
NaN/infinito e coerção silenciosa. Configuração inválida falha antes de client/
restore/RPC. O orçamento efetivo acompanha o resultado. Mudança material dos
valores aprovados exige decisão registrada; não aumentar automaticamente ao
atingir um limite. A entrada humana local ocorre após disconnect e não consome
o orçamento conectado.

#### Algoritmo proposto para implementação e teste

1. Validar configuração antes de criar/conectar o client dedicado. Iniciar
   relógio monotônico antes de restore, com deadline total incluindo restore,
   inicialização incidental, paginação, projeção e esperas internas.
2. Uma única requisição getDialogs por vez, `hash=0`, `folder_id=None`,
   primeira página com `exclude_pinned=False`, `offset_id=0`,
   `offset_date=None`, `offset_peer=InputPeerEmpty`. Cobertura: diálogos
   visíveis enumeráveis da conta, incluindo arquivados e fixados; fixtures e
   aceite real devem confirmar essa cobertura na versão usada. Nenhuma busca
   pública, enriquecimento por peer ou leitura de histórico.
3. Antes de cada chamada verificar cancelamento, tempo, páginas restantes e
   saldo bruto. Solicitar `limit=min(page_size, max_raw_dialogs-raw_received)`.
   Reservar/incrementar o contador de página antes de chamar; contar inclusive
   resposta vazia, repetida ou não elegível. Não iniciar nova página com saldo
   zero. Todos os diálogos da resposta, antes de qualquer filtro, consomem
   orçamento bruto, inclusive duplicatas, migrados e diálogos de pasta.
4. Projetar apenas canais elegíveis por ID marcado, deduplicando por ID. Não
   parar por lista filtrada vazia. Payload da página não é acumulado como
   catálogo. Cursor e resolução de InputPeer ficam exclusivamente no adapter.
5. Para continuar, usar o último diálogo bruto paginável com top_message
   correspondente: associação por peer + ID (IDs de mensagem não são globais),
   obter apenas ID/data para cursor e InputPeer da entidade correspondente da
   própria resposta. Excluir fixados nas páginas seguintes. Não usar
   `messages[-1]`, último candidato elegível, título ou username como cursor.
   Ler ID/data/peer incidental exclusivamente para navegação é operação de
   protocolo permitida no adapter por DEC-S1D-01; nunca ler texto/media/draft
   nem retornar/persistir/logar cursor. Não criar custom.Dialog ou chamar
   métodos privados em produção para reproduzir o iterador.
6. Ausência de cursor coerente quando ainda há continuação, cursor repetido,
   ciclo de cursores ou página que não avança → ADAPTER_FAILURE, sem seleção.
   Não fabricar offsets, buscar mensagens para preenchê-los ou considerar fim
   por todos os itens terem sido filtrados. DialogFolder não é candidato:
   tratar como entrada de protocolo; se a cobertura de pasta não puder ser
   comprovada por esta enumeração, falhar controladamente em vez de COMPLETE.
7. Evidência de fim: `messages.Dialogs` terminal válido; ou
   `DialogsSlice` com página menor que o limit solicitado (incluindo vazia),
   consistente com a enumeração/cursores e sem indicação contraditória de
   continuação. É a regra de término da versão instalada, sujeita a fixtures
   de conformidade. `count` isolado, total de candidatos, buffer filtrado vazio,
   prazo vencido e limite local nunca provam fim. `DialogsNotModified` sem
   cache próprio, constructor inesperado ou count que contradiga o fim →
   ADAPTER_FAILURE. Página cheia exige continuação/sonda dentro de todos os
   orçamentos; sem saldo para comprovar fim → PARTIAL.
8. Não exceder deliberadamente o saldo bruto solicitado. A primeira página
   (`exclude_pinned=False`) pode conter diálogos fixados adicionais além do
   `limit` solicitado. Aceitar esse excedente somente quando a quantidade de
   linhas excedentes não superar a quantidade de diálogos explicitamente
   marcados `pinned=True`; contar todas as linhas recebidas no orçamento bruto.
   Qualquer outro excedente ao limit, qualquer excedente com
   `exclude_pinned=True` ou qualquer resposta acima do saldo bruto deve falhar
   sem seleção e registrar somente metadados sanitizados. Isso não é lookahead
   da aplicação: é um excedente da resposta da API, e a próxima chamada continua
   usando cursor próprio e `exclude_pinned=True`. Não há garantia absoluta sobre
   itens/bytes já recebidos/desserializados de servidor anômalo.

`max_pages` limita chamadas lógicas de getDialogs emitidas pelo adapter,
não todos os RPCs/transmissões/retries internos do Telethon. Retry settings
aprovados permanecem; nenhuma segunda política de retry/sleep é adicionada.
GetDifference/GetChannelDifference internos não consomem o contador de páginas
nem de diálogos getDialogs, mas consomem o mesmo deadline. Volume/bytes dessas
respostas não são garantidos pelos limites propostos; limite rígido de todos
os RPCs/bytes exigiria nova evidência/decisão arquitetural. D_PLUS_C preservada.

#### Resultados, limites e limpeza

| Evento | Resultado contratual |
|---|---|
| Enumeração termina com evidência válida antes/no último saldo permitido | COMPLETE (`complete=True`, sem stop_reason); sem elegíveis → EMPTY. |
| Teto bruto ou de páginas sem evidência de fim | PARTIAL com RAW_DIALOG_LIMIT ou PAGE_LIMIT; contadores e aviso de cobertura incompleta. |
| Deadline termina após restore válido durante enumeração, com páginas já projetadas com integridade | PARTIAL/TIME_BUDGET, somente após cancelamento da chamada pendente e cleanup confirmado; sem usar resposta tardia. |
| Deadline antes de restore autenticado, resposta inconsistente, falha RPC/rede/acesso/FloodWait | Falha controlada; sem snapshot selecionável. FloodWait → RATE_LIMITED com retry_after; nenhum sleep/retry automático da aplicação. |
| Cancelamento explícito, inclusive durante restore, RPC, cleanup ou seleção local | CANCELLED, sem seleção/ID; descartar snapshot selecionável. |
| Cleanup não termina no limite ou falha | Falha controlada/diagnóstico CLEANUP_FAILED; não apresentar lista/seleção nem sucesso. Preservar a causa primária quando existente. |

COMPLETE significa término do mecanismo de descoberta nesta invocação, não
snapshot atomicamente consistente de uma conta mutável nem acesso a todos os
canais existentes. Se houver prova de fim no mesmo passo do limite, COMPLETE
é válido; se apenas houver coincidência com limite, PARTIAL. Snapshot parcial
pode ser apresentado/selecionado localmente por ID com aviso explícito, inclusive
por prazo quando sua integridade/cleanup forem confirmados; parcial sem
candidatos usa INCOMPLETE_EMPTY, jamais EMPTY completo. Cancelamento não permite
seleção. Erros não são convertidos em descoberta parcial bem-sucedida.

`finally` sempre solicita close, inclusive em falha/cancelamento. Deadline
não depende somente de timeout do RPC: o supervisor cancela a operação,
aguarda sua terminação e fecha transporte/tarefas com janela de cleanup
separada, resistente ao primeiro cancelamento. Não prometer que Python,
transporte ou I/O bloqueante respeitem prazo rígido: teste de cancelamento
cooperativo e detecção de cleanup pendente são obrigatórios. Sem desconexão
confirmada, não oferecer seleção; processo CLI encerra controladamente com
diagnóstico sanitizado. Não criar serviço/tarefa sobrevivente, salvar sessão,
persistir conteúdo nem afirmar apagamento seguro de memória.

#### Sequenciamento autorizado para fechar OPEN-03

A. Aprovar orçamento inicial proposto no contrato, ou substituí-lo por valores
fundamentados via decisão do usuário. Algoritmo e semântica estão definidos
como proposta; números não estão validados empiricamente.
B. Após aprovação contratual, baseline necessária e autorização explícita,
implementar os limites aprovados e os testes offline verificáveis.
C. Medir/calibrar durante implementação/aceite, somente com autorização específica
de Telegram/sessão. Coletar contagens agregadas, páginas, duração restore/
descoberta/cleanup, motivo de parada e evidência de fim/cobertura, sem payload,
credenciais, cursor ou identidade da conta. Comparar limites com os resultados;
não provocar FloodWait para medir. Se PARTIAL, registrar cobertura não comprovada
e propor ajuste autorizado; nunca aprovar cobertura completa por amostragem.
D. Registrar configuração, versão, resultados, incertezas e eventual decisão de
calibração no checkpoint documental consolidado da entrega após implementação/
validação. Nenhuma medição real ou atividade intermediária criada aqui.
## 5. Autenticação e integração canônica

FATO: `AuthenticationApplication.authenticate` cria o gateway e chama `close`
em `finally`; retorna somente `AuthOutcome`. Portanto chamar essa aplicação
e depois listar usando o mesmo gateway encerrado é incorreto.

O fluxo de descoberta na CLI (nome candidato `channels`), com sua aplicação,
cria um único `TelethonGateway` pelas seams existentes,
valida credenciais pela função existente, chama `restore`, e só chama
`discover_channels` para AUTHENTICATED. AUTH_REQUIRED/SESSION_INVALID termina
com orientação para o comando `auth` existente; não solicita OTP/2FA no novo
fluxo, não usa `start` e não cria segunda implementação de login.

```text
CLI → aplicação de descoberta → gateway.restore existente
    → AUTHENTICATED → discover_channels → snapshot próprio → close → seleção local
    → AUTH_REQUIRED/SESSION_INVALID → orientação ao auth existente → fim
finally → gateway.close confirmado → apresentação/seleção local
```

Vault/DPAPI, configuração, StringSession, lifecycle, logger e retry settings
continuam regidos por S1-A/B e ADR-008. Restore falho não apaga/regrava blob;
descoberta não salva metadados/conteúdo no vault. Um processo posterior pode
restaurar a mesma sessão protegida. Não verificar presença de sessão lendo o
blob real nesta atividade. A alternativa de login inline somente pode reutilizar
um workflow extraído com aprovação explícita e regressão, nunca duplicá-lo.
Preservar comandos `auth` e `smoke`, seus resultados e limpeza.

## 6. Erros, FloodWait e ownership

O gateway port descreve dados/erros e não executa retries. O adapter é o único
dono do client, RPCs, sessão, InputPeer/InputChannel e caches privados. A
aplicação é dona de workflow, deadline, cancelamento, orçamento e decisão de
esperar/repetir. A CLI é dona de apresentação/entrada local. Parsers e storage
não participam de S1-D.

Proposta: `ChannelDiscoveryError` seguro com categorias AUTH_REQUIRED,
SESSION_INVALID, ACCESS_DENIED, NETWORK, RATE_LIMITED, ADAPTER_FAILURE e
INVALID_SELECTION; rate limit carrega somente `retry_after_seconds: int`
não negativo. Adaptar erros existentes de restore sem alterar o texto/API do
`AuthenticationError` de S1-B. Os atuais NetworkError/RateLimited/AdapterError
herdam AuthenticationError e têm mensagens de auth: não repeti-las como texto
de descoberta e não refatorar a hierarquia frozen silenciosamente.

Traduzir FloodWait e variantes pertinentes, Unauthorized/session revogada,
ChannelPrivate/ChannelInvalid e falhas de transporte conhecidas, incluindo
IncompleteReadError, para erros próprios. Desconhecido → ADAPTER_FAILURE sem
repr, args, traceback/contexto bruto público; `from None`. Cancelamento não
deve ser reclassificado como falha inesperada nem engolido. Cleanup deve rodar
inclusive em falha/cancelamento e não mascarar a falha primária com segredo.

Preservar `flood_sleep_threshold=0`, `request_retries=1`,
`connection_retries=1`, `raise_last_call_error=True`, `auto_reconnect=False`.
FATO: em Telethon 1.45.0, `FloodWaitError.seconds=0` é normalizado pela biblioteca
para 1; o boundary carrega o valor efetivamente exposto, sem prometer o original
do wire. Para a proposta inicial, não fazer retry/sleep automático de aplicação;
reportar a espera e encerrar a invocação. Uma nova tentativa explícita não pode
antecipar a espera indicada. Política automática futura exige decisão própria e orçamento finito
aprovado; os deadlines propostos constam da seção 4. Não há
segundo loop de retry escondido no port/CLI.

## 7. GAP-03 — payload e limites de leitura

### Evidência instalada (inspeção estática, sem import/conexão)

Ambas `.venv` e `.venv-replay` declaram Telethon 1.45.0 em `telethon/version.py`.
A análise abaixo usa os arquivos instalados de `.venv-replay/Lib/site-packages/telethon/`:

| Arquivo / símbolo | Evidência |
|---|---|
| `client/dialogs.py`, `_DialogsIter._init/_load_next_chunk`, `iter_dialogs/get_dialogs` | Cria GetDialogsRequest com hash=0; chunks de até 100 diálogos como detalhe da biblioteca; percorre r.messages, chama `_finish_init`, associa top_message, cria custom.Dialog e usa última mensagem para offsets |
| `tl/functions/messages.py`, GetDialogsRequest (linha 2966) | Sem flag para excluir messages; retorna Dialogs/DialogsSlice/DialogsNotModified |
| `tl/types/messages.py`, Dialogs/DialogsSlice (1098/1186) | Vetor messages recebido e desserializado por `from_reader` antes do retorno |
| `tl/custom/dialog.py`, Dialog | Mantém `message`, `date` e draft; `to_dict`/stringify incluem conteúdo |
| `network/mtprotosender.py`, `_handle_rpc_result` | Chama `state.request.read_result(reader)` para desserializar resposta |
| `tl/functions/channels.py`, GetChannelsRequest (757) | Retorna Chats/ChatsSlice por InputChannel conhecido, sem vetor messages; não enumera peers desconhecidos |
| `client/users.py`, `_call` | Processa entidades da resposta e encapsula RPC em InvokeWithoutUpdates quando `_no_updates` |
| `client/telegrambaseclient.py` / `client/auth.py` | receive_updates=True por padrão; `_on_login` pede GetState/GetDifference |
| `sessions/string.py`, StringSession.save | Serializa material de conexão/auth; não serializa mensagens recebidas |

Corroboração do protocolo: [messages.getDialogs](https://core.telegram.org/method/messages.getDialogs)
retorna diálogos, mensagens e entidades; [messages.dialogs](https://core.telegram.org/constructor/messages.dialogs)
define esse vetor. [channels.getChannels](https://core.telegram.org/method/channels.getChannels)
obtém entidades por identidades conhecidas. A documentação web é corroborativa;
o comportamento da versão instalada acima é a evidência primária deste draft.
As páginas consultadas em tl.telethon.dev retornaram conteúdo incongruente e
foram descartadas como evidência.

FATO: não solicitar getHistory/getMessages/download NÃO significa não receber
mensagens. GetDialogs transfere potencialmente a última mensagem de diálogos
de usuários, grupos e canais, inclusive candidatos depois excluídos, e pode
incluir texto/metadata de mídia/drafts. A mídia binária não é baixada por esta
operação. Payload pode estar vazio em casos particulares, sem garantia universal.

```text
NO_MESSAGE_TRANSFER = NOT_GUARANTEED
LIBRARY_INTERNAL_PROCESSING = ALLOWED / incidental getDialogs and approved difference RPCs within bounded S1-D lifecycle
APPLICATION_CONTENT_PROCESSING = PROHIBITED
APPLICATION_CONTENT_PERSISTENCE = PROHIBITED
APPLICATION_CONTENT_EXPOSURE = PROHIBITED
APPLICATION_CONTENT_LOGGING = PROHIBITED
```

Não declarar NO_MESSAGE_PROCESSING sem qualificá-lo: processamento de domínio
(scanner/parser/catalog) é proibido, mas processamento interno da biblioteca
ocorre. A conversão para ChannelSummary acontece dentro de TelethonGateway
imediatamente após cada diálogo: allowlist de entity.id/title/username/flags,
ID marcado validado; nunca projetar Dialog inteiro, message/date/draft ou TL types.
Offsets internos não são checkpoints de scanner.

### Alternativas analisadas para DEC-S1D-01 (payload incidental aprovado)

1. **Alternativa de menor código:** `iter_dialogs` + projeção própria. Usa
   paginação pronta e evita acumular todos os Dialogs via get_dialogs; ainda
   transfere e materializa payload incidental, aceito em DEC-S1D-01. Não prova
   teto de diálogos brutos/páginas; alternativa descartada nesta proposta em
   favor da paginação direta especificada na seção 4.
2. **GetDialogsRequest direto:** pode evitar custom.Dialog/_finish_init/draft
   wrapper; ainda desserializa messages e requer paginação própria com offsets.
   Não resolve NO_MESSAGE_TRANSFER; custo e risco adicionais. É a recomendação
   adotada nesta proposta para tetos verificáveis de solicitações brutas
   e páginas, sujeita a testes sintéticos dos offsets e da completude.
3. **GetChannelsRequest para peers conhecidos:** resposta específica sem vetor
   messages; exige ID/access hash já resolvido de modo legítimo. Não descobre
   todos os canais e cache não é enumeração completa/confiável. Uma lista prévia
   fornecida ou allowlist é outra experiência que exige decisão de produto.
4. **NO_MESSAGE_TRANSFER absoluto:** nenhuma alternativa confiável equivalente
   foi comprovada para enumeração de todos os diálogos. hash/DialogsNotModified
   depende de cache e ausência de mudanças; limit=0/getPeerDialogs não são
   garantias de ausência de conteúdo. Se obrigatório, bloquear esta operação
   e redefinir cobertura/entrada por decisão humana, sem prometer solução.

### Controles propostos

- DEC-S1D-01: `iter_dialogs` pode receber payload incidental por exigência do
  protocolo/biblioteca. `NO_MESSAGE_TRANSFER` não é garantido; a biblioteca pode
  desserializar/manusear payload internamente. A aplicação não interpreta,
  persiste, registra, expõe na CLI ou devolve esse conteúdo em modelos do
  gateway. `NO_MESSAGE_PROCESSING`, `NO_MESSAGE_PERSISTENCE`,
  `NO_MESSAGE_EXPOSURE` e `NO_MESSAGE_LOGGING` são invariantes obrigatórios da
  aplicação. Não há leitura explícita de histórico.
- Não ler atributos de conteúdo no código da aplicação/projeção; não chamar
  getHistory, iter_messages, get_messages, download_media, download_file,
  iter_download, get_drafts, getPeerDialogs ou getFullChannel para enriquecer lista.
- Nunca stringify/to_dict/repr/logar respostas/Dialogs/exceções brutas. Logs
  operacionais usam somente etapa, categoria e resultado; conteúdo de mensagens,
  drafts, segredos e access hash proibidos. Metadados de canal são exibidos na
  CLI, sem gravar lista bruta em logs/artifacts.
- Não persistir payload, Dialog, entity, último ID/data de mensagem, catálogo ou
  escolha em banco/arquivo/cache próprio; manter somente DTOs e resolução
  privada mínima de identidade durante a invocação. Soltar referências ao fim,
  sem afirmar apagamento seguro da memória Python.
- O perfil aprovado é dedicado à instância S1-D: `receive_updates=False`,
  `catch_up=False`, sem handlers. A biblioteca pode receber/processar
  internamente `GetDifference` e `GetChannelDifference`, inclusive em
  inicialização e no loop de updates. A aplicação não solicita esses RPCs
  explicitamente e não consome seu conteúdo. As flags não garantem ausência
  desses RPCs nem removem mensagens incidentais de respostas `getDialogs`.
- Restore-only evita `sign_in` no novo fluxo, mas **não garante ausência de
  `_on_login`**: no Telethon 1.45.0, `connect` chama `get_me` e `_on_login` quando
  o `MessageBox` inicia vazio, e `_on_login` faz `GetState`/`GetDifference`.
  `StringSession` restaura a chave, não prova um `MessageBox` já inicializado.
  O comando `auth` permanece sob S1-B/C; não reabrir seu PASS.
- Verificar no futuro, offline, as chamadas efetivas/background e regressão
  do perfil sem updates. Não alegar que os controles já existem na baseline.

### OPEN-04 — registro histórico da decisão anterior (superseded por DEC-S1D-03)

FATO: o construtor instalado usa `receive_updates=True` e `catch_up=False` por
padrão. Com `receive_updates=False`, Telethon encapsula requests em
`InvokeWithoutUpdates` e reduz updates enviados pelo servidor, mas ainda cria
loops internos de update/keepalive em `connect`. `catch_up=False` evita a
recuperação voluntária de updates no início do loop; nenhum handler deve ser
registrado pela descoberta. A operação `getDialogs` continua retornando seu
vetor incidental de mensagens. A documentação do parâmetro não é prova de zero
bytes de updates em todos os caminhos.

O registro acima descrevia recomendação para evitar os RPCs e bloqueio até prova.
Esse requisito foi substituído pela decisão humana DEC-S1D-03. Permanecem
vigentes como fatos técnicos a possibilidade dos caminhos internos e a
insuficiência das flags para garantir zero diferenças; as antigas exigências
de evitá-los e de bloquear a arquitetura foram retiradas. O lifecycle delimitado,
controles da aplicação e critérios de verificação atuais estão na seção 18.

## 8. Invariantes e segurança

Nenhum tipo Telethon cruza gateway; nenhum segredo passa a CLI/modelos.
ID estável governa seleção; metadados não governam identidade. Autenticação,
sessão e acesso devem ser legítimos; não entrar em canais, enviar/editar/apagar
mensagens ou contornar proteção. Resultado local não é prova de acesso futuro.
Somente uma operação formal autorizada; nenhum avanço automático. Sem novo
storage/login/cliente concorrente, dependência ou policy. Não mudar S1-C PASS,
S1-A/B frozen ou o diagnóstico S1-TEST-01.

## 9. Critérios de aceitação verificáveis e testes offline futuros

Status dos critérios: DEFINED / NOT_EXECUTED. Aprovação dos valores OPEN-03 e GOV-01 regem aprovação/freeze conforme seção 19; revalidação da baseline é gate de implementação, e execução dos critérios abaixo é gate de aceite.

| ID | Critério | Verificação offline planejada |
|---|---|---|
| AC-01 | Restore antes de descobrir; auth necessária/expirada não lista | Fake gateway observa sequência, zero discovery fora de AUTHENTICATED; prompts de login ausentes no restore-only |
| AC-02 | ID marcado estável e sem título/username como chave | Peers sintéticos com mesmo título, username ausente/alterado, round-trip de IDs, bool/zero/positivo rejeitados |
| AC-03 | DEC-S1D-02 aplicada com classificação própria | Fixtures broadcast, megagroup/supergroup/forum, basic/user/bot/secret/forbidden/unknown/flags inconsistentes; arquivados/fixados e duplicatas |
| AC-04 | Seleção puramente local | Fake RPC count não muda ao selecionar; ID ausente/ordinal velho/inválido não escolhe primeiro item; EMPTY/CANCELLED sem ID |
| AC-05 | Orçamento aprovado e truncamento visível | Fake com páginas de 100 e última página cheia: sem prova de fim → PARTIAL; fim demonstrado sem elegíveis → EMPTY; duplicatas, migrados e não elegíveis consomem orçamento bruto; nenhuma chamada lógica getDialogs além do teto ou após deadline; overflow de fixados explicitamente marcado na primeira resposta é contado sob o saldo bruto; overflow não explicado ou acima do saldo bruto é rejeitado; contadores e razão expostos; timeout só oferece PARTIAL se snapshot íntegro e cleanup confirmado; cancelamento nunca seleciona |
| AC-06 | Boundary exclui conteúdo e TL types conforme DEC-S1D-01 | DTOs próprios; canários sintéticos em message/draft/media não aparecem em output/logs/exceções/storage; não inspecionar conteúdo na projeção |
| AC-07 | Nenhum processamento/persistência de domínio de mensagem | Spies de scanner/parser/storage nunca chamados; método fake de conteúdo proibido falha imediatamente; nenhum last-message field no DTO |
| AC-08 | Erros próprios e FloodWait | Exceções Telethon sintéticas: acesso/session/network/unknown e rate limit; duração validada; nenhum sleep/retry de aplicação/adapter; cancelamento propagado |
| AC-09 | Recursos fechados e sessão protegida preservada | close confirmado antes da seleção em sucesso/vazio/parcial, e tentado em erro/cancelamento; cleanup com deadline e falha controlada; blob anterior não alterado na descoberta; sem start/log_out/file session/export |
| AC-10 | Perfil de updates e lifecycle aprovado | Constructor/fake recorder confirma perfil apenas na instância de descoberta; auth/smoke intactos; sem handlers, chamadas de diferenças pela aplicação, history/draft/download; close em todos os caminhos; testes offline caracterizam os RPCs internos permitidos e provam que seus payloads não cruzam para aplicação/domínio/CLI/logs/storage; não exigir count zero |
| AC-11 | Integração CLI e regressão acumulada | CLI fake percorre restore→lista→seleção; auth/smoke e S1-A/B continuam válidos; saída Rich trata títulos como texto seguro |
| AC-12 | Separação de validação e autorização | Suíte offline sem client/socket real; matriz real separada; DoR/freeze/implementação/live possuem gates próprios |

Fakes usam somente valores sintéticos, factory injetável e métodos proibidos
que falham imediatamente. Testar DTO, aplicação, adapter e CLI; regressão de
sessão/auth é necessária se o adapter compartilhado ganhar perfil. Nenhum
source/test foi escrito e pytest NÃO foi executado nesta atividade. Revalidação
da baseline continua PENDING pelo diagnóstico S1-TEST-01, sem novo waiver.

## 10. Validação real separada

Somente após contrato aprovado/frozen, implementação autorizada, gates offline
e autorização real específica: validar conta própria, reuse da sessão, cobertura
aprovada, lista e escolha por ID em amostra controlada. Não autenticar novamente
nem provocar FloodWait sem escopo explícito. O payload incidental foi aprovado
em DEC-S1D-01 dentro dos limites da seção 7; não inspecionar/capturar conteúdo
como evidência. Registrar resultado sanitizado, chamadas/cobertura e limites;
seleção não autoriza scanner/download. Integração real não entra na suíte pytest
normal.

Validação real do lifecycle e eventual observação de tráfego exigem autorização
separada; a decisão arquitetural não constitui essa autorização. Não inspecionar
ou reter conteúdo incidental como evidência.

## 11. GOV-01 — evidência histórica preservada / dependência externa

Comparação SHA-256 dos cinco arquivos locais com pins do binding:

| Arquivo em `docs/continuity/policies/` | Pin adotado | SHA-256 local (CRLF) |
|---|---|---|
| PM-01-Conducao-de-Projetos-v1.0.md | b0782078a57fde833577e6b46fe3cd32048dae14569cac5ba9d821aafd1b54fa | 96dde63791e7dcb6eb097b96c1696fce33cf9580bbe81d9c0b45d72786b94fa5 |
| Politica-Prompts-Agente-v1.7-R2.6.md | 0bd42fad5f867e703aaacd4ce89c02a2ac21404657ee20d85646efd3ba8a8a6f | ca7d7d2e01b7b6423bbf6490db4aeef2fb4a4f1b5859f532a05841f420e80cc2 |
| AGENTS-Multiagente-Generico-v1.7-R2.3-Roteamento-Economico.md | cfbb1cd363e6b1c6815918747fe12ce0ad2b35388d0aed0a1d2ca66b742b66aa | b44eb998515747860bb81857eb6742eb1f048f6e341d39e9fc0a2d42d1c85537 |
| Politica-de-Uso-de-Skills-e-Plugins-Codex-Work-v1.2.md | e0664fc460008401936c334d80afbd46fe94944391aa0938d56a339853129016 | 701d9f51299b5afb4ad0ce822c0ddd61c40a5caf97da99765a82f84d19947ebf |
| Independencia-Analitica-Agente-v1.md | d668de8bdaeea16403f4909678448b59705f094302bc2fe90203c2f3cc62a94e | 5e127509944f8ac0136ff1e7f20592686c62c70312dcc16a243411b325c93f86 |

Os hashes dos mesmos textos normalizados para LF também não correspondem:
PM-01 `3b917ce0a9fb7003a1eb5ba9302b22278b5972a9535eb15f2fa3906b8358655d`;
PM-02 `1690bab647f74ecdcdd0e3e0c4895df90d67629f9bb28230a1bdf91c644374cf`;
PM-03 `680031a06f0b97df3f93d662275cb55421b495f576a4c88004c12cf35ae18aef`;
PM-04 `e03d0f5bd4548c20a94fef191f9185ef2b6262fb83b9ed0ecf5ee1028957d322`;
PM-05 `57544a26c8773b9eba1a254791b4a2e6b34771a7b6ac4a23606100e26ad24f24`.
Git informa index LF/worktree CRLF, e policies sem alterações locais. Portanto
EOL existe, mas não explica sozinho a divergência em relação aos pins.

FATO: igualdade de bytes não validada. Causa e diferença semântica em relação
aos originais adotados: NOT_ESTABLISHED; não acessamos governanca_de_projetos.
Não afirmar adulteração, atualização ou equivalência por título/version.
PM-00, VP-01 e protocolo Continuity não têm cópias correspondentes nessa pasta:
validação de seus pins NOT_PERFORMED, não presumir mismatch. O gate histórico
de abertura relata PASS dos pins na adoção; não é revalidação atual.

Impacto: rastreabilidade da governança fica não atestada; não há conflito
material demonstrado nas regras usadas versus o pedido atual e as authorities
de domínio locais, que sustentam o draft. Não é correto classificar a
divergência como APENAS_DOCUMENTAL_COMPROVADA. A análise técnica não depende
de substituir pins. Freeze/DoR não recebem PASS dessa inspeção: antes de
congelar, encaminhar GOV-01 à atividade de governança para adjudicar a
aplicabilidade/integridade das cópias. Se ela encontrar conflito material,
bloquear especificamente o trecho afetado. Policies/pins/binding não alterados.

## 12. Resultado vigente e retomada

DEC-S1D-01/02/03 preservadas; arquitetura D_PLUS_C consolidada, sem reabrir
decisões. OPEN-03 possui algoritmo, resultados, limpeza e proposta numérica
fundamentada, mas permanece PENDING_USER_APPROVAL por falta de medição
suficiente para fixar valores como validados. Medição/calibração fica para
implementação/aceite com acesso real especificamente autorizado.

Contrato consolidado READY_FOR_USER_REVIEW, DRAFT / NOT_APPROVED / NOT_FROZEN.
GOV-01 permanece dependência externa e bloqueio normativo de freeze, sem
investigação, alteração de policies ou acesso a outro repositório.
FULL_PYTEST permanece PENDING; não executado aqui. OPEN-04 arquitetural
resolvido; sua validação técnica pertence aos gates de implementação/aceite,
sem exigir implementação concluída para aprovação contratual.

Próxima ação: decisão do usuário sobre contrato e orçamento inicial; avaliar
freeze respeitando GOV-01. Não há autorização de implementação, live, sessão,
pytest, stage/commit/push ou fechamento de S1. Checkpoint documental amplo
somente após implementação/validação; estado corrente reconciliado minimamente.
## 13. Validação documental do draft anterior — snapshot histórico

```text
ACTIVITY_STATUS = PASS / atividade anterior: draft solicitado e análise entregues
ACTIVITY_COMPLETION_PERCENT = 100%
COMPLETION_BASIS = baseline, authorities locais, código/Telethon, GAP-03, pins,
                   draft, revisão estática e continuidade concluídos;
                   aprovação e implementação estavam fora da autorização
COHERENCE_WITH_S1A_S1B_S1C = PASS / dependências referenciadas; contratos intactos
CANONICAL_INTEGRATION_REVIEW = PASS / restore-only proposto evita gateway fechado
IDENTITY_AND_TELETHON_BOUNDARY_REVIEW = PASS / detalhes propostos; não implementados
READ_LIMITS_REVIEW = PASS_AS_DRAFT / limitações expostas; valores em OPEN-03
ACCEPTANCE_CRITERIA_STATUS = DEFINED_CONDITIONALLY / AC-01..12 não executados
SCOPE_REVIEW = PASS / mudanças documentais somente
SECRET_REVIEW = PASS / nenhuma credencial/sessão real lida ou incluída;
               exemplos são IDs sintéticos e hashes documentais
LOCAL_CONTRACT_LINKS = PASS / nenhum destino local ausente
DIFF_CHECK = PASS / git diff --check e no-index --check para o draft não rastreado
SOURCE_CHANGES = NONE
TEST_CHANGES = NONE
FROZEN_CONTRACT_POLICY_PIN_BINDING_CHANGES = NONE
PYTEST_EXECUTED = NO
PYTEST_REVALIDATION = PENDING
TELEGRAM_NETWORK_USED = NO / apenas documentação web pública, sem RPC Telegram
S1C_STATUS = PASS / preservado
PROJECT_STATE_RECONCILIATION = PASS / state, map, record, handoff e referência S1
GIT_ACTIONS = NONE / sem add, commit, push ou checkpoint; consultas read-only feitas
HEAD = e947406dbcab8ef593123f079daa279903805d2c / inalterado
STAGING = EMPTY / preservado
PREEXISTING_S1TEST01_EVIDENCE = PRESERVED / relatório não editado;
                            campos de diagnóstico mantidos, retomada sucedida
FINAL_VERDICT = DRAFT_DELIVERED / NOT_APPROVED / NOT_FROZEN / DOR_NOT_PASS
```

## 14. S1-D Architectural Decision Closeout — snapshot histórico superseded na seção 18

```text
ACTIVITY = S1-D Architectural Decision Closeout
ACTIVITY_STATUS = PASS / decisões autorizadas registradas e contrato reconciliado
ACTIVITY_COMPLETION_PERCENT = 100%
ROOT_RUNTIME_MODEL = GPT-6 / variante e effort não verificáveis nesta superfície
DEC-S1D-01 = APPROVED / payload incidental permitido; invariantes de aplicação obrigatórios
DEC-S1D-02 = REVISED_AND_APPROVED / broadcast channel + megagroup/supergroup
BROADCAST_SUPPORT = APPROVED
MEGAGROUP_SUPPORT = APPROVED
SUPERSEDED_DECISION_RECONCILED = YES / broadcast-only anterior preservado como superseded
FUT-CHDISC-01 = NOT_CREATED / nenhum registro anterior localizado
DISCOVERY_BUDGET_DECISION = PARTIAL / cobertura, paginação, completude, cancelamento e estado parcial definidos; limites numéricos OPEN-03
UPDATES_PROFILE_DECISION = OPEN-04 / recomendação sem updates; requer aprovação por impacto no adapter compartilhado
RESTORE_ONLY_DECISION = CLOSED / reusar sessão; orientar comando auth se ausente/inválida; repetir descoberta explicitamente
MATERIAL_OPENS = OPEN-03 numeric budgets; OPEN-04 updates profile; GOV-01 governance integrity adjudication
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
CONTRACT_FREEZE = NOT_AUTHORIZED
POLICY_PIN_STATUS = FIVE_LOCAL_POLICY_HASHES_MISMATCH / permanece sem reconciliação
GOVERNANCE_BLOCKER = YES / GOV-01 deve ser adjudicado antes de freeze/DoR
S1D_DOR = NOT_PASS / OPENs e revalidação de pytest pendentes
FILES_MODIFIED = docs/contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md; docs/governance/APPROVALS_AND_DECISIONS.md; docs/continuity/PROJECT_STATE.md; docs/continuity/ACTIVE_AUTHORITY_MAP.md; docs/continuity/CONTINUITY_RECORD.md; docs/continuity/planning/SPRINTS.md; docs/continuity/handoff/LAST_HANDOFF.md
DIFF_CHECK = PASS / git diff --check + no-index --check for untracked contract
SOURCE_CHANGES = NONE
TEST_CHANGES = NONE
TELEGRAM_NETWORK_USED = NO
GIT_ACTIONS = NONE
S1D_IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
FINAL_VERDICT = DECISIONS_RECONCILED / CONTRACT_DRAFT_REMAINS_NOT_APPROVED_NOT_FROZEN
NEXT_ACTION = Resolve OPEN-03/04 and GOV-01; prepare separate approval/freeze review
```

Não confundir PASS desta atividade documental com PASS da implementação,
dos testes, da integridade dos pins ou da aprovação das decisões OPEN.

## 15. S1-D — Remaining Technical Decisions Closeout — snapshot histórico superseded na seção 18

Inspeção estática adicional da instalação Telethon 1.45.0, sem import, conexão
ou sessão real, refinou OPEN-03/04. `iter_dialogs(limit=N)` limita itens emitidos
e não comprova teto de diálogos brutos ou páginas; paginação direta é proposta
quando esses tetos forem aprovados. `receive_updates=False` é recomendado
somente para a instância de descoberta, mas `connect` ainda pode chamar
`_on_login`/`GetDifference`, fora do payload de `getDialogs` aprovado em
DEC-S1D-01. O usuário escolheu OPTION_1 para cobertura e exigiu comprovar como
evitar `GetDifference`, sem aceitar seu payload incidental. Ambos os itens
permanecem OPEN para números/medição e solução técnica comprovada, sem inventar
valores ou ampliar aprovação. Critérios AC-05
e AC-10 foram refinados; AC-01..12 continuam DEFINED / NOT_EXECUTED.

```text
ACTIVITY = S1-D Remaining Technical Decisions Closeout
OPEN-03 = OPTION_1_APPROVED / numeric budgets and measurement remain OPEN
OPEN-04 = AVOID_GETDIFFERENCE_APPROVED / technical solution and proof remain OPEN
GOV-01 = UNRESOLVED / five policy hash mismatches remain under governance authority
S1-TEST-01 = PENDING / no pytest in this activity
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
IMPLEMENTATION = NOT_AUTHORIZED / NOT_STARTED
TELEGRAM_NETWORK = NO
SOURCE_AND_TEST_CHANGES = NONE
GIT_PUBLICATION = NONE
```

## 16. OPEN-04 — prova offline bloqueada, 2026-10-08 (registro histórico)

A investigação autorizada importou Python 3.14.7/Telethon 1.45.0, mas a única
sonda isolada de Selector travou na inicialização, em socketpair/accept, com
faulthandler encerrando o processo após 8 s. PROOF_STATUS = BLOCKED_ENVIRONMENT;
classificação = NOT_DEMONSTRATED. Os cenários A–E não foram executados e zero
GetDifference não foi medido. A sequência conhecida continua sendo evidência
estática, não captura de requests.

Não foi identificado mecanismo público suficiente para StringSession
restaurada sem estado no gateway atual: receive_updates=False encapsula, mas
não remove GetDifference; catch_up=True não recupera estado ausente e pode
solicitar diferenças; is_user_authorized/GetDialogs após connect chegam tarde
para evitar o caminho de inicialização. Persistir estado genuíno numa Session
customizada exigiria decisão de storage/lifecycle e ainda não prova ausência
de diferenças. Alterar `_on_login`/MessageBox/sender ou filtrar RPC em produção
tem custo alto de manutenção e risco de inconsistência; nenhum workaround foi
demonstrado ou aprovado. Não inferir impossibilidade universal.

Evidência detalhada, alternativas, hashes e limites estão no
[relatório de viabilidade](../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md).

## 17. OPEN-04 — retomada offline delimitada, 2026-10-08 (registro histórico)

O precheck local fora da restrição anterior passou com socketpair e
`asyncio.run`. A única prova sintética subsequente, com sessão e respostas
artificiais e sender interceptado somente na prova, não emitiu trace e foi
interrompida após espera delimitada. GET_DIFFERENCE_COUNT = NOT_MEASURED.
Nenhuma solução por API pública, compatível com autenticação e proteção de
sessão, foi demonstrada. Não inferir que o count seja zero, que a solução seja
universalmente impossível ou que um workaround privado esteja aprovado.

MAX_PROOF_ATTEMPTS=1 encerra a exploração técnica desta atividade. OPEN-04
permanece aberto para decisão arquitetural humana explícita. DEC-S1D-01/02,
BROADCAST/MEGAGROUP ELIGIBLE, OPEN-03 PENDING_MEASUREMENT, GOV-01 UNRESOLVED,
pytest PENDING_REVALIDATION e contrato DRAFT / NOT_APPROVED / NOT_FROZEN
permanecem inalterados. Evidência e limites no
[relatório de viabilidade](../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md).

## 18. DEC-S1D-03 — lifecycle aprovado e reconciliação vigente

```text
DECISION_STATUS = APPROVED
ARCHITECTURE = D_PLUS_C
OPEN-04_ARCHITECTURAL_DECISION = RESOLVED_BY_DEC-S1D-03
OPEN-04_TECHNICAL_VALIDATION = PENDING
PROVE_ZERO_GET_DIFFERENCE = SUPERSEDED
DEC-S1D-03 = ACTIVE_APPROVED_DECISION
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
S1D_DOR = NOT_PASS
S1D_IMPLEMENTATION = NOT_STARTED / NOT_AUTHORIZED
```

### A–B. Decisão e motivação

O usuário aprovou explicitamente a arquitetura D_PLUS_C após a auditoria
independente [S1D_INDEPENDENT_ARCHITECTURE_REVIEW_2026-10-08](../audit/S1D_INDEPENDENT_ARCHITECTURE_REVIEW_2026-10-08.md).
A auditoria concluiu, por inspeção estática do Telethon 1.45.0, que `connect`
pode solicitar `GetDifference` durante inicialização e que o loop de updates
pode solicitar `GetDifference` ou `GetChannelDifference`; `receive_updates=False`
e `catch_up=False` não garantem zero RPCs. A auditoria é referência técnica,
não autoridade de decisão. A decisão humana substitui a exigência anterior de
provar ausência desses RPCs, sem converter hipóteses ou propostas não aprovadas
da auditoria em decisões vigentes. Registro decisório: [APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md#dec-s1d-03--lifecycle-de-diferenças-internas).

### C–F. RPCs permitidos e fronteira de dados

Durante somente o lifecycle delimitado da operação de descoberta S1-D, fica
permitido o recebimento e processamento interno incidental pelo Telethon de
`updates.GetDifference` e `updates.GetChannelDifference`. O escopo inclui
caminhos de inicialização e loop interno de updates, não apenas restore inicial.
O Telethon pode receber e desserializar payload, processar estados e entidades
e executar mecanismos internos necessários a esse lifecycle. Isso não autoriza
a aplicação ou adapter a interpretar conteúdo incidental, encaminhá-lo ao
domínio, persistir mensagens, registrar payload, exibir na CLI ou retorná-lo em
DTOs. Não habilitar handlers de mensagens, baixar mídia, ler histórico
explicitamente, fazer join automático, administrar grupos/membros ou executar
ação remota derivada desse conteúdo.

```text
LIBRARY_INTERNAL_PROCESSING = ALLOWED
APPLICATION_CONTENT_PROCESSING = PROHIBITED
APPLICATION_CONTENT_PERSISTENCE = PROHIBITED
APPLICATION_CONTENT_EXPOSURE = PROHIBITED
NO_MESSAGE_TRANSFER = NOT_GUARANTEED
```

Não prometer zero RPCs de diferenças, somente um `GetDifference`, diferenças
somente no restore, ausência absoluta de mensagens recebidas ou apagamento
seguro de conteúdo em memória. A mitigação reduz exposição e uso na aplicação,
mas não elimina exposição transitória dentro do Telethon. Chamadas explícitas
da aplicação para sincronização, scanner ou leitura de mensagens continuam
proibidas.

### G–H. Perfil, lifecycle e fronteiras de componentes

Arquitetura aprovada para a futura implementação, ainda não executada:

- instância de cliente dedicada à operação, usando o gateway Telethon existente;
- lifecycle curto e delimitado; sem `run_until_disconnected`;
- sessão `StringSession` protegida por DPAPI e autenticação existente reutilizadas;
- perfil da instância com `receive_updates=False` e `catch_up=False`, sem handlers;
- essas flags não garantem ausência de `GetDifference` ou `GetChannelDifference`;
- sem novos serviços, dependências ou fluxo global de autenticação;
- encerrar conexão antes da seleção humana local por `telegram_chat_id`;
- limpeza controlada em sucesso, vazio, erro e cancelamento;
- preservar parâmetros atuais de retry/FloodWait como baseline, sujeitos à validação contratual.

No gateway, Telethon e tipos TL permanecem internos; projetar apenas DTOs e
metadados permitidos, sem conteúdo de mensagem. No domínio/aplicação, coordenar
restore, descoberta e seleção local sem consumir conteúdo incidental ou pedir
RPC de diferenças. Na CLI, apresentar apenas metadados permitidos e entrada de
ID; nunca conteúdo incidental. S1-A/B e o fluxo global de autenticação não são
alterados para atender S1-D.

### I. Critérios de aceite verificáveis e testes offline obrigatórios

Critérios definidos para implementação futura; todos estão
`NOT_EXECUTED` nesta atividade:

1. Factory/fake comprova cliente dedicado, flags na instância de descoberta,
   gateway e sessão protegida existentes reutilizados, sem alterar auth/smoke.
2. Lifecycle observado encerra conexão antes da seleção local e fecha em
   sucesso, vazio, erro e cancelamento; nenhum fluxo aguarda desconexão indefinida.
3. Spies/fakes demonstram que a aplicação não invoca explicitamente
   `GetDifference`, `GetChannelDifference`, sync/catch-up, history ou downloads.
4. Testes offline sintéticos exercitam os caminhos internos permitidos e
   confirmam que payloads/canários de mensagens não alcançam domínio, DTOs,
   CLI, logs, exceções públicas ou storage; nenhum handler de mensagem é ativado.
5. DTOs contêm somente metadados e `telegram_chat_id`; nenhum TL object, texto,
   media, draft, entidade de mensagem ou access hash cruza o gateway.
6. Seleção por ID é local e não dispara RPC; DEC-S1D-01/02 e elegibilidade
   preservam as classificações e exclusões já aprovadas.
7. Testes de falha/cancelamento confirmam cleanup e diagnóstico sanitizado, sem
   persistência da sessão ou conteúdo incidental pela descoberta.
8. A verificação dos caminhos internos é específica à versão Telethon adotada;
   spy offline comprova o comportamento exercitado, mas não prova o tráfego de
   sessão real nem pode exigir `GET_DIFFERENCE_COUNT = 0`.
9. Regressão de auth, sessão protegida e CLI permanece aprovada; teste real fica
   fora da suíte offline normal. OPEN-03 e os gates independentes continuam.

### J. Validação real separada e snapshot anterior de pendências

Qualquer validação real com Telegram, observação de chamadas em sessão real ou
uso de credenciais/sessão exige autorização separada. DEC-S1D-03 não concede
essa autorização. Não declarar isolamento, validação da implementação ou
comportamento real antes das verificações correspondentes.

```text
OPEN-04_ARCHITECTURAL_DECISION = RESOLVED_BY_DEC-S1D-03
OPEN-04_TECHNICAL_VALIDATION = PENDING
OPEN-03_NUMERIC_BUDGETS = PENDING_MEASUREMENT
GOV-01 = UNRESOLVED
FULL_PYTEST = PENDING_REVALIDATION
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
S1D_DOR = NOT_PASS
S1D_IMPLEMENTATION = NOT_STARTED / NOT_AUTHORIZED
```

DEC-S1D-01 e DEC-S1D-02 permanecem preservadas e inalteradas. A seção 16–17
registra o estado técnico anterior à decisão e não deve ser usada como estado
vigente para OPEN-04. Esta decisão não aprova nem congela o contrato.
Registro residual anterior à DEC-S1D-03 (histórico superseded, sem força vigente):
OPEN-04 permanece aberto. Recomenda-se decisão delimitada de recuperação do
executor; eventual revisão arquitetural requer escopo explícito. DEC-S1D-01/02,
BROADCAST/MEGAGROUP ELIGIBLE, OPEN-03 PENDING_MEASUREMENT, GOV-01 UNRESOLVED e
S1-A/B/C PASS preservados. Contrato DRAFT / NOT_APPROVED / NOT_FROZEN;
implementação NOT_GRANTED. Source/tests, policies/binding e sessão/credenciais
não foram alterados/acessados. Revalidação pytest permanece PENDING.

## 19. Consolidação final — gates e validação documental vigente

Fonte de autorização: pedido explícito do usuário em 2026-10-08,
anexo a304e9eb-2be7-4dc4-b596-ea5b7265d4fe/Texto colado.txt,
S1-D — Final Contract Consolidation, DIRECT. A instrução atual substitui a
exigência anterior de medição real pré-freeze por orçamento inicial proposto/
aprovado e medição posterior autorizada. Nenhuma aprovação de números é inferida.

| Gate | Exigência verificável | Estado nesta atividade |
|---|---|---|
| CONTRACT_GATE | Escopo, decisões, interfaces, algoritmo, limites definidos ou proposta explicitamente pendente, critérios de aceite e integridade documental aplicável | Conteúdo consolidado para revisão; números propostos aguardam decisão; GOV-01 impede atestar integridade normativa para freeze. Não exigir código ou testes futuros concluídos. |
| CONTRACT_APPROVAL | Decisão explícita do usuário sobre documento e valores OPEN-03, ou aprovação condicional identificada | NOT_GRANTED; proposta não fecha OPEN-03. |
| CONTRACT_FREEZE | Aprovação explícita e bloqueios normativos adjudicados pela authority competente | NOT_AUTHORIZED / BLOCKED_BY_GOV-01; readiness de revisão não é freeze. |
| IMPLEMENTATION_GATE | Contrato aprovado, autorização explícita e baseline necessária validada, incluindo revalidação FULL_PYTEST pendente; freeze quando exigido pela authority aplicável | NOT_PASS / NOT_AUTHORIZED. OPEN-04_VALIDATION = IMPLEMENTATION_GATE como obrigação de implementar e verificar controles; não exigir prova de código inexistente antes de aprovar contrato. |
| ACCEPTANCE_GATE | Testes funcionais/integrados, boundary de payload, lifecycle/cleanup, regressão, calibração operacional e validação real especificamente autorizada | NOT_EXECUTED. Provas offline de OPEN-04 integram a validação da implementação; aceite exige resultados, sem waiver decorrente da decisão arquitetural. |

### Casos adicionais obrigatórios para AC-05/08/09/10

- Contadores e teto solicitado: limites menores que uma página, tamanho
  configurável, página cheia no saldo final, sonda sem saldo proibida,
  duplicatas e todos os tipos não elegíveis contados, página acima do limit
  rejeitada, 20 chamadas no máximo com configuração proposta.
- Cursores: fixados fora de ordem, arquivados/diálogos de pasta, repetição de
  ID de mensagem em peers distintos, último candidato diferente do cursor
  bruto, cursor ausente/cíclico, count contraditório e NotModified inesperado.
  Lista filtrada vazia com continuação não é fim. Fixtures sintéticas devem
  caracterizar COMPLETENESS sem copiar a heurística de buffer vazio do iterador.
- Relógio falso: restore consome deadline, interrupção de RPC em andamento,
  TIME_BUDGET com snapshot íntegro versus timeout de restore, cancelamento
  antes/depois da projeção e durante cleanup/seleção; nenhuma resposta tardia.
- Cleanup: fechamento antes da entrada humana, deadline próprio, falha
  secundária preserva causa primária, ausência de seleção enquanto houver
  tarefa/transporte pendente, referências descartadas sem promessa de wipe.
- FloodWait de zero/positivo conforme valor exposto pela versão; nenhuma
  espera/retry novo da aplicação; erro após páginas válidas não libera snapshot.
- Recorder offline distingue chamada lógica getDialogs, encaminhamento
  interno e transmissão real (não medida offline). Caminhos iniciais e de
  background de GetDifference/GetChannelDifference usam canários sintéticos
  e verificam boundary, sem impor zero RPC ou acesso a conteúdo pela aplicação.

### Estado de entrega e evidência

```text
ACTIVITY = S1-D Final Contract Consolidation
CONTRACT_COMPLETENESS = COMPLETE_AS_REVIEW_DRAFT / numeric approval outstanding
DOCUMENTARY_REVIEW = PASS / decisions, interfaces, stop semantics, gates and local links checked
DIFF_CHECK = PASS / tracked diff and untracked contract no-index check; no whitespace diagnostics
PROJECT_STATE_RECONCILIATION = PASS / minimum material state updated
OPEN03_STATUS = PENDING_USER_APPROVAL / NOT_CLOSED
OPEN03_NUMERIC_BUDGETS = PROPOSED / page_size=100; raw=1000; pages=20; operation=120s; cleanup=10s
OPEN03_MEASUREMENT_PLAN = IMPLEMENTATION_AND_ACCEPTANCE / separate Telegram authorization
DEC-S1D-01 = PRESERVED
DEC-S1D-02 = PRESERVED
DEC-S1D-03 = PRESERVED
OPEN04_ARCHITECTURAL = RESOLVED
OPEN04_VALIDATION = IMPLEMENTATION_GATE / acceptance evidence required
GOV01 = EXTERNAL_DEPENDENCY / UNRESOLVED / FREEZE_BLOCKER
FULL_PYTEST = PENDING / NOT_RUN
CONTRACT_STATUS = READY_FOR_USER_REVIEW / DRAFT / NOT_APPROVED / NOT_FROZEN
IMPLEMENTATION = NOT_STARTED / NOT_AUTHORIZED
SOURCE_CHANGES = NONE
TEST_CHANGES = NONE
TELEGRAM_NETWORK_USED = NO
SESSION_ACCESS = NO
GIT_ACTIONS = NONE / read-only queries only
```

A consolidação documental solicitada pode estar concluída sem OPEN-03 fechado:
o pedido permite proposta fundamentada explicitamente pendente. A atividade
não comprova aceitação, integridade de governança, cobertura real ou latências.
As evidências Astra, OPEN-04 e S1-TEST-01 e os contratos S1-A/B/C são preservados.

## 20. Checkpoint de aprovação, implementação e revalidação — 2026-10-09

O usuário aprovou explicitamente este contrato, o baseline numérico OPEN-03 e
autorizou a implementação S1-D nesta conversa em 2026-10-09. Esta aprovação
atualiza os gates correspondentes da seção 19; não altera critérios, elimina
gates de aceite nem congela o contrato. GOV-01 permanece unresolved e bloqueia
freeze.

```text
CONTRACT_APPROVAL = APPROVED_BY_USER_2026-10-09
OPEN03_NUMERIC_BUDGETS = APPROVED / page_size=100; max_raw_dialogs=1000; max_pages=20; operation_timeout=120s; cleanup_timeout=10s
CONTRACT_FREEZE = NOT_FROZEN / BLOCKED_BY_GOV-01
IMPLEMENTATION_AUTHORIZATION = EXPLICIT_USER_APPROVAL_2026-10-09
IMPLEMENTATION_GATE = PASS
PYTHON = 3.14.7 / venv interpreter
ASYNCIO_SOCKETPAIR = PASS
ASYNCIO_RUN = PASS / Windows Proactor
PYTEST_COLLECTION = PASS / 96 tests collected
FOCUSED_PYTEST = PASS / 41 passed
FULL_PYTEST = PASS / 96 passed, 8 subtests passed in 158.55s; exit code 0; external timeout 180s not reached
RUFF = PASS
EXECUTION_CONTEXT = Independent local PowerShell; not the restricted executor
OPEN04_OFFLINE_BOUNDARY_AND_LIFECYCLE = PASS / synthetic tests
ACCEPTANCE_GATE = PENDING / operational calibration and separately authorized controlled real Telegram validation
TELEGRAM_NETWORK_USED = NO
REAL_SESSION_OR_CREDENTIALS_ACCESSED = NO
GIT_PUBLICATION = NONE
```

A implementação offline atende aos gates de implementação e regressão. O aceite
continua aberto até a calibração operacional e uma validação real delimitada,
com autorização específica. A aprovação do contrato não constitui autorização
para essa atividade real. Detalhamento corrente e safe resume point estão em
[PROJECT_STATE](../continuity/PROJECT_STATE.md); nenhum critério deste contrato
foi removido ou relaxado neste checkpoint.

## 21. GOV-01 adjudication, freeze contratual e aceite formal S1-D — 2026-10-09

O usuário decidiu `KEEP_PINNED_BASELINE`. Antes da cópia, os cinco arquivos
canônicos foram recalculados e corresponderam aos pins do binding. As cinco
cópias em `docs/continuity/policies/` foram copiadas byte a byte e, após a
cópia, correspondem individualmente aos hashes abaixo. Não houve normalização
de EOL, reformatting, BOM ou edição das fontes canônicas.

| Policy | SHA-256 canônico e destino após reconciliação | Resultado |
|---|---|---|
| PM-01 | `b0782078a57fde833577e6b46fe3cd32048dae14569cac5ba9d821aafd1b54fa` | MATCH |
| PM-02 | `0bd42fad5f867e703aaacd4ce89c02a2ac21404657ee20d85646efd3ba8a8a6f` | MATCH |
| PM-03 | `cfbb1cd363e6b1c6815918747fe12ce0ad2b35388d0aed0a1d2ca66b742b66aa` | MATCH |
| PM-04 | `e0664fc460008401936c334d80afbd46fe94944391aa0938d56a339853129016` | MATCH |
| PM-05 | `d668de8bdaeea16403f4909678448b59705f094302bc2fe90203c2f3cc62a94e` | MATCH |

```text
AUTHORITY_DECISION = KEEP_PINNED_BASELINE
GOV01_STATUS = RESOLVED
POLICY_HASH_MATCHES = 5/5
DIVERGENCES_REMAINING = 0
BINDING_UNCHANGED = YES
CANONICAL_SOURCES_UNCHANGED = YES
BASELINE_ROLE_PM04_METADATA_NOTE = PRESERVED / external registry inconsistency not modified
CONTRACT_FREEZE = PASS
CONTRACT_STATUS = FROZEN / ACCEPTED
S1D_FUNCTIONAL_ACCEPTANCE = PASS
S1D_FORMAL_ACCEPTANCE = PASS
S1D_STATUS = CLOSED
S1D_NEXT_PHASE = S2 CANDIDATE / NOT_STARTED / NO IMPLEMENTATION AUTHORIZATION
REAL_TELEGRAM_ACCESS_THIS_ACTIVITY = NO
CREDENTIALS_OR_SESSION_ACCESSED_THIS_ACTIVITY = NO
GIT_ACTIONS = NONE
```

A aprovação explícita do contrato e dos valores OPEN-03 está registrada na
seção 20. Com GOV-01 resolvido, nenhum bloqueio normativo restante impede o
freeze. Os critérios de aceite existentes estão satisfeitos: calibração real
informada pelo usuário dentro dos limites aprovados, seleção numérica PASS,
regressão completa (126 testes + 11 subtests) PASS, Ruff PASS e diff check
PASS. O incidente anterior de leitura do vault e seu risco residual permanecem
registrados; não há nova evidência que o reabra como bloqueio de aceite.
