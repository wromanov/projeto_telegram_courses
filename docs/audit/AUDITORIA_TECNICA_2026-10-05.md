# Auditoria técnica, arquitetural e de engenharia — projeto_telegram_courses

Data: 2026-10-05 — America/Sao_Paulo.

## Nota de materialização e alcance temporal

Este arquivo materializa o relatório entregue na conversa. A auditoria original foi executada em modo read-only. Depois de sua conclusão, o usuário autorizou explicitamente salvar o relatório em `docs/audit`.

Os fatos, classificações, percentuais e campos de alteração abaixo se referem à auditoria original. A criação deste arquivo é uma atividade documental posterior, autorizada, e não altera retrospectivamente a declaração de que o auditor não escreveu arquivos durante a auditoria.

Ao iniciar a materialização, foram observadas alterações preexistentes em `docs/governance/PROJECT_OPENING_GATE.md` e `docs/governance/PROJECT_STATE.md`, além de `.validation-temp/`, do binding e de `docs/governance/evidence/OPENING_RECOVERY_VALIDATION.json` não versionados. Esses arquivos não foram alterados por esta materialização. O relatório não reavalia o estado resultante dessa atividade concorrente ou posterior. Em particular, as conclusões sobre prontidão formal de S0 são as do momento auditado.

**A arquitetura geral é adequada ao produto e merece ser preservada.** O desenho ainda precisa fechar três contratos de maior risco: identidade de mídia substituída, recuperação entre arquivo e banco, e checkpoints de sincronização.

**Auditoria documental: 100%. Implementação: 0 de 11 sprints concluídas no momento auditado.** Nenhum finding crítico; **3 altos, 8 médios, 1 baixo e 2 informativos**.

## 1. Resumo executivo

```text
STATUS = PASS
AUDIT_STATUS = PASS_WITH_FINDINGS
ACTIVITY_COMPLETION_PERCENT = 100%

PROJECT_TECHNICAL_COHERENCE = MODERADA
IMPLEMENTATION_READINESS = READY_WITH_PRECONDITIONS
ARCHITECTURE = COERENTE_COM_AJUSTES
REQUIREMENTS = COERENTES_COM_LACUNAS
ENGINEERING_FOUNDATION = ADEQUADA_COM_AJUSTES
ROADMAP_AND_SPRINTS = COERENTES_COM_AJUSTES

IMPLEMENTATION_AUDIT = NOT_APPLICABLE_YET

PROJECT_ROOT = C:\Users\walac\desenvolvimento\projeto_telegram_courses
BRANCH = master
HEAD = a00f325df45f3adad13b3a99d00c3230f913b282
REMOTE = https://github.com/wromanov/projeto_telegram_courses.git
UPSTREAM = origin/master

WORKTREE_BEFORE = CLEAN
WORKTREE_AFTER = BLOCKED
FILES_MODIFIED = NENHUM PELO AUDITOR DURANTE A AUDITORIA ORIGINAL
GIT_MUTATION = NENHUMA PELO AUDITOR

FINDINGS_CRITICAL = 0
FINDINGS_HIGH = 3
FINDINGS_MEDIUM = 8
FINDINGS_LOW = 1
FINDINGS_INFO = 2

EXECUTION_MODE = DIRECT
SUBAGENTS = NENHUM
MODELO_UTILIZADO = Codex; variante exata não verificável nesta sessão
ESFORÇO = ALTO solicitado; configuração efetiva não verificável
```

O payload solicita GPT-5.6 Sol/Alto. Essa identificação não foi confirmada pelo runtime e não foi presumida no relatório.

**COMPLETION_BASIS:** foram lidos integralmente os 12 documentos primários existentes, inspecionados `.codex`, inventário, Git, evidências históricas e o binding surgido durante a auditoria. Foram avaliadas todas as áreas técnicas solicitadas, FR-01–FR-16, NFR-01–NFR-10 e S0–S10. Também foram verificados 84 destinos de links locais, todos existentes; fragmentos de seção não foram validados.

A conclusão é sobre **design e planejamento**. Não existiam `src`, testes de produto, `pyproject.toml`, configuração operacional ou implementação para validar comportamento real. Não foram instaladas dependências, executados testes de produto ou acessado Telegram.

**Ressalva do workspace:** o checkout estava limpo no início. Durante a auditoria surgiram, por atividade não executada por este auditor:

- `.validation-temp/`;
- `docs/governance/PROJECT_GOVERNANCE_BINDING.json`.

O HEAD, índice e documentos versionados permaneceram sem diferenças nas checagens finais da auditoria original. `WORKTREE_AFTER = BLOCKED` significa que não foi possível certificar um workspace globalmente inalterado; o estado observado terminou com arquivos não versionados surgidos durante a leitura.

**Prontidão de S0:** tecnicamente, o bootstrap não exige resolver antecipadamente todos os detalhes de S6–S10. Entretanto, os registros então auditados ainda apresentavam Opening Gate bloqueado e S0 sem autorização. O binding novo, isoladamente, não demonstrava fechamento desse gate.

## 2. Pontos fortes da solução

A base está bem escolhida para uma ferramenta local, individual e orientada a catálogo/download:

- **CLI primeiro:** permite validar o fluxo útil sem assumir custos de GUI, servidor ou serviço distribuído.
- **SQLite local:** combina bem com catálogo, identidade, checkpoints e histórico operacional.
- **Gateway próprio:** mantém tipos e APIs Telethon dentro do adapter.
- **Parsers sem infraestrutura:** protege a lógica de interpretação contra acoplamento com rede, SQL e arquivos.
- **Identidade por origem:** evita tratar nome de arquivo como identidade.
- **Três fontes de verdade:** reconhece corretamente que banco e filesystem podem divergir.
- **Finalização física antes de `DOWNLOADED`:** é a ordem correta.
- **Resume condicional:** o projeto exige demonstração real antes de declarar suporte.
- **Concorrência limitada:** dois workers são um ponto inicial defensável.
- **Testes locais separados de Telegram:** permite desenvolvimento sem credenciais e rede.
- **Primeiro valor verificável em S4:** integra autenticação, catálogo, transferência, organização e segunda execução.

Essas fronteiras estão explícitas na [arquitetura](../architecture/ARCHITECTURE.md), seção Boundaries, linhas 39–57, e na [fundação](../engineering/ENGINEERING_FOUNDATION.md), seção Test strategy, linhas 116–123 da baseline auditada.

Não há evidência de ciclo de dependências, God Object ou excesso de serviços **implementados**, porque ainda não existe código. O risco futuro está em concentrar scanner, parser, planner, retry e storage em um único coordenador. Os limites documentados já permitem evitar isso sem criar novas camadas.

## 3. Findings críticos

**Nenhum.**

Não foi identificado erro que obrigue abandonar a stack ou redesenhar a arquitetura inteira. As lacunas encontradas têm correções delimitadas e podem ser fechadas antes dos respectivos componentes.

## 4. Findings altos

### AUD-HIGH-01 — Identidade da mensagem não fecha identidade e revisão da mídia

