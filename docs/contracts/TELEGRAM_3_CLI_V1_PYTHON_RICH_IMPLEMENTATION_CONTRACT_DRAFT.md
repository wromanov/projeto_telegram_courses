# Telegram Courses 3.0 — contrato proposto de implementação da CLI V1

## 01. Identificação e status

- **ACTIVITY_ID:** TELEGRAM-3-CLI-V1-CONTRACT-DESIGN-01; versão 0.2, 2026-11-04. `OPTION_A_CONDITIONAL` é a recomendação técnica emitida na revisão canônica; não é, por si só, uma decisão do operador.
- **STATUS:** APPROVED_WITH_MINOR_DOCUMENTARY_CORRECTION / correção de autoridade registrada em `docs/governance/APPROVALS_AND_DECISIONS.md`. O usuário aprovou expressamente a v0.2 em `Projeto Telegram 3.0`; a autoridade dessa aprovação é USER_EXPLICIT. A aprovação do contrato não autoriza acesso Telegram real, download real, S9, S10, commit ou push. O card do Slice A autoriza somente a implementação offline limitada descrita nele.
- **Base examinada:** root `C:\Users\walac\desenvolvimento\projeto_telegram_courses`, branch `work/s0-bootstrap`, HEAD `cdbe0a8cd9e432c04a9e04a55048dade07ebc852`. Havia sete documentos modificados antes desta atividade; preservá-los. Git é fonte factual de estado, não autorização.
- **Fontes normativas:** `docs/continuity/PROJECT_GOVERNANCE_BINDING.json`, `ACTIVE_AUTHORITY_MAP.md`, `PROJECT_STATE.md`, `planning/ROADMAP.md`, `planning/SPRINTS.md`, `docs/product/REQUIREMENTS.md`, arquitetura e engenharia; contratos S4–S9 e decisões vigentes. A direção CLI/Rich de 2026-11-03 prevalece sobre referências históricas a mockups/TUI.
- **Evidência:** inspeção estática dos arquivos e dos testes citados; resultados históricos são atribuídos às respectivas fontes. Nenhum teste, banco operacional ou Telegram foi executado nesta investigação. Uma referência a teste identifica cobertura pretendida, não um novo resultado de execução.

## 02. Contexto e problema

O produto já tem catálogo, planner e motor de transferência. Seu fluxo corrente exige comandos e seleciona uma hierarquia inteira; ainda não demonstra seleção interativa de mídias arbitrárias ou um curso completo ponta a ponta. S9 permanece parcial. A recuperação real de uma mídia 585 foi concluída com quatro tentativas e hash remoto integral, segundo `PROJECT_STATE.md` e `docs/reports/TELEGRAM_3_585_FINAL_CLOSURE_01/REPORT.md`; não é evidência de curso inteiro. Preservar 586/587 e demais runs. A indicação histórica de 829 testes aprovados e 11 subtestes é resultado de outra atividade, não desta análise.

## 03. Objetivo funcional

No catálogo local de um canal, selecionar um curso e escolher arquivos individuais de quaisquer módulos ou todos os elegíveis **desse curso**, revisar plano fresco, confirmar pessoalmente e acompanhar uma fila sequencial. O resultado deve dizer o que concluiu, ignorou, bloqueou, falhou ou ficou pendente. Catálogo parcial significa apenas conteúdo observado, nunca curso remoto completo.

## 04. Escopo e exclusões

Python/Rich no Windows 11, PowerShell 5.1/Windows Terminal; comandos existentes preservados. Fora: GUI, Textual, TUI fullscreen, web, agendador, usuários, sincronização automática, execução de canal inteiro por inferência, S10, bypass e repetição automática do piloto 585. A seleção total não inclui outro curso, canal, mídia órfã ou não elegível. Aprovação visual Midnight Glass é referência histórica para GUI futura.

## 05. Inventário técnico e matriz de capacidades

Classificação é relativa ao comportamento explicitamente descrito, não à prontidão global. `IMPLEMENTED_AND_PROVEN` abaixo significa somente prova **offline histórica** indicada; não significa teste reexecutado agora. `IMPLEMENTED_NOT_PROVEN` significa código observado sem prova aqui de seu comportamento integral. `PARTIALLY_IMPLEMENTED` cobre parte da capacidade; `MISSING` ausência do fluxo desejado; `BLOCKED` uma condição que impede execução; `NOT_APPLICABLE` algo fora do escopo. As fontes de teste devem ser executadas no slice correspondente, em ambiente isolado, para validar mudanças.

