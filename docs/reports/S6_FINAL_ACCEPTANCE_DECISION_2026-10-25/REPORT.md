# Telegram 3.0 — Decisão de aceite final da S6

**ACTIVITY_ID:** `S6_FINAL_ACCEPTANCE_DECISION_2026-10-25`  
**PROJECT:** `projeto_telegram_courses`  
**DATA:** 2026-10-25  
**ESCOPO DESTA ATIVIDADE:** consolidação documental e recomendação para decisão do usuário; sem execução de testes ou operações Telegram.

## 1. Resumo executivo

A S6 continua **OPEN**. O Gate A está **PARTIAL** e o Gate B está **BLOCKED_BY_REMOTE_EVIDENCE**. O contrato S6 V1 permanece aprovado, congelado e ativo; V2 continua globalmente desligada; S7 e S8 continuam deferred. A autoridade vigente para esse estado é o [PROJECT_STATE](../../continuity/PROJECT_STATE.md), navegada pelo [ACTIVE_AUTHORITY_MAP](../../continuity/ACTIVE_AUTHORITY_MAP.md) e vinculada ao baseline adotado em [PROJECT_GOVERNANCE_BINDING](../../continuity/PROJECT_GOVERNANCE_BINDING.json).

Há evidência funcional relevante: regressão histórica de 196/196, retomada física em processos distintos a partir de checkpoint persistido e igualdade byte a byte/hash do arquivo final com uma referência local naquele caso. Isso não demonstra o requisito V1 de comprovar remotamente todo o prefixo **antes** do append. A prova V2 deixou 36.954 bytes do tamanho esperado sem cobertura remota e a origem da referência está registrada como `DOCUMENTED_UNATTESTED`. Portanto, não há aceite integral de conformidade V1.

**Recomendação:** Opção B — encerramento com escopo revisado, condicionado à aprovação expressa do usuário para a dispensa de escopo e para o aceite da S6. O aceite proposto deve registrar as lacunas e riscos sem convertê-los em PASS, manter V1 ativo e V2 global OFF, e não iniciar S7/S8 automaticamente. Até essa aprovação e o checkpoint formal posterior, `S6_STATUS=OPEN`.

## 2. Evidências comprovadas

Os fatos abaixo são evidências de resultados específicos; seu alcance não deve ser ampliado para requisitos que eles não medem.

- **Regressão funcional histórica:** 196/196 casos passaram. O resultado é histórico; não foi repetido nesta atividade. O recibo externo histórico registrou `ExitCode=null` e `observed=false`, e o código zero dos metadados do worker não o substitui. Ver [reconciliação da prova e Gate A](../S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/REPORT.md) e [triage dos Gates A/B](../S6_GATE_A_EXITCODE_ROOT_CAUSE_AND_B_TARGET_TRIAGE_2026-10-24/REPORT.md).
- **Retomada física observada:** a prova V2 registrou dois processos, um checkpoint de 8 MiB persistido e a continuação a partir dele. O arquivo final atingiu o tamanho esperado e correspondeu byte a byte e por SHA-256 à referência local. O banco de prova registrou `COMPLETED_V2`; isso não é estado `DOWNLOADED` V1. Ver a [reconciliação da prova V2](../S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/REPORT.md).
- **Limite da prova V2:** a evidência registra `remote_reread=false` para o prefixo antes da continuação. A cobertura remota conhecida alcançou `[0, 1.119.092.736)` de `E=1.119.129.690`; os 36.954 bytes finais não foram verificados. Uma faixa além de EOF não comprova esse sufixo. A igualdade local final com a referência não substitui a prova remota do prefixo exigida por V1.
- **Revisão estática V1:** a remediação documental de 24/10 confirmou que o caminho `REMOTE_HASH_REQUIRED` chama `_verify_prefix` antes de abrir o writer e falha fechado para cobertura inadequada. Isso é revisão estática do caminho; não é uma prova V1 em execução real.
- **Probe sintética posterior:** em 25/10, `PASS_SYNTHETIC` observou `ExitCode=37` para um processo sintético de saída rápida no Windows PowerShell 5.1. A espera de dois segundos pretendida não ocorreu. A probe não recupera retroativamente o exit code histórico, não confirma a causa do nulo e não valida o wrapper completo nem o Harness. O relatório de 25/10 [supersede, para o estado da probe, o checkpoint de 24/10](../S6_GATE_A_EXITCODE_SYNTHETIC_PROBE_2026-10-25/REPORT.md).
- **Registros contratuais:** V1 continua congelado e ativo; a aprovação das diretrizes V2 não ativou V2 nem encerrou S6. A aprovação formal da sprint e o avanço continuam separados, conforme [APPROVALS_AND_DECISIONS](../../governance/APPROVALS_AND_DECISIONS.md), o [contrato V1](../../contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md) e a [homologação V2](../../contracts/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_CONTRACT_2026-10-18.md).