**SEVERIDADE:** ALTO.  
**ÁREA:** domínio, deduplicação e resume.  
**CLASSIFICAÇÃO:** RISCO + DECISÃO_PENDENTE.  
**EVIDÊNCIA:** [REQUIREMENTS](../product/REQUIREMENTS.md), FR-03/FR-11, linhas 20 e 28; [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), schema e resume, linhas 26–35 e 74–85.

**PROBLEMA:** `(chat_id, message_id)` identifica a mensagem de origem. Não define sozinho qual mídia ou revisão foi baixada. A fundação prevê identidade Telegram da mídia, mas não estabelece como ela participa da unicidade, invalidação e deduplicação.

**CENÁRIO:** uma mensagem mantém seu ID, mas recebe outra mídia com o mesmo tamanho. A validação por identidade da mensagem, existência e tamanho pode aceitar o arquivo antigo. Uma parcial anterior também pode ser incompatível com a nova mídia.

**IMPACTO:** falso sucesso, mídia desatualizada e mistura de bytes em uma retomada incorreta.

**RECOMENDAÇÃO — CORREÇÃO_NECESSÁRIA:**

- preservar a identidade da mensagem;
- definir identidade da mídia e critério de revisão;
- separar mudança de título/path de mudança do conteúdo remoto;
- invalidar deduplicação e parcial quando a mídia esperada mudar;
- manter regras explícitas para mídia removida ou substituída.

Hash local ajuda a verificar o arquivo conhecido, mas não identifica automaticamente uma nova versão remota.

**FASE_AFETADA:** S2, S4, S6 e S7.  
**BLOQUEIA_IMPLEMENTAÇÃO:** **SIM**, antes do schema definitivo de mídia e da deduplicação; não bloqueia o bootstrap técnico de S0.  
**CONFIANÇA:** ALTA.

### AUD-HIGH-02 — Reconciliação é uma obrigação, mas ainda não possui decisões executáveis

**SEVERIDADE:** ALTO.  
**ÁREA:** storage, SQLite e recovery.  
**CLASSIFICAÇÃO:** RISCO.  
**EVIDÊNCIA:** [ARCHITECTURE](../architecture/ARCHITECTURE.md), fontes de verdade, linhas 72–80; [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), commit físico, linhas 62–72; [SPRINTS](../planning/SPRINTS.md), S4 e S6.

**PROBLEMA:** a ordem `.part → validação → rename → banco` é correta, mas deixa uma janela inevitável entre filesystem e SQLite. O contrato exige reconciliação sem definir o resultado de cada divergência.

**CENÁRIO:** o processo morre depois do rename e antes do commit SQLite. O arquivo final existe, enquanto o banco ainda indica transferência incompleta. A próxima execução precisa reconhecê-lo sem duplicar, sobrescrever ou aceitar um arquivo desconhecido.

