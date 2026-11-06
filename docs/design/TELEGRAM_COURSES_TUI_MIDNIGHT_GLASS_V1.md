# Telegram Courses CLI/TUI — Direcao visual 1: Midnight Glass

## Mudanca de prioridade e destino deste conceito — 2026-11-03

A Direcao 1 "Midnight Glass" foi aprovada como conceito visual no historico do projeto, mas a decisao posterior do operador determinou **CLI V1 minima usando Python + Rich**. Portanto, este documento **nao e um requisito de implementacao de TUI fullscreen para V1**. A referencia estetica pode ser reavaliada quando for iniciada a **GUI futura**, depois que o downloader concluir e comprovar um fluxo completo de curso. A GUI nao foi ainda especificada nem aprovada como desenho de telas. Ver ROADMAP.md e COURSE_DOWNLOAD_E2E_GATE em SPRINTS.md.

---


STATUS = CANONICAL_VISUAL_APPROVED / NOT_IMPLEMENTED
DECISION_DATE = 2026-11-03 (America/Sao_Paulo)
SOURCE = aprovacao humana no chat canonico "Projeto Telegram 3.0"
ACTIVITY = TELEGRAM-3-GLOBAL-CHECKPOINT-AND-PUSH

## Decisao e fronteira
O produto continuara sendo uma CLI/TUI interativa e navegavel no terminal Windows, nao um aplicativo web ou GUI separada. A Direcao 1, Midnight Glass, foi escolhida entre quatro propostas visuais. A imagem conceitual e referencia estetica; numeros, nomes de arquivos e estados exibidos nela nao sao evidencias operacionais nem especificacoes de dados reais. Nao declarar que a TUI esta implementada.

## Identidade visual aprovada
- Fundo muito escuro, contraste legivel, acentos roxo/azul e destaques discretos em ciano/verde.
- Layout premium e organizado por paineis: catalogo lateral, curso/modulo/aulas, fila ativa, resumo de transferencias e barra de atalhos.
- Selecao nitida, tabelas alinhadas, estados textuais e coloridos; nao depender apenas de cor.
- Priorizar Windows Terminal/PowerShell e fallback acessivel em terminais estreitos ou sem Unicode adequado.
- Animacoes e atualizacoes sem flicker; a TUI nao deve bloquear os workers de download.

## Fluxo navegavel e informacao obrigatoria
1. Navegar canal > curso > modulo > aula/arquivo via teclado (setas, Enter, Voltar, Tab, busca e ajuda).
2. Mostrar tamanho real por arquivo, por selecao e por curso quando conhecido; distinguir tamanho observado, estimado e desconhecido.
3. Mostrar estado por midia: pendente, em fila, transferindo, interrompido, concluido e falhou; identificar claramente integridade comprovada versus apenas download finalizado.
4. Mostrar progresso por arquivo e agregado: bytes baixados/esperados/restantes, percentual, velocidade atual e media em MB/s, ETA do arquivo e ETA da fila.
5. MB = 1.000.000 bytes e GB = 1.000.000.000 bytes (unidades decimais). Nao confundir MB/s com Mbps nem com MiB/s. Valores numericos derivados dos contadores reais, sem numeros ficticios.
6. ETA calculado a partir de velocidade suavizada e bytes restantes, exibido como indisponivel quando nao houver dados confiaveis/atividade; evitar dividir por zero e estimativas instaveis.
7. Mostrar quantidade de arquivos selecionados, validos, pendentes, ativos e falhos; painel de eventos resumido sem vazar segredos.
8. Comandos de transferencia devem respeitar confirmacoes, limites, contratos de integridade e seguranca vigentes; a TUI e somente uma camada de apresentacao/controle.

## Proxima entrega de design
Antes de codificar a nova TUI, apresentar mockups completos das telas propostas ao operador (catalogo, modulo/aulas, fila/download em andamento, detalhes/erro e configuracoes/ajuda), para adjudicacao do layout final. Nao iniciar implementacao visual automaticamente neste checkpoint.

## Invariantes
Preservar backend e dados operacionais existentes; nao alterar S9/V2, sessao Telegram, banco operacional nem executar downloads reais por esta decisao visual.

## Dependencia de prontidao funcional — 2026-11-03

A aprovacao visual permanece valida, mas a implementacao da TUI fica subordinada ao COURSE_DOWNLOAD_E2E_GATE. O operador quer dois caminhos muito simples: selecionar arquivos especificos (multi-select) ou 'Baixar tudo' no curso atual, respeitando a ordem do catalogo. A interface nao deve complicar o fluxo com dashboards obrigatorios, formularios redundantes ou misturar escopo de canal e curso. Primeiro validar o backend/CLI existente; depois mostrar mockups de telas e implementar a apresentacao.