| Capacidade | Classificação; evidência: arquivo / símbolo / comportamento e teste | Lacuna, risco e ação recomendada |
|---|---|---|
| Entrada CLI e canal | PARTIALLY_IMPLEMENTED: `cli.py:_parse_arguments`, `main`, `_select_from_local_snapshot`, `_discover_channels`; argparse, seleção numérica e Rich; `tests/integration/test_cli_channels.py`. | Fluxo comum depende de comandos/opções; acrescentar entrada interativa explícita sem quebrar comandos. Validar help, saídas e cancelamento. |
| Autenticação e sessão | IMPLEMENTED_NOT_PROVEN para esta atividade: `auth_application.py`, `telethon_gateway.py:TelethonGateway`, `telethon_session.py:_ProtectedSessionVault`, `_ProtectedCredentialsVault`; DPAPI e verificação ACL; `tests/unit/test_telethon_session.py`, integração Windows. | Não reimplementar; sem prova nova de acesso real; reutilizar guardas e exigir autorização operacional. |
| Scanner/parser/catalogação | IMPLEMENTED_AND_PROVEN offline no escopo das fixtures: `message_scanner.py`, `scan_application.py`, `catalog.py`, `rasmoo_parser.py`, `catalog_application.py:CatalogApplication.build`, `catalog_repository.py:SQLiteCatalogRepository`; `tests/integration/test_catalog.py`, `test_rasmoo_parser.py`. | Parser genérico não infere hierarquia; associação ausente não é prova de ausência remota. Exibir contagens e advertências; não varrer automaticamente. |
| Consulta do catálogo | PARTIALLY_IMPLEMENTED: `cli.py:_catalog_command` e `SQLiteCatalogRepository.get_catalog_nodes/get_catalog_items`; tabelas Rich e tamanhos desconhecidos; `test_catalog.py:test_offline_repository_cli_and_idempotent_build`. | Visualização separada não fornece navegação e marcação por arquivo; construir consulta consolidada segura e verificar se build está defasado. Comandos de catálogo existentes podem executar migrations: navegação nova deve ser somente leitura. |
| Identidade/escopo de curso | PARTIALLY_IMPLEMENTED: `s5_downloads.py:DownloadSelection`, `DownloadPlanner.build`; chave `(channel_id, telegram_message_id, media_ordinal)`, linhagem ativa; `test_s5_download_flow.py:test_s5_course_plan_scope_exclusions_and_queue_rerun`. | Seleção por nó não representa conjunto arbitrário entre módulos; incluir conjunto explícito, validar cada identidade contra snapshot do curso e conteúdo atual. Nunca usar nome como chave. |
| Marcar/desmarcar e selecionar tudo | MISSING como fluxo de produto: `cli.py:_download_batch` escolhe escopo e nó; não oferece conjunto arbitrário. `_pilot_narrow_plan` é restrito a piloto, não API geral. | Implementar seleção local com IDs estáveis, exclusão e cancelamento; testar igualdade exata do conjunto e ausência de mídia externa. |
| Ordenação | PARTIALLY_IMPLEMENTED: `DownloadPlanner.build` ordena por tupla de ordinais da linhagem (`ordinal or 0`), depois ID de mensagem e ordinal da mídia; `DownloadQueue.run` percorre `plan.pending` por índice. | Ausências/empates recebem ordem determinística, mas não prova de ordem pedagógica; confirmar política §12 e testar casos adversos e regressão S5/S9. |
| Plano e capacidade | PARTIALLY_IMPLEMENTED: `DownloadPlan` estima payload/disco e margem `max(1 GiB, 10%)`; `_download_batch` apresenta plano, compara repetição e pede confirmação; `test_s5_download_flow.py:test_s5_preview_is_offline_and_disk_gate_blocks_before_transfer`. | Ajustar para conjunto explícito, transparência de desconhecidos, plano fresco e validação pós-confirmação; não afrouxar limites. `UNKNOWN_SIZE` é excluído e sob cap pode bloquear a fila (`test_byte_budget_rejects_plan_with_excluded_unknown_size`). |
| Download e integridade | IMPLEMENTED_AND_PROVEN offline para casos específicos: `downloads.py:SingleMediaDownloadApplication`, `destination_paths`, `_finalize_no_overwrite`; `test_download_flow.py` cobre dedupe, tamanho inválido, falhas, retomada e hash; `test_downloads.py` cobre paths Windows. | Não duplicar motor. Hash local e tamanho não são automaticamente prova remota; manter modo/provas efetivamente exigidos e bloqueio seguro. |
| Fila, retry e limites | IMPLEMENTED_AND_PROVEN offline para casos específicos: `DownloadQueue.run`, `MAX_WORKERS=2`, retries limitados, orçamento e cooldown; `test_s5_queue_policy.py`, `test_s8_resilience.py`, `test_s9_queue_flow.py`. | CLI V1 fixa 1 worker; confirmar limites antes de qualquer payload e não assumir que fila de produto é supervisor S9. |
| Progresso | PARTIALLY_IMPLEMENTED: `SingleMediaDownloadApplication.progress_callback` e `DownloadQueue` emitem bytes/contagens; `test_queue_progress_reports_aggregate_counts_and_bytes`; CLI imprime linhas. | Não há experiência completa de velocidade/ETA/arquivo; callback síncrono atual pode bloquear ou propagar erro. Isolar observador, sem mexer nos contadores de orçamento. |
| Persistência/recovery | PARTIALLY_IMPLEMENTED para a prova global: `download_repository.py:DownloadRepository`, `downloads.py` e `s6_integrity.py`; testes de reinício/overlap e `test_s7_incremental_sync.py`. | S6 fechada com exceções; prova geral de retomada real continua limitada. Prévia condicional não autoriza append; validar identidade, ownership, prova, disco e limites novamente. |
| Completar curso real | BLOCKED por falta de prova e autorização própria: `PROJECT_STATE.md`, `ROADMAP.md`; prova 585 é por mídia. | Não declarar E2E ou aceite; exigir gate §22 e autorização separada. |
| GUI/S10 | NOT_APPLICABLE à atividade/V1: `ROADMAP.md`. | Não iniciar; futura interface consumirá aplicação sem importar Rich no domínio. |

## 06. Stack confirmada e dependências

