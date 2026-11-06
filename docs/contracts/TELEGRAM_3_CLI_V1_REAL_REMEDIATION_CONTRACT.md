# CLI V1 — Contrato de correção operacional

ACTIVITY_ID: TELEGRAM-3-CLI-V1-REAL-REMEDIATION-01  
VERSION: 1.0  
AUTHOR_ROLE: ARCHITECT  
CONTRACT_GATE: CLOSED_APPROVED_BY_ARCHITECT  
IMPLEMENTER: ROOT  
GIT_PUBLICATION: NOT_AUTHORIZED  
REAL_MEDIA_DOWNLOAD_THIS_ACTIVITY: NOT_AUTHORIZED

## 1. Decisão e autoridade

Corrigir a aplicação existente por composição dos componentes implementados. A implementação local é autorizada pelo card atual após CLOSED_APPROVED_BY_ARCHITECT; não depende de novo card ou de nova aprovação humana para editar código. Este contrato não altera os contratos congelados S4–S9 nem declara aceite operacional. A demonstração permanece uma capacidade offline separada e não prova funcionamento real.

O root implementará e validará. O architect é somente leitura, autor deste conteúdo e responsável pelo fechamento técnico do contrato. As authorities de continuidade são docs/continuity/PROJECT_STATE.md, ACTIVE_AUTHORITY_MAP.md e PROJECT_GOVERNANCE_BINDING.json; o card atual é a autorização específica desta correção. Preservar todos os arquivos WIP e evidências existentes.

## 2. Fatos, evidências e hipóteses

| Classificação | Constatação | Evidência |
|---|---|---|
| FATO de código | interactive compõe navegação, planejamento e confirmação, mas não um executor operacional. | cli.main chama run_interactive_catalog sem executor; interactive_catalog_cli só encaminha confirmação a _run_authorized_offline_fixture quando recebe OfflineCourseSandbox. |
| FATO de código | O leitor interativo pressupõe catálogo S3, incluindo catalog_runs e catalog_nodes.is_active; não prepara o esquema. | SQLiteCatalogRepository.list_interactive_channels/load_interactive_snapshot e seus tratamentos CATALOG_SCHEMA_UNSUPPORTED. |
| FATO de código | As migrações necessárias já existem e são encadeadas. | DownloadRepository.migrate -> SQLiteCatalogRepository.migrate -> SQLiteMessageRepository.migrate; versões 1,6,7; 2,3; 4,5 respectivamente. |
| FATO de código | Não há preparação pública coordenada que faça backup verificado antes dessas migrações e do primeiro write operacional. | Migradores locais abrem WAL e executam transações, sem backup. |
| FATO de código | O scanner de mensagens resolve o canal por ID mediante get_input_entity e converte ValueError em CHANNEL_UNRESOLVED. Existe recuperação peer limitada em outro caminho. | TelethonGateway._input_entity_for_selected_channel, recover_selected_channel_peer e iter_channel_metadata. |
| FATO de código | A recuperação peer metadata-only não alimenta automaticamente o scanner operacional. | _iterate_messages chama _input_entity_for_selected_channel; _iterate_channel_metadata usa _selected_metadata_peer e omite texto. |
| FATO de código | Vários branches de validação da descoberta retornam ADAPTER_FAILURE sem motivo específico; erros externos já têm classe sanitizada e contadores. | TelethonGateway.discover_channels e ChannelDiscoveryApplication.discover. |
| EVIDÊNCIA fornecida pelo operador | Python 3.14.7, CLI instalada, banco com 2 canais/10 mensagens/5 mídias/0 nós, catalog_runs ausente, CATALOG_SCHEMA_UNSUPPORTED e descoberta ADAPTER_FAILURE. | Card desta atividade; revalidar somente o necessário sem publicar dados privados. |
| HIPÓTESE, não causa operacional provada | Restauração por StringSession pode deixar cache de entidades insuficiente para resolver ID numérico em outra instância. | Deficiência estática demonstrada; o comportamento operacional requer diagnóstico limitado. |
| NÃO COMPROVADO | Causa concreta do ADAPTER_FAILURE, autenticação efetiva atual, acesso ao canal e estrutura remota. | O architect não abriu sessão, fez RPC nem acessou banco operacional. |

A assinatura TL instalada aceita flags opcionais, mas o decoder produz booleanos: não alterar _channel_kind por inferência a partir somente da assinatura. Não atribuir o ADAPTER_FAILURE observado à resolução de peer sem reprodução e evidência de estágio.