## 3. Matriz dos 18 requisitos S6

**Classes atuais:** A = evidência completa para o critério; B = comportamento funcional demonstrado, mas evidência formal incompleta; C = não comprovado. **Não há critério integralmente comprovado contra o conjunto V1 nesta matriz.** A classe D aparece apenas na coluna de tratamento proposto pela Opção B: é uma dispensa ou alteração de escopo que depende do usuário, nunca um PASS.

Os nomes e condições seguem a [§9 do contrato S6 V1](../../contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md). A camada offline não autentica Telegram nem comprova disponibilidade/cobertura de `upload.getFileHashes`; a prova real é um gate separado e obrigatório para aceitar resume.

| # | Critério do contrato | Classe atual | Evidência existente | Lacuna / risco | Opção B: mudança formal necessária (D) |
|---:|---|:---:|---|---|---|
| 1 | Resume após interrupção | B | Checkpoint físico persistido e continuação em outro processo foram observados na prova V2. | Essa execução não demonstrou toda a condição V1 de identidade e cobertura remota antes do append. | Sim. Aceitar a retomada física observada como demonstração funcional daquele caso, sem alegar cumprimento completo do gate remoto V1. |
| 2 | Identidade remota | B | A prova V2 registra refetch e verificação da identidade do alvo. | O pacote resumido não fecha formalmente todos os campos e a reconciliação requerida para o aceite V1. | Não altera a identidade requerida; registrar a limitação da evidência existente e reabrir se houver divergência ou novo alvo. |
| 3 | Matriz física do `.part` | B | O caso real registrou um checkpoint parcial persistido e retomado; testes funcionais históricos passaram. | Isso não cobre toda a matriz de arquivos vazios, maiores, estrangeiros, divergentes, ownership e `D` versus `P`. | Não muda o comportamento de proteção; manter cenários não demonstrados rastreáveis. |
| 4 | Integridade do prefixo | C | A revisão V1 estática confirma a ordem do guard no caminho `REMOTE_HASH_REQUIRED`. | A prova V2 não releu/provou o prefixo antes da continuação; a cobertura também não chegou ao EOF. Este requisito central de integridade não passou. | **Sim.** Exige dispensa/versionamento explícito da exigência de cobertura remota integral de `[0,P)` antes do append e da validação remota até EOF; a igualdade local da referência só vale para o arquivo/caso observado. |
| 5 | Offset físico alinhado | B | A retomada V2 partiu de checkpoint alinhado de 8 MiB. | A evidência resumida não fecha todos os requests/limites junto às fronteiras de 1 MiB e a cadeia V1 de verificação do prefixo. | Não reivindicar mais do que o caso alinhado observado; guardar os limites de request que faltam como evidência parcial. |
| 6 | Offset físico não alinhado | C | Há evidência offline histórica, mas nenhuma prova real não alinhada foi localizada para este aceite. | Não se comprovou `W`, overlap `O`, igualdade byte a byte antes de append em `P` e final sem duplicação em uma retomada real. | **Sim.** Restringir o aceite revisado à retomada alinhada observada e deixar a prova real não alinhada fora do escopo aceito. |
| 7 | Offset aceito pelo adapter | B | O fluxo V2 alinhado retomou sem falha aparente no caso medido. | Não há trace completo dos argumentos/respostas Telethon 1.45.x e de todas as fronteiras exigidas pelo critério. | Não declarar suporte genérico além do caso demonstrado; conservar a validação formal como pendência se o offset for alterado. |
| 8 | Arquivo final idêntico à referência | B | O arquivo final da prova V2 foi comparado byte a byte e por SHA-256 com a referência local. | A evidência é do perfil V2; a proveniência da referência consta como `DOCUMENTED_UNATTESTED`, e isso não demonstra a integridade remota do prefixo V1. | Não converter em conformidade V1. A aceitação revisada deve limitar explicitamente esse resultado a uma comparação local daquele caso. |
| 9 | SHA-256 e tamanho | B | O arquivo final teve tamanho esperado e SHA-256 igual ao da referência local; o registro de prova foi `COMPLETED_V2`. | O estado é V2 e a comparação não satisfaz por si só o requisito V1 de prova remota antes do append. | Não equiparar `COMPLETED_V2` a `DOWNLOADED` V1; registrar a evidência somente como resultado local do caso. |
| 10 | Persistência após restart | B | Dois processos distintos, checkpoint de 8 MiB persistido e continuação foram observados. | Não se demonstraram todos os casos de PID/ownership ambíguo nem toda a reconciliação de estado exigida após restart. | Aceitar apenas o restart observado; a exceção não certifica as demais situações de ownership. |
| 11 | Janelas de crash | C | A regressão offline histórica passou, mas não foi localizada uma matriz completa de fault injection e leitura independente para cada janela contratual. | Falhas entre `fsync`, checkpoint SQLite, validação, rename e persistência final podem continuar sem evidência de reconciliação. | **Sim.** Se a Opção B for aprovada, deferir a matriz completa como pendência formal, sem alegar durabilidade integral. |
| 12 | Deduplicação posterior | C | Testes funcionais históricos passaram. | Não há prova deste pacote que mostre uma segunda execução pós-retomada com zero payload novo. | **Sim.** Deferir o critério real de zero payload; reabrir antes de reivindicar deduplicação pós-retomada em produção. |
| 13 | Concorrência sem corrupção | B | Regressão funcional histórica 196/196 passou. | Não foi reconciliada nesta decisão uma linha do tempo completa de ownership, restore e stream para cada condição concorrente. | Não amplia o resultado; manter a concorrência nos limites S5 já aprovados. |
| 14 | Orçamento S5 | B | O banco da prova V2 possui resumo de reservas e bytes recebidos, sem reservas incertas registradas. | O Gate B não tem reconciliação formal suficiente de `P`, `D`, orçamento agregado S5 e detalhe por worker/tentativa/tipo. | **Sim.** Se aceito B, dispensar somente a evidência completa do caso histórico e mantê-la como pendência. Os limites reais aprovados por S5 não mudam. |
| 15 | Disco e margem | C | Há validações offline históricas, mas não foi localizada evidência completa do espaço livre, `.part`, bytes restantes e margem para a prova que sustenta este aceite. | Não se comprova, para esse caso, o gate de espaço antes de write/request. | **Sim.** Deferir a comprovação formal para escopo posterior de operação/hardening; não declarar que foi medida. |
| 16 | Sem falso `DOWNLOADED` | B | O caminho V1 foi inspecionado estaticamente e falha fechado; as regressões funcionais históricas passaram. | A prova real V2 terminou em `COMPLETED_V2`, não exercitou o gate V1 de falha antes do estado final. | Não converter revisão estática ou estado V2 em prova V1; preservar o fail-closed como exigência ativa. |
| 17 | Regressão S4/S5 | B | O resultado funcional histórico foi 196/196 PASS. | O recibo externo do Harness deixou o exit code nulo/não observado; o worker não o substitui. | **Dispensa de gate de projeto separada:** aceitar o resultado funcional com recibo externo incompleto somente se o usuário aprovar. Gate A continua `PARTIAL`; não é PASS. |
| 18 | Memória limitada | C | Não foi localizada medição de pico em arquivo grande com os buffers da verificação. | Limite de memória para o caso real não está demonstrado. | **Sim.** Deferir a medição com threshold definido para atividade futura; não declarar memória limitada como comprovada. |

