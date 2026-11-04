# S9 Ledger Performance Remediation 01

```text
ACTIVITY_ID = TELEGRAM_S9_LEDGER_PERFORMANCE_FIX_01
PARENT_ACTIVITY = TELEGRAM_FINAL_DELIVERY_01
PROJECT_ID = projeto_telegram_courses
PARENT_CONTRACT = S9_V1_FROZEN
TYPE = TECHNICAL_REMEDIATION
S9_CONTRACT_MODIFICATION = NONE
CONTRACT_APPROVAL = APPROVED_ROOT_QA_AND_USER_RATIFICATION
ARCHITECTURE_STATUS = APPROVED_FOR_OFFLINE_P0_IMPLEMENTATION
IMPLEMENTATION_AUTHORIZATION = YES / OFFLINE_P0_SCOPE_ONLY
ROUTING_MODE = MULTIAGENT
TELEGRAM_RPC = PROHIBITED
REAL_DOWNLOAD = PROHIBITED
GIT_STAGE_COMMIT_PUSH = PROHIBITED
```

## 1. Propósito e estado desta minuta

Este contrato formaliza a arquitetura aprovada para corrigir o custo do ledger S9 sem alterar o contrato S9 v1.0 ou seus requisitos L01–L16. O ROOT concluiu o QA contratual e o usuário ratificou a janela de detecção descrita na seção 11 em 2026-11-01. A implementação está autorizada somente dentro do escopo offline deste P0.

Se a ratificação for rejeitada, o resultado desta correção será `NO_GO` sob os invariantes atuais e o ledger continuará usando validação integral por mutação. O aceite prévio de RISK-03 para uso pessoal não é interpretado como ratificação desta nova latência de detecção.

## 2. A — Causa-raiz comprovada

O caminho quente de `S9OperationalLedger._transaction` realiza validação integral antes e depois da mutação. Antes disso, `_inspect_readonly` também abre o ledger somente para leitura e executa outra validação integral. Cada validação inclui `PRAGMA quick_check`, verificação de chaves estrangeiras, leitura e replay dos eventos de auditoria, análise/recanonização do JSON, recálculo da hash-chain e comparação das projeções do ledger.

Cada bloco de 256 KiB contabilizado exige uma reserva e uma liquidação. Cada uma dessas mutações provoca três validações integrais; portanto, cada bloco provoca seis. O custo de cada operação cresce com o histórico já acumulado. Somar esse custo ao longo de N blocos produz crescimento quadrático, aproximadamente O(N²).

## 3. B — Evidência e perfil de custo atual

### 3.1 Instrumentação curta do arquiteto

Ambiente observado: Windows 11, Python 3.14.7, SQLite 3.50.4. Os ensaios foram sintéticos, em diretório temporário fora do checkout, e não incluíram um benchmark do arquiteto de 1 GiB.

| Payload | Blocos de 256 KiB | Eventos finais | Duração | Validações integrais | JSON loads | Hashes de auditoria |
|---:|---:|---:|---:|---:|---:|---:|
| 16 MiB | 64 | 133 | 9,238 s | 384 | 26.432 | 26.560 |
| 32 MiB | 128 | 261 | 20,955 s | 768 | 102.016 | 102.272 |

No ensaio de 32 MiB, o perfil atribuiu 10,498 s a 128 chamadas de reserva e 10,453 s a 128 liquidações. `_validate` somou 9,094 s, incluindo 7,378 s em `_validate_audit`; `_check_ledger_paths` foi chamado 512 vezes e somou 5,962 s. As 256 chamadas de COMMIT somaram 0,933 s; abertura e fechamento de 512 conexões somaram, respectivamente, 0,897 s e 1,344 s. PRAGMAs somaram 2,408 s; o tempo de execução observado para `quick_check` foi 0,296 s, para foreign-key check 0,041 s e para `BEGIN IMMEDIATE` 0,008 s.

Esses tempos são obtidos por perfil de chamadas. Tempos de chamadas aninhadas não são aditivos; o cálculo de `_audit_hash` inclui serialização JSON e SHA-256, que não foram isolados em parcelas independentes. Os tempos de COMMIT não isolam de forma conclusiva a latência física de cada WAL write/fsync. Os resultados são evidência do custo dominante de replay, não previsão direta de duração do E2E.

