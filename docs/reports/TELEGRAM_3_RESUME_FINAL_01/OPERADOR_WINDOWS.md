# TELEGRAM-3-RESUME-FINAL-01 — Execução humana no Windows 11

## O que está pronto e o que ainda não foi feito
O DC preparou dois launchers e testou o recorte em modo offline. **Nenhuma transferência real foi iniciada nesta atividade.** A prova real de parada entre arquivos e retomada depende das confirmações humanas G0/G4 em duas execuções separadas.

A autorização do operador nesta conversa limita a execução ao canal RASMOO (ID -1002758699600), curso Candidato de Ouro, módulo Competências (ID 44), especificamente às mensagens 585, 586 e 587, ainda não baixadas. Os cinco vídeos recuperados do módulo Contagem Regressiva (mensagens 598–602) permanecem fora do piloto.

## Controle de orçamento
- Vídeo 585: 6.199.635 bytes.
- Vídeo 586: 11.235.719 bytes.
- Vídeo 587: 11.028.396 bytes.
- Total: **28.463.750 bytes** (menor que 256 MiB).
- Até 128 MiB por vídeo, 1 worker, 1 tentativa por mídia, nenhuma execução de outro curso/canal.
- Tempo agregado de execução: até **1.800 segundos**, com tempo consumido na etapa 1 descontado na etapa 2 (medido por duração do processo da CLI, incluindo confirmação G4).
- Modo REMOTE_HASH_REQUIRED com comprovação de hash remoto completo, incluindo a cauda real do EOF, sem downgrade.
- Nenhuma varredura nova ou download integral do canal.
- Contrato S9, Git e publicação permanecem fora do escopo.

## Etapa 1 — um vídeo e parada controlada
Abra o **Windows PowerShell 5.1 nativo** no ROMA_CASA e execute:

    Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
    & '.\tools\RUN_TELEGRAM_3_RESUME_FINAL_01.ps1' -Etapa 1

- O preflight offline deve indicar WAVE_1_PREFLIGHT=PASS e os IDs 585,586,587 pendentes.
- No G0, digite pessoalmente a frase exata com nonce gerado no próprio terminal. Não envie o nonce ao chat.
- A CLI lista só um módulo; escolha **1**, Competências.
- Confira no plano fresco: SELECTED_MEDIA_COUNT=1; PENDING_MEDIA_COUNT=1; PENDING_BYTES=6199635; LIMIT_CHECK_RESULT=PASS; garantia REMOTE_HASH_FULL.
- Somente se estiver correto, confirme G4 digitando **s**.
- A etapa deve encerrar depois do vídeo 585, sem começar 586/587; pós-condição WAVE_1_POST=PASS, mensagem WAVE1_PASS e recibo privado na pasta db do produto.
- Feche o terminal ou retorne ao prompt para evidenciar a interrupção **entre arquivos** (nenhum corte de mídia em andamento).

## Etapa 2 — novo processo, retomada dos pendentes
No PowerShell 5.1 nativo, em nova execução:

    Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
    & '.\tools\RUN_TELEGRAM_3_RESUME_FINAL_01.ps1' -Etapa 2

- O preflight deve indicar: WAVE_2_PREFLIGHT=PASS; ITEM_STATES=ALREADY_VALID,PENDING,PENDING.
- G0 novo e humano; a CLI novamente pede escolha **1** e G4.
- Confira: SELECTED_MEDIA_COUNT=3; ALREADY_VALID_COUNT=1; PENDING_MEDIA_COUNT=2; PENDING_BYTES=22264115; LIMIT_CHECK_RESULT=PASS.
- No G4, confirmar **s** somente se estiver correto.
- Antes de baixar 586/587, a fila estrita revalida remotamente o 585 sem baixar payload outra vez. Conclusão esperada: WAVE_2_POST=PASS e RESUME_FINAL_PASS.
- A segunda execução cria um marcador privado de tentativa; ela é **one-shot**. Se falhar, não a execute novamente sem diagnóstico e nova autorização.

## Se houver bloqueio
- Falha no G0 ou G4: não forçar confirmação, não usar --confirm.
- Falha de integridade, sessão, limite, ACL, timeout ou vídeo parcial: NÃO excluir .part, não reiniciar automaticamente, não aumentar tentativas nem fazer downgrade.
- Envie ao chat somente a saída final sanitizada, omitindo segredos, IDs pessoais, códigos, sessão ou títulos privados.
- O piloto não comprova a retomada de um **mesmo arquivo parcialmente transferido**; comprova somente o reinício de uma fila entre itens.
- O S9 formal G6–G9 e perfil M continuam independentes e não são automaticamente aprovados.

## Ferramentas de entrega Windows offline
Sem Telegram RPCs e sem downloads:

    & '.\tools\OPEN_TELEGRAM_3_WINDOWS_OFFLINE.ps1' -Acao ajuda
    & '.\tools\OPEN_TELEGRAM_3_WINDOWS_OFFLINE.ps1' -Acao smoke
    & '.\tools\OPEN_TELEGRAM_3_WINDOWS_OFFLINE.ps1' -Acao catalogo
    & '.\tools\OPEN_TELEGRAM_3_WINDOWS_OFFLINE.ps1' -Acao arquivos

Isto é um entrypoint operacional para o checkout existente com .venv, **não** é instalador ou executável independente. Empacotamento final continua pendente de aceite do piloto e decisão explícita do operador.
