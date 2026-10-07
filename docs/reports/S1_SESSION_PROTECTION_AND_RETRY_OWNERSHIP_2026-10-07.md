# S1 — Proposta de proteção/lifecycle da sessão e ownership de retry

Data: 2026-10-07 / America/Sao_Paulo.

```text
DOCUMENT_ROLE = REPORT
STATUS = PASS / RECOMMENDATION_READY_FOR_USER_DECISION
AUTHORITY_STATUS = DERIVED_NON_NORMATIVE
ROLE = ARCHITECT / papel analítico
MODEL_TARGET = SOL
REASONING_EFFORT_TARGET = HIGH
RUNTIME_MODEL = UNKNOWN / variante não verificável pela superfície utilizada
RUNTIME_EFFORT = UNKNOWN
EXECUTION_MODE = DIRECT
SKILLS_PLUGINS_SUBAGENTS = NONE
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
S1_STARTED = NO
```

## 1. Recomendação e limite decisório

**RECOMENDAÇÃO:** armazenar somente o material mínimo de autenticação da sessão
como blob cifrado com DPAPI no escopo do usuário Windows, em diretório local
com DACL restrita. Carregar uma `StringSession` exclusivamente dentro do adapter,
em memória, sem arquivo SQLite de sessão em claro. Reautenticar separadamente em
cada máquina; não exportar strings nem fazer backup automático da sessão.

**RECOMENDAÇÃO:** a APPLICATION possui a política de FloodWait e de retries de
operações; o TELETHON_ADAPTER traduz falhas e possui apenas mecanismos de conexão
e protocolo explicitamente limitados. O TELEGRAM_GATEWAY_PORT descreve resultados
e erros próprios, sem executar loops de retry. Não haverá dois loops independentes
repetindo a mesma operação.

Essa escolha oferece proteção do arquivo copiado e controle uniforme de esperas,
com custo de um pequeno storage Windows e de testes do comportamento efetivo do
Telethon. Não resolve comprometimento do processo ou do usuário Windows. A
adequação ao S1 é sustentada pelas capacidades documentadas; o funcionamento da
combinação ainda deverá ser comprovado offline antes de sessão real.

**DECISÃO = PENDING_USER.** Este relatório não aprova tecnologia, valores de
configuração, contrato, prontidão, início da S1 ou alteração de authority.

## 2. Estado factual, authorities e evidência

```text
REPO_ROOT = C:/Users/walacedelgado/PycharmProjects/projeto_telegram_courses
BRANCH = work/s0-bootstrap
HEAD = 8e8713629fc2d73b3fa4a3f3ba62c17f3f85197e
UPSTREAM = origin/work/s0-bootstrap / referência local, sem fetch
INITIAL_WORKTREE = seis arquivos untracked: cinco policies locais e S1_ENTRY_REVIEW
INITIAL_TRACKED_AND_INDEX_CHANGES = NONE
REPORT_PREEXISTED = NO
```

Fontes de domínio e rastreabilidade:

| Fonte | Evidência usada e consequência |
|---|---|
| [S1_ENTRY_REVIEW](S1_ENTRY_REVIEW_2026-10-07.md), seção corrente | Evidência derivada de lacunas, sem usar a primeira execução supersedida como conclusão atual. |
| [REQUIREMENTS](../product/REQUIREMENTS.md), FR-01/02, FR-15/16, NFR-04–06/08–10 | Conta própria, reutilização, descoberta legítima, sessão protegida, logs seguros e integração separada. Não prescreve DPAPI nem criptografia específica. |
| [ARCHITECTURE](../architecture/ARCHITECTURE.md), Boundaries e ADR-001/002/003 | Telethon 1.45.x dentro do adapter; port/modelos próprios; multi-processo fora do escopo inicial. |
| [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md), Configuration, Logging, Error taxonomy/retry e Test strategy | Path configurável; API credentials por ambiente sem fallback; falhas auth/access/config sem retry; backoff limitado com jitter; respeito a FloodWait. |
| [SPRINTS](../continuity/planning/SPRINTS.md), S1, Future sprint entry conditions e controles transversais | Proteção definida/verificada antes de sessão real e ownership básico fechado desde S1; S8 endurece controles existentes. |
| [ROADMAP](../continuity/planning/ROADMAP.md) | S1 = acesso Telegram; nenhuma antecipação de scanner, parser ou downloads. |
| [ACTIVE_AUTHORITY_MAP](../continuity/ACTIVE_AUTHORITY_MAP.md), binding, state, bootstrap, continuity, START_HERE e último handoff | Resolve authorities e safe resume; S0 encerrada; S1 sem autorização. Não houve nova recuperação nem gate de publicação. |