`pyproject.toml`: Python >=3.14,<3.15; Telethon >=1.45,<1.46; cryptg >=0.6,<0.7; aiosqlite >=0.22.1,<0.23; Rich >=15,<16; pytest >=9.1.1,<9.2 e Ruff >=0.16.10,<0.17; build isolado setuptools ==84.0.0; entry point `telegram_courses.cli:main`. Na `.venv`, leitura de versões indica Python 3.14.7, Telethon 1.45.0, cryptg 0.6.0, aiosqlite 0.22.1, Rich 15.0.0, pytest 9.1.1 e Ruff 0.16.10. `pip show setuptools` não o encontrou nessa `.venv`; build isolado não foi verificado. Python do PATH é 3.15.0, fora da faixa: usar `.venv` e conferir runtime, sem presumir instalação global. Nenhuma dependência adicional é justificada.

O guia `docs/GUIA_WINDOWS_USO.md` documenta PowerShell 5.1 ou superior. O checkpoint mais recente distingue PowerShell 7 supervisionado sem stdin interativo do PowerShell 5.1 nativo exigido pelo launcher específico 585; isso não prova a nova UX. Testar explicitamente a nova CLI em PS 5.1 nativo interativo, Unicode e saída redirecionada, sem relaxar guardas de TTY.

## 07. Estado comprovado e limites

S4/S5 têm testes offline e provas históricas limitadas; S6/S7/S8 fechadas com exceções conforme roadmap e state; S9 parcial. Uma scan limitada não prova completude remota. `DownloadPlanner.build` define `catalog_complete` pelo último scan completo sem stop reason, não por cobertura semântica de parser ou ausência de modificações posteriores. A CLI deve tratar esse sinal como evidência de scan, não de curso completo. Divergência documental potencial: a arquitetura proíbe SQL bruto fora dos repositórios, mas o planner atual abre SQLite read-only e faz SQL; reconhecer dívida e evitar ampliá-la, sem propor reescrita não autorizada.

## 08. Matriz de lacunas priorizadas

| Prioridade | Lacuna comprovada / risco | Resultado a validar |
|---|---|---|
| P0 | Seleção de arquivos arbitrários ausente / incluir arquivo errado. | Identidades exatas confinadas ao curso, sem prefixo truncado. |
| P0 | Plano selecionado e fila devem concordar / deriva após confirmação. | Snapshot + replanejamento + comparação integral; fail closed. |
| P0 | Ordem de ordinais ausentes/duplicados não garante ordem pedagógica. | Regra §12 determinística, incerteza exibida e aprovação prévia. |
| P0 | Resultado real completo e prova integral de recovery não demonstrados. | Gate real separado, não inferido de testes ou 585. |
| P1 | Métricas e interface ainda em linhas técnicas; callback síncrono. | Eventos observacionais isolados e medições honestas. |
| P1 | Frescor/completude semântica não comprovados por flag de scan. | Mostrar dados disponíveis e estado desconhecido/defasado com motivo. |
| P1 | Tamanho desconhecido excluído e cap pode bloquear. | Explicar exclusão/limite, sem inventar tamanho ou inserir mídia na fila. |
| P2 | SQL no planner diverge da fronteira arquitetural. | Consultas novas em repositório; migração somente se necessária e explicitamente aprovada. |

## 09. Alternativas técnicas

1. **Recomendada:** menu Rich adicional, seleção em memória por identidade e extensão mínima dos casos de uso/planner/fila existentes. Menor dependência, reaproveita segurança; exige integração e testes de equivalência de plano.
2. Acrescentar apenas flags para IDs: menor código, mas falha na navegação e marcação simples requeridas; preservar flags existentes, não substituir a UX.
3. TUI fullscreen ou novo motor: rejeitada para V1 por escopo e duplicação de invariantes. Fatiar a fila em chamadas unitárias independentes também é rejeitado: poderia perder orçamento, ordenação e resultado agregados.

## 10. Arquitetura proposta

Presentation: `cli.py` e módulo Rich pequeno se necessário; sem Telethon direto na apresentação nova. Application: operação de consulta/seleção, plano e execução sobre `DownloadPlanner`/`DownloadQueue`/S4. Domain: dados imutáveis de seleção e ordem, sem Rich/SQLite/Telethon. Infrastructure: repositórios, adapter Telegram, filesystem, DPAPI/ACL, logging. Preferir estender tipos existentes e consultas de repositório; não criar framework de camadas. GUI futura dependerá dos mesmos casos de uso, não de prompts. A fronteira real existente ainda não cumpre integralmente o diagrama; validar dependências via testes e revisão.

## 11. Fluxo UX

1. Novo subcomando explícito, por exemplo `telegram-courses interactive`, preservando sintaxe e sem fazer rede automaticamente. Exigir TTY para interações; em não TTY falhar com mensagem e opções existentes, sem confirmação implícita.
2. Escolher catálogo local e canal previamente disponível; mostrar scan, build, data disponível, itens sem classificação e advertência de frescor desconhecido. Nenhuma descoberta/scan implícita.
3. Escolher curso, listar módulos/aulas/mídias paginadas ou em páginas simples com `Table`; nomes sanitizados e tamanhos/status quando verificáveis. `Tree` opcional; Rich não fornece seleção múltipla nativa: usar `Prompt` textual com números/intervalos, comandos de marcar, desmarcar, todos, revisar e voltar. Índices são locais à tela e mapeados a identidades, não persistidos como chave.
4. Revisão mostra seleção atravessando módulos, exclusões e pendências. Alterar seleção ou cancelar é permitido antes da confirmação; zero selecionados não executa.
5. Mostrar plano completo e limites, confirmação explícita padrão não; detectar deriva e pedir revisão novamente. Executar sequencialmente, exibir progresso e resumo individual/consolidado. A confirmação vale somente para o plano/limites apresentados.

