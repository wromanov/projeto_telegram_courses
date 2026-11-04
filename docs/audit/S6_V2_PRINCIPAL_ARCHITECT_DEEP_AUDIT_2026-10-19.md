# Auditoria de Arquitetura Profunda — S6 V2

**Data:** 19 de outubro de 2026  
**Projeto:** projeto_telegram_courses  
**Atividade:** S6 V2 — Principal Architect Deep Audit  
**Resultado da auditoria:** concluída  
**Status de implementação:** não iniciada por este parecer  
**Principal Architect:** CLOSED  
**Reentrada do Principal Architect:** PROHIBITED

## 1. Síntese executiva

As regressões observadas na validação do S6 V2 concentram-se nas fronteiras entre harness, processo filho, supervisor e coleta de evidências. Duas das três falhas registradas são expectativas incorretas nos testes: o harness espera PASS para pós-verificação de referência no perfil OPERATIONAL_ONLY, embora NOT_APPLICABLE seja o resultado previsto pelo contrato. A falha restante é uma execução trusted E2E interrompida no processo filho antes de produzir identidade remota; o supervisor relata CHILD_REPORT_MISSING_OR_INVALID e encobre a causa primária.

A hipótese de maior confiança para essa terceira falha é exceder o limite de caminho durante o planejamento. A reconstrução estática do caminho alcança 263 caracteres, e o arquivo temporário .part chega a 268, contra o limite de 240 aplicado por destination_paths. A exceção histórica exata não foi preservada em evidência acessível, portanto PATH_TOO_LONG é uma inferência forte, não uma causa confirmada por traceback.

Recomendação: estabilizar de forma delimitada o harness e a infraestrutura de QA, preservando as salvaguardas existentes e o comportamento de produção. Não há evidência que justifique reescrever o S6 ou alterar downloads.py, gateway, schema, V1 ou a política de integridade.

## 2. Escopo, método e limites

O parecer examina as evidências disponíveis para as falhas de S6 V2, os contratos entre componentes de execução e a capacidade de rodar ciclos autônomos de diagnóstico, correção e validação. A análise correlaciona receipts, resultados de testes e registros de execução existentes com o comportamento esperado pelo harness e pelo supervisor.

A auditoria é analítica e read-only. Não foi feita alteração de código nem executada uma nova rodada de testes durante a auditoria. Os números abaixo descrevem artefatos de execução já existentes; não são resultados de validação produzidos por este documento.

A falta de traceback preservado limita a identificação retrospectiva da exceção do trusted E2E. Onde a evidência termina, o parecer separa fato de inferência e não converte correlação temporal em causa provada.

## 3. Diagnóstico factual

### 3.1 Baseline observado

| Item | Evidência disponível |
|---|---|
| Branch | work/s0-bootstrap |
| HEAD | 98d9d6b9ce152b8d2764a4d160fcbdf4722fb257 |
| Estado de trabalho | WIP com alterações locais; preservar o estado existente |
| Receipt anterior | .s6r/2656a231b02f/t/receipt.json — Harness: 163 passed |
| Receipt atual examinado | .s6r/598cd797e185/t/receipt.json — 176 testes, 173 passed, 3 failed |
| Run ID atual | bafaa544d4ef4840bfc52c6a122145e9 |
| Estado funcional | V1 ativo; V2 desligado; aceite formal de S6 pendente; S7/S8 adiados |

Os dados de uma execução anterior não devem ser confundidos com a execução atual. Problemas de ambiente Proactor observados em outro contexto e o KeyError: attempts não explicam as três falhas registradas neste receipt.

### 3.2 Duas falhas de expectativa

Em tests/manual_proofs/test_s6_v2_proof_harness.py, por volta da linha 3194, os testes esperam PASS da pós-verificação de referência no perfil OPERATIONAL_ONLY. O contrato aplicável produz NOT_APPLICABLE. Os caminhos alinhado e desalinhado já passam pelas verificações E2E precedentes; a divergência está na expectativa final do teste, não numa regressão demonstrada do comportamento de referência.