## 3. Correção executável

### 3.1 Preparação e compatibilidade SQLite

Adicionar um serviço pequeno de preparação do banco, por exemplo database_preparation.py. Ele deve inspecionar esquema e versões usando conexão read-only, identificar esquema legado conhecido versus atual e bloquear esquema desconhecido/inconsistente com categoria clara. Não inserir marcadores de migração para esconder coluna ausente nem corrigir SQL desconhecido por tentativa.

Antes de qualquer alteração de banco preexistente pelo novo fluxo, exigir backup SQLite consistente, usando sqlite3.Connection.backup; não copiar somente o arquivo principal de um banco WAL aberto. Validar integridade do backup e registrar hash/caminho privado, versões e contagens por tabela sem conteúdo. Validar também foreign_key_check quando o esquema possuir FKs. Backup deve ser arquivo exclusivo, nunca sobrescrito, com proteção de diretório e rejeição de redirecionamentos/reparse/hardlinks inseguros. Falha do backup ou da verificação bloqueia a alteração.

Ensaiar primeiro a cadeia existente de migrações em uma cópia isolada. Verificar preservação de IDs, mensagens, mídias, associações e downloads, integridade, versões e repetição idempotente. Para banco conhecido, reutilizar migradores existentes; criar migration nova somente se uma lacuna real e reproduzida exigir, sem alterar SQL congelado retroativamente. Uma versão aplicada com formato incompatível deve bloquear e apresentar diagnóstico.

A abertura read-only de catálogo já atual deve continuar possível sem migração. Banco legado deve receber ação compreensível de preparação/catalogação; não terminar apenas com CATALOG_SCHEMA_UNSUPPORTED. Banco novo pode ser criado por ação explícita de catalogação. Não migrar silenciosamente ao apenas listar/plano.

Root valida automaticamente somente cópias isoladas. Qualquer ação sobre banco operacional exige backup verificado, controle de exclusão de writer ativo e autorização operacional vigente; não inferir autorização para write real da autorização de editar código.

Rollback: cada migrador deve manter rollback transacional da sua etapa. Como a cadeia tem várias transações, uma falha intermediária preserva o backup e classifica preparação incompleta. Não restaurar automaticamente por overwrite. Encerrar conexões/writers, preservar banco falho e sidecars como conjunto, verificar o backup e realizar restauração controlada apenas com autorização apropriada; depois revalidar integridade. Nunca apagar WIP, .part ou evidências para recuperar esquema.

### 3.2 Diagnóstico e acesso Telethon

Preservar CredentialVault, DPAPI CURRENT_USER, ACLs e _ProtectedSessionVault; não exportar sessão, api_hash, auth_key, telefone, OTP, 2FA ou entidades TL. A criação/restauração de gateway real deve ocorrer somente depois de preflight e autorização de acesso de metadados G0 aplicável, em TTY nativo. Não iniciar login automático ao abrir catálogo local; quando necessário orientar para auth com prompts protegidos existentes.

Adicionar códigos allowlist de estágio/motivo aos branches ADAPTER_FAILURE da descoberta e à resolução de peer: perfil inválido, estado, resposta/tipo/coleções, overflow, entidade conflitante, ID inválido, cursor ausente/repetido, restore e cleanup. Usar classe de exceção sanitizada e posições de stack já sanitizadas quando úteis; proibir str(error), repr(TLObject), fonte/locals, títulos, usernames, mensagens, IDs privados ou caminhos de sessão nos logs exportáveis. Preservar categoria pública e causa primária quando cleanup falhar.

Reproduzir cada defeito de código efetivamente corrigido com cliente Telethon double. A deficiência de peer deve ser resolvida com identidade exata e limites: usar entidade InputPeer do canal escolhido mantida na instância ou recuperação limitada existente adaptada ao scanner. Nunca varrer diálogos ilimitadamente, selecionar por título ou persistir access_hash em catálogo aberto. O caminho metadata-only limitado atual não pode ser usado como scanner RASMOO, pois omite texto. A varredura operacional usa o scanner existente e texto necessário à classificação dentro do escopo aprovado.

Após instrumentação, o root pode diagnosticar metadados reais somente se preflight/G0 vigente for satisfeito. Respeitar limites DiscoveryLimits existentes, timeouts, receive_updates=False, catch_up=False, retries finitos e cleanup. Uma falha externa deve ser demonstrada por estágio/categoria sanitizados; não alegar que mock PASS comprova autenticação real. Sem TTY ou autorização vigente, registrar a validação real como bloqueada e entregar implementação testada.

