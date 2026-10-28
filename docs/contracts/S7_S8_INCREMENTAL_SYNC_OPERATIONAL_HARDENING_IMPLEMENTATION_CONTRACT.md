# S7 + S8 — Contrato integrado de implementação
**Projeto:** `projeto_telegram_courses`  
**Contrato:** `S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT`  
**Versão:** 1.0 — 2026-10-25  
**Estado:** APPROVED / FROZEN v1.0 / RATIFICADO PELO USUÁRIO EM 2026-10-25 / IMPLEMENTAÇÃO NÃO AUTORIZADA  
**Autoridade:** requisitos, arquitetura, fundação de engenharia e plano de sprints aprovados; decisão S6 de 25/10/2026  
**Execução:** S7 primeiro; S8 após resultado integrado de S7, mantendo a dependência formal de aceite. Nenhum início automático.

## 1. Objetivo e resultado esperado

Entregar duas sprints sequenciais em um único contrato técnico, para reduzir troca de contexto sem fundir seus aceites:
- **S7 — Incremental Synchronization:** detectar e incorporar mudanças observáveis do Telegram ao catálogo SQLite, com checkpoint durável, retomada de varredura interrompida e ausência de duplicatas;
- **S8 — Operational Hardening:** consolidar erros, retries, FloodWait, logs, progresso CLI Rich, configuração, verificações de espaço em disco, memória e concorrência limitada.

A especificação técnica NÃO concede autorização de implementação, testes novos, operações reais Telegram, commit ou push. Exige autorização específica antes da execução. S7 e S8 possuem gates e relatórios próprios; o contrato integrado não permite saltar dependências.

## 2. Fontes normativas e precedência

1. `docs/product/REQUIREMENTS.md`: FR-09, FR-10, FR-11 (S7); FR-12, FR-14, FR-15, FR-16 (S8); NFR-01–NFR-10 conforme pertinência.
2. `docs/architecture/ARCHITECTURE.md`: ADR-002 (TelegramGateway), ADR-003 (SQLite), ADR-004 (parsers), ADR-005 (resume), ADR-006 (Rich CLI), ADR-007 (workers), ADR-008 (sessão e retry).
3. `docs/engineering/ENGINEERING_FOUNDATION.md`: migrations SQL, estados, transações, proveniência e proteção de sessão, logging, erros, disk gate e testes.
4. `docs/continuity/planning/SPRINTS.md`: escopos e gates S7 e S8; `docs/continuity/PROJECT_STATE.md` governa estado, autorização e próximos passos.
5. `docs/contracts/S5_COURSE_SELECTION_PLANNER_QUEUE_CONTRACT.md` e `docs/contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md`: limites de fila, orçamento e integridade, sem alterações implícitas.
6. `docs/governance/APPROVALS_AND_DECISIONS.md` e `docs/reports/S6_FINAL_ACCEPTANCE_DECISION_2026-10-25/REPORT.md`: S6 encerrada com exceções, não homologada integralmente contra V1.

Divergência ou lacuna normativa material: **STOP / REPORT**; não escolher silenciosamente a interpretação mais permissiva. Não modificar os contratos congelados anteriores para satisfazer a implementação.

## 3. Situação de entrada (observada por inspeção documental de 25/10)

- S0–S5 fechadas; S6 `CLOSED_WITH_EXCEPTIONS`; Gate A `PARTIAL`, Gate B `BLOCKED_BY_REMOTE_EVIDENCE`.
- `V1_ACTIVE=YES`, `V2_GLOBAL=OFF`. Não usar `COMPLETED_V2` como `DOWNLOADED` V1.
- Código existente: `message_scanner.py`, `scan_application.py`, `sqlite_repository.py`, `catalog_repository.py`, `telegram_gateway.py`, `telethon_gateway.py`, `cli.py`, `config.py`; migrations em `src/telegram_courses/migrations/`.
- O scanner atual tem `ScanRequest` com limite e timeout, `ScanStatus` COMPLETE/PARTIAL/FAILED, `scan_runs` com watermark, `sync_checkpoints` por run e `persist_batch` transacional. **Isso não prova high-water durável incremental entre runs, detecção de edições antigas ou deleções.**
- SQLite é autoridade do catálogo/checkpoints; Telegram é autoridade de conteúdo remoto; filesystem é autoridade de arquivos físicos. Não transformar ausência numa página parcial em deleção.
- A implementação S7/S8 deve trabalhar sobre o checkout efetivo e WIP existente. Primeiro inspecionar diffs e APIs; não presumir HEAD limpo nem sobrescrever código já modificado.