## 12. Contrato de seleção e ordenação

- Identidade canônica existente `(channel_id, telegram_message_id, media_ordinal)` mais verificação de `telegram_media_id`, tipo e tamanho na execução; nós por ID e ancestralidade ativa do curso. A seleção é um conjunto, não multiconjunto; validar duplicatas e associações ambíguas. Rótulos nunca autorizam ou identificam mídia.
- `Baixar tudo`: conjunto de todas as mídias **elegíveis observadas** ligadas a aulas descendentes do curso selecionado no snapshot; listar separadamente bloqueadas/excluídas e não incluir órfãs ou itens de outros cursos. A decisão OPTION_A_CONDITIONAL permite selecionar conteúdo observado de catálogo parcial dentro do escopo e limites especificamente autorizados; a CLI deve identificar essa condição e nunca declarar completude remota sem evidência. Zero elegíveis não inicia; não truncar silenciosamente para caber em caps.
- **Decisão OPTION_A_CONDITIONAL:** preservar provisoriamente a regra S5 existente, sem alterar contratos congelados: tupla de ordinais de ancestrais (ausente/zero hoje vira 0), depois `telegram_message_id`, `media_ordinal`. São metadados do catálogo, não prova de sequência pedagógica. Verificar colisões, ancestrais opcionais e valores inválidos; sinalizar ordinais ausentes, duplicados ou inconsistentes e mostrar ao operador a sequência exata de cada item antes da confirmação. O aviso não modifica a ordem nem infere correção pedagógica. Se for necessária mudança de regra ou de contrato congelado, interromper a parte dependente e solicitar decisão específica.
- Ordenar a seleção como subsequência do plano de curso, nunca pela ordem de cliques. A fila com um worker consome `plan.pending` em ordem; retries do mesmo item terminam antes de avançar. Resultados e tela são apresentados na ordem do plano, inclusive itens já válidos/bloqueados. Teste espiona sequência de início, tentativas e exibição; nenhuma outra fila prioriza ou reordena. Falhas não se tornam sucesso; comportamento por categoria segue §17.

## 13. Contrato de planejamento

Ler snapshot consistente e validar curso, conjunto, linhagem, identidade, status, exclusões, tamanho, destino e configuração. Reusar cálculo S5: bytes de payload e disco são estimativas distintas para retomada (offset alinhado/overlap), e margem é `max(1 GiB, 10% do espaço adicional estimado)`. Exibir canal/curso, todos os itens e ordem, tamanho por arquivo, soma conhecida, número desconhecido, bytes válidos e parciais identificados, volume restante estimado, espaço livre, margem, destino, caps de itens/bytes, workers/tentativas, já válidos, bloqueados/excluídos e motivo. Não somar desconhecidos como zero completo.

**Seleção não é elegibilidade:** item selecionado é uma intenção explícita ou abrangida por `Baixar tudo`; elegível é somente o item que satisfaz as regras atuais do planner; excluído é exibido com sua identidade e motivo, sem transferência. A UX deve mostrar também itens não elegíveis observados no curso, inclusive ao escolher `Baixar tudo`, para que nenhum arquivo desapareça silenciosamente. O conjunto executável de `Baixar tudo` contém apenas os elegíveis catalogados do curso. `UNKNOWN_SIZE` permanece excluído: em `DownloadPlanner.build` vira `EXCLUDED`, sem candidato; `DownloadQueue.run` rejeita o plano se `max_transfer_bytes` estiver configurado e houver esse motivo em `plan.excluded`, e `_download_batch` reprova o limite de bytes nas mesmas condições. Sem limite de bytes, essa checagem específica não bloqueia, mas o item continua excluído; outros guardas podem bloquear. Esses fatos são inspeção estática, não uma execução nova. Não remover automaticamente exclusões do plano para contornar o bloqueio: apresentar a razão e exigir revisão explícita, respeitando as regras e autorizações vigentes. Testar com e sem cap e com seleção manual/todos.

Vincular a confirmação a um snapshot comparável completo; um identificador ou fingerprint pode apoiar a comparação, mas não substitui a comparação de seus campos. O `plan_id` S5 atual cobre seleção e entradas, não todos os elementos abaixo. Imediatamente após a confirmação e antes de iniciar a fila, refazer a consulta e comparar: canal e curso; conjunto exato de identidades, associação/linhagem e identidade remota disponível; sequência; status e motivos de bloqueio/exclusão; tamanho e estimativas; destino; modo de integridade e evidência local aplicável; limites de itens/bytes, workers e tentativas. Revalidar espaço livre e margem, que podem mudar independentemente. Falta de informação verificável ou qualquer divergência relevante invalida a confirmação: bloquear, apresentar o novo plano e solicitar nova confirmação. Guardas finais de filesystem, ownership, identidade remota e orçamento ainda ocorrem no motor; não prometer atomicidade entre DB, disco e Telegram nem executar RPC na simples revisão offline.

## 14. Integração com downloader