**Resumo da matriz:** `A=0`, `B=12`, `C=6`. A decisão B exigiria as oito dispensas de escopo marcadas na tabela (`1, 4, 6, 11, 12, 14, 15, 18`), além da dispensa separada do gate processual externo do Gate A. Nenhuma delas é concedida por este relatório.

## 4. Pendências reais versus limitações formais

### Pendências técnicas/evidenciais reais

- Cobertura remota completa e válida para o prefixo antes do append e para o arquivo até EOF. O caso registrado deixa 36.954 bytes sem prova remota; não há alvo alternativo selecionado.
- Prova real não alinhada com comparação integral de overlap, além da cobertura de requests/alinhamentos exigida.
- Evidência completa de `P` físico versus `D` persistido e do orçamento S5 para a prova; o resumo de contadores não fecha a reconciliação requerida.
- Evidência específica das janelas de crash, deduplicação posterior sem payload, verificação do gate de disco/margem e medição de memória limitada.

### Limitações formais do registro

- O Gate A não tem `Process.ExitCode` externo persistido/observado na execução histórica. A causa do nulo continua não confirmada; o valor do worker não substitui o processo externo.
- A probe de 25/10 comprova somente captura de exit code no processo sintético rápido observado. O atraso de dois segundos falhou e a prova não executou nem validou o Harness.
- A prova `TRUSTED_REFERENCE_MATCH` pertence ao perfil V2 e comprova comparação local do resultado com uma referência naquele caso. Ela não é o requisito V1 de hash remoto integral do prefixo antes do append. A referência está documentada como não atestada quanto à origem.
- A S6 V1 tem 18 critérios com condições próprias; resultado agregado de regressão não é evidência automática de cada condição. O estado documental anterior à probe de 25/10 descrevia a probe como não executada; para esse fato, prevalece o relatório posterior da probe. O checkpoint de 24/10 continua útil para os demais fatos que não foram substituídos.