O custo medido por bloco cresce com a quantidade de eventos. O ensaio de 32 MiB foi quase duas vezes mais longo que o de 16 MiB para o dobro dos blocos, enquanto a quantidade de JSON loads/hash aumentou mais rapidamente por causa do histórico reprocessado.

### 3.2 Evidência E2E e benchmark existente

O E2E sintético histórico do perfil M contabilizou aproximadamente 1 GiB e foi interrompido pelo limite L10 de 1.800 s, após 1.809,87 s. O ledger tinha 567,75 MiB liquidados e 0,25 MiB reservados. A taxa observada foi 18,9 MiB/min, abaixo dos aproximadamente 34,13 MiB/min necessários para 1 GiB em 30 minutos. Esse E2E é uma reprovação e não conta como PASS.

Um benchmark ledger-only anterior ao P0 contabilizou 64 MiB em 119,46 s (32,15 MiB/min), com `synchronous=FULL`. Ele ocorreu depois de um microajuste da atividade pai e não constitui uma comparação rigorosamente equivalente com o novo perfil do arquiteto. Deve ser tratado como dado contextual, não como baseline comparável.

## 4. C — Arquitetura candidata

### 4.1 Estado incremental e transação

Manter uma conexão SQLite persistente durante cada época exclusiva de escrita. Na admissão/reabertura, verificar caminhos, identidade, quarentena, integridade física, foreign keys, estado e hash-chain integralmente; reconstruir em memória a identidade do run/arquivo, head da auditoria, contadores e saldos, reservas, mídias/tentativas, scans e estado de execução.

Para uma mutação, serializar a instância local, executar `BEGIN IMMEDIATE`, conferir as precondições e as linhas/head envolvidos, calcular deltas usando o estado reconstruído e os deltas confirmados da época, atualizar projeções e acrescentar o novo evento atomicamente. Manter WAL e `synchronous=FULL`. Publicar o novo estado em memória e fornecer ACK somente após o commit durável. Não agrupar reserva e liquidação: a reserva precisa estar durável antes da chamada externa.

Uma falha com resultado de COMMIT ambíguo invalida a época. A instância não pode reutilizar seus contadores nem repetir automaticamente a operação externa; precisa falhar fechada e reconstruir o estado por replay integral antes de qualquer retomada.

O guard de caminho/identidade e a verificação de ausência do marcador `.quarantine` permanecem por operação: verificar antes de cada mutação e novamente antes de devolver ACK. Se o guard falhar, o caminho mudar ou o marcador existir/aparecer, não iniciar a mutação ou não devolver ACK, invalidar a época e falhar fechada. Essa detecção do guard e do marcador não é postergada até o próximo replay integral.

### 4.2 Ownership e handoff pai–filho

O `_QueueRunLock` atual permanece sob controle do supervisor durante a fila e continua impedindo outra fila para o run. Ele é distinto do lock de ownership da época de escrita. O supervisor pai e o CLI filho não podem usar cache de épocas diferentes simultaneamente.

1. O pai possui conexão, writer lock e estado validado. O processo filho é criado com `CREATE_SUSPENDED`, associado ao Job Object e confirmado pelo callback `confirm_child`.
2. O pai grava `CHILD_PROCESS_CONFIRMED` com commit integral e ACK durável. Guarda `H = (run_id, sequence, event_hash, child_pid, creation_time, stage)` como referência de continuidade; H não contém nem autentica os totais em memória.
3. Ainda antes de `ResumeThread`, o pai invalida integralmente seu cache, fecha sua conexão e libera o writer lock. Falha de persistência/liberação aborta o lançamento e deixa o filho sem autorização para trabalhar.
4. O filho adquire o writer lock, executa replay integral de admissão, reconstrói o estado e verifica identidade/run/head, inclusive a associação do evento H à identidade/processo/etapa antes da primeira mutação.
5. O supervisor monitora o filho sem abrir o ledger. Depois de `process_exit` e confirmação de que a árvore terminou (`tree_confirmed`), um callback explícito readmite o pai **dentro de `supervisor.run()` e antes de qualquer evento ou recibo posterior ao filho**. O pai descarta o cache antigo, adquire o writer lock, executa replay integral, confirma que H permanece no histórico e reconstrói os totais/head finais. Só então pode escrever auditoria de encerramento e recibos.