Adaptar planner e passar plano exato à fila existente com `workers=1`; não chamar downloader em loop fora da fila nem usar `_pilot_narrow_plan` como API. A fila e `SingleMediaDownloadApplication` continuam autoridades de estado, reserva de bytes, streaming, retry e finalização. O fluxo normal não usa `--confirm`; a opção existente permanece compatível para seus usos antigos, sujeita aos contratos aplicáveis. Não substituir supervisor S9 nem alegar recibos G0–G9. Executor revalida o que for necessário após confirmação e falha fechado em incerteza.

## 15. Progresso e métricas

Preferir adaptação mínima dos callbacks existentes: receber identidade/fase, bytes e total conhecido, contagens e timestamp monotônico; limitar frequência de atualização e proteger exceções de apresentação, sem alterar orçamento, persistência ou decisões do downloader. A renderização síncrona pode atrasar o produtor: medir e testar esse custo sob callback lento; não declarar isolamento temporal sem evidência. Evitar trabalho pesado ou bloqueante no callback. Se a solução mínima não satisfizer o requisito de não bloquear materialmente o download, apresentar evidência e propor o menor mecanismo adicional limitado; não impor previamente fila assíncrona ou infraestrutura complexa. Falha visual deve ser sinalizada sem propagar exceção para o motor, e o resumo final deve vir do resultado autoritativo, não de atualizações perdidas. Encerrar a apresentação no cancelamento.

Mostrar curso/módulo/arquivo e posição, bytes, total, porcentagem somente com denominador válido, tempo decorrido, velocidade e ETA. MB/s = bytes transferidos em janela monotônica / segundos / 1.000.000; média = bytes efetivamente recebidos desde o início medido / tempo correspondente, não somar prefixo preexistente como tráfego. Em retry reiniciar série por tentativa e indicar bytes cumulativos separadamente; orçamento inclui bytes de prova/overlap e falhas conforme motor, que podem diferir dos bytes do arquivo. ETA do arquivo = bytes restantes / taxa sustentada válida; lote somente quando tamanhos, ritmo e escopo permitirem estimativa defensável; sem dados, duração positiva ou taxa suficiente mostrar `Indisponível`. Testar relógio falso, zeros, pausas, resets, duplicatas, retomada, overflow e callback lento/falho.

### 15.1 Resultado consolidado da fila

O resultado deve ser derivado dos estados por identidade e incluir contagens de selecionados, elegíveis, já válidos, concluídos, pendentes, excluídos, bloqueados, falhos e cancelados; os itens aparecem na sequência aprovada. Estas categorias são mutuamente exclusivas como **resultado principal**: primeiro identificar `SEM_SELECAO`; depois `SEM_ELEGIVEIS` quando aplicável; nos demais casos aplicar a precedência cancelamento, falha, bloqueio, parcial, concluído e todos já válidos. Não ocultar categorias secundárias:

| Resultado | Condição e apresentação |
|---|---|
| `SEM_SELECAO` | Nenhum item selecionado; nenhuma execução. |
| `SEM_ELEGIVEIS` | Seleção não vazia, nenhum elegível e nenhum bloqueio operacional global; listar exclusões e motivos; nenhuma execução. |
| `TODOS_JA_VALIDOS` | Seleção não vazia, todos os selecionados são elegíveis e já válidos sob as provas aplicáveis; zero transferências. Não afirmar completude remota. |
| `CONCLUIDO` | Todos os selecionados elegíveis terminaram validados ou já válidos, pelo menos um concluído nesta execução, sem exclusões, bloqueios, falhas, pendências ou cancelamento. |
| `PARCIAL` | Houve ao menos um item concluído ou já válido, mas existem exclusões ou pendências sem outra condição de maior precedência; informar exatamente quais. |
| `BLOQUEADO` | Um guarda global ou item foi bloqueado, sem falha nem cancelamento com precedência; mostrar causa, concluídos e pendências. |
| `FALHA` | Pelo menos um item falhou terminalmente e não houve cancelamento; mostrar os demais estados. |
| `CANCELADO` | Operador interrompeu ou cancelou execução; mostrar o que já concluiu e o que ficou pendente, sem classificar lote como concluído. |

Quando a seleção de `Baixar tudo` contiver somente elegíveis, exclusões observadas fora do conjunto executável ainda devem ser exibidas como ressalva de cobertura, não convertidas em sucesso do curso remoto. O `SKIPPED` atual de `cli.py:_download_batch` tanto pode cobrir todos válidos quanto ausência de elegíveis; não usar essa etiqueta isolada como sucesso. O caso de rechecagem S9 tem semântica própria e seus recibos permanecem inalterados; mapear resultados de apresentação sem reinterpretar ou modificar o contrato S9.

## 16. Persistência e recuperação

SQLite e filesystem continuam fontes complementares. Reabrir/replanejar a partir da identidade, não persistir índices de tela; já válido exige tamanho/hash/estado válidos conforme contrato. Não alterar arquivo final existente divergente; não marcar completo antes da validação e finalização sem overwrite. `.part` sem ownership/prova é preservado e bloqueado. Reconciliação de rename/DB usa código existente. Retomada exige identidade, prova remota aplicável, ownership e checkpoints S6, orçamento e guards; candidato condicional na prévia não é prova. O piloto de hash de 585 não habilita extensão global. Falha SQLite ou interrupção deixa status honesto e permite reconciliação por caso de uso já contratado, nunca reparo destrutivo automático.

## 17. Segurança, invariantes e erros