## 4. Contrato de comportamento S7 (FR-09, FR-10, FR-11)

### S7-01 — Política de checkpoint incremental

1. Distinguir **high-water confirmado da sincronização entre runs** de (a) limite superior/watermark de uma varredura e (b) cursor de progresso de um run parcial. Não tratar esses três valores como intercambiáveis.
2. Persistir identidade do canal, checkpoint comprometido, status do run, timestamps e contadores auditáveis. Só avançar o high-water **após persistência transacional do lote e conclusão das condições de avanço**, nunca antes da durabilidade dos dados correspondentes.
3. Em execução inicial, derivar baseline apenas de checkpoint verificável existente ou criar baseline por varredura limitada/explicitamente estabelecida. Não interpretar automaticamente `last_message_id` de um run parcial como último ID já sincronizado em definitivo.
4. Ao reiniciar após falha, recuperar a partir do último checkpoint comprometido e reprocessar uma janela conservadora quando necessário. Reprocessamento idempotente é preferível a perda silenciosa.
5. Identidade e unicidade: chave remota `(telegram_chat_id, telegram_message_id)`; associação de mídia conserva `media_ordinal` e identidade remota disponível. Execuções repetidas não criam mensagens/mídias duplicadas.

### S7-02 — Escopo explícito da detecção

1. **Novas mensagens:** detectar acima do high-water durável com varredura incremental limitada, ordenação/cursores consistentes e avanço seguro.
2. **Edições de mensagens já vistas:** suportar quando a mensagem for reobservada em janela limitada de reconciliação ou refetch explicitamente autorizado, comparando `edit_date_utc` e campos persistidos. **Não prometer detecção arbitrária de edições antigas fora do intervalo observado.**
3. **Mídia substituída ou alterada:** comparar identidade/tamanho/metadados da mídia; invalidar qualquer pressuposto de que download anterior continua válido para a nova identidade. Preservar arquivos físicos e histórico; tratar a mudança no catálogo/planejamento sem sobrescrever mídia local nem falsificar `DOWNLOADED`.
4. **Mensagens apagadas, inacessíveis ou removidas:** distinguir confirmação remota de exclusão de indisponibilidade, rate limit, permissão insuficiente e resultados parciais. Sem prova inequívoca, classificar `UNVERIFIED/NOT_OBSERVED` e **não** apagar registros, associações, downloads ou arquivos. Exclusão/tombstone lógica exige evidência, política explícita e transação segura; exclusão física automática é proibida.
5. **Perda de acesso a canal:** falha controlada; checkpoint anterior preservado, sem varrer como se fosse canal vazio.
6. **Conteúdo RASMOO e genérico:** a sincronização não depende dos marcadores `= / == / === / #Fxxx`; usar o parser pluggable aprovado e preservar nós/associações estáveis na reconstrução.

### S7-03 — Catálogo, downloads e fronteiras

1. Reconciliar a mudança da mensagem com catálogo, mídia e estado operacional sem violar FKs, IDs estáveis ou deduplicação. A geração de catálogo é separada da leitura remota e deve preservar associações de mídias não alteradas.
2. Não alterar `.part` ou final baixado como efeito colateral de sincronizar. Para item em fila, `PARTIAL` ou `DOWNLOADING`, sinalizar/reconciliar conflito de identidade antes de novo planejamento; nunca promover para `DOWNLOADED` sem validação física e regra S6 V1.
3. `REMOTE_HASH_REQUIRED`, checagem de prefixo antes de append, fail-closed e orçamento S5 permanecem obrigatórios. A exceção de aceite da S6 não é licença para reduzir proteção.
4. Isolar detalhes Telethon no `TelethonGateway`; modelos de domínio e aplicação continuam próprios do projeto. Parsers não fazem Telegram/SQL/download.

