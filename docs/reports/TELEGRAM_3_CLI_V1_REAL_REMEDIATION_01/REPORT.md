# Relatório de remediação da CLI V1

**ACTIVITY_ID:** `TELEGRAM-3-CLI-V1-REAL-REMEDIATION-01`  
**Contrato:** `docs/contracts/TELEGRAM_3_CLI_V1_REAL_REMEDIATION_CONTRACT.md` v1.0  
**Resultado técnico:** `READY_FOR_REAL_COURSE_HOMOLOGATION`  
**Homologação operacional:** não realizada  
**Download de mídia real:** não autorizado e não realizado

## 1. Estado e limites

- Repositório: `C:\Users\walac\desenvolvimento\projeto_telegram_courses`
- Branch: `work/s0-bootstrap`
- HEAD: `cdbe0a8cd9e432c04a9e04a55048dade07ebc852`
- A árvore de trabalho contém WIP de atividades CLI anteriores e desta integração. O inventário final mostrou 95 caminhos alterados ou não rastreados; não havia arquivos staged. Esse conjunto não é atribuído integralmente a esta atividade.
- Nenhum reset, restore, clean ou stash foi executado. Não houve commit nem push.

O resultado significa que a integração local e os checks offline estão prontos para um gate posterior de homologação. Não declara autenticação, descoberta, download nem produto real homologados. A evidência de Telegram real permanece bloqueada até preflight/G0 aplicável e TTY nativo. G4 e autorização específica continuam obrigatórios antes de qualquer payload.

## 2. Alterações de integração

A CLI operacional em `telegram-courses interactive` compõe navegação de catálogo local, descoberta limitada de canais e construção/atualização de catálogo. A descoberta preserva limites explícitos e confirmação antes da consulta de metadados. A experiência de seleção continua ligada ao plano por identidades exatas e à execução já existente.

O serviço `course_live_execution` mantém separadas a confirmação do plano e a autorização de execução de uso único. Ele revalida o contexto imediatamente antes da fila, exige backup verificado quando aplicável, cria o gateway somente quando há itens pendentes, restaura a sessão antes de qualquer operação e exige estado autenticado. A execução reutiliza `DownloadQueue`/`SingleMediaDownloadApplication` S5 com um worker. Falha de autenticação bloqueia a fila; falhas de fechamento do gateway são expostas no resumo e no código de saída sem substituir o resultado autoritativo da fila.

A preparação SQLite rejeita caminhos inseguros, classifica esquemas incompletos como desconhecidos e preserva o original enquanto prepara a cópia/backup previsto. O ajuste de resolução de peer mantém recuperação limitada ao canal selecionado e opt-in; não introduz varredura ilimitada nem persistência de `access_hash` no catálogo.

Progresso e resultado seguem separados: o resumo deriva de `QueueResult`, callback de apresentação não substitui estado autoritativo e falha de cleanup é sinalizada separadamente. A apresentação permanece sanitizada.

### Arquivos de produção na integração

- Alterados: `src/telegram_courses/cli.py`, `catalog.py`, `catalog_repository.py`, `channel_discovery.py`, `downloads.py`, `s5_downloads.py`, `sqlite_repository.py` e `telethon_gateway.py`.
- Componentes adicionados/compostos no WIP preservado: `catalog_selection.py`, `course_download_planning.py`, `course_execution.py`, `course_live_execution.py`, `course_offline_execution.py`, `course_progress_rich.py`, `database_preparation.py`, `demo_cli.py` e `interactive_catalog_cli.py`.
- Os módulos das Slices A–C e da demonstração já estavam no worktree como WIP. Não foram reescritos em um motor alternativo.

## 3. Validação offline

Foram executados **110 testes focados, todos PASS**, em SQLite temporário, filesystem temporário, clientes/gateways fake e dados sintéticos. O lote cobriu preparação e cópia SQLite, autenticação inválida, revalidação do plano, fila S5, peer recovery fake, progresso/resultados, catálogo interativo e regressões de execução offline. Não foi executada a suíte global.

Também passaram:

- Ruff nos arquivos da integração;
- `compileall` nos módulos Python selecionados;
- `git diff --check` antes do fechamento documental (sem erro; Git avisou sobre conversão LF/CRLF em arquivos WIP).
- importação da CLI sem carregar `telegram_courses.telethon_session`.
- revisão estática pós-correção por agente independente: quatro correções conferidas, sem finding de produção aberto no recorte.

O loop de eventos do Windows exigiu execução local de testes fora do sandbox restrito, porque o `ProactorEventLoop` usa socketpair TCP de loopback. A permissão elevada foi usada somente para a execução offline dos testes; não habilitou acesso externo.

## 4. Segurança e efeitos operacionais

**Não ocorreu** Telegram RPC, autenticação, acesso a sessão real, download real, leitura ou escrita em banco operacional, migração de schema, alteração de ACL operacional, commit ou push. Os testes usaram dados sintéticos e artefatos temporários. Os contratos congelados S4–S9 não foram alterados. A demonstração fake não foi tratada como prova de conectividade real.

## 5. Riscos e próximo passo seguro

1. Autenticação, ACL/DPAPI, conectividade, FloodWait, identidade real do canal e comportamento do peer só podem ser confirmados em ambiente autorizado. Testes com doubles não provam esses fatos.
2. A preparação de banco foi verificada com fixtures sintéticas; ainda é necessária uma amostra legada representativa, cópia verificada e backup íntegro antes de qualquer preparação autorizada de um banco operacional.
3. O uso manual em PowerShell 5.1/Windows Terminal e a homologação de curso real permanecem pendentes.
4. Não transferir mídia nesta atividade. Para avançar: cumprir o preflight/TTY/G0 para diagnóstico somente de metadados, registrar bloqueios externos com evidência sanitizada e obter autorização G4 específica antes de qualquer payload.

**Envio ao chat canônico:** ferramenta aceitou; readback posterior mostrou a mensagem e uma resposta. A resposta trata o resultado como prontidão técnica, mantém homologação pendente e recomenda G0/TTY com Telegram real. Essa resposta não é autorização do operador; nenhum acesso real foi iniciado.
