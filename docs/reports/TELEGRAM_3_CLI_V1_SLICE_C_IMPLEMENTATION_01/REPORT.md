# Slice C — implementação controlada offline

## 01–04. Identificação, ambiente e arquivos

01. **ACTIVITY_ID:** `TELEGRAM-3-CLI-V1-SLICE-C-IMPLEMENTATION-01`.
02. **Host:** ROMA_CASA; **branch:** `work/s0-bootstrap`; **HEAD:** `cdbe0a8cd9e432c04a9e04a55048dade07ebc852`; Python 3.14.7 na `.venv`.
03. **Git inicial:** 13 arquivos rastreados modificados e WIP não rastreado de contrato, relatórios e código/testes das Slices A/B. **Git final:** WIP inicial preservado, com adições e alterações da Slice C; nenhum arquivo staged, commit ou push. O contrato CLI v0.2 já estava não rastreado e não pode ser comparado ao HEAD por `git diff`.
04. **Arquivos da Slice C:** `src/telegram_courses/course_execution.py`, `course_offline_execution.py`, `course_progress_rich.py`, `course_review_context.py`, `interactive_catalog_cli.py`, `s5_downloads.py`, `downloads.py`; `tests/unit/test_course_execution.py`, `test_course_progress_rich.py`, `test_s5_queue_policy.py`, `tests/integration/test_course_offline_execution.py`; relatório e documentos de continuidade.

## 05–10. Arquitetura e fila

05. **Reuso:** `DownloadPlanner`, `DownloadQueue`, `SingleMediaDownloadApplication`, repositório SQLite, reservas e políticas S5, integridade e recuperação S4/S6; Rich 15 existente.
06. **Alternativas:** rejeitado loop manual por mídia, outro downloader e composição com gateway real. A caixa de correio de uma posição para renderização é limitada e separada da fila S5; foi escolhida para que um observador lento não bloqueie callbacks do motor.
07. **Arquitetura:** modelos e métricas em `course_execution.py`; leitura de contexto em `course_review_context.py`; composição sintética em `course_offline_execution.py`; apresentação Rich em `course_progress_rich.py`.
08. **Fluxo:** seleção e confirmação Slice B produzem `ConfirmedCoursePlan`; a execução sintética exige autorização separada, vinculada ao sandbox temporário e de uso único. Antes da fila, recarrega contexto e plano e compara as condições; deriva bloqueia. O gateway interno serve somente bytes em memória e o banco/destino pertencem ao sandbox. A injeção para a jornada interativa é programática e restrita a esse sandbox; não há opção de CLI, flag ou variável para habilitar Telegram real.
09. **Estados:** resumo deriva dos resultados por identidade da fila, na ordem do plano; distingue `SEM_SELECAO`, `SEM_ELEGIVEIS`, `TODOS_JA_VALIDOS`, `CONCLUIDO`, `PARCIAL`, `BLOQUEADO`, `FALHA` e `CANCELADO`. `SKIPPED` não é sucesso. Exclusões observadas fora do plano permanecem ressalva separada.
10. **Ordem:** subsequência S5 e `workers=1`, até três tentativas pelas regras existentes. Teste sintético observou máximo de um arquivo ativo.

## 11–19. Progresso, limites e integridade

11. **Arquivo:** curso, módulo, nome, posição, status, bytes, total e percentual quando conhecido. Barra cheia indica `VALIDANDO` até resultado validado do motor.
12. **Lote:** bytes elegíveis validados versus total conhecido, contagem de concluídos/já válidos e bytes recebidos; não confunde tráfego repetido com conclusão. ETA do lote fica indisponível sem base confiável.
13. **Velocidade:** bytes efetivamente recebidos na tentativa, divididos por tempo monotônico e por 1.000.000; prefixo preexistente não vira tráfego novo.
14. **ETA:** taxa de progresso líquido da tentativa somente após amostra positiva e pelo menos um segundo; caso contrário `Indisponível`.
15. **Retry:** fila S5 mantém limite de tentativas, categorias, jitter e cooldown/FloodWait. Série de velocidade e amostra de ETA reiniciam por tentativa; tráfego acumulado continua separado.
16. **Cancelamento:** evento cooperativo ou cancelamento da tarefa cancela a fila, impede novas admissões e aguarda resultado S5. Teste cancelou após 60 bytes, preservou `.part` e retomou com prova/overlap. Sandbox conserva evidência ao sair com cancelamento, falha, parcial ou `.part`; limpeza posterior das fixtures de teste foi explícita.
17. **Falhas:** limites, disco, deriva, identidade e autorização inválida bloqueiam; falha terminal e cancelamento têm estados próprios. Exceções do observador ou console não alteram resultado do motor; observador ainda ocupado é sinalizado como apresentação incompleta.
18. **Consolidado:** selecionados, elegíveis, já válidos, concluídos, pendentes, excluídos, bloqueados, falhos e cancelados; bytes recebidos, validados, já válidos, prova, sobreposição, orçamento e parcela incerta são distintos. Resultado autoritativo vem de `QueueResult`, não do último evento visual.
19. **Integridade:** downloader e S5 mantêm guards, identidade, prova de prefixo, hash, no-overwrite e persistência. Foram adicionadas observações protegidas de bytes e exposição dos contadores já existentes do orçamento; nenhuma regra ou contrato S4–S9 foi reduzido. O downloader ainda chama a migração existente sobre o banco sintético; não foi criada migration e o teste comparou o schema antes/depois.