## 5. Riscos residuais

- **Integridade V1:** a execução V2 que produziu arquivo igual à referência não provou que um prefixo arbitrário foi verificado remotamente antes do append. Não se deve generalizar o resultado para outros arquivos ou sessões.
- **Disponibilidade:** a cobertura remota incompleta impede provar o gate B para o alvo registrado. O caminho V1, conforme revisão estática, falha fechado quando a cobertura não é suficiente; isso limita a retomada disponível, mas a revisão não substitui validação real.
- **Referência:** a correspondência de bytes é observada entre os arquivos locais; a proveniência da referência não está atestada no pacote. Isso limita a força da comparação como atestado externo.
- **Gate A:** a regressão funcional foi positiva, mas a execução histórica não tem exit code externo reconciliado. A probe sintética não fecha essa lacuna; a causa raiz não é conhecida.
- **Resiliência e operação:** critérios de offset não alinhado, crash, dedup, disco/margem, memória e reconciliação S5 continuam sem evidência completa. A aceitação B carregaria esses riscos como exceções documentadas, não como requisitos cumpridos.
- **Cronograma:** A mantém S6 aberta e impede a entrada regular de S7/S8. B reduz novas execuções agora, mas exige governança explícita e checkpoint depois da decisão do usuário.

## 6. Opção A — conformidade estrita

Manter S6 aberta até obter evidência integral dos Gates A e B e dos critérios obrigatórios V1. As atividades mínimas seriam:

1. **Gate A, com autorização separada:** uma execução nativa completa do Harness usando o procedimento corretivo documentado. Preservar recibo durável do exit code do processo externo, resultado JUnit, metadados do worker, identidade do supervisor/processo externo e reconciliação de PID/processo. `PASS_SYNTHETIC` não substitui essa execução.
2. **Gate B, com autorização Telegram separada:** selecionar um alvo controlado que demonstre identidade exata e cobertura remota válida de `[0,E)` sem gaps ou faixas além de EOF. Executar prova de mídia grande com checkpoint persistido e processo reiniciado; provar cobertura do prefixo **antes** de append e da continuação até EOF; cobrir retomadas alinhada e não alinhada com overlap validado; comparar o arquivo de referência; reconciliar `P`, `D`, SQLite e todos os limites/orçamentos S5. Se nenhum alvo satisfizer as condições remotas, o Gate B permanece bloqueado.