### S7-04 — Migrations e compatibilidade

Preferir aproveitar schema/APIs existentes. **Migration aditiva, numerada e reversivelmente documentada** somente se a política de high-water, reconciliação de edições ou marcação de confirmação de remoção não puder ser satisfeita pelo schema atual. Não alterar migrations 001–005 já aplicadas, não executar migration em SQLite real do usuário nesta atividade sem autorização e não introduzir SQL fora da camada repository. Testar banco vazio e banco com dados legados, FK/WAL/busy_timeout, atomicidade e idempotência de reexecução. Especificar comportamento de compatibilidade para dados históricos sem checkpoint novo.

### S7-05 — Interface e limites

Expor modo incremental na CLI Rich existente, com seleção explícita de canal, escopo/limite de reconciliação e resultado de run (`new`, `updated`, `unchanged`, `unverified`, `interrupted`). Evitar nova CLI paralela, fluxo full scan implícito, sincronização infinita ou cron/scheduler. Parâmetros devem respeitar política de configuração e não exigir credenciais em argumentos/logs. O alcance inicial de busca de edições/remoções deve ser **limitado, configurável e expresso ao usuário**, sem alegar completude universal.

## 5. Contrato de comportamento S8 (FR-12, FR-14, FR-15, FR-16)

### S8-01 — Erros e retry

- Classificar e tratar `AuthenticationError`, `AccessError`, `TelegramRateLimitError`, `NetworkError`, `ParserError`, `DatabaseError`, `StorageError`, `InsufficientDiskSpace`, `DownloadError`, `IntegrityError` e `ConfigurationError`, reutilizando taxonomia aprovada e preservando exceções/categorias existentes quando compatíveis.
- Transientes: retry **finito** com backoff exponencial e jitter, respeitando limites de tentativas/cancelamento da aplicação. Limites concretos vêm da configuração/política S5 vigente, não de valores inventados neste contrato.
- `FloodWait`: adapter traduz para erro de domínio com `retry_after_seconds`; aplicação decide espera/aborto conforme budget. Proibidos espera oculta, retry infinito, bypass de rate limit e multiplicação indevida de reservas.
- Falhas terminais de login/acesso/configuração/integridade, proteção de conteúdo e espaço insuficiente não recebem retry automático. Falhas inesperadas geram erro controlado e diagnóstico sanitizado.

### S8-02 — Logs, progresso e operação

- Log estruturado com timestamp UTC, severity, componente, evento e contexto mínimo (run/correlation ID, categoria, tentativa e estado). Sanitizar/redigir `api_hash`, tokens, códigos, senhas, `StringSession`, caminhos sensíveis e payloads de mensagens conforme pertinência. Não gravar conteúdo sensível em tracebacks/recibos.
- Rich CLI mostra progresso real e distingue `COMPLETED`, `PARTIAL`, `FAILED`, `CANCELLED`, `SKIPPED`. Nunca exibir sucesso antecipado à persistência/validação física.
- Configuração via TOML + ambiente + argumentos conforme precedência aprovada; inválidos falham com mensagem útil sem fallback secreto; continuar compatível com configuração existente e não colocar credenciais em TOML versionado.
- Cancelamento e interrupção preservam checkpoint e dados duráveis; não esconder erro por falha de cleanup.

### S8-03 — Segurança de disco, memória e workers

