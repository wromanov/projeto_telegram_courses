# Requisitos — projeto_telegram_courses

## Diretriz vigente da experiencia de uso — CLI V1 Rich (2026-11-03)

APPROVED_INTERFACE_V1 = PYTHON + RICH / SIMPLE_CLI
NEXT_INTERFACE = GUI_AFTER_COMPLETE_COURSE_OPERATIONAL_VALIDATION
MIDNIGHT_GLASS = HISTORICAL_VISUAL_REFERENCE_ONLY

O operador quer somente dois caminhos: (1) marcar arquivos desejados de um curso; (2) selecionar "Baixar tudo" para os arquivos catalogados do curso, em ordem de modulo/aula/midia, inicialmente com um worker. A CLI deve permitir confirmar o plano, mostrar quantidade, tamanho de arquivo/lote, velocidade real MB/s, ETA fundamentado, erros, progresso, arquivos ja validos e resumo final. A implementacao deve usar componentes Rich simples, sem impor uma TUI fullscreen ou criar GUI agora.

A capacidade deve ser aferida com auditoria do fluxo existente e prova de um curso completo no escopo aprovado. O design e a implementacao de uma GUI sao trabalho posterior e independente do aceite da CLI. A referencia Midnight Glass nao define automaticamente o desenho final da GUI. Os limites, autorizacoes, dados sensiveis e condicoes de integridade existentes continuam aplicaveis.

---


DOCUMENT_ROLE = REQUIREMENTS  
BASELINE_STATUS = APPROVED_USER_BASELINE_RECONCILED  
RECONCILED_AT = 2026-10-05 / America/Sao_Paulo  
PRODUCT_SCOPE = GENERIC_MULTI_CHANNEL_TELEGRAM_COURSE_TOOL  
FIRST_REAL_VALIDATION_TARGET = RASMOO  
INITIAL_INTERFACE = WINDOWS_CLI_WITH_RICH

Fonte: Card B do usuário, seções 3–6, referenciado em [APPROVALS_AND_DECISIONS.md](../governance/APPROVALS_AND_DECISIONS.md). IDs, títulos, escopo e limites são o baseline aprovado. Descrições e evidências abaixo operacionalizam esse baseline junto à arquitetura/fundação aprovada; não afirmam recuperar texto original mais detalhado nem resultados de testes. Limites numéricos de memória, desempenho e paralelismo máximo serão definidos com evidência na unidade pertinente, antes de seu aceite.

## Requisitos funcionais

Prioridade inicial para todos os FRs; retomada em bytes continua condicional dentro de FR-12. Status: planejados, sem implementação. Dependências e unidades de entrega constam de [SPRINTS.md](../continuity/planning/SPRINTS.md).

| ID | Título | Comportamento requerido | Evidência de aceite planejada |
|---|---|---|---|
| FR-01 | Telegram Authentication | Autenticar a conta do próprio usuário pelas interfaces legítimas do Telegram. | Integração separada comprova login e reutilização de sessão; falhas são explícitas. |
| FR-02 | Channel Discovery | Descobrir e selecionar canais acessíveis à conta autenticada. | Canal acessível é identificado pelo gateway; indisponibilidade é reportada sem contorno. |
| FR-03 | Message Catalog | Catalogar mensagens e associações de mídia por identidade de canal/mensagem. | Scanner e persistência preservam identidade, metadados e associações sem duplicatas. |
| FR-04 | Hierarchical Parsing | Interpretar Channel → Track? → Course → Module? → Lesson → MediaItem. | Fixtures comprovam hierarquia e associações; Track/Module opcionais conforme estrutura real. |
| FR-05 | Generic Parser Model | Permitir parsers plugáveis e independentes do transporte, com RasmooParser e GenericParser iniciais. | Contrato e seleção funcionam com fixtures; nenhum marcador RASMOO é dependência universal. |
| FR-06 | Selective Download | Selecionar mídias, cursos e módulos para download. | S4 valida uma mídia; S5 valida que plano e fila respeitam a seleção. |
| FR-07 | Local Organization | Organizar arquivos conforme catálogo e política de caminhos Windows. | Caminhos determinísticos e sanitizados preservam identidade sem sobrescrever colisões silenciosamente. |
| FR-08 | Media Support | Baixar mídias suportadas pelo fluxo inicial e interfaces legítimas adotadas. | Amostras suportadas são transferidas e validadas; tipos raros/especiais têm condição explícita de suporte. |
| FR-09 | Persistent State | Manter catálogo e estado operacional local em SQLite. | Reinício preserva registros e checkpoints; transações e unicidade são verificadas em banco temporário. |
| FR-10 | Incremental Synchronization | Sincronizar incrementalmente e reconciliar alterações observadas. | Execução repetida não duplica catálogo; fixtures verificam checkpoints/atualizações. Alcance de detecção de edições/remoções deve ser definido antes de S7. |
| FR-11 | Deduplication | Evitar novo download de mídia corretamente identificada e validada. | Segunda execução não duplica o item; flag do banco e existência física isoladas não bastam. |
| FR-12 | Failure Recovery | Recuperar falhas/interrupções com estados explícitos, retries limitados e reconciliação. | Testes locais exercitam falhas/partiais; retomada em bytes exige teste técnico real da fundação. |
| FR-13 | Pre-scan | Inspecionar catálogo e seleção antes do download. | CLI mostra varredura, mídias e tamanhos conhecidos/desconhecidos antes da transferência. |
| FR-14 | Progress | Exibir progresso útil na CLI Rich. | Fluxo distingue progresso, conclusão e falha sem afirmar sucesso antes da validação física. |
| FR-15 | Logging | Registrar eventos operacionais e falhas com contexto seguro. | Console/logs permitem diagnóstico sem credenciais, códigos de login ou conteúdo de sessão. |
| FR-16 | Configuration | Configurar caminhos, workers, retries, logging e opções de validação. | Configuração válida é aplicada; inválida falha de forma controlada; segredos sem fallback fixo. |

