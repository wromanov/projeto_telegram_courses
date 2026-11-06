# Entrega final da CLI V1 offline

ACTIVITY_ID: TELEGRAM-3-CLI-V1-FINAL-DELIVERY-01  
RESULTADO: **CLI_V1_FUNCTIONAL_OFFLINE**

O comando público `telegram-courses demo --workspace <diretório>` cria um workspace marcado com catálogo SQLite e dados fictícios, reutiliza a navegação, o planner S5, a confirmação, o executor sintético da Slice C, a fila S5 com um worker e a apresentação Rich. O gateway é exclusivamente em memória; a autorização da execução continua separada da confirmação do plano. O workspace é preservado para reabertura, retomada e deduplicação. Diretórios existentes sem marcador, caminhos operacionais conhecidos, reparse points, hardlinks do banco/marcador e travessias `..` são rejeitados. Nenhum conteúdo é apagado automaticamente pelo comando.

## Como executar

Na raiz do projeto, para catálogo local: `.\.venv\Scripts\telegram-courses.exe interactive --database <caminho>`.

Para demonstração: `.\.venv\Scripts\telegram-courses.exe demo --workspace "$env:LOCALAPPDATA\TelegramCoursesDemo"`. Na primeira execução o caminho deve ser novo. Escolher canal `1`, curso `1`, marcar `1,2` ou `T`, revisar com `V`, planejar com `P`, confirmar com `s` e autorizar a execução sintética com outro `s`. `Q` volta/sai. Repetir o comando no mesmo workspace e planejar novamente mostra `TODOS_JA_VALIDOS`.

## Evidência

- Subprocesso usando o executável público: seleção de todos, revisão, plano, confirmação, autorização, `CONCLUIDO`; reabertura do mesmo workspace, `TODOS_JA_VALIDOS`.
- Outro subprocesso público com seleção múltipla exibiu progresso e velocidade medida de `1,26 MB/s`; ETA indisponível quando sem base confiável. Os testes de métricas cobrem o cálculo de ETA.
- Em console Windows isolado, `CTRL_C_EVENT` real após 262.144 bytes produziu `CANCELADO`, preservou `.part`, gravou `FAILED_RETRYABLE` com checkpoint 262.144 e `owner_pid=NULL`. Reabertura concluiu a retomada; abertura seguinte retornou `TODOS_JA_VALIDOS`.
- 66 testes offline focados passaram após a integração; após reforço do marcador, 27 testes diretamente afetados e um teste adicional de revogação do marcador passaram. Ruff e `git diff --check` passaram. Não foi executada suíte global.
- O teste automatizado usa entrada por subprocesso; Ctrl+C manual no PowerShell 5.1 e Windows Terminal não foram homologados. A homologação real de Telegram requer autorização e escopo específicos.

## Alterações e segurança

Produção: `src/telegram_courses/cli.py`, `demo_cli.py`, `course_offline_execution.py` e a mensagem de confirmação em `interactive_catalog_cli.py`. Teste: `tests/integration/test_demo_cli.py`. Guia: `docs/GUIA_WINDOWS_USO.md`. O comando de download legado e os contratos S4–S9 não foram alterados. Nenhuma sessão, credencial, RPC Telegram, banco operacional ou download real foi usado. O WIP anterior permanece; sem staging, commit ou push. Branch `work/s0-bootstrap`, HEAD `cdbe0a8cd9e432c04a9e04a55048dade07ebc852`.

O relatório sanitizado foi encaminhado ao chat canônico e o readback confirmou a mensagem e a resposta, que recomenda `ACCEPTED_WITH_LIMITATIONS` com base nas evidências reportadas. Workspaces e diretórios sintéticos de validação criados nesta atividade permanecem no repositório como não rastreados; nenhum dado foi apagado automaticamente.