### 3.3 Descoberta e catalogação utilizáveis

Adicionar ao ponto de entrada publicamente documentado telegram-courses interactive uma pequena camada de menu operacional com opções para abrir catálogo local, descobrir canais e atualizar/construir catálogo. Reutilizar ChannelDiscoveryApplication, ScanApplication/MessageScanner, SQLiteMessageRepository, CatalogApplication, ParserRegistry e RasmooParser. O comando sem --database deve usar Configuration.database_path. Preservar comandos existentes e a demo.

Descoberta produz snapshot; seleção usa identidade exata desse snapshot. Persistir somente o canal explicitamente selecionado, após preparação segura. Exibir canal, parser, max_messages e timeout antes da varredura, com confirmação de consulta de metadados. Exigir limites positivos explícitos; não criar varredura ilimitada ou automática ao abrir o programa. No contexto S9, limites/supervisor/ledger/G0 congelados continuam obrigatórios; o novo fluxo deve recusar ambientes de supervisão S9 que não consiga honrar integralmente, apontando ao launcher existente.

Permitir construir catálogo a partir de mensagens locais já persistidas, sem RPC. RASMOO deve ser seleção explícita ou configuração existente do canal, sem heurística nova de gramática. Parser genérico permanece disponível e conteúdos não classificáveis devem aparecer como não classificados, sem inventar cursos/aulas. Não expandir gramática sem reprodução de formato e evidência suficiente.

catalog_runs.COMPLETE significa construção concluída sobre o snapshot local, não completude remota. A interface deve comunicar status/stop_reason da varredura e manter parcial/desconhecido quando não houver EOF demonstrado; um incremental recente não basta para afirmar cobertura histórica completa. Baixar tudo significa todos os elegíveis catalogados do curso escolhido. Preservar IDs, associações, ordem S5, índices estáveis e paginação de 20; distinguir ordem determinística de pedagógica.

### 3.4 Integração confirmação -> fila real

Implementar um serviço operacional pequeno, por exemplo course_live_execution.py, para consumir ConfirmedCoursePlan e uma autorização de execução específica e de uso único. A autorização deve vincular banco, plano/review completo, seleção exata, curso/canal, destino, integridade e limites. Confirmar plano e autorizar transferência são ações distintas; a segunda deve mostrar claramente acesso real e requerer curso, destino, caps e confirmação TTY. Não expor --confirm, environment ou opção oculta para pular essa fronteira no fluxo novo.

Reutilizar a revalidação completa de CoursePlanReview.matches_after_confirmation e load_course_review_context imediatamente antes da fila. Deriva de identidade, seleção, ordem, status, tamanho, destino, contexto ou limites invalida autorização. Disco insuficiente bloqueia; desconhecido com pendências bloqueia; delta >=1 GiB exige nova confirmação; delta menor só permite capacidade ainda suficiente. Tamanhos desconhecidos e exclusões permanecem visíveis e nunca entram por inferência.

A única cadeia de transferência será DownloadPlan -> DownloadQueue(workers=1) -> SingleMediaDownloadApplication -> gateway Telethon. Usar uma instância lazy de gateway com restauração compartilhada, criada apenas após a autorização pertinente; fechar em todos os caminhos. Expor corretamente stream_media, get_file_hashes e validate_media_identity. Não executar loop manual de mídias nem duplicar orçamento, retry, integridade, reserva, dedupe ou persistência.

Extrair apenas a orquestração comum necessária do executor offline para reutilizar callbacks/progresso/summary; não permitir gateway real dentro de OfflineCourseSandbox nem enfraquecer marcador, root ou autorização fake. A implementação do adapter real fica na composição operacional, sem dependência de Rich no domínio.

Manter REMOTE_HASH_REQUIRED e V1 ativos; não liberar modos V2, prefixos sem prova, exceções de piloto ou caminhos de recuperação congelados. Preservar callbacks protegidos, métricas físicas versus orçamento, MB/s decimal, clock monotônico, ETA indisponível sem base e resumo derivado de QueueResult com os oito estados v0.2. Preservar S5 retry/cooldown; homologação S9 para no primeiro FloodWait e usa seus limites mais restritos.

