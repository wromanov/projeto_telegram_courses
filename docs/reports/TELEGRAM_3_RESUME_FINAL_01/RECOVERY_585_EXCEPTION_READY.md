# TELEGRAM-3-RESUME-FINAL-01 — Recuperação excepcional da mídia 585

Estado de entrega: **READY_FOR_HUMAN_G0_G4**, não executada em produção.

## Autorização operacional e escopo
Autorização expressa neste chat para UMA tentativa ADICIONAL (a segunda da mídia 585), canal RASMOO -1002758699600, curso Candidato de Ouro, módulo Competências id 44. O arquivo .part de 6.029.312 bytes deve ser preservado e sua identidade remota confirmada antes de qualquer apêndice. Restam 170.323 bytes úteis para completar os 6.199.635 bytes finais.

- Reserva GetFile por solicitação: 262.144 bytes. Teto agregado desta única execução: **6.291.456 bytes**.
- Integridade: REMOTE_HASH_REQUIRED e require_full_remote_hash; prefixo e arquivo completo verificados por SHA-256 de cada faixa remota. Sem downgrade.
- Concurrency: 1 worker, 1 tentativa da fila, teto de 1.800 segundos, sem repetições automáticas.
- Mídias 586/587, 598–602 e outros conteúdos fora de escopo. Nenhuma ação no S9, Git, ACL ou catálogo além da atualização do registro 585 pela fila normal.
- G0 humano simplificado: no PowerShell digitar SIM; depois G4 humano digitando s, somente após conferir plano fresco; sem nonce aleatório nem seleção redundante do módulo fixo.

## Verificações executadas offline
- SQLite modo somente leitura: 585 FAILED_RETRYABLE, attempts=1, downloaded_bytes=6029312, failure_category=TRANSFER_BUDGET_EXHAUSTED, owner_pid=NULL, .part no tamanho esperado, arquivo final ausente; 586/587 nunca tentados.
- tools/telegram_3_resume_585_once_guard.py: RECOVERY585_PREFLIGHT=PASS.
- Dry-run completo via CLI com stdin de teste G4=n: plano com 1 CONDITIONAL_RESUME_CANDIDATE, PENDING_BYTES=170323, LIMIT_CHECK_RESULT=PASS, REMOTE_HASH_FULL, nenhuma RPC ou transferência.
- Simulações de download com dados sintéticos tamanho 6199635: 3 cenários PASS — retomada sem baixar prefixo e finalização remota integral; prefixo adulterado bloqueia; orçamento recusado bloqueia.
- Verificação sintática PowerShell, Ruff e compileall: PASS.
- Regressão ampliada final: 103 PASS (parser, downloader, S9, integração). Execução anterior ampliada: 145 PASS.
- Novas chamadas Telegram nesta atividade: 0. Tentativas reais adicionais consumidas: 0.

## Como executar (somente operador em PowerShell 5.1 no ROMA_CASA)
    Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
    & '.\tools\RUN_TELEGRAM_3_RECOVER_585_ONCE.ps1'

O launcher exige o preflight exato antes de criar um marcador *one-shot* e inicia somente após o operador digitar SIM em G0. Módulo predefinido; nenhuma seleção necessária. A CLI imprime o plano; conferir SELECTED_MEDIA_COUNT=1, PENDING_MEDIA_COUNT=1, PENDING_BYTES=170323, LIMIT_CHECK_RESULT=PASS, REMOTE_HASH_FULL e então confirmar G4 com s. Se recusar G0, nenhum marcador é criado. Se aceitar G0, o marcador permanece, mesmo se G4 for recusado ou a recuperação falhar, evitando nova execução inadvertida. Nunca apagar o marcador nem o .part para contornar falhas.

Em sucesso: verifica SHA-256 do arquivo final e linha DOWNLOADED, attempts=2, gera RECOVERY585_POST=PASS e recibo privado da Etapa 1; habilita etapa 2 (com nova confirmação humana e sem duplicar o 585). O teste formal de etapa 2 não está aprovado até execução real.

## Restrições remanescentes
- Sem execução remota por DC do G0/G4: a ferramenta bloqueou explicitamente interação. Não simular, não repetir usando shell não interativo.
- Caso a operação falhe, parar, preservar .part, categoria e banco, diagnosticar antes de nova autorização.
- S9 formal permanece PARTIAL; não alegar aceite global do produto ou continuação segura após interrupção dentro de um mesmo arquivo até evidência real.

## Atualização pós-execução real — 2026-11-03 03:01:50 UTC

O operador executou o launcher de recuperação 585, com G0/G4 humanos. O processo concluiu com FAILED e a segunda tentativa durável foi consumida.

Evidências lidas posteriormente com SQLite em modo somente leitura:
- Mensagem 585: state=FAILED_RETRYABLE, attempts=2, downloaded_bytes=6029312, expected_bytes=6199635, failure_category=GATEWAY_FAILURE, owner_pid=NULL.
- O arquivo .part continua com 6029312 bytes; MP4 final não existe; PRAGMA quick_check=ok.
- Recibo de sucesso da wave1 ausente; marker resume_final_01_recover585_once.started existe e mantém o bloqueio de uso único.
- O planner apresenta 585 CONDITIONAL_RESUME_CANDIDATE, 586/587 PENDING e 598-602 ALREADY_VALID.
- Trace fornecido pelo operador: asyncio.IncompleteReadError 0/8 bytes durante Telethon _client.connect(), antes de download. O mapeamento no _LazyGateway registra GATEWAY_FAILURE como categoria genérica. Não há prova de corrupção de arquivo, de bloqueio de conta nem de causa de rede específica.
- O warning Future exception was never retrieved é secundário ao erro de conexão e não demonstra consumo de payload.

**Status atualizado: RECOVERY585=FAILED_RETRYABLE_NETWORK_CONNECT; ATTEMPTS_USED=2; ONE_SHOT_LOCK=CONSUMED.** Nenhuma terceira tentativa autorizada. Não executar novamente o launcher, não apagar o marker nem o .part. Próximos passos: diagnóstico de conectividade/sessão sob autorização apropriada, sem payload, e nova avaliação humana de uma tentativa adicional. O estado READY_FOR_HUMAN_G0_G4 anterior foi superado por este resultado.