## 20–25. Evidência e validação

20. **Testes:** 162 PASS na bateria final offline. Cobertura inclui plano exato, um worker, ordem, autorização separada, gateway fake, deriva, limites, disco, retry, falha, cancelamento, parcial, retomada, overlap, métricas, observador lento/falho, estados, CLI, sanitização e schema.
21. **Regressões:** incluídas S5, integração de orçamento S9, fluxo sintético S9 e Slices A/B/CLI. Nenhuma suíte global foi executada.
22. **Checks:** Ruff PASS; compileall PASS; `git diff --check` PASS com avisos LF/CRLF preexistentes. A primeira rodada da nova fixture teve quatro falhas por conexão SQLite não fechada e uma asserção de categoria; corrigidas. Uma rodada posterior teve 143 PASS/1 FAIL por truncamento do nome na apresentação; layout ajustado, e bateria final passou.
23. **Evidência de custo:** teste com observador artificialmente bloqueado comprovou que o produtor não espera; benchmark isolado de 10.000 publicações sem throttle mediu 0,157980 s, média 15,80 µs/evento neste host. Não é benchmark de throughput ou transferência real. A caixa descarta atualizações intermediárias quando cheia; resultado final é independente dela.
24. **Telegram:** gateway da Slice C é exclusivamente em memória. Nenhuma sessão real, credencial, RPC ou download real foi acessado. Um teste de importação confirma que o módulo offline não carrega `telethon_session`; isso não substitui auditoria de todo o processo.
25. **Escrita:** apenas SQLite e filesystem sintéticos temporários. Nenhum banco operacional foi acessado ou alterado. Nenhum contrato congelado rastreado ou arquivo de migration foi alterado.

## 26–28. Limites e próximo passo

26. **Riscos:** amostras de disco e identidade não são transação atômica; renderer lento pode permanecer em thread daemon por curto período e é sinalizado como incompleto; prova e sobreposição reportam bytes observados, não uma alegação de hash remoto independente; não houve validação manual do PowerShell 5.1 nem E2E Telegram real. S9 mantém seus limites históricos.
27. **Critérios A–Q:** integração e autorização separada, ordem/worker, orçamento, integridade, Rich, velocidade/ETA, isolamento de callback, cancelamento e resumo demonstrados offline pelas fixtures; 162 testes, Ruff e compileall passaram. Resultado é técnico offline e não representa aceite do produto nem prova operacional.
28. **Slice D:** aguardar revisão canônica da Slice C; eventual prova real exige card e autorização operacional separados, escopo e limites explícitos, guardas e confirmações aplicáveis. Não iniciar Slice D automaticamente.

**Comando principal:** `.venv/Scripts/python.exe -B -m pytest --basetemp=<diretório temporário> tests/unit/test_course_execution.py tests/unit/test_course_progress_rich.py tests/unit/test_course_download_planning.py tests/unit/test_catalog_selection.py tests/unit/test_s5_queue_policy.py tests/unit/test_s9_queue_integration.py tests/integration/test_course_offline_execution.py tests/integration/test_s5_download_flow.py tests/integration/test_s9_queue_flow.py tests/integration/test_interactive_catalog.py tests/integration/test_slice_b_review_cases.py tests/integration/test_cli_channels.py`.

**Entrega ao chat canônico:** MCP aceitou o envio; o readback mostrou a mensagem (`SENT / READBACK_OBSERVED`). O chat respondeu propondo `SLICE_C_REVIEW_PENDING` e recomendando revisão independente dos gates C1–C4 antes do aceite. Essa recomendação não inicia outra atividade nem autoriza Slice D ou operação real. Nenhum reenvio automático.