## Requisitos não funcionais

Prioridade inicial; planejados e ainda sem verificação de produto.

| ID | Título | Restrição e evidência planejada |
|---|---|---|
| NFR-01 | Windows Compatibility | Fluxos compatíveis com Windows; smoke de execução em S0 e pacote em S10. |
| NFR-02 | Large File Memory Usage bounded | Streaming com memória limitada, sem carregar arquivo inteiro; medição com arquivo grande antes do aceite pertinente. |
| NFR-03 | Concurrency bounded/configurable | Workers limitados/configuráveis; padrão 2; concorrência ilimitada proibida; máximo operacional depende de benchmark. |
| NFR-04 | FloodWait Handling | Respeitar espera/rate limit do Telegram; testes simulados ou reproduzíveis verificam pausa e recuperação sem bypass. |
| NFR-05 | Credentials not versioned | Credenciais fora do versionamento; inspeção de configuração/logs e posterior controle de exclusão no bootstrap. |
| NFR-06 | Telegram Session Protection | Sessões sensíveis fora do versionamento/logs e protegidas localmente. Controle Windows concreto definido/verificado antes de sessão real em S1. |
| NFR-07 | Windows Filename Sanitization | Sanitizar caracteres reservados, dispositivos, pontos/espaços finais e colisões; testes unitários específicos. |
| NFR-08 | Maintainability | Gateway, parsers, aplicação e persistência delimitados; dependências e SQL confinados aos adapters/repositórios. |
| NFR-09 | Unit Tests without live Telegram | Suíte normal sem login, rede ou credenciais Telegram, usando fixtures/adapters falsos. |
| NFR-10 | Telegram Integration Tests separated | Integração explicitamente separada da suíte normal, com acesso legítimo e amostra controlada. |

## IN_SCOPE inicial

- Autenticação com conta própria e canais acessíveis à conta.
- Catalogação, parsers de estrutura plugáveis, RasmooParser e GenericParser.
- Seleção de curso/módulo, download e organização local.
- SQLite, deduplicação, sincronização incremental, retries e recuperação.
- Logs, progresso, configuração e CLI Windows com Rich.

## OUT_OF_SCOPE inicial

- GUI desktop, mobile, servidor web, multiusuário, cloud service e streaming integrado.
- Redistribuição/publicação de conteúdo e upload automático para terceiros.

## CONDITIONAL

- Retomada em bytes: application-layer, refetch e validação de .part; aceita somente depois de interrupção/reinício/continuação real com arquivo grande.
- Mídias raras/especiais, alto paralelismo e canais sem estrutura consistente: dependem de contrato e validação próprios, sem promessa universal.
- Hash de arquivo: opcional/configurável; validação de tamanho e identidade continua obrigatória.

## FUTURE

GUI fora do escopo inicial; migração para TDLib preservada como alternativa. Distribuição Windows é PHASE 8/S10, depois de validação real, conforme roadmap.

## NON_GOALS

- Automação de mouse/Telegram Desktop quando a API for suficiente.
- Bypass de content protection, acesso não autorizado, bypass de autenticação e contorno de mecanismos antiabuso.

## ACCESS_BOUNDARY

Somente conteúdo normalmente acessível à própria conta e permitido pelas interfaces legítimas utilizadas. Conteúdo protegido/restrito não é contornado e indisponibilidade é reportada. O formato = / == / === / #Fxxx é um parser suportado, sem dependência universal da arquitetura.

## Rastreabilidade

[ARCHITECTURE.md](../architecture/ARCHITECTURE.md) define limites/ADRs; [ENGINEERING_FOUNDATION.md](../engineering/ENGINEERING_FOUNDATION.md) define contratos; [ROADMAP.md](../continuity/planning/ROADMAP.md) e [SPRINTS.md](../continuity/planning/SPRINTS.md) definem sequência/evidências. O aceite real depende dos gates de cada unidade; este documento não inicia nem autoriza execução.

## Refinamento de uso da CLI — 2026-11-03

USER_DECISION = SELECIONAR_ARQUIVOS_OU_BAIXAR_TUDO_EM_ORDEM
SCOPE = SELECTED_COURSE / NOT_ENTIRE_TELEGRAM_CHANNEL
BASELINE_FR = FR-06, FR-07, FR-09, FR-11, FR-13, FR-14
STATUS = USER_EXPECTATION / END_TO_END_PRODUCT_PROOF_PENDING

A experiencia minima utilizavel e: abrir catalogo de cursos, escolher um curso, marcar/desmarcar arquivos especificos (multi-selecao entre modulos) OU escolher 'Baixar tudo' para enfileirar todos os arquivos conhecidos do curso em ordem de modulo/aula/midia. O plano mostra quantidade, tamanho total conhecido, limites e arquivos desconhecidos. Executar somente apos confirmacao apropriada; mostrar progresso/velocidade MB/s/ETA quando mensuraveis e status; validar e organizar arquivos, persistir estado e deduplicar apos reinicio.

Selecionar tudo em um catalogo parcial nao e evidencia de que todas as midias do curso remoto foram descobertas. Exibir cobertura/indeterminacao e nunca chamar o curso de 'completamente baixado' sem validar o conjunto completo elegivel. A nova especificacao nao autoriza downloads reais, elimina controles de integridade ou muda o escopo dos contratos congelados. Ver COURSE_DOWNLOAD_E2E_GATE no plano de sprints.