Também permanece aberta a política de destino preexistente. A fundação exige ausência de sobrescrita silenciosa, mas menciona “replace/rename”. `os.replace` pode substituir um destino existente; portanto, exige uma decisão de propriedade anterior à operação. [Documentação Python](https://docs.python.org/3.14/library/os.html#os.replace).

**IMPACTO:** duplicação, perda de arquivo por substituição, tarefas permanentemente inconsistentes e falso `DOWNLOADED`.

**RECOMENDAÇÃO — CORREÇÃO_NECESSÁRIA:** definir a matriz de reconciliação da seção 10 e testar falhas nos limites do commit. Recovery básico deve existir em S4, mesmo que a continuação por bytes permaneça em S6.

**FASE_AFETADA:** S4–S7.  
**BLOQUEIA_IMPLEMENTAÇÃO:** **SIM**, antes da finalização e deduplicação de S4.  
**CONFIANÇA:** ALTA.

### AUD-HIGH-03 — Checkpoint é criado em S2, mas sua semântica fica aberta até S7

**SEVERIDADE:** ALTO.  
**ÁREA:** scanner, sincronização e persistência.  
**CLASSIFICAÇÃO:** RISCO + INCONSISTÊNCIA DE SEQUENCIAMENTO.  
**EVIDÊNCIA:** [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), checkpoint planejado, linha 34; [SPRINTS](../planning/SPRINTS.md), S2 e aceite de S7, linhas 47–62 e 145–160.

**PROBLEMA:** “último message ID/data” não esclarece se representa última mensagem vista, última página persistida ou intervalo integralmente processado. A definição do alcance de edições/remoções só é exigida antes de S7, embora influencie os dados persistidos em S2.

**CENÁRIO:** um scan recebe mensagens recentes primeiro, salva o maior ID e sofre interrupção antes de concluir o intervalo. Um rerun que busca somente IDs superiores pode deixar mensagens anteriores sem catalogação.

A iteração Telethon é descendente por padrão; a ordem pode ser invertida, com mudanças na semântica dos offsets. [Documentação Telethon](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.messages.MessageMethods.iter_messages).

**IMPACTO:** lacunas silenciosas, checkpoint aparentemente válido e catálogo incompleto. Buscar apenas mensagens novas também não detecta edições ou exclusões antigas.

**RECOMENDAÇÃO — CORREÇÃO_NECESSÁRIA:**

- definir cursor por canal e tipo de varredura;
- separar progresso de backfill de progresso incremental;
- avançar checkpoint somente junto aos dados efetivamente confirmados;
- definir limite superior da execução e recuperação de scan incompleto;
- declarar alcance de revisão de mensagens antigas;
- preservar contexto necessário ao parser incremental.

**FASE_AFETADA:** S2, S3 e S7.  
**BLOQUEIA_IMPLEMENTAÇÃO:** **SIM**, antes de persistir checkpoints definitivos em S2.  
**CONFIANÇA:** ALTA.

## 5. Findings médios

### AUD-MED-01 — Cardinalidades e associação do parser estão incompletas

**SEVERIDADE:** MÉDIO.  
**ÁREA:** domínio e parsers.  
**CLASSIFICAÇÃO:** DECISÃO_PENDENTE.  
**EVIDÊNCIA:** [ARCHITECTURE](../architecture/ARCHITECTURE.md), hierarquia, linhas 59–70; [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), amostra RASMOO, linhas 125–127.

**PROBLEMA:** Track e Module são explicitamente opcionais, mas faltam regras para Lesson sem mídia, mídia sem Lesson, documentos auxiliares, várias mensagens por aula e vários elementos lógicos em uma mensagem. O fallback genérico também não define como apresenta conteúdo sem Course identificável.

**IMPACTO:** associações arbitrárias e retrabalho no schema/parser.

**RECOMENDAÇÃO — MELHORIA_RECOMENDADA:** fechar cardinalidades, identidade dos nós e exemplos esperados de entrada/saída; manter conteúdo não associado disponível, sem inventar uma estrutura factual.

**FASE_AFETADA:** S2–S3.  
**BLOQUEIA_IMPLEMENTAÇÃO:** NÃO globalmente; fechar antes desses componentes.  
**CONFIANÇA:** ALTA.

### AUD-MED-02 — Schema conceitual ainda não especifica constraints e consultas críticas

**SEVERIDADE:** MÉDIO.  
**ÁREA:** SQLite.  
**CLASSIFICAÇÃO:** RISCO.  
**EVIDÊNCIA:** [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), schema baseline, linhas 26–47.

**PROBLEMA:** apenas a unicidade canal/mensagem está expressamente definida. Faltam PKs, FKs, políticas de exclusão, unicidade de mídia/tarefa/checkpoint, índices e agrupamento transacional de algumas operações.

**IMPACTO:** duplicação operacional, associações entre canais incompatíveis, fila com tarefas concorrentes sobre a mesma parcial e consultas degradadas.

**RECOMENDAÇÃO — MELHORIA_RECOMENDADA:** fechar o conjunto mínimo da seção 10 antes da primeira migration. A ausência de DDL nesta fase não é defeito por si só; a lacuna é o contrato de integridade ainda aberto.

**FASE_AFETADA:** S2–S5.  
**BLOQUEIA_IMPLEMENTAÇÃO:** NÃO para S0; exige fechamento em S2.  
**CONFIANÇA:** ALTA.

### AUD-MED-03 — Máquina de estados mistura transferência e mudança remota

**SEVERIDADE:** MÉDIO.  
**ÁREA:** downloads.  
**CLASSIFICAÇÃO:** AMBIGUIDADE + RISCO.  
**EVIDÊNCIA:** [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), estados registrados, linhas 49–60 e 85.

**PROBLEMA:** o fluxo principal possui transições, mas `SKIPPED`, `REMOVED`, `UPDATED` e `PARTIAL_INVALID` não possuem entradas, saídas e invariantes completas. `UPDATED`/`REMOVED` podem significar mudança remota, mudança de catálogo ou condição física local.

**IMPACTO:** decisões de retry/recovery dependentes de interpretações diferentes.

**RECOMENDAÇÃO — MELHORIA_RECOMENDADA:** separar a condição remota da transferência, usando o mínimo de campos necessário, e especificar transições persistidas. Não acrescentar todos os estados citados no payload: a nomenclatura canônica existente é `FAILED_RETRYABLE`.

**FASE_AFETADA:** S4–S7.  
**BLOQUEIA_IMPLEMENTAÇÃO:** NÃO globalmente.  
**CONFIANÇA:** ALTA.

### AUD-MED-04 — Ownership de retry, FloodWait, fila e shutdown não está fechado

**SEVERIDADE:** MÉDIO.  
**ÁREA:** gateway e concorrência.  
**CLASSIFICAÇÃO:** RISCO.  
**EVIDÊNCIA:** [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), retry e workers, linhas 103–114.

**PROBLEMA:** faltam limites entre retries internos da biblioteca e retries da aplicação, escopo de pausa por rate limit, backpressure e comportamento de cancelamento.

Telethon pode esperar automaticamente por FloodWait conforme seu threshold; isso precisa ser coordenado com a aplicação. [Documentação Telethon](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.telegrambaseclient.TelegramBaseClient).

**IMPACTO:** tentativas multiplicadas, esperas pouco explicáveis, workers persistindo estado durante encerramento e duas tarefas disputando um arquivo.

**RECOMENDAÇÃO — MELHORIA_RECOMENDADA:** pool global no MVP, fila limitada, uma tarefa por mídia/revisão, orçamento de tentativas persistente, espera cancelável e política de encerramento. Não manter transações SQLite abertas durante chamadas de rede.

**FASE_AFETADA:** S1, S4–S6 e S8.  
**BLOQUEIA_IMPLEMENTAÇÃO:** NÃO globalmente.  
**CONFIANÇA:** ALTA.

### AUD-MED-05 — Sanitização Windows ainda não constitui uma política completa de paths

**SEVERIDADE:** MÉDIO.  
**ÁREA:** filesystem e entradas externas.  
**CLASSIFICAÇÃO:** RISCO.  
**EVIDÊNCIA:** [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), política Windows, linhas 87–89.

**PROBLEMA:** faltam orçamento do caminho completo, colisões após truncamento, equivalência de maiúsculas/minúsculas e verificação de que o destino permanece dentro da raiz configurada.

**IMPACTO:** falha com hierarquias profundas, colisões e possibilidade de gravação fora do destino previsto se nomes externos forem usados indevidamente.

**RECOMENDAÇÃO — MELHORIA_RECOMENDADA:** builder determinístico com sufixo de identidade, limites de componentes/path e verificação de containment. Incluir nomes reservados com extensão, caracteres de controle e variantes reservadas documentadas pelo Windows. [Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file).

**FASE_AFETADA:** S4 e S10.  
**BLOQUEIA_IMPLEMENTAÇÃO:** NÃO para S0; fechar antes de escrever mídia.  
**CONFIANÇA:** ALTA.

### AUD-MED-06 — Proteção da sessão e fronteira de segredo em SQLite precisam de decisão explícita

**SEVERIDADE:** MÉDIO.  
**ÁREA:** segurança.  
**CLASSIFICAÇÃO:** DECISÃO_PENDENTE + RISCO.  
**EVIDÊNCIA:** [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), configuração/sessão, linhas 91–107.

**PROBLEMA:** o projeto corretamente exige proteção antes da sessão real, mas não define localização, ACLs, tratamento de backups e persistência segura de exceções.

Há uma distinção necessária no pedido: **o catálogo SQLite da aplicação deve permanecer sem segredos**. A sessão padrão Telethon também usa SQLite e contém material de autorização. Proibir segredos em qualquer SQLite exigiria escolher outra forma de armazenamento de sessão. [Documentação de sessões Telethon](https://docs.telethon.dev/en/stable/concepts/sessions.html).

**IMPACTO:** acesso indevido à conta ou vazamento em logs, backups e relatórios.

**RECOMENDAÇÃO — CORREÇÃO_NECESSÁRIA antes de S1:** escolher o armazenamento da sessão, protegê-lo com controles Windows verificáveis, excluir sessão e auxiliares do Git, e sanitizar `downloads.error_details` e tracebacks persistidos.

**FASE_AFETADA:** S0–S1 e S8–S10.  
**BLOQUEIA_IMPLEMENTAÇÃO:** NÃO globalmente; bloqueia criação de sessão real sem o controle exigido.  
**CONFIANÇA:** ALTA. Nenhuma exposição atual foi demonstrada.

### AUD-MED-07 — Suporte de mídia e limites de aceite permanecem pouco mensuráveis

**SEVERIDADE:** MÉDIO.  
**ÁREA:** requisitos e capacidade.  
**CLASSIFICAÇÃO:** HIPÓTESE + DECISÃO_PENDENTE.  
**EVIDÊNCIA:** [REQUIREMENTS](../product/REQUIREMENTS.md), FR-08 e NFRs, linhas 25 e 35–50.

**PROBLEMA:** “mídias suportadas” não enumera o conjunto inicial. Memória, volume de catálogo, tempo de operação, capacidade de fila e máximo de workers não têm critérios quantitativos fechados.

**IMPACTO:** aceites subjetivos e descoberta tardia de restrições relevantes.

**RECOMENDAÇÃO — MELHORIA_RECOMENDADA:** definir formatos iniciais e cenários de medição antes do aceite correspondente. Avaliar 10 mil/100 mil mensagens e milhares de tarefas; não declarar capacidade apenas pela escolha de SQLite.

A decisão de definir thresholds com evidência é boa. Falta identificar claramente o experimento e a condição de aprovação.

**FASE_AFETADA:** S2, S4–S5 e S8–S9.  
**BLOQUEIA_IMPLEMENTAÇÃO:** NÃO.  
**CONFIANÇA:** ALTA.

### AUD-MED-08 — Continuidade não representa o checkout atual e o binding novo ainda não fecha a evidência

**SEVERIDADE:** MÉDIO.  
**ÁREA:** continuidade e readiness.  
**CLASSIFICAÇÃO:** INCONSISTÊNCIA_DOCUMENTAL.  
**EVIDÊNCIA:** [PROJECT_STATE](../governance/PROJECT_STATE.md), linhas 11–22 da versão auditada; [PROJECT_OPENING_GATE](../governance/PROJECT_OPENING_GATE.md), seção Git: CASE A; [binding observado](../governance/PROJECT_GOVERNANCE_BINDING.json).

**PROBLEMA:** os registros auditados descreviam WORK, Git não inicializado e HOME ausente. O checkout auditado é HOME, possui `master`, HEAD e origin. O binding surgiu durante a auditoria, enquanto os documentos continuavam declarando ausência.

**VERIFICAÇÃO DO BINDING:** JSON parse PASS; sete pins de políticas coincidem com o relatório histórico. Schema e bytes das fontes externas **não foram revalidados**, pois os roots registrados não estavam disponíveis nesta sessão.

Os hashes históricos de 12 documentos diferem dos bytes do checkout auditado; a equivalência após conversão CRLF→LF em memória foi confirmada. Isso explica a diferença e não demonstra alteração de conteúdo nem valida integridade exata de bytes.

**IMPACTO:** retomada com fatos desatualizados e promoção indevida de um gate a PASS.

**RECOMENDAÇÃO — CORREÇÃO_NECESSÁRIA para prontidão formal:** reconciliar o estado com o checkout e validar o binding na atividade apropriada, preservando a evidência histórica.

**FASE_AFETADA:** preparação de S0.  
**BLOQUEIA_IMPLEMENTAÇÃO:** **SIM para início formal de S0**, enquanto suas condições documentadas não estiverem demonstradas.  
**CONFIANÇA:** ALTA sobre a divergência; validade das fontes externas no momento auditado permanece desconhecida.

Este finding retrata o momento da auditoria; alterações posteriores nos documentos de estado/gate precisam ser avaliadas separadamente.

## 6. Findings baixos

### AUD-LOW-01 — Interface operacional da CLI ainda não tem contrato suficiente

**SEVERIDADE:** BAIXO.  
**ÁREA:** CLI e configuração.  
**CLASSIFICAÇÃO:** MELHORIA_RECOMENDADA.  
**EVIDÊNCIA:** [ARCHITECTURE](../architecture/ARCHITECTURE.md), ADR-006, linhas 108–110; [SPRINTS](../planning/SPRINTS.md), S0 e fluxos futuros.

**PROBLEMA:** os fluxos estão planejados, mas não existe especificação completa dos comandos `auth`, `channels`, `scan`, `catalog`, `download`, `sync` e `status`, com escopo, argumentos, efeitos e códigos de saída.

**IMPACTO:** pequenas inconsistências e automação difícil.

**RECOMENDAÇÃO — MELHORIA_RECOMENDADA:** fechar progressivamente nomes, seleção por identidade, preview do lote, tamanhos conhecidos/desconhecidos, modo não interativo, precedência de configuração e saída para falha parcial.

**FASE_AFETADA:** S0–S5 e S7–S8.  
**BLOQUEIA_IMPLEMENTAÇÃO:** NÃO.  
**CONFIANÇA:** ALTA.

## 7. Hipóteses não verificadas

| Premissa | Classificação | Resultado |
|---|---|---|
| Telethon oferece autenticação, histórico, refetch e streaming | VERIFICADO documentalmente | Adequado ao boundary proposto; execução do projeto não demonstrada |
| Streaming admite offset de bytes | VERIFICADO documentalmente | Resume completo continua exigindo spike |
| `cryptg 0.6.0` possui wheel para CPython 3.14/Windows x64 | VERIFICADO | Existe o artefato correspondente; não prova integração da stack. [PyPI](https://pypi.org/project/cryptg/0.6.0/) |
| CPython, Telethon, cryptg, aiosqlite, Rich, pytest e Ruff funcionam juntos | HIPÓTESE | Ambiente exato ainda não foi montado |
| RASMOO corresponde às fixtures previstas | HIPÓTESE | Nenhuma amostra real de mensagens foi disponibilizada nesta auditoria |
| Dois workers produzem bom desempenho operacional | HIPÓTESE defensável | Medir antes de aumentar |
| Validação por tamanho detecta corrupção | INCORRETA como garantia geral | Corrupção pode preservar tamanho |
| Hash opcional oferece validação remota universal | INCORRETA como garantia geral | Falta referência confiável para comparação |
| Refetch resolve referência expirada sem mudar mídia | PRECISA_DE_SPIKE | Distinguir atualização da referência e substituição do conteúdo |
| IDs novos permitem detectar todas as edições/exclusões | INCORRETA | Exige estratégia adicional |
| Updates recuperam arbitrariamente qualquer período offline | NÃO GARANTIDO | Telegram documenta limites e tratamento de gaps antigos. [Telegram Updates](https://core.telegram.org/api/updates) |
| Rename seguro funciona em todos os destinos Windows configuráveis | PRECISA_DE_SPIKE | Não foi validado NTFS, locks, destino existente ou volumes distintos |
| Binding novo demonstra adoção válida | NÃO VERIFICADO | Existência e parse JSON são insuficientes |

O gateway deve distinguir sessão revogada, autenticação necessária, mensagem ausente, perda de acesso, mídia indisponível e referência expirada. Ausência por falta de acesso não deve ser registrada automaticamente como exclusão.

Referências de arquivo podem expirar e precisar de atualização; isso reforça o refetch previsto, sem justificar bypass de restrições. [Telegram File References](https://core.telegram.org/api/file_reference).

**AUD-INFO-01 — FATO:** não existe implementação de produto. Ausência de `.gitignore`, `pyproject.toml`, `src` e testes é compatível com o estado pré-S0; não foi tratada como vulnerabilidade atual.

**AUD-INFO-02 — EXTERNAL_GOVERNANCE_FINDING:** os registros históricos relatam divergências de integridade dos pacotes Opening/Continuity, referências antigas no manifest e metadata ambígua de PM-04. São evidências herdadas, não verificações novas das fontes externas. Não houve consulta ou alteração no repositório externo indisponível. [Registro histórico](../governance/PROJECT_OPENING_GATE.md), seção Blocker remanescente da versão auditada.

## 8. Spikes técnicos recomendados

**TECHNICAL_SPIKES_REQUIRED:**

| ID | Quando | Experimento e evidência exigida |
|---|---|---|
| SP-01 — Stack Windows | S0, antes de S1 | Ambiente com versões exatas; imports, execução async e SQLite; registrar versão SQLite e dependências |
| SP-02 — RASMOO representativo | Antes de fechar schema/parser de S2–S3 | Amostra controlada com índices, mídia, documentos, órfãos e edições; saídas esperadas de associação |
| SP-03 — Streaming e resume | Prova pequena antes de congelar adapter em S4; aceite completo em S6 | Interromper, reiniciar, refetch e continuar; offsets alinhados e não alinhados; comparar resultado ao download completo de referência |
| SP-04 — Commit Windows | S4 | Falhas antes/depois de rename, antes/depois do commit DB, destino existente, arquivo bloqueado e falha de espaço; rerun consistente |
| SP-05 — Sync e mídia revisada | Definições em S2; validação integrada em S7 | Novas mensagens, edição antiga, mídia substituída, exclusão/perda de acesso e scan interrompido; verificar alcance declarado |

Telethon documenta `iter_download` com offset e chunks; o adapter deve oferecer somente as capacidades efetivamente demonstradas pelo projeto. [Documentação Telethon](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.downloads.DownloadMethods.iter_download).

FloodWait deve ser testado predominantemente por simulação. Não é necessário provocar bloqueios reais para demonstrar classificação, espera e cancelamento.

**RESUME = REQUER_SPIKE.** O desenho é defensável; não está pronto para ser declarado funcional.

## 9. Overengineering

| Elemento | OVERENGINEERING_FINDING | Parecer |
|---|---|---|
| `TelegramGateway` com um adapter inicial | NÃO | Boundary real de fornecedor e testabilidade |
| `BaseParser`, RasmooParser e GenericParser | NÃO | Dois comportamentos previstos e necessidade concreta |
| SQLite e oito tabelas | NÃO demonstrado | Cada tabela tem responsabilidade plausível; detalhar antes de expandir |
| SQL migrations numeradas | NÃO | Custo pequeno e valor real para bases persistentes |
| Estados `UPDATED`/`REMOVED` na transferência | SIM, potencial | Dimensões misturadas podem multiplicar transições sem ganho |
| Workers por chat ou por tipo | NÃO existente | Adicionar agora seria prematuro; pool global basta |
| TDLib como implementação paralela | NÃO existente | Preservar como alternativa, sem construir antecipadamente |
| Sistema de plugins com descoberta dinâmica | NÃO necessário | Seleção simples de parsers atende o MVP |
| ORM, broker, serviços distribuídos | NÃO existente | Correta exclusão explícita |
| Hash de todos os arquivos em todo rerun | NÃO existente | Custo deve ser justificado por política de integridade |

FR-05 contém uma escolha arquitetural — parsers plugáveis — além da capacidade funcional. Pode ser esclarecido sem reorganizar toda a documentação: o requisito deve demonstrar suporte aos formatos previstos; a arquitetura define o mecanismo.

Não há benefício demonstrado em trocar Telethon, SQLite, Rich ou migrations simples.

## 10. Underengineering

O principal problema é a diferença entre **invariantes declaradas** e **regras de decisão suficientes para implementação**.

### Domínio e cardinalidades

| Conceito | Contrato mínimo recomendado |
|---|---|
| Channel | Identidade Telegram estável, separada de título/username; representar mudança ou migração explicitamente |
| Track | Opcional; não fabricar obrigatoriedade para canais diferentes |
| Course | Identidade própria do catálogo; política explícita quando o canal não fornece curso identificável |
| Module | Opcional; organização não deve exigir módulo fictício sem indicação |
| Lesson | Elemento lógico independente; pode estar indexado antes de possuir mídia |
| MediaItem | Elemento transferível independente; associação lógica pode estar pendente |
| DownloadTask | Estado operacional de transferência de uma mídia/revisão |
| SyncCheckpoint | Progresso confirmado, com escopo e semântica definidos |

**Lesson e MediaItem devem permanecer distintos:** renomear/reorganizar uma aula não implica alterar os bytes; substituir os bytes não necessariamente altera a identidade lógica da aula.

Uma mensagem pode conter vários elementos de índice. Uma aula pode ter várias mensagens/mídias. Documentos auxiliares precisam de associação explícita ou condição de conteúdo não associado. Essas possibilidades devem ser comprovadas pela amostra, sem introduzir uma relação muitos-para-muitos universal por antecipação.

### Identidade e deduplicação

| Evento | Comportamento recomendado |
|---|---|
| Rerun sem mudança | Reutilizar arquivo verificado para a mídia/revisão esperada |
| Rename de título/arquivo | Preservar identidade; aplicar política explícita de path |
| Edição apenas textual | Atualizar catálogo; evitar download desnecessário |
| Mídia substituída | Invalidar conclusão da revisão anterior para a mídia atual |
| Mídia removida | Registrar indisponibilidade; não apagar arquivo local implicitamente |
| Arquivo local removido | Deixar de considerá-lo fisicamente disponível; permitir redownload controlado |
| Path reorganizado | Atualizar localização após operação física bem-sucedida |
| Channel migration | Não presumir que IDs anteriores continuam no mesmo namespace |
| Conteúdo repetido em mensagens distintas | São origens distintas; dedup por conteúdo é uma otimização adicional |

**FILENAME != IDENTITY.** Essa decisão deve ser preservada.

Hash é útil para verificar arquivo previamente conhecido, comparar um download retomado com referência controlada e investigar corrupção. Dedup global por conteúdo não é requisito inicial demonstrado.

### Reconciliação obrigatória

| Divergência | Resultado mínimo seguro |
|---|---|
| DB `DOWNLOADED`, final ausente | Registrar divergência; não deduplicar como disponível |
| Final existe, tarefa não concluída | Validar vínculo, revisão e tamanho; concluir se houver evidência suficiente |
| Final existe, DB não conhece | Tratar como órfão; não adotar apenas por nome/tamanho |
| `.part` existe, DB `NEW` | Validar origem e revisão; recuperar ou reiniciar de forma controlada |
| Final tem tamanho incorreto | Invalidar conclusão; evitar consumo como arquivo válido |
| Parcial tem tamanho/progresso divergente | Reconciliação explícita; não fazer append automático |
| Mensagem ausente ou inacessível | Classificar causa; preservar dados locais por padrão |
| Mensagem/mídia alterada | Separar atualização de catálogo e invalidação de mídia |
| DB restaurado sem arquivos | Reconciliar disponibilidade física |
| Arquivos restaurados sem DB | Inventário/importação controlada; não inferir identidade pelo filename |

A solução não precisa de transação distribuída. Precisa de finalização idempotente e recovery dessas janelas.

### SQLite

O motor é adequado como escolha. A capacidade específica do projeto ainda não foi demonstrada.

Antes da primeira migration, definir:

- PKs e identidade canônica de canal;
- `UNIQUE(channel_id, telegram_message_id)`;
- unicidade da mídia conforme sua política de revisão;
- unicidade da tarefa ativa para impedir disputa pela mesma parcial;
- FKs e política de remoção de mensagens/mídias/catalog nodes;
- unicidade de checkpoint por seu escopo;
- checks de estado, bytes e attempts não negativos;
- consistência entre canal da mensagem e associação de catálogo.

Índices iniciais devem atender consultas reais:

| Consulta | Índice candidato |
|---|---|
| Buscar mensagem de origem | Canal + message ID, já coberto pela unicidade |
| Listar filhos do catálogo | Canal/parent/kind/ordem conforme consulta |
| Recuperar mídias de mensagem ou nó | FKs correspondentes |
| Buscar tarefas prontas | Estado + momento de próxima tentativa, se persistido |
| Obter checkpoint | Chave única do escopo |
| Consultar scans recentes | Canal + timestamp |

Aplicar `foreign_keys` e `busy_timeout` nas conexões pertinentes; manter transações curtas. Repository-only writes é uma boa decisão, mas não serializa writers por si só.

WAL permite concorrência entre leitura e escrita, mantendo um writer por vez, e não deve ser presumido adequado para filesystem de rede. Validar o local configurado do banco. [SQLite WAL](https://www.sqlite.org/wal.html).

Não são necessários particionamento, Redis ou migração de banco para justificar 100 mil mensagens. São necessários índices, paginação, batches e medição.

### Máquina de estados e commit físico

O conjunto canônico contém **11 estados**, incluindo `FAILED_RETRYABLE`.

| Regra | Contrato necessário |
|---|---|
| `NEW → QUEUED` | Plano válido e tarefa sem concorrente equivalente |
| `QUEUED → DOWNLOADING` | Ownership adquirido antes de escrever |
| `DOWNLOADING → DOWNLOADED` | Somente depois de validação e finalização física |
| `DOWNLOADING → PARTIAL` | Parcial recuperável e progresso reconciliável |
| `FAILED_RETRYABLE → QUEUED` | Orçamento de tentativas e espera satisfeitos |
| `PARTIAL → QUEUED` | Mesma mídia/revisão e decisão de resume/restart |
| `PARTIAL_INVALID` | Saída explícita por descarte/reinício controlado |
| `SKIPPED` | Motivo registrado; não equivaler silenciosamente a sucesso |
| `UPDATED`/`REMOVED` | Semântica remota/local separada ou precisamente delimitada |

Persistir ownership/início antes de escrever e conclusão depois do arquivo finalizado. Persistir cada chunk no SQLite seria custo desnecessário; checkpoints de bytes podem ser periódicos, desde que recovery use evidência física e revisão.

Para Windows, manter a parcial no volume do destino, fechar handles antes da finalização e tratar locks/permissões/destino existente. Definir se a garantia cobre apenas morte do processo ou também perda de energia; rename e durabilidade não são a mesma propriedade.

### Retry, concorrência e resume

A taxonomia atual pode ser preservada. Precisa de uma tabela de ações, não necessariamente de novas classes para cada categoria:

- **TRANSIENT:** retry limitado;
- **RATE_LIMIT:** espera explícita e cancelável;
- **AUTH/CONFIGURATION:** intervenção, sem retry automático;
- **NOT_FOUND/MEDIA_UNAVAILABLE:** refetch/classificação, sem loop cego;
- **DISK/FILESYSTEM:** causa específica; disco cheio e path inválido não são transitórios genéricos;
- **DATABASE:** distinguir contenção temporária de corrupção/falha persistente;
- **VALIDATION/PARSER/FATAL:** preservar evidência e encerrar o escopo afetado.

No resume, a sequência prevista está correta, mas append só deve ocorrer após validar **origem, revisão, offset e capacidade do adapter**. Tamanho remoto desconhecido e parcial suspeita exigem política explícita. Um hash recém-calculado sem referência não prova que a parcial estava íntegra.

## 11. Risk Register priorizado

“Antes da implementação” abaixo significa **antes do componente afetado**, não que todos os itens precisam bloquear S0.

| ID | Descrição / finding | Probabilidade | Impacto | Fase | Mitigação | Resolver antes |
|---|---|---|---|---|---|---|
| R-01 | Mídia substituída aceita como já baixada — HIGH-01 | MÉDIA | ALTO | S2/S4/S6/S7 | Identidade/revisão e invalidação | SIM |
| R-02 | Crash entre rename e DB — HIGH-02 | MÉDIA | ALTO | S4–S6 | Recovery idempotente e testes de falha | SIM |
| R-03 | Checkpoint avança além de dados persistidos — HIGH-03 | MÉDIA | ALTO | S2/S7 | Cursor confirmado e commit conjunto | SIM |
| R-04 | Parser associa aula/documento incorretamente — MED-01 | MÉDIA | ALTO | S2–S3 | Dataset real e regras determinísticas | SIM |
| R-05 | Tarefas/associações duplicadas — MED-02 | MÉDIA | MÉDIO | S2–S5 | Constraints e transações | SIM |
| R-06 | Retry/cancelamento deixam operação inconsistente — MED-03/04 | MÉDIA | MÉDIO | S4–S8 | Ownership, orçamento e shutdown | SIM |
| R-07 | Paths inválidos ou colidentes — MED-05 | MÉDIA | MÉDIO | S4/S10 | Builder e testes Windows | SIM |
| R-08 | Sessão exposta — MED-06 | MÉDIA | ALTO | S1 | ACL, exclusões e redaction verificadas | SIM |
| R-09 | Stack/streaming não atende ambiente real — MED-07 | BAIXA | MÉDIO | S0/S4/S6 | Spikes e medições | SIM |
| R-10 | Edições antigas ficam fora do sync — HIGH-03 | ALTA se usar somente IDs novos | MÉDIO | S7 | Alcance explícito e rescan/refetch | SIM |
| R-11 | Estado de continuidade promove readiness incorreto — MED-08 | ALTA | MÉDIO | Pré-S0 | Reconciliação e validação do binding | SIM |
| R-12 | Logs/histórico crescem sem política | MÉDIA | BAIXO | S8 | Rotação e retenção simples | NÃO |

Nenhum risco foi classificado como perda inevitável ou corrupção já existente.

## 12. Decisões pré-implementação

**PRE_IMPLEMENTATION_DECISIONS / DECISÕES_PRÉ_IMPLEMENTAÇÃO**

| Prioridade | Decisão | Prazo |
|---|---|---|
| BLOQUEANTE para S0 formal | Reconciliar checkout, binding, fontes e resultado do Opening Gate; resolver autorização na atividade pertinente | Antes de iniciar S0 |
| BLOQUEANTE para dados | Identidade da mídia/revisão e semântica do checkpoint | Antes do schema em S2 |
| BLOQUEANTE para transferência | Recuperação e ownership do arquivo final/parcial | Antes de S4 |
| BLOQUEANTE para sessão real | Storage e proteção Windows verificável | Antes de S1 |
| RECOMENDADA | Cardinalidades, órfãos, documentos e fallback genérico | Antes de S2–S3 |
| RECOMENDADA | Constraints, índices e transações mínimas | Antes da migration S2 |
| RECOMENDADA | Retry/FloodWait, cancelamento e fila bounded | Antes de sua primeira operação |
| RECOMENDADA | Tipos de mídia iniciais e critérios de memória/volume | Antes do aceite correspondente |
| PODE_ESPERAR | Maximum workers calibrado acima do padrão | Após benchmark |
| PODE_ESPERAR | Dedup global por hash | Após demonstrar necessidade |
| PODE_ESPERAR | GUI, TDLib, novos parsers, ORM ou arquitetura distribuída | Fora do MVP |

Os findings altos bloqueiam **seus componentes**. Não justificam impedir a criação de um ambiente técnico de desenvolvimento depois de satisfeitas as condições formais de S0.

## 13. Melhorias recomendadas e rastreabilidade

**TOP_5_IMPROVEMENTS, por retorno técnico:**

1. **Fechar identidade/revisão de mídia:** protege dedup, resume e sync com a mesma decisão.
2. **Definir e testar reconciliação filesystem/SQLite:** resolve as principais janelas de falha.
3. **Antecipar contrato do checkpoint para S2:** evita migração e lacunas silenciosas em S7.
4. **Obter uma amostra RASMOO representativa antes do schema/parser:** fecha cardinalidades com evidência.
5. **Fechar constraints e matriz mínima de falhas/estados antes de S4:** protege idempotência e concorrência.

### FR-01 a FR-16

Todos possuem implementação planejada e alinhamento arquitetural básico. A tabela distingue existência de aceite de suficiência desse aceite.

| FR | Clareza, completude e ambiguidade | Testabilidade / aceite a fechar | Dependência e sprint |
|---|---|---|---|
| 01 — Auth | Claro; incompleto para sessão revogada, 2FA e recuperação | Login, reutilização, falhas e proteção local | S0 → S1 |
| 02 — Discovery | Claro; tipos de chats e migração não delimitados | IDs estáveis, acessível/inacessível e seleção | FR-01 → S1 |
| 03 — Catalog | Claro; revisão e associação incompletas | Rerun, edição e scan interrompido | FR-02/09 → S2 |
| 04 — Hierarchy | Track/Module claros; demais cardinalidades abertas | Saídas esperadas para ausência de níveis e mídia | FR-03 → S3 |
| 05 — Parsers | Objetivo claro; mecanismo também é arquitetural | Fallback e seleção determinística | FR-03/04 → S3 |
| 06 — Selection | Claro; seleção vazia/inválida e lote parcial abertos | Apenas itens escolhidos, resultado parcial e rerun | Catálogo → S4/S5 |
| 07 — Organization | Claro; paths longos, rename e containment incompletos | Colisões, truncamento e destino existente | FR-04/06 → S4 |
| 08 — Media | Ambíguo quanto ao conjunto suportado | Enumerar formatos e comportamento para não suportados | Gateway → S4/S6 |
| 09 — Persistence | Claro; constraints/transações incompletas | Reinício, unicidade, rollback e relações | S2; transversal |
| 10 — Sync | Parcial; alcance de edições/exclusões aberto | Checkpoint seguro e limite de detecção declarado | S2/S3 → S7 |
| 11 — Dedup | Claro para rerun simples; revisão aberta | Mesmo ID com mídia substituída e arquivo ausente | FR-03/08/09 → S4/S7 |
| 12 — Recovery | Claro como objetivo; decisões incompletas | Falhas nos limites do commit, cancelamento e resume | S4/S6/S8 |
| 13 — Pre-scan | Claro; relação scan/plano/dry-run parcial | Quantidades e tamanhos conhecidos/desconhecidos | S3/S5 |
| 14 — Progress | Claro; pouco específico | Estados de espera, falha parcial e término físico | Primeira operação; S8 consolida |
| 15 — Logging | Claro; correlação/retention/redaction parcial | Diagnóstico sem segredos em logs, DB e exceções | Transversal; S8 |
| 16 — Config | Claro; validação por opção e paths relativos parcial | Precedência, tipos, workers/retries inválidos | S0 em diante; S8 |

Não foi encontrado FR sem sprint planejada. FR-03 e FR-09 são complementares; catálogo e persistência não são duplicação indevida. FR-12 e FR-11 precisam compartilhar contratos sem perder responsabilidades distintas.

### NFR-01 a NFR-10

| NFR | Clareza / completude | Testabilidade e evidência necessária | Primeira unidade |
|---|---|---|---|
| 01 — Windows | Claro; ambiente suportado precisa ser delimitado | Smoke no Windows e pacote após integração | S0 |
| 02 — Memória | Objetivo claro; threshold aberto | Medição por cenário, sem arquivo inteiro em memória | S4 |
| 03 — Concorrência | Padrão claro; fila/limites operacionais abertos | Workers ativos, backpressure e cancelamento | S4/S5 |
| 04 — FloodWait | Claro; ownership incompleto | Espera e retry coordenados e canceláveis | S1 |
| 05 — Credenciais | Claro | Exclusões e inspeção de superfícies persistidas | S0/S1 |
| 06 — Sessão | Claro; mecanismo pendente | Proteção Windows antes de login real | S1 |
| 07 — Sanitização | Parcialmente completo | Path completo, colisões, root e nomes especiais | S4 |
| 08 — Manutenção | Limites claros; métricas pouco objetivas | Imports/SQL/tipos respeitam boundaries | S0 em diante |
| 09 — Unit offline | Claro e verificável | Suíte normal sem rede/login/segredos | S0 |
| 10 — Integração separada | Claro e verificável | Execução explícita com amostra e acesso legítimo | S1 |

### Outras relações de rastreabilidade

- **REQUISITO_SEM_IMPLEMENTAÇÃO_PLANEJADA:** nenhum identificado.
- **ARQUITETURA_SEM_REQUISITO:** tabelas, gateway e migrations são suporte justificável aos FR/NFR; não são expansão funcional.
- **SPRINT_SEM_ENTREGA_VERIFICÁVEL:** nenhuma, embora alguns critérios ainda dependam de decisões abertas.
- **DECISÃO_SEM_TESTE suficiente:** identidade/revisão, reconciliação e transições auxiliares.
- **RISCO_SEM_MITIGAÇÃO executável:** os riscos altos têm intenção de mitigação, mas faltam regras e cenários fechados.
- **CONTRADIÇÃO_DOCUMENTAL:** ambiente/Git/binding versus estado auditado; semântica de checkpoint definida depois de sua introdução.

### Logging, configuração e CLI

Um contexto pequeno é suficiente: `run_id`, operação, identidade de chat/mensagem e tarefa de download. Não é necessário acrescentar tracing distribuído.

Persistir causa sanitizada, attempts e próxima tentativa quando aplicável. Evitar logs por chunk e stack trace repetido a cada retry.

A precedência documentada é defensável. Segredos devem continuar por ambiente/provedor próprio; `.env` não tem suporte demonstrado e exigiria tratamento explícito se adotado. Validar paths, tipos e limites antes de iniciar efeitos operacionais.

Para lote, o preview deve mostrar itens, bytes restantes conhecidos, tamanhos desconhecidos e capacidade do volume de destino. A checagem inicial não elimina a necessidade de tratar disco cheio durante a transferência.

## 14. O que não deve ser alterado

Recomendo preservar:

- CLI com Rich como interface inicial;
- conta própria e acesso legítimo ao Telegram;
- Telethon isolado pelo gateway;
- modelos próprios acima do adapter;
- parsers independentes de rede, banco e filesystem;
- Track e Module opcionais;
- distinção entre Lesson e MediaItem;
- SQLite local com SQL explícito e migrations simples;
- responsabilidade dos repositórios sobre SQL;
- identidade de origem separada do filename;
- `.part`, validação e finalização antes de `DOWNLOADED`;
- resume controlado pela aplicação e condicionado a evidência;
- pool global limitado, inicialmente com dois workers;
- testes offline normais e integração Telegram separada;
- GUI, TDLib e arquitetura distribuída adiadas.

Os ajustes recomendados tornam essas decisões executáveis; não exigem substituí-las.

## 15. Impacto no roadmap e nas sprints

A ordem geral é boa. **S8 não é o primeiro uso dos controles básicos:** o plano expressamente os exige desde a unidade pertinente. [SPRINTS](../planning/SPRINTS.md), seção Controles transversais e rastreabilidade NFR, linhas 219–238.

Também seria incorreto afirmar que toda integração real ocorre apenas em S9: S1, S2 e S4 já prevêem verificações Telegram.

| Sprint | Parecer e ajuste |
|---|---|
| S0 | Preservar bootstrap; reconciliar facts/gate e validar stack exata |
| S1 | Preservar auth/discovery; fechar sessão, falhas e rate limit básico |
| S2 | Antecipar identidade/revisão, checkpoint, constraints e paginação |
| S3 | Validar dataset e associações determinísticas, inclusive fallback |
| S4 | Preservar primeiro valor; incluir recovery básico entre arquivo e DB |
| S5 | Pool global, fila bounded, exclusão mútua por tarefa e espaço de lote |
| S6 | Manter aceite de resume real; spike preliminar deve ocorrer antes |
| S7 | Implementar alcance de sync já decidido; não descobri-lo ao iniciar |
| S8 | Consolidar hardening e medições; não receber controles essenciais inéditos |
| S9 | Aceitar produto integrado com amostra ampliada e limitações explícitas |
| S10 | Manter distribuição depois da validação; testar comportamento empacotado |

Não há dados de duração, capacidade ou esforço para avaliar tamanho de sprint com confiança. S6 e S8 concentram riscos diferentes; seus experimentos precisam ser delimitados antes do início.

**Primeiro vertical slice:** os nove critérios provam valor end-to-end, mas privilegiam o caminho feliz.

Recomendo **um único critério adicional de alto retorno**:

> **RECOVERY_AFTER_FINALIZATION = PASS:** interromper entre finalização física e persistência de conclusão; reiniciar; obter um único arquivo correto e estado consistente.

Não anteciparia toda a aceitação de byte resume para S4. A ausência de duplicata deve ser comprovada também pela ausência de nova transferência desnecessária, não apenas pela contagem de arquivos.

## 16. Conclusão — parecer obrigatório

| Pergunta | Parecer |
|---|---|
| 1. A arquitetura geral é adequada? | **Sim**, com ajustes de contratos |
| 2. Existe erro estrutural a corrigir antes de implementar? | Não exige redesenho; identidade/revisão, checkpoints e recovery exigem fechamento antes dos componentes |
| 3. Há overengineering? | Localizado/potencial nos estados misturados; não na stack ou boundaries |
| 4. Há underengineering? | Sim: regras executáveis de integridade, recuperação e operação |
| 5. O domínio está adequado? | Base adequada; cardinalidades e conteúdo não associado estão incompletos |
| 6. SQLite está preparado para o volume? | Motor adequado; schema e capacidade do projeto ainda não demonstrados |
| 7. Deduplicação é robusta? | Para rerun simples, defensável; incompleta para revisão/substituição |
| 8. `.part`/resume é defensável? | Sim; **REQUER_SPIKE** e políticas de reconciliação |
| 9. Sync incremental está definido? | **Não suficientemente** |
| 10. Isolamento Telethon está adequado? | Sim documentalmente; verificar no código futuro |
| 11. Parsers são genéricos o suficiente? | Boundary adequado; comportamento do fallback e associação pendente |
| 12. Concorrência é apropriada? | Sim como início; faltam fila, ownership, rate limit e shutdown |
| 13. Recovery está suficiente? | Invariantes corretas; decisões e cenários insuficientes |
| 14. Segurança está adequada? | Direção adequada; proteção concreta da sessão ainda pendente |
| 15. Testes demonstram comportamento crítico? | Estratégia permite; ainda não existem testes e faltam cenários detalhados |
| 16. Primeiro slice valida maiores riscos? | Valida integração e valor; acrescentar recovery após finalização |
| 17. Roadmap está na ordem correta? | Globalmente sim; antecipar definições e spikes específicos |
| 18. Há decisões a antecipar? | Sim: identidade/revisão, cursor, cardinalidades e commit/recovery |
| 19. Está pronto para começar S0? | **Formalmente ainda não demonstrado no momento auditado**; bootstrap técnico é viável após fechar suas condições |
| 20. Quais as cinco melhorias de maior retorno? | Identidade/revisão; reconciliação; checkpoint; amostra RASMOO; constraints/estados/falhas |

**BLOCKING_FINDINGS:**

- `AUD-HIGH-01`: antes do modelo persistente de mídia/dedup;
- `AUD-HIGH-02`: antes do commit físico e rerun de S4;
- `AUD-HIGH-03`: antes do checkpoint definitivo em S2;
- `AUD-MED-06`: condição obrigatória antes da sessão real;
- `AUD-MED-08`: prontidão formal de S0 ainda não demonstrada no momento auditado.

A aprovação anterior foi considerada como decisão documentada, sem substituir análise técnica. A solução tem uma base boa; sua principal necessidade é fechar comportamentos de falha e mudança com exemplos verificáveis.

A conclusão da auditoria **não concede PASS ao Opening Gate, aceite de sprint ou autorização de implementação**.

## 17. Próxima atividade recomendada

**NEXT_REQUIRED_ACTIVITY = REVISÃO DE PRONTIDÃO PRÉ-S0 DO CHECKOUT ATUAL.**

Essa atividade deve reconciliar os fatos de HOME/Git e o binding emergente com as authorities disponíveis, incorporando as decisões antecipadas desta auditoria ao plano antes de liberar os componentes afetados. O resultado esperado é uma baseline concreta e verificável para iniciar S0.

Caso a reconciliação de governança tenha sido concluída por atividade posterior, sua evidência deve ser usada para atualizar a decisão de prontidão sem interpretar este relatório histórico como avaliação do estado novo. Os findings técnicos continuam sujeitos à resolução nos componentes indicados.

**Auditoria concluída: 100%. Produto implementado no momento auditado: 0 de 11 sprints. Nenhuma alteração foi executada por este auditor durante a auditoria original.**
