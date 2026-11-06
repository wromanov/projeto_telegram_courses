# Revisão técnica — CLI V1 / Slice B

ACTIVITY_ID = TELEGRAM-3-CLI-V1-SLICE-B-REVIEW-01  
PARECER = SLICE_B_REVISION_REQUIRED  
INDEPENDÊNCIA = NÃO DEMONSTRADA: revisão executada na mesma conversa/agente que implementou a Slice B. Uma revisão por agente independente continua necessária.

## Matriz

| Gate | Evidência | Resultado | Risco e ação necessária |
|---|---|---|---|
| B1 seleção | Testes S5 e CLI verificam conjunto exato, seleção entre módulos, duplicatas, escopo e seleção vazia. | PARTIAL | Nem todos os casos individuais do card foram repetidos isoladamente; completar matriz por revisor independente. |
| B2 ordem/elegibilidade | Testes cobrem ordem, exclusões e tamanho desconhecido; tela distingue sequência determinística de pedagógica. | PARTIAL | Ordinais ausentes/duplicados e todos os tipos excluídos não foram demonstrados individualmente nesta revisão. |
| B3 confirmação | `fingerprint()` inclui resultado do limite de disco, mas não `available_disk_bytes`. Reprodução sintética: 1.000.000.000.000 e 900.000.000.000 bytes resultam em PASS e fingerprints iguais, embora o valor apresentado tenha mudado. Com espaço indeterminado, `can_confirm` também retorna verdadeiro. | FAIL | O card exige invalidar confirmação quando a disponibilidade relevante muda. Deliberar política de espaço indisponível e corrigir com testes; não há execução de fila nesta tela. |
| B4 CLI | Testes verificam paginação, índices globais, seleção, confirmação, TTY e alterações do catálogo. | PARTIAL | Desmarcação entre páginas, EOF/Ctrl+C e sanitização não foram todos reproduzidos individualmente nesta revisão. |
| Segurança/efeitos | Inspeção estática da tela interativa não encontrou chamada de fila, sessão ou Telegram. Testes usam dados sintéticos. Contratos rastreados em `docs/contracts` sem diff. | PARTIAL | Não houve instrumentação exaustiva de todas as rotas; contrato v0.2 está não rastreado e não é comparável ao HEAD por `git diff`. Um teste S5 executa fila com fixture sintética; nenhuma fila real foi executada. |

## Execução e limites

Host ROMA_CASA; branch `work/s0-bootstrap`; HEAD `cdbe0a8cd9e432c04a9e04a55048dade07ebc852`; Python 3.14.7 na `.venv`. WIP rastreado e não rastreado preservado. Testes focados: 52 PASS, incluindo integração S5 e regressões Slice A; Ruff, compileall e `git diff --check` PASS. A primeira tentativa supervisionada parou no evento assíncrono e foi interrompida; a repetição no ambiente autorizado passou. Há avisos Git de normalização LF/CRLF.

Comandos: `python -B -m pytest` nos arquivos `tests/unit/test_course_download_planning.py`, `tests/unit/test_catalog_selection.py`, `tests/integration/test_s5_download_flow.py`, `tests/integration/test_interactive_catalog.py`; `python -B -m ruff check` nos módulos e testes afetados; `python -B -m compileall -q` nos módulos e testes da revisão; `git diff --check`. Foram usados somente dados sintéticos, sem Telegram real ou acesso a banco operacional.

Implementação existente e testes cobrem cenários específicos; os casos individuais ausentes são não comprovados, não PASS. O finding B3 é reprodução direta, não mera ausência de teste. Próxima ação: revisão independente do finding e decisão humana sobre correção limitada e política de espaço indeterminado. Slice C, Telegram real e Git publication não foram autorizados por esta revisão.

Entrega ao chat canônico: MCP aceitou o envio e o readback mostrou a mensagem (`SENT / READBACK_OBSERVED`). A revisão independente e a decisão canônica continuam pendentes.