**Riscos e prazo:** o fluxo pode exigir transferência de pelo menos 1 GiB, espaço temporário e mais de uma fase de leitura/download. Interrupções deixam artefatos de prova a preservar; consultas e transferências podem encontrar FloodWait, rate limits ou cobertura de hashes insuficiente. A busca por alvo pode falhar repetidamente, sem garantia de que outro upload cubra EOF. Não há ETA confiável. Até fechar esses gates, S6 permanece OPEN e S7/S8 não atendem à condição de entrada da S6.

## 7. Opção B — encerramento com escopo revisado

Aceitar formalmente somente o escopo funcional observado: regressão histórica, retomada física alinhada em processos distintos e igualdade local do arquivo final com a referência naquele caso. O aceite deve dizer **S6 aceita com exceções formais**, nunca `S6 V1 conforme`, `Gate A PASS` ou `Gate B PASS`.

Para esse encerramento, o usuário precisaria aprovar expressamente:

- uma dispensa/versionamento de escopo em relação à §4, §9, §10 e S6-OD-01 do contrato congelado, para aceitar o resultado local observado sem evidência de cobertura remota integral do prefixo antes do append e até EOF;
- limitar a alegação real à retomada alinhada observada, adiando a prova não alinhada;
- registrar como exceções/deferimentos a matriz completa de crash, o zero-payload de deduplicação, a reconciliação detalhada de orçamento S5/P/D, o gate medido de disco/margem e a medição de memória;
- dispensar, para o aceite da sprint, o recibo externo histórico incompleto do Gate A. O status factual do Gate A continua `PARTIAL`; a probe sintética continua sendo apenas `PASS_SYNTHETIC`.

Essas alterações não mudam os limites operacionais S5. O texto base V1 não deve ser editado ou substituído agora; a exceção precisa ser aprovada e registrada em artefato versionado/decisão formal, sem reescrever a história. `V1_ACTIVE=YES`, `V2_GLOBAL=OFF`, sem ativação de V2. A igualdade local da referência vale para o arquivo observado e não confere integridade remota genérica a V1.

**Pendências rastreáveis e gatilhos de reabertura:**

| Pendência mantida | Critério claro para eventual retomada |
|---|---|
| Prefixo remoto e EOF | Retomar o gate se for exigida evidência V1 integral ou se um novo caso precisar de retomada comprovada; exigir cobertura `[0,P)` antes do writer, continuação até `[0,E)`, identidade confirmada e sem gaps/over-EOF. |
| Offset não alinhado | Retomar antes de alegar suporte/aceite para `P` não alinhado; demonstrar `W`, `O`, igualdade do overlap antes de append em `P` e arquivo final sem duplicação. |
| Crash e ownership | Retomar se o fluxo de persistência mudar ou antes de declarar essa durabilidade; cobrir as janelas `fsync`, checkpoint, validação, rename e persistência final, com inspeção SQLite/filesystem. |
| Deduplicação pós-resume | Retomar antes de afirmar o requisito real; uma segunda execução deve demonstrar zero payload novo para o item validado. |
| S5, disco e memória | Para nova prova/aceite operacional, registrar orçamento por chamada/worker/tentativa com `P`/`D`, limite S5 e saldo; verificar espaço e margem antes de escrita; definir e medir o threshold de memória. Os limites S5 seguem obrigatórios. |
| Exit externo do Harness | Reabrir somente se a conformidade do Harness for necessária para decisão futura ou houver nova execução; exigir exit externo persistido e reconciliado, sem usar código de worker como substituto. |

Este relatório não altera escopo nem fecha sprint. A Opção B só poderá ser executada após aceite explícito do usuário da dispensa e da S6.

## 8. Recomendação objetiva

**Recomendo a Opção B, condicionada à aprovação explícita do usuário.** O benefício é encerrar o ciclo de reexecuções agora com base em evidência funcional concreta: a regressão reportada passou, a retomada alinhada foi observada e o arquivo final do caso comparado correspondeu integralmente à referência local. A Opção A exigiria novas execuções nativas e uma nova prova Telegram de grande porte, com custos, risco de rate limit/interrupção e sem garantia de que outro alvo permita cobertura remota até EOF.