Ctrl+C deve cancelar cooperativamente a task da fila, aguardar sua limpeza, impedir novas admissões e exibir resumo autoritativo. Preservar .part/checkpoints/owner/estados e integridade S6. Não criar estado persistido paralelo de fila. ALREADY_VALID não deve abrir gateway nem receber payload desnecessário.

## 4. Arquivos e fronteira de alteração

| Arquivo previsto | Responsabilidade autorizada |
|---|---|
| src/telegram_courses/cli.py | Composição operacional, menus/argumentos compatíveis e preparação segura dos caminhos novos. |
| src/telegram_courses/interactive_catalog_cli.py | Navegação integrada, revisão e hook de execução com autorização separada. |
| src/telegram_courses/telethon_gateway.py | Diagnóstico sanitizado e correção reproduzida de descoberta/resolução exata do canal. |
| src/telegram_courses/channel_discovery.py | Causa/cleanup sanitizados somente se necessário à propagação correta. |
| src/telegram_courses/database_preparation.py (novo, nome equivalente permitido) | Inspeção read-only, backup verificado e invocação controlada de migradores existentes. |
| src/telegram_courses/course_live_execution.py (novo, nome equivalente permitido) | Autorização operacional e composição do executor real. |
| src/telegram_courses/course_execution.py, course_offline_execution.py, course_progress_rich.py | Extração mínima da orquestração compartilhada e presenter reutilizável, preservando isolamento fake. |
| catalog_repository.py / sqlite_repository.py / scan_application.py | Somente adaptações comprovadamente necessárias de metadata de canal, preparação ou associação do peer; SQL permanece no repository. |
| tests/unit e tests/integration pertinentes | Testes da integração real com doubles, cópias SQLite e fronteiras negativas. |
| docs/GUIA_WINDOWS_USO.md e relatório consolidado da atividade | Comandos, confirmações, evidências e limitações. |
| docs/continuity/PROJECT_STATE.md e handoff aplicável | Reconciliação do novo estado e ponto seguro de retomada. |

DownloadPlanner, DownloadQueue, SingleMediaDownloadApplication e migrations congeladas devem permanecer sem mudanças de semântica. Se uma correção mínima nesses arquivos for indispensável, demonstrar falha, manter invariantes e registrar evidência antes/depois; nenhuma autorização implícita para redesenhar.

## 5. Ordem de execução do root

1. Materializar contrato, obter conferência do architect e registrar CLOSED_APPROVED_BY_ARCHITECT.
2. Implementar preparação SQLite e ensaiar legado/atual, backup, falha e idempotência em cópias.
3. Completar diagnóstico de descoberta e resolução peer exata com reprodução offline.
4. Integrar menus de metadados/catálogo e fluxo de seleção/plano à execução operacional já existente, com dois consentimentos e um worker.
5. Executar testes focados, regressões afetadas, Ruff, compilação e git diff --check; corrigir falhas dentro do escopo.
6. Executar comando público com doubles em integração; depois diagnóstico real limitado somente se preflight/G0/TTY/autorizações vigentes permitirem. Nenhum payload real neste card.
7. Reconciliar estado e relatório; enviar resumo sanitizado ao chat canônico, distinguindo envio aceito, readback e resposta.

## 6. Aceites verificáveis

| Aceite | Evidência mínima |
|---|---|
| SQLite legado preservado | Fixture representativa com mensagens/mídias/downloads; backup íntegro e hash; migração; IDs e conteúdo preservados; segunda preparação idempotente; falha não perde backup nem dados; esquema desconhecido e path inseguro bloqueados. |
| Auth/discovery | Clientes TL doubles para AUTH_REQUIRED, sessão inválida, rede, FloodWait, resposta malformada, overflow permitido/indevido e cleanup; logs sem secrets; diagnóstico real observado ou bloqueio externo/TTY explícito. |
| Peer/scanner | Instância restaurada sem cache resolve somente canal selecionado por mecanismo limitado; não desvia de canal; falha preserva categoria; scanner mantém texto para parser; nenhuma mídia transferida. |
| Catálogo operacional | Fluxo público com snapshot/scan/build reais da aplicação sobre cópia sintética, parser RASMOO existente, hierarquia/exclusões/parcial corretos e reabertura. Construção real fica evidência separada quando autorizada. |
| Plano/fila | Seleção individual/múltipla/tudo chega exatamente à fila S5, ordem e workers=1; negativos de plano alterado, disco/caps, exclusões e autorização reutilizada; nenhum gateway antes da autorização. |
| Resultado/progresso | MB/s e ETA verificáveis por relógio controlado; retry/overlap sem progresso falso; callback falho não afeta motor; oito estados coerentes; ALREADY_VALID sem payload. |
| Cancel/recovery | Regressões C4 pertinentes e integração nova: cancelamento impede próximo item, preserva parcial/checkpoint/owner, não promove incompleto; reabertura retoma ou bloqueia pela regra S6. |
| Público/Windows | Executável instalado inicia interactive com configuração/defaults; testes do comando público com doubles; TTY/Unicode/cancelamento no PowerShell quando viável. Entrada simulada não prova teste manual. |
| Segurança | Testes negativos de bypass/ambiente S9, gateway real proibido no demo, backup ausente, path inseguro; contratos S4–S9 e guardas preservados; nenhum dado privado em fixtures/relatório. |
| Qualidade | Testes relevantes realmente executados PASS, Ruff e diff check PASS; não exigir suíte global sem justificativa. |