- Antes de iniciar lote/transferência com tamanho conhecido, estimar bytes restantes e margem de segurança contra espaço disponível. Indisponível/insuficiente: bloquear **antes de escrever** e registrar condição. Tamanho desconhecido não vira estimativa fictícia.
- Streaming de arquivo grande sem carregar arquivo inteiro. Definir limiar mensurável de pico de memória em ambiente controlado antes de declarar NFR-02 plenamente aceito; produzir medida e hipótese de variação. Não alegar memória limitada com base apenas em revisão estática.
- Workers padrão 2, limitados/configuráveis; teto operacional depende de benchmark aprovado, sem concorrência ilimitada. Limites, reservas, retries e budgets existentes em S5 não podem ser ampliados silenciosamente.
- DPAPI `CURRENT_USER`, sessão fora do repositório e dos logs; autenticação, acesso e content protection seguem regras já aprovadas.

## 6. Sequência de implementação autorizável

Uma só atividade formal ativa de cada vez. **Não dividir em 10 microatividades artificiais.** Use dois estágios técnicos com relatórios e aceite próprios:

**ESTÁGIO 1 — S7**
1. Preflight read-only: verificar estado real do checkout/WIP; mapear APIs e schema, demonstrar lacuna entre scan convencional e sync incremental; registrar arquivo-alvo e eventual necessidade de migration.
2. Implementar comportamento S7-01..05 em alterações delimitadas (aplicação, repos, gateway/CLI, migrations somente se necessárias).
3. Validar fixtures offline de mensagens novas/editadas/substituídas/apagadas, perda de acesso, run parcial, reinício, overlap de janelas, banco legado, dedup e integridade de estado.
4. Executar testes focados primeiro; somente então uma regressão offline acumulada de S7, preservando inventário e status. Não usar o Harness específico de prova S6 para homologar S7.
5. Emitir relatório e encaminhar aceite S7. Não prosseguir à implementação S8 antes do aceite requerido pela governança.

**ESTÁGIO 2 — S8**
1. Sobre S7 aceita, completar S8-01..03 sem redesenhar o domínio nem substituir políticas existentes.
2. Validar matriz de erro/retry/FloodWait, sanitização de logs, progresso, configuração, disco, memória e concorrência em fixtures/SQLite/FS isolados.
3. Executar testes focados e uma regressão offline integrada S1–S8 com inventário explícito e evidências duráveis; não iniciar sucessivas reexecuções por conveniência.
4. Emitir relatório e encaminhar aceite S8. A prova real de S9, o empacotamento de S10 e publicação exigem autorizações/gates próprios.

**Validações reais Telegram** são separadas da suíte offline, não estão autorizadas por este contrato e só ocorrem em escopo controlado aprovado. O mesmo vale para escrita em banco, sessão e arquivos originais do usuário.

## 7. Matriz objetiva de aceite

| ID | Aceite | Evidência mínima |
|---|---|---|
| S7-A1 | Novas mensagens sincronizadas sem duplicatas | Fixture de 2 runs, mesmo canal/IDs, mudança real e idempotência |
| S7-A2 | Checkpoint seguro | Falha/cancelamento entre leitura e commit; reinício não salta mensagens nem promove cursor parcial |
| S7-A3 | Edição e substituição de mídia | Janela de reconciliação controlada, update determinístico, identidade remota e download antigo preservados |
| S7-A4 | Exclusão/indisponibilidade não confundidas | Fixture de deleção confirmada versus scan parcial/acesso negado; nenhum tombstone ou delete falso |
| S7-A5 | Persistência e compatibilidade | SQLite temporário novo e legado; migrations condicionais, FK/transação, catalog IDs estáveis |
| S7-A6 | Integração CLI/parsers | Execuções offline da CLI com parser especializado/genérico, status e limites explícitos |
| S8-A1 | Retry/FloodWait corretos | Transientes com limite; terminal sem retry; FloodWait traduzido e budget respeitado |
| S8-A2 | Logs/CLI/config seguros | Segredos redigidos, status confiáveis, precedência e entradas inválidas cobertas |
| S8-A3 | Disco/memória/workers seguros | Gate de espaço, streaming medido, worker bounds e ausência de regressão S5/S6 |
| INT-A | Regressão integrada | Suíte offline não exige Telegram; resultados/erros/skips identificados e ações limitadas |
| INT-B | Preservação V1/S6 | Sem alteração de integridade V1, budgets S5, estados e provas históricas; falha fechada permanece |