Conta legitimamente acessível, DPAPI CURRENT_USER/ACL, isolamento de sessão e credenciais, paths Windows e reparse points, destino privado quando aplicável, sem sobrescrita, logs sanitizados, limites e integridade S4–S9 permanecem. Nenhuma redução de exigências, alteração de contrato congelado ou reabertura automática de sprint. Confirmar escopo, TTY e limites antes de payload; autorização de contrato não é autorização de rede.

| Evento | Conduta proposta e condição de validação |
|---|---|
| Cancelar/Ctrl+C | Parar novas admissões, cancelar cooperativamente, aguardar fechamento e preservar `.part` e estado; relatar concluídos/falhos/pendentes. Testar interrupção antes e durante fluxo. |
| Rede/FloodWait | Aplicar categorias, orçamento de tentativas e cooldown existentes; respeitar limite de perfil mais restritivo. Em S9, primeiro FloodWait encerra homologação. Não contornar. |
| Sessão expirada/acesso negado/mídia ausente | Parar item ou lote conforme categoria/contrato; autenticação e novo acesso exigem autoridade própria. Nunca inferir exclusão remota. |
| Disco insuficiente/cap/SQLite | Bloquear antes de payload quando detectado; em erro durante execução parar novas admissões e preservar evidências. Revalidar com testes de falha. |
| Parcial ou final divergente / hash ou identidade divergente | Bloquear e preservar; não sobrescrever nem promover a concluído. Prova ausente não é prova de integridade. |
| Catálogo parcial/desatualizado | Avisar e restringir ao observado; não afirmar completude. Deriva relevante após confirmação invalida plano; sem estado verificável, bloquear. |

## 18. Matriz de testes proposta

Cada linha exige testes com fixtures sintéticas e repositórios/FS temporários, sem sessão nem rede real; asserts de conjunto, ordem, estados e efeitos, não apenas texto. Preservar regressões existentes afetadas.

| Área | Cobertura mínima / aceite |
|---|---|
| Seleção | uma, várias, desmarcar, módulos distintos, todos do curso, duplicata, outro curso/canal, associação inválida, zero e cancelamento; conjunto exato e zero stream antes do aceite. |
| Ordem | ordinais 2/10, irregulares, ausentes e duplicados, pais opcionais, várias mídias por aula, IDs desempate; início e resultados iguais à subsequência do plano, inclusive retry. |
| Catálogo/plano | scan parcial, build defasado/desconhecido, sem classificação, selecionado versus elegível/excluído, `UNKNOWN_SIZE` com e sem limite de bytes, seleção manual e total, limites, espaço/margem; modificar separadamente identidade, conjunto, ordem, status, tamanho, destino, integridade e limites após confirmação; cada divergência bloqueia e exige nova confirmação. Nenhuma exclusão é ocultada. |
| UX | navegação, retorno, seleção e confirmação `não` padrão, TTY/EOF, caracteres Windows e PS 5.1; comandos antigos e help preservados. |
| Execução | um worker, limites itens/bytes, reservas e tentativa falha cobradas, bloqueados/excluídos, sucesso e falha individual, FloodWait, disco e cancelamento. |
| Métricas | relógio falso, MB/s decimal, janela sem dados/zero, retry/overlap, ETA indeterminável, callback falho/lento e custo de renderização medido, sem alteração de contadores; se mecanismo adicional vier a ser justificado, testar também saturação e perda de atualizações intermediárias. |
| Resultado | selecionar zero; selecionar apenas inelegíveis; todos já válidos; todos concluídos; concluídos com exclusões/pendências; bloqueio; falha; cancelamento antes e durante execução; combinações com precedência §15.1 e aviso de cobertura fora do conjunto. `SKIPPED` isolado nunca comprova sucesso. |
| Persistência | dedupe após reinício, SQLite/FS divergentes, rename antes de commit, parcial e ownership, prova remota falsa/ausente e preservação; fake gateway não chamado quando bloqueado. |
| Integração offline | fluxo completo de seleção e tudo com SQLite/FS isolados e gateway fake, verificação do manifesto, ordem, limites, confirmação, resultados e rerun. |

Executar seleção focada e regressões por risco, não suite extensa automaticamente. Validar PS 5.1 nativo separadamente; registrar comandos, versões, resultados, falhas e limites. Falhas do executor supervisionado `socketpair`/event loop são histórico conhecido, não prova de defeito de produto.

## 19. Slices de implementação propostos

Cada slice depende de aprovação expressa do contrato e autorização da atividade correspondente. Auditoria desta atividade é entrada, não slice de implementação. Os quatro slices abaixo reduzem handoffs preservando testes independentes; nenhum começa agora.

