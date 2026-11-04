# TELEGRAM-3-CLOSURE-01 — evidência e prontidão

## Resultado

S9_ACCEPTANCE = PARTIAL. O contrato S9 §13 classifica F sem M ou G7 como parcial. A execução bem-sucedida contém G0 humano, G1–G3 e G5; G4 e G5 passaram. Não foram encontrados recibos G6, G7, G8 ou G9 nesse run, nem evidência integral M de memória. Não se comprovou hash remoto independente. O contrato permanece inalterado.

PRODUCT_READINESS = PARTIAL. A transferência unitária foi demonstrada; lote e retomada têm testes offline, mas não demonstração real autorizada. Uma ampliação de acesso ou de downloads reais requer autorização humana específica. O S10 não foi executado.

## Evidência existente

Run encerrado `20261102T222254Z-64aad96a40f6`: os recibos G0–G3 têm eventos de preparação e persistência correspondentes; o hash do recibo supervisor G5 confere. Uma cópia estável somente para leitura do ledger passou sua validação de 158 eventos; o estado de metadados era G5/RUNNING/PASS, sem reconciliação terminal. A verificação final local de SQLite, tamanho e SHA-256 passou. O arquivo tem 12.087.200 bytes e seu SHA-256 local confere com o banco; o operador relatou reprodução bem-sucedida. Não se retomou o run.

A descoberta limitada a 200 mensagens registrou 196 mídias MP4, vinculadas a aulas, com quatro trilhas, 21 cursos, 47 módulos e 516 aulas no catálogo observado. Isso não demonstra inventário integral do canal. Um arquivo foi baixado. Há duas pendências de associação globais no banco, sem atribuição comprovada ao canal examinado.

## Entrega e validação

A fila de produto oferece `--private-downloads`, exige destino explícito e confirmação interativa e prepara diretórios privados após a confirmação. Parcial existente deve ser arquivo regular, sem reparse point, com um único link e ACL privada verificada; falhas preservam os dados. A fronteira existente não considera processos da mesma conta ou privilegiados como adversários; verificações usam caminhos em momentos distintos. A fila de produto não é o supervisor S9 e não emite recibos G0–G9. O preparador Windows usa guardas existentes e não modifica ACLs existentes ou o vault DPAPI. O guia descreve autorização, catálogo, planejamento, limites e recuperação.

Validação: 115 testes offline passaram, incluindo fila, deduplicação, retomada simulada, FloodWait, caminhos privados, ACL rejeitada simulada e hard links reais; Ruff passou. Revisão independente não encontrou falha material restante dentro da fronteira existente; a rejeição de ACL no teste é simulada, não uma medição de ACL permissiva real. Nenhum acesso Telegram real foi executado nesta atividade.

## Medições e limites

Na execução real, 12.087.200 bytes em 15,642 s ativos correspondem a aproximadamente 0,737 MiB/s; o intervalo é amostrado e inclui componentes que não foram separados. A parede da fila foi 60,964 s, incluindo a confirmação G4. O ledger ocupou 163.840 bytes e registrou 158 eventos; tempo exclusivo de auditoria/ledger e espera de rate limiting não foram medidos. Rede, disco e hash da execução real não podem ser decompostos com a evidência existente.

Uma medição sintética offline separada, com 12.087.200 bytes de zeros em arquivo temporário privado, levou 0,0561 s para escrever e sincronizar e 0,0716 s para ler e calcular SHA-256, possivelmente usando cache. Não são medições de produção nem justificam otimização.

## Pendências

Obrigatórias para conclusão operacional: autorização específica e demonstração de lote real limitado e retomada real segura; avaliar os recibos e critérios contratuais S9 ausentes, inclusive evidência remota aplicável, sem fabricar prova; resolver qualquer bloqueio encontrado. As exceções anteriores de S6/S7 e a limitação NFR-02 permanecem. Instalação empacotada é S10, não autorizada nem executada. Melhoria opcional: teste nativo com ACL permissiva real em fixture isolada e telemetria que separe os custos reais.

Guia: [GUIA_WINDOWS_USO.md](../../GUIA_WINDOWS_USO.md). Nenhum stage, commit ou push foi realizado.
