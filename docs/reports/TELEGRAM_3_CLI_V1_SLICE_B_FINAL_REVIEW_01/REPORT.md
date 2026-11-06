# Revisão final da CLI V1 — Slice B

ACTIVITY_ID = TELEGRAM-3-CLI-V1-SLICE-B-FINAL-REVIEW-01  
RESULTADO = SLICE_B_READY_FOR_CANONICAL_ACCEPTANCE  
REVISÃO_INDEPENDENTE = ACCEPT_WITH_FINDINGS / revisor independente, somente leitura  
ACEITE_CANÔNICO = PENDENTE

## Resultado dos gates

| Gate | Evidência | Resultado e limites |
|---|---|---|
| B1 — seleção | Testes S5 e CLI de identidade exata, múltiplos módulos, duplicatas, seleção vazia e escopo. | PASS para os cenários sintéticos executados. |
| B2 — ordem e elegibilidade | Testes existentes e novo caso para ordinal ausente, exclusão PHOTO e `UNSUPPORTED_MEDIA`; tamanho desconhecido e ordinais repetidos cobertos. | PASS com limite: ordem determinística não comprova ordem pedagógica nem completude remota. |
| B3 — confirmação | Comparação usa o plano revisado e valor de espaço livre após confirmação; testes de variação zero, um byte, 1 GiB menos um byte, 1 GiB e 1 GiB mais um byte, nos dois sentidos. Integração testa os limites e bloqueios. | PASS: variação ≥ 1 GiB exige nova confirmação; menor variação é aceita quando a capacidade continua suficiente; pendências com espaço desconhecido ou insuficiente bloqueiam. |
| B4 — CLI | Testes adicionais de desmarcação entre páginas, EOF/Ctrl+C, caracteres de controle e marcação Rich literal; navegação e índices globais testados. | PASS offline com limite: navegação manual em PowerShell 5.1 não foi comprovada nesta atividade. |

## Correções e revisão independente

O fingerprint continua protegendo identidade, seleção, ordem, estado, tamanho, destino, integridade, limites e contexto; a comparação de espaço usa diferença absoluta, não faixas arredondadas, em relação ao valor apresentado na revisão. Mudanças de capacidade abaixo do limiar não sobrepõem um bloqueio de espaço insuficiente ou desconhecido. A confirmação desta slice não chama a fila.

O revisor independente identificou que células de tabelas interpretavam tags Rich recebidas do catálogo. As seis tabelas foram ajustadas para usar `rich.text.Text` literal. O revisor reproduziu o caso antes e depois e considerou o achado resolvido. Seu parecer final foi `ACCEPT_WITH_FINDINGS`: não encontrou defeito material remanescente; inspecionou os testes complementares e reproduziu a renderização em memória, sem alegar reexecução integral da bateria.

## Validação e segurança

- 61 testes focados de planner, seleção, S5 e CLI: PASS após as correções.
- Cinco testes adicionais sintéticos de B2/B4: PASS; Ruff e compileall do arquivo: PASS.
- Ruff dos módulos/testes alterados, compileall e `git diff --check`: PASS; avisos Git LF/CRLF permanecem.
- Fixtures SQLite/filesystem e gateways dos testes são sintéticos. Nenhum banco operacional ou sessão foi acessado; nenhuma RPC Telegram, download real, commit ou push. Contratos S5–S9 rastreados sem diff; contrato v0.2 não rastreado não é comparável ao HEAD por `git diff`.

## Riscos residuais e continuidade

- A leitura de disco é pontual; banco e filesystem não formam transação atômica. Qualquer futura execução deverá aplicar seus próprios guardas e revalidar.
- Não houve navegação manual comprovada em PowerShell 5.1 ou E2E de curso real. Catálogo parcial e ordem pedagógica continuam limitados pela evidência.
- Variações frequentes de pelo menos 1 GiB podem provocar reconfirmações. A política não altera limites ou contratos congelados.
- A decisão de aceite canônico permanece humana. Slice C, acesso Telegram real e publicação Git exigem autoridade própria.

Envio ao chat canônico: MCP aceitou o envio e o readback mostrou a mensagem (`SENT / READBACK_OBSERVED`). A decisão de aceite canônico permanece pendente.