Um teste sintético satisfaz somente o critério observado; não declarar validação remota, memória, deduplicação de transferência ou integridade de produção que não tenha sido realmente medida.

## 8. Limites de escopo e mudanças bloqueadas

Fora de escopo: GUI/web, scheduler, scraping, upload, automação de Telegram Desktop, refactor amplo, frameworks/infraestrutura novos, ativação global V2, reabrir S6 sem decisão, reescrever contratos congelados, alterar registros de prova, reprocessar catálogo completo sem motivo, exclusão física de mídias, downloads de grande porte e publicação Git.

Se alteração de API, schema, contrato, política de exclusão ou semântica de download for material e não estiver prevista claramente: registrar proposta de delta, risco e compatibilidade e solicitar decisão antes de aplicar. Não presumir autorização por ser uma alteração "pequena".

## 9. Atribuições e processo multiagente

Na futura atividade Codex:
- Invocar explicitamente `$codex-task-router` somente no prompt/Card que autorizar a atividade; a seleção de subagentes cabe ao roteador.
- ROOT coordena, delimita, integra e adjudica; não escolhe subagentes arbitrariamente.
- Architect e Diagnostic Analyst realizam inspeção, diagnóstico e contratos **sem escrever código**.
- Mechanical Implementer é o único perfil autorizado a implementar código, mediante escopo explícito.
- Scribe escreve documentos/relatórios; validação deve utilizar a capacidade apropriada selecionada pelo roteador.
- `principal_architect` permanece CLOSED / NO_REENTRY no ciclo S6. Não reabrir por conveniência.
- Ferramentas nativas Codex para repositório, arquivo, terminal e testes; parar e reportar se bloqueado.
- Preservar documentação histórica e WIP. Nenhum Git add/commit/push, operação Telegram ou modificação de dados reais é inferido da aprovação do contrato.

## 10. Entrega, evidência e handoff

Cada estágio deve produzir 1 relatório consolidado:
- `docs/reports/S7_INCREMENTAL_SYNC_IMPLEMENTATION/REPORT.md`
- `docs/reports/S8_OPERATIONAL_HARDENING_IMPLEMENTATION/REPORT.md`

Incluir `ACTIVITY_ID`, objetivos, diffs/arquivos, APIs e migrations efetivas, regressões focadas/acumuladas (contagem e comando), falhas e riscos, `FR/NFR` cobertos, requisitos não provados, estados/checkpoints, testes reais Telegram `0` salvo autorização separada, operações Git `NONE` salvo autorização e `ACTIVITY_COMPLETION_PERCENT`.

Entrega ao chat existente **Projeto Telegram 3.0**: quando houver acesso à ferramenta de comunicação, descobrir/verificar o destino antes de usar `send_message_to_thread`, obedecer revisão e autorizações. Se bloqueado, registrar `DELIVERY_STATUS=BLOCKED` e disponibilizar relatório no ambiente de execução; não inventar IDs ou burlar revisões.

## 11. Condição final

```text
CONTRACT = S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT
VERSION = 1.0
SPECIFICATION = APPROVED_AND_FROZEN / USER_RATIFIED_2026-10-25
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
S7_STATUS = ENTRY_REVIEW_PENDING / NOT_STARTED
S8_STATUS = DEFERRED / NOT_STARTED
S6_STATUS = CLOSED_WITH_EXCEPTIONS
V1_ACTIVE = YES
V2_GLOBAL = OFF
NEXT_ACTION = SEPARATE_S7_ENTRY_REVIEW_AND_IMPLEMENTATION_AUTHORIZATION_REQUIRED
```

Contrato integrado estabelece o que o implementador deverá entregar **quando autorizado**; não altera sozinho estado do projeto, governança ou software.