| Slice | Entrada e objetivo / componentes previstos | Invariantes, testes e aceite | Riscos, dependência e rollback |
|---|---|---|---|
| A — catálogo e seleção | Estado atual + contrato aprovado; `catalog_repository.py`, aplicação e CLI; snapshot local, navegação e conjunto. | Somente leitura no menu; testes de seleção, escopo e parcial §18. Aceite: conjunto exato, cancelamento sem escrita/download. | Associação incompleta; depende de baseline S3/S5. Rollback: reverter alterações do slice em checkout autorizado, preservando DB e WIP. |
| B — plano e confirmação | A aceito; `s5_downloads.py`, repositório/CLI; seleção específica e total, ordem, fingerprint e preview. | Mesmo planner e limites; testes de ordenação, desconhecido, deriva, caps, confirmação negativa. Aceite: plano é conjunto exato e divergência exige nova confirmação. | Compatibilidade S5/S9 e ordem ambígua; bloqueio para decisão se frozen contract conflitar. Rollback de código isolado, sem tocar banco. |
| C — execução e progresso | B aceito; `s5_downloads.py`, `downloads.py` somente se necessário, apresentação Rich. | Uma fila/worker, segurança existente, eventos isolados; testes de ordem real de chamadas, falhas, orçamento e métricas. Aceite: resultados correspondem a plano e eventos não interferem. | Observador pode bloquear; validar explicitamente. Rollback de adaptador/integração sem apagar parciais/DB. |
| D — integração offline e preparo real | A–C aceitos; testes focados e guia; fixtures SQLite/FS/gateway fake, PS 5.1. | Matriz §18 e regressões afetadas passam; nenhum Telegram real. Aceite: `IMPLEMENTED_OFFLINE`, plano de teste real limitado e riscos documentados. | Runtime supervisionado; usar host nativo autorizado para validações locais. Rollback de alterações documentais/testes do slice sem alterar dados. |

## 20. Arquivos previstos para alteração futura

Conforme necessidade demonstrada: `src/telegram_courses/cli.py`, `s5_downloads.py`, `catalog_repository.py`, eventualmente `catalog_application.py`, módulo de apresentação novo e `downloads.py` apenas para observabilidade segura; testes focados em `tests/unit/` e `tests/integration/`; `docs/GUIA_WINDOWS_USO.md`. Não antecipar migrations ou mudanças em sessão, contratos históricos, supervisor S9 ou credenciais. Se necessárias, propor escopo e aprovação próprios. Esta lista é previsão, não autorização de edição.

## 21. Critérios de aceite por slice

Os critérios verificáveis e rollback constam na tabela §19; cada entrega deve registrar resultado de cada teste aplicável de §18, revisão de diferenças, compatibilidade com contratos e ausência de efeitos externos. Nenhum slice promove automaticamente estado de outro. Resultado offline passa somente quando todos os quatro slices e regressões pertinentes passarem; bloqueios permanecem explícitos.

## 22. COURSE_DOWNLOAD_E2E_GATE

Manifesto privado de um curso escolhido e sua evidência de cobertura; comparar associação dos arquivos observados com catálogo, distinguir limites da fonte. Demonstrar seleção manual específica **e** conjunto total elegível do curso; plano com ordem e limites corretos; confirmação humana; execução real separadamente autorizada; validar cada final físico, tamanho e evidência de integridade conforme modo contratado; conciliar SQLite/FS; reiniciar e demonstrar dedupe sem novo payload indevido. Registrar contagens, exclusões, falhas e recibos sanitizados. Se qualquer premissa de representatividade, integridade ou execução não passar, gate não passa. Uma prova limitada não comprova conteúdo remoto não observado.

Estados independentes: `READY_FOR_IMPLEMENTATION` = contrato expressamente aprovado + autorização específica + dependências/decisões resolvidas; `IMPLEMENTED_OFFLINE` = slices e testes locais aceitos, sem inferir E2E; `READY_FOR_BOUNDED_REAL_TEST` = protocolo, preflight e escopo prontos e aprovação específica para execução ainda necessária; `E2E_PROVEN` = evidência real do gate completa e revisada; `PRODUCT_ACCEPTED` = decisão humana explícita após E2E. Nenhum desses estados é declarado alcançado agora.

## 23. Riscos e mitigação

Ordem determinística pode não ser pedagógica: advertir e comparar com fonte. Scan completo não prova parser completo: diferenciar evidência e incerteza. Deriva do plano: reconfirmar e proteger no motor. Mudanças em fila podem quebrar budget/S9: regressões focadas e não alterar contratos. Métricas de retomada podem superestimar velocidade: separar bytes físicos e tráfego. Falha de renderização pode interferir: canal limitado e isolamento. Falhas SQLite/energia exigem preservar estado; nunca limpeza automática. Dados privados em outputs exigem sanitização. S6/S7 têm exceções e S9 é parcial; não ocultar.

## 24. Dependências e bloqueios

Contrato e autorizações §28 pendentes; versão suportada `.venv`; fixtures representativas; validação PS 5.1 nativo; sem acesso operacional nesta atividade. `PROJECT_STATE` indica 585 concluído e 586/587 requerem autorização específica. Evidência para validar frescor semântico pode ser insuficiente: sinalizar desconhecido. Se a aplicação da ordem S5 conflitar com contratos congelados ou se a prova de integridade exigida estiver indisponível, bloquear decisão/execução afetada e levar evidência ao chat canônico.

## 25. Rollback

Fatiar alterações e registrar diffs/testes para reversão seletiva autorizada; não usar reset/restore/clean/stash automaticamente nem substituir WIP preexistente. Nunca apagar banco, arquivo final, parcial, sessão, ACL ou recibo para desfazer código. Se uma futura migration se tornar necessária, definir antes backup consistente, compatibilidade e recuperação em cópia isolada; não há migration aprovada por este rascunho.

## 26. Validação real posterior