**Divergências conhecidas, não reconciliadas:** PROJECT_STATE conserva root de outro
computador; usa-se o root factual acima. As cinco policies locais têm os mesmos
hashes registrados na seção corrente da entry review, diferentes dos pins do
binding. O pedido atual permite as policies vigentes disponibilizadas localmente;
essa seleção vale somente para esta atividade, sem migração. PM-02, trecho de
routing arquitetural material, PM-01 §§8–12 e PM-05 foram usados para
authority, escopo, materialidade e independência analítica. Não se afirma validar
byte a byte o baseline externo nem se acessou `governanca_de_projetos`.
Essas divergências preexistentes não são novo mismatch do relatório com as
authorities de domínio; qualquer conflito novo material exigiria REPORT_AND_STOP.

**FATO / evidência técnica primária:** Telethon aceita um objeto Session em vez
de path. SQLiteSession é o padrão; StringSession mantém estado em memória e
serializa credenciais reutilizáveis. A string deve ser tratada como segredo.
[Telethon — Session Files](https://docs.telethon.dev/en/stable/concepts/sessions.html).
StringSession não é um snapshot completo de caches/estado de updates.
[Telethon — Sessions API](https://docs.telethon.dev/en/stable/modules/sessions.html).

**FATO / evidência Windows:** DPAPI normalmente vincula a decifragem ao mesmo
usuário e computador, com exceção documentada de perfis roaming. O flag
LOCAL_MACHINE amplia a decifragem para usuários da máquina. Há proteção de
integridade do blob; não implica proteção de memória.
[Microsoft — CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
Reset administrativo de senha pode afetar recuperação.
[Microsoft — exemplo e limitações DPAPI](https://learn.microsoft.com/en-us/windows/win32/seccrypto/example-c-program-using-cryptprotectdata).

**FATO / evidência local complementar:** leitura estática, sem importar/executar
Telethon, de `.venv/Lib/site-packages/telethon/version.py` (1.45.0),
`sessions/string.py`, `client/users.py`, `helpers.py` e pontos de `client/auth.py`.
Isso confirma o formato serializado e detalhes internos discutidos na seção 5;
não demonstra integridade da distribuição nem compatibilidade executada.
Não foram abertos arquivos de sessão, credenciais ou secrets locais.

## 3. Alternativas de proteção Windows

### A — SQLiteSession convencional com boundary de filesystem

```text
OPTION = SQLiteSession em diretório privado, DACL verificada
BENEFITS = Menor integração; persistência de caches/estado nativa; compatibilidade direta
RISKS = Auth key em claro no disco e cópias; sidecars/backups ampliam exposição
SECURITY_PROPERTIES = Separa usuários comuns por ACL; não cifra material persistido
OPERATIONAL_COST = Baixo; verificar diretório, arquivo e sidecars
TESTABILITY = Offline com SQLite e dados sintéticos; ACL exige Windows real
COMPATIBILITY = Nativa com Telethon 1.45.x; mantém caches entre processos sucessivos
LIMITATIONS = ACL não garante confidencialidade de cópia ou acesso offline ao volume
```

Criação com ACL herdada não prova boundary adequado; verificar permissões efetivas.
Operadores com privilégios de backup podem superar controles comuns de acesso.
[Microsoft — File Security](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights).
Uma DACL ausente não é uma DACL restrita.
[Microsoft — DACLs and ACEs](https://learn.microsoft.com/en-us/windows/win32/secauthz/dacls-and-aces).

**AVALIAÇÃO:** opção plausível para ameaça limitada a outros usuários sem
privilégios. Não a escolheria como padrão porque cópias do material permanecem
reutilizáveis. NFR-06 não a proíbe textualmente; rejeição é recomendação técnica.

### B — SQLiteSession com DACL e EFS

```text
OPTION = Diretório/arquivos de sessão sob EFS, com DACL restrita
BENEFITS = Criptografia transparente sem trocar o storage Telethon; conserva caches
RISKS = Certificado/chave e recuperação dependem do ambiente; cópias/exportações podem perder proteção
SECURITY_PROPERTIES = Cifra arquivos em volume compatível; acesso do usuário continua transparente
OPERATIONAL_COST = Médio; detectar suporte, verificar sidecars e gerenciar certificados/recovery
TESTABILITY = Offline Windows real para arquivos/sidecars; simulação não prova EFS efetivo
COMPATIBILITY = Transparente ao SQLite em princípio; ainda requer validação do ambiente
LIMITATIONS = Sem suporte comprovado no computador atual; não protege processo autorizado
```

EFS protege arquivos em NTFS e seu suporte deve ser detectado.
[Microsoft — File Encryption](https://learn.microsoft.com/en-us/windows/win32/fileio/file-encryption).
**AVALIAÇÃO:** defensável em Windows administrado com recuperação de certificados
estabelecida; custo ambiental não justificado para S1. Criptografia de volume
pode complementar proteção física, mas não substitui o boundary por usuário nem
garante proteção de cópias exportadas. Não se presume EFS ou volume cifrado ativo.

### C — DPAPI por usuário + StringSession em memória + blob com DACL

```text
OPTION = Blob DPAPI de credencial mínima; StringSession restrita ao adapter
BENEFITS = Nenhum banco de sessão em claro; cópia do blob não entrega diretamente a auth key
RISKS = Wrapper/persistência novos; perda de perfil; caches não persistem; plaintext existe em memória
SECURITY_PROPERTIES = Confidencialidade/integridade do blob; boundary Windows por usuário mais ACL
OPERATIONAL_COST = Médio e delimitado; integração Win32, gravação atômica, lifecycle e falhas controladas
TESTABILITY = Fake protector/store e dados sintéticos; DPAPI/DACL reais em integração local sem Telegram
COMPATIBILITY = Session é extensão nativa; reutilização de login é capacidade prevista; combinação não executada
LIMITATIONS = Sem proteção contra malware do mesmo usuário, admin/SYSTEM, debugger, dumps ou replay de blob antigo
```

**INFERÊNCIA:** a persistência mínima é suficiente como escolha inicial para
auth/discovery; entidades devem ser redescobertas legitimamente após reinício.
S1 deve comprovar seleção por modelos próprios sem depender de cache persistido.
Reavaliar antes de scanners/updates futuros; não prometer suporte completo com
StringSession a todos os fluxos S2–S10.

### D — Storage Session customizado com persistência cifrada de estado completo

```text
OPTION = Implementação de Session própria com dados/caches cifrados
BENEFITS = Pode manter caches e atualizar material sem persistência em claro
RISKS = Contrato amplo; bugs de serialização/consistência; manutenção ligada à versão Telethon
SECURITY_PROPERTIES = Dependem de cifra, key management, ACL e tratamento de memória escolhidos
OPERATIONAL_COST = Alto para S1; maior superfície de implementação e validação
TESTABILITY = Offline possível, mas matriz de auth key/DC/entities/update state/delete/close é ampla
COMPATIBILITY = Ponto de extensão existe; implementação concreta não validada
LIMITATIONS = Benefício de cache completo ainda não requerido em S1; não cifrar SQLite depois de usá-lo em claro
```

**AVALIAÇÃO:** preservar como alternativa futura se houver evidência de necessidade.
Não adicionar banco externo, serviço de secrets ou criptografia artesanal em S1.
MemorySession sem persistência é opção efêmera, mas não atende à evidência de
reutilização entre execuções esperada para FR-01 como padrão. StringSession em
arquivo/env sem cifra é credencial em claro, não mecanismo de proteção.

```text
RECOMMENDED_SESSION_PROTECTION = C / DPAPI_CURRENT_USER + RESTRICTED_DACL + ADAPTER_ONLY_STRINGSESSION
RATIONALE = Protege persistência/cópias com extensão nativa e escopo pequeno, aceitando reautenticação em outra máquina
REJECTED_ALTERNATIVES = A: cópia em claro; B: pré-requisitos/recuperação EFS não estabelecidos; D: contrato excessivo para auth/discovery
```

## 4. Lifecycle proposto

**SECURITY_REQUIREMENT existente:** NFR-05/06 e Logging da foundation exigem
exclusão de Git/logs/artefatos compartilhados e proteção local definida/verificada
antes de sessão real. Não existe requisito aprovado de DPAPI, backup, exportação,
retenção temporal, path fixo ou suporte multi-máquina.

**IMPLEMENTATION_DETAIL proposto, pendente de aprovação:** DPAPI sem
LOCAL_MACHINE, sem segredo adicional fixo no código; operações sem prompts
inesperados do sistema; armazenamento versionado; nenhuma queda para plaintext.
Falha de protector/path/DACL impede criação/carregamento de material sensível.
Proteção em repouso adicional é escolha recomendada, não requisito de produto
retroativamente inventado.

| Campo | Proposta de lifecycle |
|---|---|
| SESSION_PATH | Default `%LOCALAPPDATA%/projeto_telegram_courses/session/default.session.dpapi`; fora do repo, downloads, logs e pastas compartilhadas/sincronizadas. Alias opaco, sem telefone. Resolver path absoluto mantendo precedência CLI → ambiente → settings → default da foundation. |
| SESSION_CREATION | Antes de conexão/login, validar storage e DACL com bytes sintéticos. Futuro login explícito gera material em memória; após autenticação, cifrar e persistir antes de declarar sessão reutilizável. Não guardar OTP/2FA/phone_code_hash no blob persistente. |
| SESSION_REUSE | Validar path/DACL/versão/tamanho; decifrar apenas no adapter; construir objeto Session em memória. Autorização local não prova autorização remota: verificar no fluxo autenticado futuro; revogação não abre login silencioso. |
| SESSION_INVALIDATION | Estado local inválido após revogação/expiração detectada, incompatibilidade, corrupção ou falha DPAPI. Bloquear reutilização e informar causa segura. Falha de rede não invalida sessão nem remove blob. |
| SESSION_REVOCATION | Ação explícita sobre autorização remota, distinta de desconexão e remoção local. Adapter executa logout legítimo da sessão disponível; se indisponível, orientar encerramento da sessão pelos dispositivos do Telegram. Nunca afirmar revogação sem confirmação remota. |
| SESSION_DELETION | Fechar client/handles, bloquear regravação e remover blob/temporários exclusivamente dentro do diretório validado. Informar que apagar localmente não revoga remotamente. Sem promessa de apagamento forense de SSD/backups/dumps. |
| MULTI_MACHINE_BEHAVIOR | Sessões independentes por máquina/usuário; autenticação legítima em cada uma. Não copiar blob/auth key nem sincronizar storage. Exceção DPAPI de roaming não cria suporte do produto. |
| BACKUP_POLICY | Não oferecer backup/exportação/importação de sessão em S1; excluir da coleta de suporte, fixtures e backups controlados pela aplicação. O app não garante exclusão de backups externos do computador; registrar essa limitação. |
| RECOVERY_POLICY | Reautenticar se perdido perfil/blob ou impossível decifrar; nunca recuperar chave de repo/log ou de backup compartilhado. Suspeita de vazamento exige revogação remota e nova sessão. |

Ownership local: aplicação coordena intenção e estado do fluxo; adapter possui
serialização Telethon e um storage/protector Windows encapsulado na infraestrutura.
Os nomes internos dessa abstração ainda não são contrato aprovado. `SessionStore`
e `SessionProtector` são papéis conceituais; não adicionar storage à API pública
da aplicação apenas para expor bytes de sessão.

Detalhes de integridade e operação para futura especificação:

- Diretório criado/validado com ACEs para o SID corrente e, quando justificado,
  SYSTEM/administradores; sem grants amplos herdados para usuários comuns. Não
  alegar proteção contra administradores. Revalidar arquivos preexistentes,
  temporários e destino de substituição; diretório no perfil não basta.
- Paths customizados devem satisfazer os mesmos controles. Recusar repo,
  compartilhamentos, reparse points ou escapes do boundary validado; não tentar
  adivinhar que toda pasta local está livre de backup/cloud sync. Falha segura
  exige mensagem para escolher path adequado, sem sobrescrita silenciosa.
- Cifrar antes de escrever; criar temporário já protegido no mesmo diretório,
  substituir atomicamente e verificar resultado. Nunca decifrar para arquivo
  SQLite temporário. Não criar cópias `.bak` automáticas da credencial.
- Persistir material mínimo após login e mudanças relevantes de auth key/DC;
  comprovar hooks/checkpoints na implementação. Desconexão normal preserva
  sessão, logout impede save posterior. Não depender apenas do encerramento
  normal; crash pode exigir novo login e nunca deve produzir sucesso falso.
- Se login remoto ocorreu mas persistência falhou, informar sessão não salva;
  oferecer encerramento remoto explícito. Não apagar evidência local em falha
  de rede nem prometer que logout foi realizado quando não houve confirmação.
- Um processo por storage; segundo processo deve falhar de forma controlada.
  Não acrescentar suporte multi-processo. Exclusão/invalidação deve impedir que
  um client antigo grave novamente a sessão removida.
- Python não garante zerar todas as cópias imutáveis do segredo em memória.
  Minimizar lifetime; não serializar objetos em logs/dumps/tracebacks de suporte.
  Um blob antigo pode restaurar credencial ainda válida: integridade DPAPI não
  substitui revogação remota ou controle de replay.

O novo sufixo `.session.dpapi` não é coberto pelo padrão atual `*.session`.
Default fora do repo reduz risco, mas exclusão explícita do blob/temporários e
checagem de artefatos devem entrar em futura implementação autorizada. Não
alterar `.gitignore` nesta atividade. Ciphertext continua sendo material de
sessão e não deve entrar em Git, fixtures ou relatórios compartilhados.

## 5. FloodWait / retry: política, tradução e mecanismos internos

**FATO:** o client tem parâmetros próprios de retry e espera automática;
`timeout` de conexão não limita sozinho a duração de uma chamada RPC.
[Telethon — TelegramClient](https://docs.telethon.dev/en/stable/modules/client.html).
FloodWait comunica duração pelo atributo `seconds`; erros RPC desconhecidos
também existem, exigindo fallback controlado.
[Telethon — RPC Errors](https://docs.telethon.dev/en/stable/concepts/errors.html).

**RECOMENDAÇÃO:** APPLICATION controla budget por operação, limite de tentativas,
deadline, cancelamento, backoff exponencial limitado e jitter. O valor máximo de
tentativas, base/cap de backoff, deadline e limite de espera automática precisam
de escolha registrada antes da implementação; não se inventa threshold aprovado.

FloodWait usa espera mínima do servidor, não backoff que a encurte. Converter
duração em prazo usando relógio monotônico; admitir jitter somente adicional.
Compartilhar cooldown no gateway/conta do processo de forma conservadora, para
que outra operação não antecipe nova chamada. Toda repetição consome budget.
Se a espera exceder o budget/deadline, terminar com rate limit e informar quando
tentar novamente; nunca truncar espera e repetir cedo. Cancelamento interrompe
a espera sem nova chamada. Reinício do CLI não autoriza ignorar bloqueio conhecido:
o contrato futuro deve definir persistência de cooldown sem secrets ou declarar
que, após terminar, retomada será manual respeitando o prazo informado.

Retry de operação só é permitido para ação explicitamente segura de repetir.
Listar/resolver canais é candidato; enviar código, confirmar login ou logout
não deve ser reenviado automaticamente por timeout ambíguo. A ausência de resposta
não prova que o servidor não executou a ação. Necessidade de 2FA é etapa do fluxo
de autenticação com input humano, não falha transitória ou loop automático.

### Matriz por categoria

OWNER significa dono da política/resultado; a tradução Telethon → projeto é
sempre do adapter. RETRY_LOCATION identifica onde ocorre uma repetição de operação,
não retransmissões internas do MTProto.

| ERROR_CLASS / categoria | OWNER | RETRY_ALLOWED | RETRY_LOCATION | RETRY_POLICY | PROPAGATION | USER_VISIBLE_RESULT |
|---|---|---|---|---|---|---|
| TelegramRateLimitError / FloodWait | APPLICATION; adapter extrai duração | Condicional, apenas operação repetível e budget suficiente | APPLICATION | Esperar pelo menos duração informada; cooldown compartilhado, tentativas/deadline limitados | Erro próprio com retry_after e escopo seguro | Pausa cancelável e prazo; se excedido, operação adiada/falha explícita |
| NetworkError / timeout transitório | APPLICATION | Sim para ação segura; não para login ambíguo | APPLICATION | Backoff exponencial com jitter, deadline; cancelar chamada anterior antes de repetir | NetworkError com reason=timeout, sem request bruto | Tentativa limitada; esgotamento com orientação de rede ou confirmação manual |
| NetworkError / transporte-rede | APPLICATION para operação; ADAPTER para conexão | Condicional | APPLICATION; conexão no ADAPTER | Sem reconexão infinita ou loop duplicado; repetir só quando conexão pode ser restabelecida com budget | NetworkError reason=transport; sessão preservada | Indisponibilidade/reconexão limitada; nenhuma perda de sessão declarada |
| AuthenticationError / autenticação inválida | APPLICATION para fluxo humano | Não automático | NONE | Interromper; nova entrada humana explícita | AuthenticationError com código seguro | Código/senha inválidos ou login necessário; sem eco do valor |
| AuthenticationError / sessão revogada ou expirada | APPLICATION; ADAPTER bloqueia credencial inválida | Não automático | NONE | Invalidar reutilização; pedir reautenticação explícita | AuthenticationError reason=session_invalid | Sessão inválida; não confundir com rede indisponível |
| AccessError / canal inexistente ou inacessível | APPLICATION | Não automático | NONE | Informar indisponibilidade; sem join/bypass/fallback por outra conta | AccessError com código próprio, sem afirmar inexistência quando indistinguível | Canal não encontrado ou sem acesso; seleção pode ser refeita manualmente |
| ConfigurationError / configuração inválida | APPLICATION / bootstrap | Não | NONE | Validar antes da operação; correção explícita | ConfigurationError seguro | Campo inválido e como corrigir; sem divulgar conteúdo sensível |
| ConfigurationError / credencial ausente | APPLICATION / bootstrap | Não | NONE | Falhar antes de conexão; sem fallback | ConfigurationError reason=missing_credential | Informar nome do campo/env faltante, nunca seu valor |
| Falha não classificada / erro próprio a definir | APPLICATION / boundary global | Não por padrão | NONE | Encerramento controlado; classificar depois, sem assumir transitoriedade | Código unknown + correlation id seguro; sem objeto RPC/chained repr público | Falha inesperada; diagnóstico sanitizado |
| Erro Telegram transitório explicitamente permitido | APPLICATION | Condicional para ação repetível | APPLICATION | Allowlist e mesmo budget/backoff da operação | Código próprio a definir no contrato; não inventar classe canônica atual | Repetição limitada ou falha transitória explícita |

Taxonomia foundation preservada: timeout/transporte são reasons de NetworkError;
session_invalid é reason de AuthenticationError. Classe/código para unknown e
Telegram transient é proposta pendente, não nova authority. Erros locais de
persistência/proteção são StorageError, ou ConfigurationError quando path/setup
inválido; não recebem retries Telegram. Logs não devem reter exceção com request,
phone, API hash ou outros argumentos, inclusive via encadeamento de exceções.

### Contenção de retries internos Telethon

Configuração candidata para validação futura: `flood_sleep_threshold=0`,
`request_retries=0`, `raise_last_call_error=True`, `auto_reconnect=False` e
budget finito/explicitamente conhecido de conexão (candidato: sem repetição
automática). Nenhuma dessas opções foi alterada ou executada nesta atividade.

**EVIDÊNCIA estática local:** em Telethon 1.45.0, `retry_range(0)` ainda faz a
primeira tentativa. `users.py` contém espera fixa de 2 s no tratamento de alguns
erros de servidor mesmo na tentativa final; normaliza FloodWait zero para 1 s;
mantém cache de FloodWait; também pode mudar DC antes de esgotar o loop. Portanto,
essa configuração reduz loops, mas não prova zero espera interna, zero
transmissões internas ou sucesso automático de migração DC.

**RECOMENDAÇÃO para contrato:** contar duração interna no deadline único;
adapter traduz a última falha sem deixá-la virar ValueError genérico. Migração
DC permanece no adapter, com replay protocolar limitado e testado, separado de
retry de falhas auth/access/config. Nenhum tipo/erro DC sai do adapter. Não
reabrir request_retries indiscriminadamente para corrigir migração, nem editar
a biblioteca nesta proposta. AuthMethods e resolução de entidades podem efetuar
subchamadas: testes futuros precisam observar chamadas efetivas, não só invocações
do port. Os valores candidatos e o mecanismo exato de migração têm validação
pendente; isso é detalhe de implementação aberto, sem negar a recomendação de
ownership já fechada tecnicamente.

Alternativa avaliada: deixar adapter/Telethon fazer todos os retries. Simplifica
uso direto da biblioteca, mas esconde esperas do CLI, deixa orçamento fragmentado
e não atende sozinho ao backoff com jitter da foundation. Não recomendo dividir
FloodWait entre espera curta do Telethon e longa da aplicação: isso torna o
resultado dependente de threshold e facilita duplicação de loops. A aplicação
não deve implementar detalhes MTProto para eliminar todo mecanismo interno.

## 6. Boundary recomendado

```text
WHAT_APPLICATION_MUST_KNOW = Resultado de auth/discovery em modelos próprios, classe/reason seguros, duração de rate limit, segurança de replay por operação, budget/deadline/cancelamento
WHAT_APPLICATION_MUST_NOT_KNOW = TelegramClient, TLRequest, RPCError, auth key, StringSession, DPAPI bytes, DC migration ou caches Telethon
WHAT_ADAPTER_OWNS = Client/protocolo, objeto Session, storage/protector Windows encapsulados, conexão limitada, tradução de erros e persistência do material sensível
WHAT_PORT_EXPOSES = Auth/discovery, resultados/challenges próprios, erros seguros e retry_after; nenhuma operação de exportar sessão
ERROR_TRANSLATION_BOUNDARY = Dentro do TELETHON_ADAPTER, antes de atravessar TELEGRAM_GATEWAY_PORT
TELETHON_TYPES_DO_NOT_ESCAPE_ADAPTER = REQUIRED / ADR-002 preservado
```

Métodos/modelos exatos de autenticação, challenge 2FA, seleção de canais e
encerramento ainda exigem contrato funcional S1. Não ficam implicitamente
aprovados por esses campos. A aplicação pode reconhecer estados de sessão sem
receber o segredo serializado. O port não conhece DPAPI e não possui timers;
assim a aplicação é testável com fake gateway e eventual troca de adapter.

## 7. Critérios de validação futura

Tudo abaixo é **plano de validação**, não evidência de execução nesta atividade.

| OFFLINE_VALIDATION | Critério observável |
|---|---|
| Paths e boundary | Default/overrides absolutos; recusa de repo/share/reparse/escape; nenhum path em segredo/log; segundo processo controlado. Testes sem sessão Telegram. |
| DACL Windows local | Inspecionar permissões efetivas de diretório/blob/temp; rejeitar grants amplos/null DACL; usuário comum distinto sem leitura. Se identidade secundária indisponível, declarar teste incompleto. |
| DPAPI Windows local | Round-trip de bytes sintéticos; blob alterado/usuário incorreto falham; nenhuma queda para plaintext; teste real Win32 sem rede. Fake prova lógica, não criptografia/permissões reais. |
| Lifecycle/storage | Ausente → login requerido; save atômico, crash antes/depois de replace, falha de save, corrupção, alteração de DC/key, invalidação, remoção e prevenção de regravação após logout. Nenhum segredo real em fixture. |
| Persistência mínima | Serialização sintética e reabertura demonstram campos mínimos; entidades/caches redescobertos por fake; não afirmar suporte a updates duráveis. |
| Error translation | Cada linha da matriz traduz para tipo/código próprio; unknown controlado; nenhum objeto Telethon/Win32/segredo no resultado ou traceback público. |
| FloodWait simulado | Relógio/sleep falsos: zero e espera positiva; nenhuma chamada antecipada; escopo compartilhado; cancelamento, deadline excedido, novo FloodWait e esgotamento. Sem espera real longa ou produção de rate limit. |
| Retry da operação | Contagem exata por tentativa; backoff/jitter limitados; sem retry auth/access/config/unknown; ações não repetíveis não repetidas após timeout; chamada anterior encerrada. |
| Adapter Telethon sem rede | Simular sender/RPC/connection/DC migration no 1.45.x efetivo; medir subchamadas e esperas residuais; provar budget global e ausência de loops multiplicados. Não basta testar somente fake gateway. |
| Redaction e artefatos | Canários sintéticos ausentes de console/logs/exceções/relatórios; nenhum blob real/ciphertext compartilhado; `.gitignore` futuro cobre sufixos/temp; suíte normal sem rede/login/credenciais. |

**REAL_TELEGRAM_VALIDATION:** somente depois de aprovação, implementação e PASS
dos controles locais anteriores; integração mínima separada com conta própria:
login legítimo, encerramento/reabertura e reutilização, descoberta/seleção de um
canal acessível e resultado de indisponibilidade quando observado legitimamente.
Validar logout/reautenticação somente sobre sessão de teste com escolha explícita;
revogação controlada pode ter cenário separado. Sem catálogo/download, sem mass
calls e sem provocar FloodWait. Simulação é evidência adequada de política;
offline não comprova autorização/discovery reais. Nenhuma integração executada.

## 8. Decisões do usuário e conteúdo futuro de contrato

| Escolha pendente | Recomendação oferecida | Consequência |
|---|---|---|
| Proteção/lifecycle | Aprovar opção C e reautenticação por máquina | Aceita custo do wrapper, caches efêmeros e perda de portabilidade automática. |
| Ameaça residual | Aceitar boundary de usuário Windows com limitações declaradas | DPAPI/DACL não isolam processos maliciosos do mesmo usuário ou admin/SYSTEM. Se proteção contra esses atores for exigida, esta proposta precisa ser revista. |
| Backup/recuperação | Sem exportação/backup de sessão; recuperar por login | Perda de perfil não tem promessa de recuperação do segredo; conta Telegram deve continuar recuperável por meios legítimos. |
| Ownership | Aplicação para FloodWait/retry; adapter para protocolo/conexão limitada | Exige configuração e testes do Telethon para não multiplicar tentativas. |
| UX e budgets | Definir espera cancelável versus encerrar quando exceder orçamento; registrar limites finitos | Sem valores aprovados hoje. Isso pode ser resolvido no contrato S1, sem nova arquitetura. |

Podem entrar posteriormente em contrato: state machine de sessão e auth,
inputs seguros de OTP/2FA, métodos/modelos próprios, erros/reasons,
replay-safe por operação, path/DACL/DPAPI, persistência/cooldown,
limites/configuração, cenários offline e integração mínima.

```text
UNRESOLVED_ARCHITECTURE_DECISIONS = Aprovação do ownership e storage propostos; métodos/modelos auth/discovery, budgets/cooldown e estratégia limitada de DC migration ainda a especificar/validar
UNRESOLVED_SECURITY_DECISIONS = Aprovação da ameaça residual, DPAPI por usuário, backup/recuperação e controles de path/DACL; mecanismo/evidência ainda não implementados
```

Não há decisão técnica deliberadamente omitida entre alternativas desta
atividade: a recomendação é C com APPLICATION como dono de política. Permanecem
escolha humana e prova futura, distintas de falta de recomendação.

## 9. Self-review, verificações desta atividade e retorno

Revisão de coerência documental concluída: FR-01/02 e NFR-04–06/08–10
preservados; caminho segue precedência da foundation; taxonomia existente
mantida; sem retry automático terminal; sem tipos Telethon externos; controles
S1 não adiados para S8. Criptografia, no-backup e valores candidatos foram
explicitamente classificados como propostas, sem inventar requisito aprovado.
Nenhum novo conflito material com requirements/architecture/foundation foi
identificado. A recomendação independe de preferência por tecnologia previamente
sugerida; alternativas e limitações foram comparadas.

Verificações documentais: whitespace/diff do relatório untracked e dos arquivos
rastreados; status/índice; comparação de hashes dos arquivos de entrada antes e
depois; revisão manual e busca de padrões de valores secretos. Esses checks
validam o artefato e seu escopo, não segurança/compatibilidade da implementação
proposta. Não foram executados testes de produto ou integração.

Não há mudança de decisão/state canônico: apenas REPORT autorizado.
PROJECT_STATE_RECONCILIATION = NOT_APPLICABLE nesta atividade derivada; nenhuma
alegação de atualização/fechamento formal de sprint, handoff ou gate S1.

```text
FINAL_REPORT
STATUS = PASS / RECOMMENDATION_READY_FOR_USER_DECISION
ACTIVITY_COMPLETION_PERCENT = 100%
COMPLETION_BASIS = Alternativas, lifecycle, ownership por categoria, boundary, critérios futuros, escolhas pendentes e revisão documental concluídos; percentual somente desta proposta
REPORT_CREATED = docs/reports/S1_SESSION_PROTECTION_AND_RETRY_OWNERSHIP_2026-10-07.md
RECOMMENDED_SESSION_PROTECTION = DPAPI_CURRENT_USER + RESTRICTED_DACL + STRINGSESSION_IN_ADAPTER_MEMORY
RECOMMENDED_SESSION_LIFECYCLE = Create/save protegido; reuse verificado; invalidation explícita; revogação remota distinta de deletion local; login separado por máquina; sem exportação/backup automático
RECOMMENDED_FLOODWAIT_OWNER = APPLICATION / adapter traduz duração sem espera automática de FloodWait
RECOMMENDED_RETRY_OWNERSHIP = APPLICATION para política de operações; TELETHON_ADAPTER para protocolo/conexão limitados; TELEGRAM_GATEWAY_PORT somente contrato
OFFLINE_VALIDATION = Plano completo na seção 7; implementação ainda não validada; nenhuma sessão/credencial real
REAL_TELEGRAM_VALIDATION = Plano mínimo separado; NOT_EXECUTED
USER_DECISIONS_REQUIRED = Aprovar ou ajustar proteção/lifecycle, ameaça residual e ownership; definir UX/budgets no futuro contrato
UNRESOLVED_ARCHITECTURE_DECISIONS = Aprovação humana e detalhes de contrato/adapter indicados na seção 8
UNRESOLVED_SECURITY_DECISIONS = Aprovação humana e evidência local futura dos controles indicados na seção 8
FILES_CHANGED = Somente este relatório / escrita do agente
VALIDATIONS = PASS / coerência documental, whitespace, escopo por hashes/status/índice, inspeção de secrets e authority boundary
UNAUTHORIZED_CHANGES = NO
GIT_ACTIONS = NONE / sem stage, commit, push, tag ou publicação; apenas consultas/checks read-only
S1_STARTED = NO
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
FINAL_VERDICT = Proposta concluída para decisão; prontidão/segurança implementada e início S1 não declarados
NEXT_ACTION = Usuário decide a recomendação; somente depois poderá autorizar sua incorporação em contrato/authorities e preparação S1, sem avanço automático
```