Readmitir o pai somente depois de `supervisor.run()` retornar é tarde, pois esse método grava os eventos finais e persiste o recibo antes do retorno.

Se a árvore não estiver comprovadamente parada, o pai não readquire ownership nem abre/lê/escreve o ledger. A execução permanece bloqueada, sem evento de PASS ou recibo externo. A contenção e a auditoria não podem criar escritores concorrentes.

O hot path dentro do filho também requer lock local da instância cobrindo a operação inteira, inclusive COMMIT e publicação dos deltas. Nenhuma conexão/cursor pode escapar da região serializada; o lock local não deve ser mantido durante espera de rede. O contrato S9 exige um worker; chamadas simultâneas por threads ainda precisam de exclusão explícita.

### 4.3 Replay integral em conexão fresh

Em todo checkpoint/replay integral após uma época já ter aberto uma conexão SQLite, manter o writer ownership lock, invalidar e descartar o cache incremental e fechar essa conexão. Reabrir o ledger com uma conexão fresh e executar o replay completo sob o lock, verificando também identidade, caminho, quarentena, integridade SQLite, projeções e cadeia. Após replay PASS, fechar a conexão de replay, abrir/estabelecer uma conexão writer fresh, confirmar identidade e head reconstruídos e só então retomar a época. Nunca usar a conexão SQLite já aberta ou seu cache de páginas como evidência do replay integral. Em caso de falha no close/reopen, identidade/head, path guard ou replay, a época permanece inválida e bloqueada.

### 4.4 Validação integral em checkpoints

O desenho propõe cinco checkpoints lógicos de validação integral por fila:

1. admissão inicial do pai;
2. aquisição/admissão do filho;
3. fechamento normal do filho;
4. readmissão do pai depois de `process_exit + tree_confirmed`;
5. fechamento/reconciliação final do pai.

Se um helper compartilhado fizer o trabalho de dois checkpoints lógicos sem necessitar de duas passagens de dados, deve-se contabilizar uma única execução física. Os benchmarks precisam registrar cada passagem física, incluindo validações adicionais de recibo ou reconciliação, sem esconder scans duplicados. Validações completas não podem reaparecer em cada mutação, snapshot ou helper por acidente.

Cada checkpoint integral depois da abertura de uma época segue o procedimento de conexão fresh da seção 4.3. O checkpoint não é uma nova varredura na mesma conexão persistente.

Nenhum PASS/recibo externo pode ser emitido antes da validação integral final. Um resultado interno do filho não constitui evidência final; o pai somente o aceita depois de readmissão e replay completos.

Para receipts E2E PASS dentro do escopo da seção 5, o replay fresh que sela o arquivo deve ocorrer no callback `prepare`, depois de persistir duravelmente `RECEIPT_PREPARED` e antes de qualquer rename no-overwrite. No producer `s9_gate_reconciliation.py`, isso cobre tanto a criação nova quanto o ramo de recovery/idempotência que emite ou revalida PREPARED sem rename; executar exatamente uma vez por receipt. No producer `s9_operational_reconciliation.py`, `_persist_receipt` preserva no-overwrite e `_private_run_output_path` recusa destino existente: o callback aplica-se à nova criação G8/G9, sem branch idempotente dentro desse helper. Recovery de receipt operacional existente ocorre em nova época/processo, cujo construtor reabre o ledger e executa replay fresh antes de revalidar o receipt. O caller não deve duplicar o replay. O append de `RECEIPT_PERSISTED` e `GATE_FINISHED` continua durável após eventual rename. Cada replay físico é contado como checkpoint de receipt. Não executar callback para receipt BLOCKED ou para G1–G4.

### 4.5 Sinais de mudanças externas

`PRAGMA data_version` não é autenticação nem prova de integridade contra escrita direta no arquivo/WAL. Se usado, serve somente como sinal de que outra conexão SQLite cooperativa fez commit; uma mudança observada exige replay integral, com conexão fresh, antes da próxima mutação. O guard de caminho/identidade e a ausência de `.quarantine` são verificados em toda mutação e antes de todo ACK, independentemente do replay integral.