## 7. Limites e riscos residuais

Acesso ao cofre não prova sessão autenticada. Rede, ACL/DPAPI, TTY, identidade, rate limit ou ausência de amostra RASMOO suficiente podem impedir validação real e devem ser demonstrados como pendência específica. Causa real de ADAPTER_FAILURE não será marcada corrigida somente por nova instrumentação. Banco legado desconhecido pode exigir decisão após reprodução em cópia; não aplicar ALTER oportunista em produção.

As permissões deste card autorizam código local, migrações em cópias e diagnósticos necessários dentro das autorizações operacionais vigentes. Não autorizam transferência real nem alteração operacional sem backup/controle/autorização apropriados. Preflight/G0 antes de sessão/RPC e G4 específico antes de payload são obrigatórios quando aplicáveis; confirmações do produto não devem ser rotuladas como recibos S9 nem liberar ledger/supervisor ausentes. Sob ambiente S9, recusar o novo caminho se não puder preservar integralmente seus gates e utilizar o launcher existente.

O root não executará payload real nesta atividade. A homologação posterior exige autorização específica do curso, identidades, destino, limites, prazo, integridade e procedimento de interrupção; deve confirmar plano fresco e validar arquivo/SQLite/dedupe. Sem essa execução, não declarar PRODUCT_HOMOLOGATED nem download real PASS.

Resultado técnico permitido após implementação: READY_FOR_REAL_COURSE_HOMOLOGATION somente com integração implementada, qualidade PASS e requisitos reais de metadados evidenciados ou bloqueios externos claramente delimitados; se requisito funcional material permanecer ausente, IMPLEMENTATION_PARTIAL_WITH_BLOCKERS. Falha do gate de contrato: BLOCKED_BY_ARCHITECT_CONTRACT.

## 8. Alternativas rejeitadas

Rejeitados: outro downloader/fila/planner; reutilizar demo como caminho real; substituir scanner por metadata-only sem texto; migrar silenciosamente no leitor; copiar apenas .sqlite de WAL ativo; exportar sessão/access_hash; tratar erro genérico como causa confirmada; liberar V2 ou exceção de piloto; considerar todos os itens SKIPPED como curso completo; criar nova slice ou framework de TUI.

CONTRACT_GATE será alterado para CLOSED_APPROVED_BY_ARCHITECT somente após conferência deste arquivo materializado. Nenhuma implementação de Fase 2 antes disso.

## 9. Fechamento do gate arquitetural

CONTRACT_GATE: CLOSED_APPROVED_BY_ARCHITECT  
ARCHITECT_REVIEW: conferência integral da cópia materializada; conteúdo corresponde à minuta enviada, sem divergência técnica nem correção obrigatória.  
REVIEWED_COPY_SHA256_BEFORE_GATE_RECORD: 4AAF1AB889963330E014EC0E8E6F592981A70C202CDF9B116A5482D2302FB980  
S4_S9_CONTRACTS: UNCHANGED  
IMPLEMENTATION_AUTHORIZATION: USER_CARD / ROOT_IMPLEMENTATION_AFTER_ARCHITECT_GATE  
REAL_MEDIA_DOWNLOAD: NOT_AUTHORIZED  
OPERATIONAL_DATABASE_WRITE: NOT_AUTHORIZED_WITHOUT_VERIFIED_BACKUP_AND_REQUIRED_CONTROL  
ARCHITECT_GATE_DECISION: 2026-11-05
