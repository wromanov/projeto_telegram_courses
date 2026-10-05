# Requisitos — projeto_telegram_courses

DOCUMENT_ROLE = REQUIREMENTS  
BASELINE_STATUS = APPROVED_USER_BASELINE_RECONCILED  
RECONCILED_AT = 2026-10-05 / America/Sao_Paulo  
PRODUCT_SCOPE = GENERIC_MULTI_CHANNEL_TELEGRAM_COURSE_TOOL  
FIRST_REAL_VALIDATION_TARGET = RASMOO  
INITIAL_INTERFACE = WINDOWS_CLI_WITH_RICH

Fonte: Card B do usuário, seções 3–6, referenciado em [APPROVALS_AND_DECISIONS.md](../governance/APPROVALS_AND_DECISIONS.md). IDs, títulos, escopo e limites são o baseline aprovado. Descrições e evidências abaixo operacionalizam esse baseline junto à arquitetura/fundação aprovada; não afirmam recuperar texto original mais detalhado nem resultados de testes. Limites numéricos de memória, desempenho e paralelismo máximo serão definidos com evidência na unidade pertinente, antes de seu aceite.

## Requisitos funcionais

Prioridade inicial para todos os FRs; retomada em bytes continua condicional dentro de FR-12. Status: planejados, sem implementação. Dependências e unidades de entrega constam de [SPRINTS.md](../planning/SPRINTS.md).

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

[ARCHITECTURE.md](../architecture/ARCHITECTURE.md) define limites/ADRs; [ENGINEERING_FOUNDATION.md](../engineering/ENGINEERING_FOUNDATION.md) define contratos; [ROADMAP.md](../planning/ROADMAP.md) e [SPRINTS.md](../planning/SPRINTS.md) definem sequência/evidências. O aceite real depende dos gates de cada unidade; este documento não inicia nem autoriza execução.