Uma escrita raw same-account, não coordenada, em linhas históricas do DB/WAL que não sejam tocadas pelo hot path pode não ser percebida pela próxima mutação. O próximo checkpoint integral em conexão fresh deve detectar a incoerência e bloquear fechamento/PASS/recibo. A janela de ratificação é limitada a esse caso. Uma reescrita coerente por alguém que possa recomputar a cadeia pode permanecer indetectável sem âncora externa; esse risco distinto já foi aceito pelo usuário em RISK-03 e não é eliminado por esta proposta. Mudança de path guard ou criação de `.quarantine` não estão nessa janela e devem bloquear a próxima mutação/ACK sem esperar checkpoint.

## 5. D — Superfícies e arquivos afetados

Os arquivos esperados para implementação são:

- `src/telegram_courses/s9_operational_ledger.py`: conexão persistente por época, estado incremental, sincronização local, checkpoints, recuperação e invalidação.
- `src/telegram_courses/s9_supervisor.py`: callback de liberação antes de `ResumeThread` e callback explícito de readmissão após contenção/término, antes da auditoria/recibo final.
- `src/telegram_courses/s9_supervisor_cli.py`: ownership do pai/filho integrado à fila sem liberar `_QueueRunLock` do pai; no caminho G7 que usa o helper genérico de receipt, passar o checkpoint de receipt. G1/G2/G3 permanecem sem replay adicional.
- `src/telegram_courses/cli.py`: aquisição e uso da época do ledger pelo processo filho no caminho S9 de queue.
- `src/telegram_courses/s9_gate_reconciliation.py`: callback `prepare` para receipts E2E PASS G5–G9, depois de PREPARED durável/revalidado e antes de eventual rename. G1–G4 não recebem replay adicional.
- `src/telegram_courses/s9_operational_reconciliation.py`: callback `prepare` limitado à nova criação de receipts E2E PASS/OFFLINE_SYNTHETIC_PASS G8/G9, depois de PREPARED durável e antes de eventual rename; conservar `_private_run_output_path` e no-overwrite para destinos existentes. Recovery de receipt existente deve reabrir ledger em nova época/processo e fazer replay fresh no construtor antes de revalidar o receipt.
- Testes unitários/integração focados do ledger, handoff, concorrência, recuperação e gates.

O escopo de receipt é somente callback `prepare` nesses dois producers e handoff G7 no helper genérico; não introduzir replay adicional nos caminhos G1–G4 ou G1/G2/G3. Não fazer refatoração geral, migração de schema ou alteração de interfaces públicas sem necessidade demonstrada e revisão do ROOT.

## 6. E — Invariantes que devem permanecer

- Uma reserva exata e durável precede cada RPC; não pode haver reserva dupla nem saldo liberado prematuramente.
- Bytes observados vêm da fonte permitida pelo contrato; estado incerto é cobrado integralmente como `UNCERTAIN`.
- Limites de bytes e mídia F/M, tentativas, scans e deadline permanecem exatos e fail-closed.
- Eventos T24 permanecem atômicos com a mutação correspondente e duráveis antes de ACK.
- `journal_mode=WAL`, `synchronous=FULL` e `BEGIN IMMEDIATE` continuam preservados.
- Hash-chain, verificação SQLite/foreign key, proteção de overwrite e reabertura fail-closed permanecem.
- O guard de caminho/identidade e a ausência do marcador `.quarantine` são verificados antes de toda mutação e antes do ACK correspondente; falha bloqueia sem esperar replay de fechamento.
- FloodWait, falha de ledger/auditoria, commit ambíguo, crash e falha de contenção não podem produzir PASS.
- A árvore de processos precisa estar comprovadamente parada antes de readmissão do pai após o filho.
- Nenhum PASS ou recibo externo é válido antes da validação integral dos dados finais.
- Não alterar S9-L01..L16, contrato v1 congelado, nem os limites de uso pessoal de RISK-03.

## 7. F — Recuperação