Produzir card próprio com canal/curso e manifesto privado, critérios de cobertura, operador, ambiente nativo, root privado e cópia consistente do DB, autorização de acesso e transferência, limites de itens/bytes/tentativas/tempo, modo de integridade, confirmação interativa, espaço, encerramento e coleta sanitizada. Fazer preflight e checar escopo antes da primeira RPC; apresentar plano fresco e confirmação antes do primeiro payload. Não induzir falhas ou FloodWait; interrupção/recovery somente se explicitamente incluída e segura. Comparar rerun/DB/FS e recibos; relatar o que não foi demonstrado. Não reutilizar automaticamente run ou autorizações de S9/585.

## 27. Questões em aberto

1. **Resolvidas para a v0.2 aprovada:** `CLI-V1-CONTRACT-REVIEW-01` recomendou tecnicamente OPTION_A_CONDITIONAL para ordem S5 e conteúdo observado de catálogo parcial; o usuário aprovou a v0.2 com correção documental menor no chat canônico. A atribuição de ambas as autoridades está registrada em `APPROVALS_AND_DECISIONS.md`.
2. Nível de prova de integridade e limites de cada teste real permanecem decisão operacional específica; não generalizar o requisito de um piloto nem enfraquecer o contrato vigente.
3. Fonte confiável para frescor de build e evidência de cobertura semântica deve ser determinada nos slices; se ausente, mostrar desconhecido, não inventar timestamp ou completude.
4. Impacto temporal real dos callbacks Rich protegidos exige medição no slice C. Se for material, apresentar evidência antes de definir mecanismo adicional.

## 28. Decisões que exigem aprovação

Revisão humana do contrato, das alternativas e das questões §27; autorização explícita de implementação e slices; eventual alteração de contrato congelado ou schema; plano e autorização real específicos; aceite E2E e de produto. Estas são recomendações, não decisões atribuídas ao operador. Eventual pergunta deve seguir o formato do card e ser enviada ao chat `Projeto Telegram 3.0`; decisão dependente aguarda resposta humana explícita.

## 29. Recomendações fundamentadas

Reutilizar S5/S4 porque já existe planejamento com identidade, dedupe e limites; seleção nova deve filtrar por identidade dentro do curso e manter plano revisado. Preservar provisoriamente a ordem S5 conforme decisão OPTION_A_CONDITIONAL e mostrar incerteza e sequência exata. Apresentar evidências de scan e parser separadamente para não confundir completude de varredura com completude do curso. Começar por callbacks protegidos e medição, adicionando mecanismo somente se necessário. Manter apresentação desacoplada e trabalhar com fakes antes de qualquer teste real. A validade dessas propostas depende dos testes e da aprovação descritos.

## 30. Condições para iniciar implementação

`APPROVED_WITH_MINOR_DOCUMENTARY_CORRECTION`; aprovação humana expressa registrada em `Projeto Telegram 3.0` e reconciliada em `APPROVALS_AND_DECISIONS.md`. O card TELEGRAM-3-CLI-V1-SLICE-A-IMPLEMENTATION-01 concede autorização independente para implementar somente o Slice A offline. Nenhuma RPC, download, S10, commit ou push decorre da aprovação do contrato ou do card.

## Anexo A — matriz de correções v0.2

| Pedido | Correção / evidência / validação futura |
|---|---|
| Ordem | §12 registra OPTION_A_CONDITIONAL, regra S5 provisória, ambiguidades e sequência prévia; fonte `DownloadPlanner.build`; teste de ordem e empates §18. |
| Catálogo parcial | §§03, 07, 11–13 limitam o resultado ao observado e ao curso; fonte `catalog_complete` e decisão do usuário; testar parcial/externos §18. |
| Resultado | §15.1 define oito resultados, precedência e ressalvas; fonte `_download_batch` e `DownloadQueue.run`; testar cada cenário e combinação §18. |
| Plano | §13 enumera os campos revalidados após confirmação; `plan_id` atual insuficiente; testar deriva por campo antes de payload. |
| Tamanho desconhecido | §13 distingue seleção/elegibilidade/exclusão e documenta bloqueio sob cap; fonte `DownloadPlanner.build`, `DownloadQueue.run`, `_download_batch`; teste com/sem cap. |
| Rich | §15 prioriza callbacks protegidos e medição; solução assíncrona somente com necessidade demonstrada; testar lentidão/falha e métricas. |
| Testes | §18 cobre casos focados e integração offline; §22 mantém E2E real separado. |
| Escopo | §§04, 06 e 19 preservam stack e quatro slices, sem GUI, Textual, novo motor ou S10. |

## Anexo B — riscos residuais

1. Ordenação S5 é reproduzível, mas a ordem pedagógica pode permanecer desconhecida; avisar e mostrar a sequência não prova correção.
2. Catálogo parcial, parser ou fonte desatualizada podem omitir conteúdo remoto; não afirmar completude, mesmo após concluir tudo catalogado.
3. A comparação após confirmação não torna SQLite, filesystem e Telegram atômicos; guardas e identidade remota devem ser novamente aplicados no momento devido.
4. Uma exclusão `UNKNOWN_SIZE` com cap pode bloquear todo o plano atual; não alterar silenciosamente o conjunto para fazê-lo passar.
5. Callback síncrono protegido ainda pode consumir tempo; medir antes de afirmar que a apresentação não bloqueia materialmente.
6. Regras de classificação de resultado são propostas para V1 e exigem testes e revisão de compatibilidade; não modificam os recibos S9.
7. S6/S7/S8 mantêm exceções, S9 é parcial e o gate de curso real continua não demonstrado; aprovação de contrato não é aceite de produto nem autorização de acesso.