O custo da Opção B é aceitar formalmente um risco residual de disponibilidade e de garantia de integridade: o caso observado não demonstra a integridade remota V1 do prefixo e as demais lacunas listadas continuam não comprovadas. A mitigação de governança é manter V1 ativo, V2 global OFF, preservar a regra V1 fail-closed e registrar as exceções sem transformá-las em PASS. Essa proporcionalidade justifica recomendar B para o objetivo de avançar o planejamento, mas não permite declarar conformidade V1 nem avançar S7/S8 sem os gates próprios.

## 9. Texto de decisão para aprovação do usuário

> **APROVO A OPÇÃO B — ENCERRAMENTO DA S6 COM ESCOPO REVISADO E EXCEÇÕES DOCUMENTADAS.** Aceito a dispensa formal das exigências de cobertura remota V1 do prefixo antes do append e até EOF para o caso observado, a limitação da prova real ao cenário alinhado, e as pendências de Gate A, crash, deduplicação, reconciliação detalhada S5/P/D, disco/margem e memória conforme este relatório. Reconheço que isso não prova conformidade integral ao contrato S6 V1 e que a comparação final com a referência é evidência local de um caso, não prova remota genérica. Autorizo registrar documentalmente o aceite da S6 com essas exceções após esta aprovação. Mantenho `V1_ACTIVE=YES` e `V2_GLOBAL=OFF`. Esta decisão não inicia S7/S8, não autoriza implementação, testes, Harness, chamadas Telegram/RPC, downloads ou publicação Git; essas atividades dependem de gates e autorizações próprios.

## 10. Procedimento mínimo após eventual aceite e transição S7+S8

1. **Aguardar a decisão do usuário.** Sem aprovação expressa da Opção B e das exceções, manter S6 OPEN e não executar mudanças.
2. **Após aprovação, reconciliar formalmente as authorities** em atividade documental delimitada: registrar a decisão e as dispensas em `APPROVALS_AND_DECISIONS`, atualizar `PROJECT_STATE` e `SPRINTS` com o status aprovado e as pendências/gatilhos desta decisão, e confirmar `V1_ACTIVE=YES`, `V2_GLOBAL=OFF`, sem reescrever recibos históricos. Se a aprovação não abranger essa reconciliação, obter a autorização correspondente antes de editar as authorities.
3. **Fechar o checkpoint de S6** somente quando a reconciliação documental refletir a decisão humana, distinguindo aceite com exceções de conformidade V1. Manter cada critério não comprovado rastreável e não tratar como PASS.
4. **Realizar revisão de entrada da S7** após o checkpoint de S6, confirmando escopo, critérios de aceite e tratamento de itens parcialmente baixados segundo as regras V1 ativas. A revisão prepara a próxima unidade; não inicia implementação.
5. **Preparar S8 depois da dependência de S7**, preservando a sequência registrada no [plano de sprints](../../continuity/planning/SPRINTS.md) e no [roadmap](../../continuity/planning/ROADMAP.md). Início de S7 ou S8 requer autorização própria de implementação e seus gates.

## Campos finais

```text
ACTIVITY_ID = S6_FINAL_ACCEPTANCE_DECISION_2026-10-25
ACTIVITY_COMPLETION_PERCENT = 100% / aplica-se somente ao relatório decisório, não à Sprint S6
REQUIREMENTS_PROVEN = 0/18 plenamente provados contra os critérios completos V1
REQUIREMENTS_UNPROVEN = 18/18 com aceite integral ainda pendente (0 A, 12 B parciais, 6 C não comprovados; 8 critérios requereriam exceção D para a Opção B)
GATE_A_STATUS = PARTIAL
GATE_B_STATUS = BLOCKED_BY_REMOTE_EVIDENCE
RECOMMENDED_OPTION = OPÇÃO B / condicionada à aprovação do usuário
CONTRACT_CHANGE_REQUIRED = YES / dispensa ou exceção versionada explícita; nenhuma mudança executada agora
USER_ACCEPTANCE_REQUIRED = YES
S6_STATUS = OPEN
CODE_CHANGES = NO
TEST_EXECUTIONS = 0 nesta atividade
TELEGRAM_CALLS = 0 nesta atividade
NEXT_EXACT_ACTION = Usuário aprova ou rejeita explicitamente a exceção de escopo da Opção B e o aceite da S6
```