- **Crash antes do COMMIT:** SQLite recupera a transação incompleta; somente reservas já confirmadas continuam no estado reconstruído.
- **Crash após COMMIT e antes da atualização em RAM:** replay em conexão fresh reconstitui o commit persistido; memória antiga não é reutilizada.
- **COMMIT ambíguo ou erro de I/O:** invalidar a época, bloquear novas RPCs/ACKs e recuperar com replay integral em conexão fresh; nunca repetir automaticamente uma solicitação cujo efeito externo seja incerto.
- **Reserva sem liquidação após contenção comprovada:** o pai readmitido pode marcá-la incerta e cobrar seu valor integral; não pode atribuir bytes observados sem medição confiável.
- **Falha do filho antes de obter ownership:** pai aguarda contenção/saída e então reabre/revalida; se a árvore continuar ativa ou não comprovada, não abre nem disputa o ledger.
- **Lock abandonado por crash:** significa recovery obrigatório, nunca permissão para reutilizar cache antigo.
- **Corrupção/quarentena/integridade falha:** bloquear e preservar DB, WAL e evidência para diagnóstico; não inicializar por cima nem remover marcadores.

## 8. G — Consistência e ACK

Uma única época possui o writer lock e conexão de estado. Dentro dela, SQLite `BEGIN IMMEDIATE` serializa escrita, enquanto lock local serializa estado/conexão. A mutação de projeções e o append do evento são atômicos na mesma transação. O ACK inclui sequência/hash efetivamente persistidos e somente é devolvido depois de `synchronous=FULL` e COMMIT bem-sucedido.

O estado em RAM avança somente após commit durável. Erro ambíguo invalida a época. Em handoff ou checkpoint da época, o novo dono descarta conexão/cache anteriores, reexecuta a cadeia integral em conexão fresh e compara a referência H quando aplicável antes de continuar. Eventuais commits cooperativos observados por `data_version` forçam replay completo em conexão fresh; `data_version` nunca é tratado como autenticidade. O guard path/identidade e o marcador `.quarantine` são conferidos por operação e antes de ACK.

## 9. H — Complexidade esperada

Atual: O(N) de replay por mutação e, aproximadamente, O(N²) para N blocos, pois cada bloco provoca seis passagens cujo custo cresce com o histórico.

Candidata: K replays integrais em checkpoints delimitados, de custo total O(KN), mais deltas de estado e consultas indexadas no hot path, aproximadamente O(N log N) ou O(N) esperado para N eventos, conforme índices e estruturas escolhidos. K é limitado pelo número de checkpoints/handoffs/reconciliações, não por bloco. Cada reserva e liquidação ainda executa commit durable independente e mantém seus custos de WAL/fsync. A complexidade observada deve ser comprovada nos benchmarks de caminho efetivo; não se presume que a proposta atingirá o alvo.

## 10. I — Compatibilidade SQLite/WAL

O SQLite em WAL admite um único writer por vez; transações `BEGIN IMMEDIATE` adquirem a transação de escrita imediatamente e podem aguardar/falhar quando outro writer está ativo. `synchronous=FULL` deve permanecer em cada commit que sustenta ACK. Replays integrais/checkpoints não podem ser removidos para obter velocidade.

Não usar `locking_mode=EXCLUSIVE` como defesa universal contra raw writes ou como prova de integridade. Uma sonda local do arquiteto observou que uma conexão SQLite concorrente ficou bloqueada sob o modo exclusivo, enquanto a abertura raw `r+b` do arquivo ainda era possível (nenhum byte foi gravado pela sonda). Esse comportamento não prova proteção contra escrita direta; também não fundamenta mudança do contrato de locking.

Referências oficiais:

- [SQLite Write-Ahead Logging](https://sqlite.org/wal.html)
- [SQLite Transactions](https://www.sqlite.org/lang_transaction.html)
- [SQLite PRAGMA reference](https://sqlite.org/pragma.html)
- [How To Corrupt An SQLite Database File](https://www.sqlite.org/howtocorrupt.html)

## 11. J — Critérios mensuráveis e ratificação requerida

### 11.1 Gates obrigatórios do card P0

Benchmarks progressivos do caminho real do CLI/gateway sintético e ledger, em ambiente comparável: 64 MiB, 256 MiB e 1 GiB. Registrar para cada um bytes/blocos/eventos, duração total, MiB/s, média e p95 por operação, duração de commits/fsync, tempo em validação/checkpoints, CPU, RSS/memória, escrita DB/WAL, resultado de integridade e origem do ensaio. Comparar baseline e depois sem misturar perfis ou inventar métricas.

O gate de performance rígido é `E2E_M_1GIB = PASS` e `L10_M_ELAPSED <= 1800s` no CLI sintético efetivo. Recomenda-se margem operacional substancial, sem criar limite contratual adicional para benchmarks ledger-only.

Também são obrigatórios: `FULL_OFFLINE_REGRESSION = PASS`; `ACCOUNTING = EXACT`; `RECOVERY = PASS`; `LEDGER_INTEGRITY = PASS`; `AUDIT_T24 = PASS`; `FAIL_CLOSED = PRESERVED`; revisão independente de segurança `PASS` ou `PASS_WITH_LIMITS`; e zero achados bloqueadores. O E2E M de 1 GiB anteriormente reprovado não conta como PASS nem pode ser omitido.

### 11.2 Decisão humana pendente — janela de detecção raw

**Ratificação humana recebida.** Em 2026-11-01, o usuário respondeu `ACEITO` diretamente nesta conversa ROOT e autorizou a formalização e implementação offline sob estas condições. Na arquitetura aprovada, uma escrita raw feita pelo mesmo usuário Windows em linhas históricas do DB/WAL não tocadas durante a época pode não ser detectada pela próxima mutação incremental. Sob a hipótese de adulteração não coordenada, o próximo replay integral em conexão fresh descarta a conexão/cache anterior, detecta a incoerência e bloqueia fechamento/PASS/recibo. `PRAGMA data_version` não detecta nem autentica essa escrita. A ratificação não cobre nem posterga guard de path/identidade ou marcador `.quarantine`: ambos são verificados por mutação e antes de ACK. Uma reescrita coerente com recálculo da cadeia por quem tenha acesso same-account continua fora da garantia sem âncora externa, conforme risco RISK-03 já aceito.

O pedido de decisão é:

> Para o uso pessoal já aprovado, ratifico que uma escrita raw same-account não coordenada em linhas históricas do DB/WAL não tocadas durante a época possa escapar à detecção na próxima mutação e ser detectada somente no próximo replay integral em conexão fresh, que bloqueia fechamento/PASS/recibo? Guard de path/identidade e marcador `.quarantine` continuarão sendo verificados a cada mutação e antes de ACK. **ACEITO** / **REJEITO**.

`ACEITO` foi recebido diretamente do usuário e libera a implementação desta arquitetura, após o QA contratual do ROOT, sem modificar o contrato S9 v1.0. Se a decisão tivesse sido `REJEITO`, o resultado seria `NO_GO` e retorno à validação integral atual por mutação. O aceite formal anterior de RISK-03 não foi usado como substituto desta ratificação.

## 12. K — Riscos residuais

- A janela raw ratificada, se aceita, é limitada a escrita same-account não coordenada em linhas históricas do DB/WAL não tocadas durante a época; a próxima mutação pode não detectá-la. O checkpoint seguinte usa conexão fresh e bloqueia fechamento/PASS/recibo se a incoerência existir. Guard de path/identidade e `.quarantine` continuam verificados por mutação/ACK.
- Processo com acesso de escrita à mesma conta Windows pode alterar ou reencadear evidência local conforme o risco de uso pessoal RISK-03 previamente aceito; este contrato não adiciona âncora externa.
- A proposta adiciona ciclo de vida de ownership e estado incremental; implementação incorreta pode deixar cache stale, ACK adiantado, orçamento divergente ou conexão concorrente. Locks, callbacks de handoff e invalidação precisam ser provados por testes.
- Com FULL mantido, commits e fsync por reserva/liquidação continuam. A remoção do custo quadrático ainda precisa mostrar throughput suficiente no E2E real do harness.
- Abrir muitas instâncias/processos ou manter árvore sem containment pode bloquear ou impedir readmissão. O comportamento obrigatório nesses casos é fail-closed e sem recibo.

## 13. L — Plano de testes

Testes unitários de equivalência entre replay integral e estado incremental em cada transição; limites exatos de bytes/media/tentativas/scans/deadline; append e ACK; rejeição por linha/head divergente; serialização thread-local; e ausência de full replay no hot path por bloco.

Testes adversariais e de recuperação do card P0:

- crash após reserva, após liquidação, antes/durante/após commit e transação incompleta;
- reabertura e reconstrução após cada ponto de crash, incluindo commit ambíguo;
- hash incompatível, evento ausente, DB truncado e WAL inconsistente;
- escritor SQLite concorrente, duas instâncias/processos e leitura/escrita externa;
- escrita raw no DB/WAL e alteração do marcador `.quarantine` durante época;
- executar essas adulterações gravando bytes reais no DB/WAL e criando/alterando `.quarantine` em diretório temporário isolado; provar que marker/path é detectado na próxima mutação antes de qualquer escrita/ACK, enquanto incoerência histórica em linha não tocada é identificada no checkpoint integral por conexão fresh; confirmar em ambos que não há recibo/PASS;
- saldo divergente, reserva excedida, reserva dupla e mudança em linha/head tocados;
- cancelamento, timeout, FloodWait e falha de auditoria;
- recibo adulterado/overwrite e ordem de ACK/commit;
- receipts E2E PASS G5–G9: provar a ordem `RECEIPT_PREPARED` durável → callback `prepare` de replay integral fresh → eventual rename/no-overwrite; no `s9_gate_reconciliation.py`, provar exatamente uma chamada por receipt tanto em criação nova quanto em recovery/idempotência sem rename. Em `s9_operational_reconciliation.py`, provar callback somente para nova criação PASS/OFFLINE_SYNTHETIC_PASS G8/G9, destino existente recusado sem overwrite, e recovery reabre o ledger numa nova época com replay fresh no construtor antes de revalidar o receipt. Provar ausência do callback para receipts BLOCKED e G1–G4; incluir handoff G7 pelo helper genérico em `s9_supervisor_cli.py`;
- handoff pai→filho no estado suspenso, filho antes/depois de obter lock, identidade H, readmissão do pai antes da auditoria/recibo e invalidação de cache stale;
- handoff G1/G5/G8: confirmar ownership/checkpoint nos caminhos aplicáveis antes de PASS/receipt e ausência de replay extra nos receipts G1–G4; os caminhos G1/G2/G3 não chamam o callback do helper genérico;
- árvore não comprovadamente encerrada não readquire writer, não lê/escreve ledger e não produz PASS/recibo;
- threads/async em torno do mesmo objeto sem concorrência dentro da mutação;
- T24, contenção, recovery e testes offline de regressão S9.

Todos os casos de replay integral inválido devem provar que não há PASS/recibo externo. Benchmarks precisam incluir o CLI/gateway sintético e o caminho real do ledger, não somente funções isoladas. Executar regressão offline integral, testes focados, Ruff focal, compileall e `git diff --check` conforme card. Temporários devem permanecer fora do checkout, com caminho curto e diretório isolado.

## 14. M — Rollback lógico

Em falha, interromper novas operações e conter o processo; não readquirir ownership com árvore ativa/incerta. Preservar ledger, WAL, marcador de quarentena, recibos e logs como evidência. Reabrir somente em modo de validação integral/read-only para diagnosticar. Desabilitar o caminho incremental e retornar à validação integral por mutação em uma retomada controlada, se a integridade/formato forem válidos. Se não forem, manter bloqueado/quarentenado e não reutilizar o ledger. Não remover, sobrescrever ou resetar dados; não usar `git reset`, `restore`, `clean`, `stash` ou qualquer publicação Git como parte do rollback.

## 15. Aprovação e limite de implementação

```text
ROOT_ARCHITECTURE_REVIEW = APPROVED_AFTER_USER_RATIFICATION
ROOT_CONTRACT_QA = PASS
HUMAN_RAW_DETECTION_WINDOW_RATIFICATION = ACCEPTED / USER_MESSAGE_IN_CURRENT_ROOT_CHAT / 2026-11-01
IMPLEMENTATION_AUTHORIZATION = YES / OFFLINE_P0_SCOPE_ONLY
CONTRACT_S9_CHANGE = NONE
CANONICAL_CHAT_DELIVERY = SENT_AND_OBSERVED / ASSISTANT_ACKNOWLEDGED_USER_RATIFICATION / THREAD_ID=6add6aa9-12e0-83e8-b02f-870f0a0edaf9
```

O ROOT revisou a consistência técnica e o plano de testes (`ROOT_CONTRACT_QA = PASS`). O usuário ratificou explicitamente a janela raw nesta conversa em 2026-11-01; o implementador pode atuar exclusivamente no escopo offline ratificado. A decisão também foi enviada ao chat canônico e o readback observou a aprovação e o reconhecimento do assistente no destino. Isso confirma a entrega da comunicação, sem transformar a resposta do assistente em fonte da autoridade humana.