Evidência: [test_s6_v2_proof_harness.py](../../tests/manual_proofs/test_s6_v2_proof_harness.py#L3194).

### 3.3 Falha do trusted E2E

No trusted E2E, o processo filho termina com PROCESS_FAILED e exit code 5 antes de produzir child_result. O supervisor exige que child_result seja um dicionário mesmo para uma falha anterior à emissão do resultado. Como consequência, a observação primária é substituída por CHILD_REPORT_MISSING_OR_INVALID.

A sequência observada não prova a exceção interna: gateway_restored aparece antes da falha e queue.begin não chega a ocorrer, mas a causa não pode ser deduzida apenas dessa proximidade. O artefato final não preserva traceback suficiente para confirmar o erro ocorrido entre esses marcos.

A melhor hipótese disponível é PATH_TOO_LONG:

- A reconstrução estática da rota usada pelo fixture produz caminho final de 263 caracteres.
- O caminho temporário com sufixo .part chega a 268 caracteres.
- A validação em destination_paths impõe limite de 240 caracteres.
- O planner executa essa validação antes de queue.run.
- O filho encerra antes de publicar a identidade remota, compatível com falha no planejamento.
- O código genérico OTHER para exceções de domínio pode ter contribuído para que a causa não apareça nos diagnósticos.

A hipótese é classificada como **inferência de alta confiança**, não confirmação histórica. Deve ser reproduzida com evidência nova antes de qualquer correção que dependa dela.

### 3.4 Fixture de probe descartado

O probe trusted está localizado sob proof_root, mas a configuração de ambiente aponta S6_V2_TEST_ALLOWED_ROOT para um evidence_root aninhado. A guarda do probe descarta silenciosamente um caminho fora da raiz permitida. Isso reduz a observabilidade e pode tornar o fixture incapaz de exercitar a condição que se pretendia inspecionar.

### 3.5 Análise comparativa das três falhas

| Falha | Fato observado | Diagnóstico | Confiança |
|---|---|---|---|
| E2E comum, alinhado | As etapas E2E anteriores passam; expectativa de pós-verificação é PASS | Teste conflita com NOT_APPLICABLE no perfil OPERATIONAL_ONLY | Alta |
| E2E comum, desalinhado | As etapas E2E anteriores passam; mesma expectativa incorreta | Mesmo defeito de expectativa, independente do alinhamento | Alta |
| Trusted E2E | Filho sai com código 5 sem child_result; supervisor retorna CHILD_REPORT_MISSING_OR_INVALID | Caminho acima do limite é a hipótese principal; exceção exata não confirmada | Alta para o defeito do envelope; inferencial para PATH_TOO_LONG |

O teste também abre phase2.json antes de validar o resultado da fase 1. Quando a fase 1 falha e a fase 2 não é criada, o diagnóstico pode terminar em FileNotFoundError secundário, obscurecendo a falha que deveria ser reportada primeiro.

## 4. Causas e lacunas confirmadas

### Confirmadas

1. **Expectativa inconsistente com o perfil:** dois testes esperam PASS para um estado que o contrato classifica como NOT_APPLICABLE.
2. **Envelope incompleto de falha do filho:** uma exceção anterior a child_result não é representada de forma válida para o supervisor.
3. **Perda da causa primária:** o supervisor reduz a falha a CHILD_REPORT_MISSING_OR_INVALID.
4. **Classificação de exceção frágil:** _safe_exception_class compara tipos por igualdade exata; exceções derivadas de domínio podem cair em OTHER.
5. **Probe fora da raiz autorizada:** o fixture é descartado pela guarda quando a raiz permitida está configurada para evidence_root.
6. **Ordem de validação dos artefatos:** phase2.json é aberto antes de confirmar se a fase anterior permitiu sua criação.

### Não confirmadas

- A exceção histórica específica do trusted E2E.
- Proactor como explicação para a falha trusted atual.
- Problema de manifest, hash ou identidade sintética: os dados sintéticos examinados são coerentes em identidade/tamanho/SHA, e a pós-verificação reporta PASS.
- Ausência de uma linha de download como causa primária; o comportamento é compatível com uma falha anterior.
- Estado compartilhado como causa comum entre as três falhas.

## 5. Achados sistêmicos de arquitetura

### 5.1 Fronteiras de responsabilidade pouco nítidas

Harness, teste, processo filho, supervisor, launcher e receipt participam do mesmo diagnóstico, mas seus resultados se sobrepõem. Uma falha de execução pode ser registrada como falha de protocolo, e uma falha de coleta pode substituir a causa inicial. Os registros deveriam distinguir observações do filho, do supervisor e do validador.

### 5.2 Formação de caminhos dependente de fixtures

A montagem de caminho combina raízes do fixture, identificador de caso, catálogo e nome do arquivo. Esse desenho permite ultrapassar o limite antes da fila. A correção não deve remover o limite nem relaxar a guarda: deve tornar o caminho previsível, reproduzível e observável.

### 5.3 Ambiente de teste sensível ao modo de inicialização

Monkeypatches do processo pai não são herdados automaticamente pelo filho. O ambiente, incluindo PYTHONPATH e sitecustomize, pode mudar o comportamento conforme launcher e contexto. O bootstrap sintético precisa de handshake explícito e evidência de que a configuração esperada foi carregada.

### 5.4 Recursos e persistência

O registro mostra gateway_restored, mas não evidencia gateway_closed. A propriedade e o fechamento de recursos precisam ter um responsável inequívoco. Além disso, SQLite, ledger e filesystem não compartilham uma transação atômica; reconciliação e evidências precisam tolerar encerramentos parciais sem declarar PASS prematuramente.

Existem salvaguardas que devem ser preservadas: reserva/idempotência, checkpoints, no-overwrite e guardas de evidência. A auditoria não encontrou fundamento para removê-las.

### 5.5 Validação da infraestrutura

Sandbox PASS não equivale a validação nativa. A infraestrutura examinada tem lacunas potenciais:

- coleta e JUnit não são reconciliados por uma lista exata de testes;
- deadlines podem se sobrepor;
- Python e PowerShell podem disputar a escrita do receipt;
- encerrar o processo raiz não prova que processos descendentes terminaram;
- parse PowerShell não prova runtime nem binding;
- variáveis herdadas podem variar entre invocações;
- receipts não ligam de forma suficiente o resultado ao snapshot da fonte.

Essas são fragilidades da arquitetura de validação; não foram todas demonstradas como causas das três falhas atuais.

## 6. Opções para execução autônoma

| Opção | Avaliação |
|---|---|
| A. Codex nativo no Windows | Menor custo se o runtime demonstrar execução, controle do ciclo de vida e retorno íntegro dos artefatos. Essa capacidade ainda não está comprovada neste caso. |
| B. Executor local restrito e offline | Melhor opção para autonomia sustentada caso A não esteja disponível. Exige perfis fixos, conta sem segredos, isolamento de rede no sistema operacional, supervisor e protocolo de pedido/resultado. |
| C. Orquestrador local independente | Alternativa intermediária, mas sem controle bidirecional exigiria handoff humano por execução. Com submit/status/cancel/result, torna-se essencialmente a opção B. |
| D. VM ou runner de CI dedicado | Melhor isolamento e repetibilidade, com maior custo operacional e filesystem distinto do workspace. |

Já existem subprocessos, launcher PowerShell, runner Python e artefatos compartilhados (stdout, stderr, JUnit e receipts) que o processo raiz consegue ler. Não foi encontrado um protocolo local persistente de pedido/cancelamento/resultado. A capacidade de executar fora do sandbox nativo não foi demonstrada.

Não executar RPC/Telegram nem permitir egress de rede em um perfil destinado a testes sintéticos. Um executor restrito não deve aceitar comandos arbitrários: deve operar sobre perfis allowlisted e snapshots identificados por digest.

## 7. Recomendação de arquitetura

Adotar **estabilização estrutural delimitada** do harness e do pipeline de QA, mantendo o escopo de produção intacto.

O desenho-alvo recomendado inclui:

1. **RunSpec imutável:** digest do snapshot, perfil allowlisted, entrypoint, interpretador, ambiente, diretórios, limites e deadlines.
2. **Supervisor único:** dono do processo e de sua árvore, com cancelamento e um resultado terminal autoritativo.
3. **Envelope de filho válido em todos os estados:** sucesso e falha devem produzir status, etapa, código de erro seguro, referências de evidência e identificação do run; o envelope não deve forjar resultado de negócio.
4. **Evidência append-only:** observações do filho, supervisor e validador separadas, sem sobrescrever a causa inicial.
5. **Handshake de bootstrap sintético:** confirmação explícita de que o filho recebeu ambiente e fixture esperados.
6. **Validador independente:** reconciliar testes coletados, JUnit, exit codes, artefatos, identidade, integridade e digest da fonte.
7. **Protocolo restrito de execução:** submit/status/cancel/result, IDs únicos, digest de snapshot, deadlines, ACL e publicação atômica de resultados.
8. **Barreiras de rede e filesystem:** enforcement no sistema operacional, raízes permitidas explícitas e verificação de caminhos positivos, negativos e symlinks.

Erros de diagnóstico devem preservar a causa primária sem expor segredos. A resolução do envelope não pode transformar uma falha do filho em PASS.

## 8. Plano de implementação por etapas

Este plano é recomendação para trabalho futuro, não autorização executada pela auditoria.

| Etapa | Trabalho delimitado | Responsabilidade sugerida |
|---|---|---|
| 0 | Registrar root, snapshot e hashes do WIP; preservar receipts, SQLite, logs e arquivos não rastreados | Root / scribe |
| 1 | Definir contrato do envelope de falha e códigos diagnósticos seguros | Analista de diagnóstico; implementação mecânica após contrato fechado |
| 2 | Corrigir expectativas de NOT_APPLICABLE, a ordem de leitura phase1/phase2 e a raiz do probe | Responsável pelo harness e testes |
| 3 | Reproduzir caminho longo e curto; manter teste negativo para o limite de 240; registrar estágio e código seguro | Analista de diagnóstico + validador |
| 4 | Endurecer launcher e runner: dono do processo, descendentes, deadlines, escrita única de receipt, ambiente explícito | Responsável pela infraestrutura de teste |
| 5 | Decidir A ou B com base em capability observada; se B, fixar conta, perfis, ACL e isolamento offline | Root / autoridade do projeto |
| 6 | Validar E2Es, harness e regressão relevante no mesmo snapshot; reconciliar persistência e provar ausência de RPC por bloqueio de egress | Validador + root |
| 7 | Reconciliar documentos canônicos e PROJECT_STATE conforme authorities vigentes, sem apagar histórico | Scribe + root |

**Limites de escrita recomendados:** harness, testes, runner, launcher e infraestrutura de teste. Alterações em downloads.py, gateway, schema, V1, política de integridade ou fluxo de produto exigem um finding separado e contrato próprio.

### Condições de parada

Interromper a execução se houver rede ou dados protegidos inesperados, drift de snapshot, processo descendente sem controle, evidência contraditória, escape de raiz, resultado terminal ambíguo ou expansão de escopo.

## 9. Validação e classificação de aceite

A validação proposta deve demonstrar, no mesmo snapshot:

- testes focados para envelopes de sucesso, falha anterior ao resultado e exceção de domínio;
- caminhos válidos e inválidos, incluindo o limite, sufixo temporário e symlinks;
- propagação de ambiente e handshake de bootstrap em processo filho real;
- ciclo de vida do processo e término de descendentes;
- execução dos três E2Es e reconciliação dos resultados;
- consistência entre SQLite, ledger e filesystem após sucesso, falha e cancelamento;
- ausência de RPC comprovada por bloqueio de egress no nível do sistema;
- igualdade exata entre IDs coletados e JUnit, sem skip/xfail não aprovado;
- coerência entre exit code, receipt, digest e artefatos;
- regressão relevante de S5/S6 no mesmo snapshot.

Classificações:

- **PASS:** evidência completa e reconciliada, sem divergências.
- **FAIL:** violação de contrato reproduzida ou resultado contraditório.
- **BLOCKED:** validação impedida por capability ou pré-condição ausente.
- **INCOMPLETE:** faltam artefatos ou reconciliação para decidir.

O receipt atual representa **FAIL da suíte**, com 173/176 aprovados. O trusted E2E é funcionalmente falho; sua causa específica permanece sem confirmação. A auditoria não converte isso em BLOCKED por ambiente.

## 10. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Falha reportada como PASS por envelope permissivo | Separar status do processo de resultado de negócio; validar invariantes no supervisor |
| Envelope de falha permitir dados fabricados | Schema mínimo, validação independente e evidências append-only |
| Exposição de secrets em traceback | Mensagens e códigos seguros; sanitização com retenção da causa sem conteúdo sensível |
| Remover limite de caminho para contornar fixture | Manter o limite e redesenhar a fixture; testar o caso negativo |
| Processo descendente continuar após timeout | Supervisor da árvore de processos e verificação de encerramento |
| Evidência sobrescrita ou divergente | Publicação atômica, escritor único e receipts vinculados ao digest |
| WIP ser perdido durante correção | Hashes do snapshot, diffs por lote e preservação de arquivos não rastreados |
| Bootstrap sintético falhar silenciosamente | Handshake obrigatório antes de aceitar a execução |
| Loop autônomo sem término | Budget e deadlines por etapa, cancelamento e condição terminal única |

## 11. Rollback e preservação

Antes de qualquer implementação futura, preservar hashes do estado de trabalho, arquivos não rastreados e artefatos de execução. Trabalhar em lotes pequenos e identificáveis; reverter somente o lote da alteração quando necessário. Não usar reset, clean ou operações que descartem estado. Preservar receipts, SQLite, logs e evidências, confirmar término de processos antes de limpar qualquer runtime e verificar que não restou executor em segundo plano.

Artefatos de prova não devem ser convertidos em evidência de aceite sem reconciliação. Alteração no código, validação de integração, regressão nativa, prova real e aceite do usuário são estados independentes.

## 12. Decisões em aberto para a autoridade do projeto

1. Autorizar ou não ciclos autônomos de diagnóstico, correção e teste nativo.
2. Se execução nativa Codex não estiver comprovada, autorizar a preparação do executor local restrito (opção B), incluindo conta, isolamento e diretórios.
3. Definir se PowerShell 5.1 será runtime obrigatório ou se parse estático é suficiente para o gate.
4. Manter decisões separadas para prova real, adoção de V2, aceite formal de S6, início de S7/S8 e publicação Git.

Nenhuma dessas decisões é tomada por este parecer. A conclusão da auditoria não concede autoridade de implementação, avanço de fase ou publicação.

## 13. Handoff e conclusão

**Recomendação principal:** opção B quando a capacidade nativa (A) não puder ser demonstrada. Antes disso, preservar o WIP e reproduzir o trusted E2E com caminho curto e longo, mantendo o limite como teste negativo. Iniciar a estabilização pelo contrato de falha e observabilidade, corrigir os dois testes de expectativa e o fixture do probe, então endurecer o runner.

**Pergunta de diagnóstico para uma investigação subsequente:** qual exceção ocorre entre gateway_restored e queue.begin no trusted E2E, e uma raiz curta elimina a falha mantendo os outros contratos? A reprodução deve registrar estágio e código seguro, preservar o caso longo como negativo e evitar mudanças em integridade, timeout ou asyncio sem evidência causal.

**Nível de confiança:**
- Alto: duas expectativas incorretas; envelope de falha inválido; perda da causa primária; descarte do probe.
- Alto, mas inferencial: limite de caminho como causa do encerramento trusted histórico.
- Não estabelecido: explicações por Proactor, manifest/hash ou estado compartilhado.

A auditoria está encerrada. A implementação não foi iniciada, a V2 permanece desligada, o aceite formal de S6 permanece pendente e não houve ação de Git.

