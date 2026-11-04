# TELEGRAM-3-BATCH-RESUME-PILOT-01 — DC IMPLEMENTATION (2026-11-02)

## Autorização
Autorização expressa do operador nesta conversa: RASMOO (-1002758699600), até cinco MP4 do curso Candidato de Ouro; cada arquivo <=134217728 B; agregado <=536870912 B; um worker; uma tentativa por mídia; até 3600s; descoberta <=3x200; modo REMOTE_HASH_REQUIRED sem downgrade; retomada controlada. Sem contrato S9, Git, publicação ou acesso a outros canais.

## Estado implementado no ROMA_CASA (somente DC)
- Diretório privado %LOCALAPPDATA%\telegram_courses_product preparado pelo preparador oficial.
- Banco privado de produto criado por SQLite backup consistente da run S9 encerrada 20261102T222254Z-64aad96a40f6, fonte mode=ro. Catálogo tem 196 MP4 observados, escopo Candidato de Ouro / Contagem Regressiva com 5 arquivos, 73071671 bytes, maior 24492009 bytes.
- src/telegram_courses/downloads.py: parâmetro opt-in require_full_remote_hash exige faixas completas e SHA-256 remoto correspondente antes da finalização do arquivo V1; ausente/incompleto/divergente falha fechado e mantém parcial.
- src/telegram_courses/cli.py: opção opt-in --require-full-remote-hash somente para fila privada interativa, acompanhada de --required-module-id, --max-single-media-bytes e --max-runtime-seconds; restringe o menu ao módulo, verifica tamanho por mídia, bloqueia tentativa de reutilizar parcial já consumido sem autoridade nova; revalida remotamente mídias ALREADY_VALID antes de tratá-las como válidas quando ainda há itens pendentes; encerra execução ativa após deadline.
- tools/telegram_3_pilot_scope_guard.py: pré-check somente leitura do módulo ID 46, pertencente ao curso Candidato de Ouro, cinco MP4 dentro dos limites.
- tools/RUN_TELEGRAM_3_BATCH_RESUME_PILOT_01.ps1: launcher separado, no PowerShell 5.1 nativo. Guard de escopo antes de RPC; token G0 fresco e interação humana; CLI pede escolha [1] do módulo e confirmação G4 fresca após plano.
- S9 original/contrato não modificado. Nenhum download em lote iniciado.

## Validação offline observada
- 90 testes PASS: unit/downloads, integration/download_flow, integration/s5_download_flow, unit/s9_queue_integration.
- Ruff: All checks passed! em cli.py, downloads.py, ambos os testes e guard.
- PowerShell AST: PASS.
- Guard real local do escopo: PASS (5, 73071671, 24492009).
- Uma tentativa anterior de testes com 89 PASS/1 FAIL por args artificiais antigos; compatibilidade corrigida; rerun final 90 PASS.
- PowerShell shell intermediário do DC perdeu $LASTEXITCODE no texto de uma verificação combinada, mas ambos os comandos pytest e Ruff exibiram sucesso; isso não afeta o launcher escrito.

## Limitacoes e orientacao
- Não é aceite S9 G6–G9 nem comprovação M: o piloto é externo ao contrato S9.
- Não houve RPC real nesta atividade nem validação nativa de cinco transferências.
- G0 e G4 ainda não foram concedidos para esta run; são pessoais e devem ocorrer no PowerShell nativo do operador.
- O limite de 3600s dentro da CLI cobre o trabalho assíncrono da fila (não o tempo que o operador passa lendo G0/menus/G4).
- Se aparecer .part de tentativa já consumida, o piloto bloqueia; o operador deve autorizar nova tentativa para essa mídia. Uma run com todos os arquivos já válidos pode retornar SKIPPED sem RPC adicional nem nova prova remota (idempotência local, não reatestado remoto).
- A primeira execução não prova retomada real entre itens; se concluir, realizar ensaio de retomada entre itens somente mediante execução controlada e preservando orçamento/autorizações.

## Próxima ação humana
No PowerShell 5.1 nativo, executar:
Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
& '.\tools\RUN_TELEGRAM_3_BATCH_RESUME_PILOT_01.ps1'

Revisar e digitar o token aleatório G0; selecionar [1] (módulo de cinco vídeos); revisar os limites e confirmar G4 somente se correto. Enviar saída sanitizada de status final; nenhuma sessão/credencial/código pessoal.
