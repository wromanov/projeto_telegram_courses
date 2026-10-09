# S1-D — Independent Architecture Review / GetDifference Resolution

Data: 2026-10-08, America/Sao_Paulo. Projeto: `projeto_telegram_courses`.

Modalidade: DIRECT / revisão técnica independente. Inspeção somente de leitura; este relatório foi salvo em `docs/audit` por instrução posterior expressa do usuário. Nenhuma prova de execução, importação Python, pytest, conexão Telegram, leitura de credenciais ou sessão real foi realizada.

Baseline factual: repositório `C:\Users\walac\desenvolvimento\projeto_telegram_courses`, branch `work/s0-bootstrap`, HEAD `e947406dbcab8ef593123f079daa279903805d2c`, upstream local `origin/work/s0-bootstrap`. Havia seis documentos rastreados modificados e três documentos não rastreados antes da auditoria; staging vazio. Esses deltas foram preservados. Não houve fetch, stage, commit ou push.

Classificações: **FACT** = evidência diretamente inspecionada; **INFERENCE** = dedução explicitada; **HYPOTHESIS** = possibilidade não demonstrada; **UNKNOWN** = informação insuficiente. Informações de execução fornecidas pelo usuário são identificadas como tal, sem atribuí-las a esta auditoria.

## A. Executive Technical Verdict

**O diagnóstico anterior está parcialmente correto: o caminho inicial foi corretamente identificado, mas a discussão arquitetural precisa incorporar o loop de updates e distinguir autenticação, estado de sincronização e processamento de conteúdo.**

1. **FACT:** no Telethon 1.45.0 instalado, uma conexão nova com `MessageBox` sem estado global, seguida de `get_me()` bem-sucedido, executa `_on_login()`. Esse método solicita `GetState` e, depois, `GetDifference`, sem condicional baseada em `receive_updates` ou `catch_up`.
2. **FACT:** `receive_updates=False` envolve RPCs em `InvokeWithoutUpdatesRequest`; não elimina o RPC interno. `catch_up=False` não desliga a inicialização de `_on_login` nem o mecanismo inteiro de updates.
3. **FACT:** persistir estado em outra Session não resolve isoladamente: `connect()` só carrega esse estado quando `catch_up=True`; essa mesma opção agenda catch-up no loop. Portanto, é possível desviar da chamada inicial e provocar diferenças logo depois.
4. **FACT adicional:** o loop interno solicita diferenças por lacunas e deadlines. Não há guarda `_no_updates` nesse caminho. A proposta de permitir diferenças **exclusivamente durante a restauração** não cobre todo o comportamento da biblioteca.
5. **INFERENCE:** o conflito está entre a exigência de zero RPC de diferenças e o lifecycle do cliente geral Telethon 1.45.0 utilizado pelo projeto. Não há evidência de defeito na proteção DPAPI nem de autenticação inválida. A implementação de S1-D ainda não existe; não cabe classificá-la como implementação defeituosa.

**Recomendação:** manter Telethon, StringSession protegida por DPAPI e gateway; se o usuário aceitar a exposição transitória adicional, reformular OPEN-04 para uma fronteira de uso de dados, mediante decisão explícita que abranja o lifecycle delimitado da descoberta. Não recomendar uma exceção descrita como “somente um GetDifference inicial”, pois isso não é garantido pelo código.

Se zero diferenças permanecer um requisito absoluto de privacidade, a recomendação muda: **manter OPEN-04 bloqueado**, sem workaround privado em produção. A revisão não encontrou mecanismo público suficiente para esse requisito na combinação atual. Isso é `NOT_FOUND_IN_REVIEW`, não `PROVEN_IMPOSSIBLE` para toda arquitetura ou versão.

**UNKNOWN:** sequência efetivamente transmitida em execuções reais; volume/conteúdo das respostas; causa do silêncio da última prova sintética; compatibilidade runtime de qualquer novo candidato. A auditoria fornece adjudicação estática, não uma prova de zero RPC.

## B. Telethon Source Findings

### B.1. Versão e rastreabilidade

Foram lidos `version.py` e `telethon-1.45.0.dist-info/METADATA` da `.venv-replay`; ambos identificam **1.45.0**. Não foi necessário importar a biblioteca. Python 3.14.7 é informação das evidências anteriores e do pedido atual, não uma nova medição desta atividade.

Os três hashes abaixo foram recalculados e coincidem com os registrados na investigação anterior:

| Arquivo relativo a `.venv-replay/Lib/site-packages/telethon/` | SHA-256 |
|---|---|
| `client/telegrambaseclient.py` | `a25de6b17facbdf6888f4c12aae8d0d9a5aaaa45d7219ebf7399f4523fb9814e` |
| `client/auth.py` | `955c6da74f697a9d923fb7f7eb5a9217b715a6a4839c6d0d3d10701b4f354592` |
| `sessions/string.py` | `1185fb0a82cae97e87575cde676f7ca16f9791d3eefab221cad970d843208ebd` |

As linhas seguintes se referem à instalação local inspecionada. Documentação pública foi usada como complemento; não como substituta do comportamento dessa versão.

### B.2. Condição exata e sequência de inicialização

Em `client/telegrambaseclient.py`, `connect()`, linhas 560–619:

- Conecta o sender; se ele informa que já estava conectado, retorna sem repetir a inicialização.
- Carrega estados da Session no MessageBox somente dentro de `if self._catch_up`, linhas 583–603.
- Envia a inicialização de camada/conexão contendo `help.GetConfigRequest`, linhas 605–611.
- Testa `self._message_box.is_empty()`, chama `get_me()` e, se há usuário, aguarda `_on_login(me)`, linhas 613–616.
- Só depois cria as tarefas de updates e keepalive, linhas 618–619.

`MessageBox.is_empty()`, em `_updates/messagebox.py:250–254`, significa precisamente **ausência de `ENTRY_ACCOUNT` no mapa**. Não significa ausência de auth key, de identidade ou de qualquer estado de canal. `load()`, linhas 217–235, só insere `ENTRY_ACCOUNT` se `session_state.pts != 0`.

`client/users.py:get_me`, linhas 169–178, consulta `users.GetUsersRequest([InputUserSelf()])`; retorna `None` em `UnauthorizedError`. É `connect()`, e não `get_me()`, quem chama `_on_login` nesse caminho.

Sequência estática para restauração válida em uma nova instância com StringSession:

```text
vault → StringSession restaurada → connect
  → sender.connect
  → InvokeWithLayer / InitConnection / GetConfig
  → GetUsers(InputUserSelf)
  → _on_login
      → GetState
      → GetDifference(pts, date, qts do GetState)
      → MessageBox.load
  → criação das tarefas de updates e keepalive
  → get_me adicional do gateway.restore
  → descoberta, quando futuramente implementada
```

Esta sequência pressupõe sucesso nos passos anteriores. Falha de transporte, revogação, cancelamento ou erro de RPC pode interrompê-la. Não é captura de rede.

### B.3. GetState, GetDifference e transmissão

Trecho decisivo de `client/auth.py:_on_login`, linhas 394–396:

```python
state = await self(functions.updates.GetStateRequest())
# the server may send an old qts in getState
difference = await self(functions.updates.GetDifferenceRequest(
    pts=state.pts, date=state.date, qts=state.qts))
```

O comentário explica a motivação declarada pelo código: corrigir possível `qts` antigo. Não demonstra que todo `getDialogs` exija diferenças ou que toda resposta de `GetState` seja inadequada.

`GetState` retorna cursores/estado, não um vetor de mensagens. `GetDifference` pode retornar diferenças com mensagens, mensagens criptografadas, outros updates e entidades. Não recebe um filtro “somente os canais elegíveis”. Referências oficiais: [GetState](https://core.telegram.org/method/updates.getState), [GetDifference](https://core.telegram.org/method/updates.getDifference).

**Nuance importante:** essa chamada inicial usa o estado recém-obtido, não explicitamente o último estado salvo há meses. Não é correto descrevê-la automaticamente como download integral do backlog. Também não é correto garantir resposta vazia: há concorrência e a própria justificativa de `qts` antigo. O volume real permanece desconhecido.

Em `_on_login`, linhas 398–405, a biblioteca aproveita o estado final/intermediário, ou ajusta `pts` em `DifferenceTooLong`. Esse método não percorre as mensagens para chamar handlers nem implementa um loop explícito para drenar `DifferenceSlice`. Entretanto, a resposta já foi desserializada e `UserMethods._call` já encaminhou suas entidades à Session.

As etapas não são equivalentes:

| Etapa | Evidência e limite |
|---|---|
| Construção | `_on_login` instancia o TL request. Isso sozinho não prova envio. |
| Encaminhamento | `__call__` delega a `_call`; há resolução, controles de FloodWait e possibilidade de erro. |
| Enfileiramento | `client/users.py:72` chama `sender.send`; o sender normal serializa/cria `RequestState` e enfileira em `network/mtprotosender.py:165–201`. |
| Transmissão | Depende do transporte e de sua tarefa de envio. Não observada nesta auditoria. |
| Resposta/processamento | `_call`, linhas 92–94, aguarda resultado e chama `session.process_entities(result)` antes de retornar. |

Consequentemente, um recorder antes do transporte prova uma **tentativa encaminhada**, não necessariamente bytes enviados. Zero requests em uma conexão que falhou antes da descoberta não satisfaz o requisito funcional.

### B.4. receive_updates e catch_up

`receive_updates=False` define `_no_updates=True`. Em `client/users.py:59–64`, o request é envolvido em `InvokeWithoutUpdatesRequest`; a inicialização recebe tratamento equivalente em `telegrambaseclient.py:607–611`.

O protocolo define `invokeWithoutUpdates` como invocação sem inscrever a conexão para updates; o retorno continua sendo o retorno da consulta interna. Portanto, não é um filtro que transforma `GetDifference` em operação sem conteúdo. Fonte: [invokeWithoutUpdates](https://core.telegram.org/method/invokeWithoutUpdates).

`set_receive_updates(False)` também não elimina o caminho inicial; depois de `connect()`, seria tarde para impedir o RPC já solicitado. A [documentação pública do cliente](https://docs.telethon.dev/en/stable/modules/client.html) apresenta essas opções como controle de recebimento/catch-up, não como allowlist de RPCs.

`catch_up=False` impede o carregamento de estados nesse trecho de `connect()` e o catch-up inicial opcional. Com `True`, `client/updates.py:275–278` chama `catch_up()`, que enfileira `UpdatesTooLong`, linha 261. Logo, carregar um estado genuíno pode evitar `_on_login`, mas não oferece zero diferenças durante o ciclo completo.

### B.5. Caminhos posteriores, não cobertos pela exceção “somente restore”

**FACT:** `client/updates.py:_update_loop` consulta `MessageBox.get_difference()` nas linhas 313–317 e `get_channel_difference()` nas linhas 368–372. Não há teste `_no_updates` envolvendo esses caminhos.

Em `_updates/messagebox.py`:

- `NO_UPDATES_TIMEOUT = 15 * 60`, linha 46;
- `check_deadlines()`, linhas 256–292, marca entradas vencidas como necessitando diferenças;
- `get_difference()`, linhas 608–624, constrói o RPC correspondente.

**INFERENCE sustentada pelo código:** uma instância que permaneça conectada suficientemente tempo, com estado global carregado e sem atualização do deadline, pode solicitar diferenças mesmo com `receive_updates=False`. Não é necessário ter handlers registrados. Lacunas também podem disparar recuperação.

Além disso, `client/dialogs.py:_DialogsIter._load_next_chunk`, linhas 85–88, introduz estados de canal no MessageBox a partir de `dialog.pts`. Portanto, `iter_dialogs` não é neutro em relação ao mecanismo interno de updates. Há também risco de `GetChannelDifference` posterior, sujeito às condições do loop, ao tempo e à disponibilidade das entidades.

Desconectar antes de pedir a seleção local reduz esse risco operacional. Um deadline inferior a 15 minutos não deve ser vendido como prova universal: há outros gatilhos, atrasos e mudanças de versão.

### B.6. StringSession, Session e DPAPI

`sessions/string.py`, linhas 29–64, serializa versão de formato, DC, endereço, porta e auth key. Não serializa update states, entidades ou takeout ID. A base `MemorySession` começa com `_update_states={}`, em `sessions/memory.py:27–40`.

É importante separar:

- **Session:** pode manter estados por `get_update_state`, `set_update_state`, `get_update_states`.
- **Cliente em memória:** MessageBox, caches, tarefas e deadlines são estruturas próprias.
- **StringSession exportada:** contém autenticação/conexão; não é snapshot completo das estruturas acima.

`SQLiteSession` oficialmente persiste estados, em `sessions/sqlite.py:221–245`. A API de Session customizada também é suportada e documentada em [Session Files](https://docs.telethon.dev/en/stable/concepts/sessions.html). Mas o carregamento e o catch-up do cliente continuam sendo os descritos acima.

Trocar por SQLite em disco não preserva automaticamente a segurança atual: `sessions/sqlite.py:210–217` grava a auth key na tabela. Criptografar somente depois de fechar não elimina exposição anterior de banco/journal. Uma Session customizada poderia proteger autenticação e cursores via DPAPI sem banco em claro, mas exigiria formato, migração, escrita atômica e testes de regressão; não resolveria por si só zero diferenças.

No projeto, `telethon_gateway.py:_new_client`, linha 111, usa o cliente padrão sem especificar `receive_updates` ou `catch_up`: os defaults são `True` e `False`. `restore`, linha 261, conecta e depois chama `get_me`. `_confirm_and_save`, linha 233, exporta a string para o vault. `telethon_session.py:525–564` protege/desprotege esse texto usando DPAPI.

**Conclusão:** StringSession é causa relevante da perda de estado entre instâncias, mas não é defeito de autenticação nem causa única. Preservar cursores inventados para manipular `is_empty()` seria mascarar o estado; não é solução recomendada.

## C. Previous Attempts Adjudication

| Tentativa | O que demonstrou | O que não demonstrou / adjudicação |
|---|---|---|
| Inspeção de `connect` e `_on_login` | Caminho inicial real no código; hashes conferem. | Não prova transmissão em uma execução anterior. Diagnóstico central correto. |
| `receive_updates=False` | Wrapper público para não inscrever a conexão. | Não suprime consulta explícita de diferenças nem todo o loop interno. Não repetir como candidato isolado a zero RPC. |
| `catch_up=False` | Evita o catch-up inicial opcional. | Não evita `_on_login`, deadlines ou lacunas. |
| Filtro broadcast/megagroup | Pode proteger a saída funcional da descoberta. | Não filtra payload anterior ao adapter nem requests de inicialização. |
| DTOs apenas com metadados | Fronteira apropriada para aplicação e domínio. | Não reduz retroativamente transferência/desserialização pela biblioteca. |
| Reuso da StringSession protegida | S1-C aceitou autenticação e reutilização segundo evidências registradas. | Não prova persistência de cursores de updates; não há contradição entre autenticação funcionar e MessageBox vazio. |
| Proactor e Selector | Relatórios registram bloqueio na criação de socketpair/accept. | Não avaliam a solução Telethon. Trocar o loop não resolveu naquele contexto. |
| ENV-01 fora da restrição | O pedido atual relata loopback/socketpair/asyncio e teste focado funcionando fora do executor restrito. | Não prova causa específica da restrição nem conclusão da suíte completa. Evidência fornecida pelo usuário, não repetida aqui. |
| Última prova sintética | Relatório registra uma tentativa interrompida sem trace. | Não caracteriza zero RPC, incompatibilidade do candidato nem defeito do Python. Causa do silêncio continua UNKNOWN. |
| Workarounds privados | Identificação de alternativas teoricamente possíveis. | Nenhuma implementação ou sustentabilidade demonstrada. |
| Aceitar diferenças incidentais | Alternativa de produto tecnicamente plausível. | Não foi aprovada; precisa abranger e testar o lifecycle, não só `_on_login`. |

O desenho da última prova reuniu conexão, autorização, descoberta, tarefas e desconexão antes de produzir evidência útil. Isso dificultou localizar a falha. **HYPOTHESIS**, não diagnóstico: fake incompleto, Future sem resolução, tarefa de background/cleanup pendente, buffering da saída ou problema do executor podem explicar o silêncio. O código transitório completo e uma stack dessa tentativa não estão no relatório consultado; não é possível escolher uma dessas causas.

Os testes existentes do gateway usam `FakeClient.connect()` (`tests/unit/test_telethon_gateway.py:47–74`). São válidos para o contrato do gateway, mas não exercitam `TelegramClient.connect()` e não respondem a OPEN-04.

Não vale repetir a suíte inteira, reinstalar dependências, alternar Proactor/Selector ou refazer uma prova monolítica para decidir se o wrapper remove `GetDifference`: o código já esclarece isso.

Há uma divergência de atualização documental: o state/relatório de S1-TEST-01 consultado ainda registra o diagnóstico anterior, enquanto o pedido atual informa ENV-01, teste focado aprovado e timeout de 180 segundos. Esses novos fatos são tratados como evidência fornecida pelo usuário; não foram reconciliados silenciosamente. FULL_PYTEST permanece pendente, sem causalidade atribuída a WinError 10013.

## D. Solution Comparison

### D.1. Viabilidade e riscos

| Alternativa | Viabilidade / API privada | Complexidade e manutenção | Privacidade |
|---|---|---|---|
| **A — Zero GetDifference com configuração pública atual** | Não encontrada solução suficiente. `receive_updates=False` + `catch_up=False` não atende. Patches em `_on_login`, MessageBox ou sender seriam privados. | Configuração é simples, mas insuficiente; workaround privado tem custo alto e revisão por versão. | Zero diferenças reduziria coleta desnecessária, mas não removeria conteúdo incidental já aceito de getDialogs. |
| **B — Outra Session/lifecycle** | Session customizada é pública; persistência genuína é possível. `catch_up=True` pode evitar o caminho inicial e recuperar diferenças depois. Reuso da mesma instância apenas desloca inicialização. | Média/alta: schema, migração DPAPI, consistência, invalidação, regressão. | SQLite padrão adiciona persistência sensível; snapshot protegido limita isso, sem garantir zero payload. |
| **C — Cliente isolado de descoberta** | Viável como instância dedicada e sem handlers; usa o mesmo `connect`. Não resolve zero RPC sozinho. | Baixa/média se reutilizar gateway/vault; alta se duplicar autenticação ou criar processo/serviço sem necessidade. | Reduz mistura de handlers/caches e tempo de retenção; não impede transferência interna. |
| **D — Aceitar diferenças incidentais com fronteira rigorosa** | Compatível com o cliente atual, sem overrides privados em produção. Exceção só para restore é insuficiente; aceitação deve ter escopo explícito de lifecycle. | Menor custo estrutural; exige testes de fronteira, erros e comportamento por versão. | Aceita conteúdo adicional transitório no processo, potencialmente fora dos canais elegíveis. Não equivale a zero coleta. |
| **E — Outra integração/biblioteca** | Não há candidato validado nesta revisão. RPC direto pelo mesmo TelegramClient continua passando por connect; sender próprio é integração de baixo nível. | Alta: autenticação, sessão, Windows, packaging, scanner/downloads e segurança precisam de revalidação. | Não há garantia de menor coleta; outra biblioteca pode sincronizar/persistir mais dados. |

### D.2. Compatibilidade, evidências e autoridade

| Alternativa | Auth e S1-D | Evolução futura | Evidência / aprovação necessária |
|---|---|---|---|
| A | Baseline de auth preservável, mas descoberta não atende zero RPC com as opções revisadas. | Restrição teria de ser reavaliada para sync em S7. | Candidato público concreto e prova do ciclo inteiro antes de implementar; não autorizar patch privado por inferência. |
| B | Pode preservar a auth key, mas altera contrato de storage e migração; blob atual não contém cursores. | Persistir estado pode fazer sentido quando updates forem necessidade funcional real. | Decisão arquitetural, regressão S1-A/B e reautenticação. Não escolher apenas para OPEN-04. |
| C | Compartilha vault e fluxo existente; não faz login inline. | Perfis separados por operação são úteis para scanner/download sem duplicar domínio. | Aprovação do perfil e integração; combinar com A ou D, pois isolamento não decide política de payload. |
| D | Preserva formato DPAPI e semântica de auth; modifica requisito de OPEN-04. | Mantém seam do gateway e evita acoplamento ao MessageBox; scanner/sync têm contratos próprios. | Aprovação explícita de privacidade/produto; testes offline e validação real separada. |
| E | Migração material e possível reautenticação. Bot API não é substituta da enumeração de diálogos da conta de usuário. | Potencial benefício só mediante outras necessidades concretas. | Novo escopo de avaliação e decisão arquitetural; Pyrogram já rejeitado e TDLib diferido pela arquitetura vigente. |

Uma classe base customizada, um antigo “bare client” ou transporte MTProto próprio não constitui solução pública pronta para esse fluxo. Não foi encontrada uma opção documentada equivalente a “restaurar autenticação e executar RPCs sem iniciar gerenciamento de updates” no TelegramClient instalado.

## E. Recommended Architecture

### E.1. Escolha preferencial, condicionada à aprovação

**D combinada com o isolamento simples de C:** uma instância de descoberta de vida limitada, criada pelo adapter, usando o vault e StringSession existentes, com tipos próprios na saída. Sem novo serviço, dependência ou formato de sessão.

Componentes conceituais:

- Aplicação de descoberta coordena orçamento, cancelamento e resultado.
- `TelethonGateway` continua dono exclusivo do cliente e dos tipos TL.
- Factory/perfil de descoberta configura explicitamente `receive_updates=False`, `catch_up=False`, mantém controles atuais de retry e logger isolado, e não registra handlers/conversations.
- `restore` reutiliza a sessão; ausente/inválida encaminha ao comando `auth`, sem login duplicado.
- Descoberta projeta somente `telegram_chat_id`, título, username opcional e tipo próprio broadcast/megagroup.
- Desconecta **antes da espera por escolha humana**, pois a seleção já é local por ID. Evita manter a conexão viva enquanto a CLI espera entrada.
- `finally` cobre falha, cancelamento e limpeza; o prazo inclui conexão e desconexão. Não manter cliente residente entre comandos apenas para evitar uma nova inicialização.

As configurações existentes de `flood_sleep_threshold=0`, `request_retries=1`, `connection_retries=1`, `raise_last_call_error=True` e `auto_reconnect=False` devem ser preservadas como ponto de partida. Elas não comprovam uma única tentativa de rede, ausência de retry no loop de updates ou um teto exato de RPCs internos.

O algoritmo de paginação continua dependente de OPEN-03. `iter_dialogs` tem menor código próprio, mas inicializa mensagens e estado de canais dentro da biblioteca. Paginação raw facilita contar páginas, mas transfere semântica de offsets ao adapter. Não usar raw apenas como suposto remédio para OPEN-04: o connect continua igual. Se raw for escolhido, distinguir processamento de IDs/datas necessário à paginação de interpretação de texto/mídia; essa fronteira precisa constar do contrato.

### E.2. Análise de ameaça e minimização

| Camada | Consequência / controle recomendado |
|---|---|
| Transferência | Diferenças podem transportar conteúdo fora dos candidatos. Não há filtro por canais elegíveis nesse RPC. Aprovação precisa reconhecer essa exposição. |
| Telethon | Desserializa respostas, processa entidades e pode processar updates internamente. Ausência de handlers não significa ausência de processamento. |
| Adapter | Não interpreta texto, mídia ou conteúdo de diferenças; não entrega objetos TL; projeta metadados permitidos de descoberta. |
| Aplicação/domínio | Recebem apenas DTOs próprios; nenhum callback de mensagens, parser, scanner ou downloader é acionado em S1-D. |
| Persistência | Manter somente a string protegida conforme o fluxo autorizado; nenhum cache persistente de mensagens/entidades é introduzido. StringSession mantém entidades em memória, mas não as exporta. |
| Logging | Preservar logger da biblioteca isolado e diagnósticos sanitizados; não logar repr de requests, respostas, exceções ou payloads. Testar também falhas. |
| Downloads/ações remotas | Diferença não é autorização para download, leitura explícita de histórico, join, mark-as-read ou administração. Métodos correspondentes continuam proibidos na aplicação. |

**INFERENCE de segurança:** a proibição absoluta tem benefício material de minimização: reduz dados presentes na memória, superfície de desserialização e impacto de captura indevida por debug/crash dump. Não é uma exigência absurda. Entretanto, não é tecnicamente necessária para enumerar os diálogos nem suficiente para garantir ausência de mensagens, porque getDialogs já inclui payload incidental aprovado. A API de [getDialogs](https://core.telegram.org/method/messages.getDialogs) não exige como parâmetro um estado produzido por GetDifference.

Uma fronteira correta reduz fortemente exposição funcional, persistência e logging, mas não é equivalente a impedir a transferência. DPAPI protege o material em repouso; não protege todo objeto de mensagem dentro do processo. Descartar referências também não equivale a apagar criptograficamente a memória Python.

Para esta ferramenta enxuta, considero D+C o melhor equilíbrio **se essa exposição transitória for aceitável ao usuário**. Se a restrição representar uma obrigação rígida de minimização, D não atende; não cabe ao parecer dispensá-la.

### E.3. Longo prazo e contrato

Não há justificativa suficiente para migrar a sessão agora. Persistência de cursores deve ser reconsiderada quando houver requisito real de sincronização, especialmente S7, com formato protegido e comportamento de recuperação definidos.

Windows/Python 3.14 continuam requerendo validação no contexto executor funcional. Nenhuma mudança global de asyncio é proposta. `cryptg` não decide o fluxo de updates. A faixa atual de dependência admite novos patches de Telethon 1.45.x; revalidar estes caminhos quando a versão instalada mudar, sem assumir equivalência.

Não modificar o fluxo de auth globalmente apenas para a descoberta: `receive_updates=False` pode afetar recursos que dependam de updates. Regressões do gateway e do vault serão necessárias se a implementação compartilhada ganhar um perfil, sem revogar os PASS históricos de S1-A/B/C.

**Impacto contratual inevitável para D:** substituir “zero GetDifference” por invariantes verificáveis de não uso de conteúdo pela aplicação e aceitação explícita do processamento incidental da biblioteca no lifecycle delimitado. Não prometer “nenhuma sincronização interna”, “somente um RPC” ou “somente durante restore”.

Se a aprovação for somente para a chamada inicial, D+C ainda não está comprovada como suficiente. Seria necessário demonstrar tecnicamente essa restrição adicional ou manter OPEN-04 aberto.

## F. Minimal Validation Plan

**Plano proposto, não executado.** Não é necessário mais experimento para concluir que o wrapper não remove o RPC. Execução futura deve ocorrer somente sob autorização delimitada. A primeira prova deve caracterizar o comportamento, não tentar obter zero a qualquer custo.

### F.1. Prova mínima sem event loop nem sockets

**Hipótese:** `_on_login` real encaminha `GetState` e `GetDifference` sequencialmente quando recebe respostas sintéticas válidas.

Harness transitório, sem arquivo de sessão ou acesso ao vault real:

1. Executar o corpo real de `AuthMethods._on_login` sobre objeto de teste mínimo.
2. Substituir somente a fronteira de invocação por awaitable de resposta imediata que registre o tipo do request; fornecer usuário, State e DifferenceEmpty sintéticos.
3. Registrar a chamada a `MessageBox.load` por fake nesse teste específico. Não usar esse fake para provar semântica do MessageBox.
4. Avançar a coroutine diretamente, sem `asyncio.run`, pois todos os awaits do harness se completam imediatamente. Suspensão inesperada é falha imediata, não espera indefinida.
5. Esperado: `GetStateRequest → GetDifferenceRequest → load`, com os cursores sintéticos propagados corretamente.

Limite: prova apenas a lógica do método; não prova connect, wrapper, transporte, background ou ausência de RPC em produção. O positivo conhecido evita um teste que passe porque não exercitou o caminho.

### F.2. Caracterização delimitada do ciclo real da biblioteca

Após autorização, em executor comprovadamente funcional, uma única bateria curta com o `TelegramClient.connect`, `get_me`, `_on_login`, `UserMethods._call` e lógica de updates reais. Fake **somente no sender/transport e relógio de teste**, não nos métodos cuja decisão se quer observar.

- `sender.send` deve respeitar o contrato síncrono de retornar um awaitable/Future resolvido; requests desconhecidos falham imediatamente.
- Desembrulhar recursivamente `InvokeWithLayer`, `InitConnection` e `InvokeWithoutUpdates` ao contar métodos internos.
- Registrar somente tipos e ordem em stdout sem buffering; imprimir um marco antes da criação do loop e antes/depois de cada fase.
- Um supervisor externo encerra após, por exemplo, 10 segundos por caso; timeout dentro do loop não cobre travamento no construtor do próprio loop. Preservar stack, stderr e exit code sanitizados.

Casos mínimos, sem se tornar uma sequência aberta:

| Caso | Resultado observável esperado / critério |
|---|---|
| StringSession sintética válida, estado vazio, updates desligados, catch-up desligado | Controle positivo: GetDifference encaminhado durante connect; wrapper preserva request interno. |
| Sessão de teste com estado genuinamente modelado, catch-up desligado e ligado | Distinguir estado ignorado de estado carregado; observar também o catch-up posterior, sem encerrar a prova logo após connect. Dados fabricados são fixtures, não proposta de estado inventado em produção. |
| MessageBox real com deadline avançado pelo relógio de teste | Exercitar marcação de diferença e request do loop, sem esperar 15 minutos reais. |
| Sessão não autorizada / erro de RPC | Falhar antes da descoberta; zero requests por falha não é sucesso funcional. |
| Disconnect/cancelamento | Nenhuma tarefa órfã; trace distingue falha principal de falha de limpeza. |

Para avaliar `GetChannelDifference`, incluir estado de canal e entidade sintéticos equivalentes aos introduzidos por `iter_dialogs`; observar as condições do caminho real. Não confundir prova de conta com prova de todos os updates.

### F.3. Fronteira do adapter, após autorização de implementação

Injetar respostas com canários sintéticos em texto, mídia, drafts e entidades de diálogos privados. Verificar que:

- DTOs/CLI contêm apenas metadados permitidos dos canais elegíveis;
- nenhum canário aparece em logs, exceções públicas ou persistência;
- nenhum método de histórico, download, join ou administração é acionado;
- seleção por ID ocorre depois do encerramento da conexão;
- limites/cancelamento produzem resultado parcial ou falha conforme o contrato;
- auth e proteção da sessão continuam passando em seus testes pertinentes.

Isso valida contenção de dados; não prova que a biblioteca nunca recebeu mensagens.

### F.4. STOP e critérios de decisão

STOP em tentativa de rede real, acesso a vault/credencial real, request desconhecido, primeira exceção inesperada, suspensão sem resolução, timeout ou tarefa sobrevivente. Não repetir automaticamente nem expandir para full pytest ou reparo do Windows.

Se surgir um candidato de zero RPC, ele precisa ter **descoberta concluída**, contagem interna zero para os métodos proibidos, cleanup concluído e cobertura de background/falhas; um fake de `connect()` ou execução abortada não serve. Nenhum candidato público suficiente foi identificado para submeter a esse aceite agora.

Validação real posterior requer autorização própria e observação sanitizada de métodos, sem captura de conteúdo. Uma execução real bem-sucedida não prova ausência universal em todos os timings. OPEN-03, GOV-01 e a investigação do timeout da suíte continuam atividades separadas.

## G. Decision Required From User

**Pode ser decidido tecnicamente agora:** descartar as duas flags isoladas como solução de zero diferenças; não migrar Session somente por OPEN-04; não repetir provas monolíticas; não aceitar uma exceção “somente restore” como suficiente sem evidência adicional; manter DPAPI/gateway e seleção local.

**Decisão humana material:** escolher entre manter a proibição absoluta ou aceitar transferência e processamento internos incidentais de diferenças pela biblioteca durante a operação delimitada de descoberta, reconhecendo que podem abranger dados fora dos canais elegíveis.

Para a alternativa recomendada, proponho uma nova **DEC-S1D-03**, ainda **não aprovada**, com escopo explícito:

> Permitir que o Telethon processe respostas incidentais de diferenças durante o lifecycle delimitado da descoberta, inclusive caminhos internos de updates avaliados e abrangidos pela decisão, sem uso de conteúdo pelo adapter/aplicação, persistência, logging, exposição ou ação remota derivada. Manter updates não solicitados desabilitados, catch-up opt-in desabilitado e desconexão antes da seleção local. A decisão deve declarar expressamente se inclui GetChannelDifference; não presumir sua autorização por aceitar GetDifference.

Esta é uma proposta de decisão, não uma autorização nem garantia já testada. Seu escopo final deve ser aceito pelo usuário. Autorizar somente GetDifference inicial deixa o problema de lifecycle pendente.

DEC-S1D-01 não precisa ser reescrita: continua específica ao payload de getDialogs. DEC-S1D-02 permanece integral. Contudo, adotar D altera a escolha registrada de OPEN-04 (`PROVE_AVOIDANCE_OF_GETDIFFERENCE`) e exige registro explícito dessa revisão; não é possível afirmar preservação integral de todas as restrições atuais.

Se a proibição for mantida, nenhuma decisão aprovada precisa mudar, mas OPEN-04 continua aberto sem solução pública suficiente. A menor ação adicional seria autorizar avaliação de um mecanismo upstream público específico quando houver candidato concreto, não uma nova rodada indefinida de tentativas.

Não foi editado PROJECT_STATE, contrato, approvals, policies, pins ou binding. O pedido autorizou a auditoria e depois seu armazenamento em `docs/audit`; não autorizou adoção da recomendação ou reconciliação de decisões. Este parecer não fecha OPEN-04, S1-D ou S1, nem atesta integridade de governança. A eventual reconciliação canônica deve ocorrer após a decisão correspondente.

## H. Final Telemetry

```text
ACTIVITY = S1-D Independent Architecture Review
STATUS = PASS / auditoria entregue; não significa solução de zero RPC validada
ACTIVITY_COMPLETION_PERCENT = 100%
TELETHON_VERSION_VERIFIED = 1.45.0 / source e metadata locais; sem import runtime
PREVIOUS_DIAGNOSIS_VERDICT = PARTIALLY_CORRECT / caminho inicial confirmado; lifecycle ampliado
GET_DIFFERENCE_CALL_PATH = STATICALLY_CONFIRMED / startup e background; sem captura de rede
GET_DIFFERENCE_AVOIDANCE = NOT_DEMONSTRATED
PUBLIC_API_ALTERNATIVE = NOT_FOUND_IN_REVIEW para zero RPC no lifecycle atual
RECOMMENDED_ARCHITECTURE = D_PLUS_C / StringSession DPAPI + gateway + instância delimitada; depende de decisão
SECURITY_PRIVACY_IMPACT = ADDITIONAL_TRANSIENT_LIBRARY_PAYLOAD_REQUIRES_EXPLICIT_ACCEPTANCE
PRIVATE_INTERNALS_REQUIRED = NO_FOR_RECOMMENDED_PRODUCTION_DESIGN / test seams somente no harness
NEW_DEPENDENCIES_REQUIRED = NO_FOR_RECOMMENDED_DESIGN
MATERIAL_USER_DECISION_REQUIRED = YES / proibição absoluta versus payload incidental no lifecycle
OPEN04_RECOMMENDED_DISPOSITION = REMAIN_OPEN_PENDING_EXPLICIT_DECISION_AND_VALIDATION
OPEN03_STATUS = PENDING_MEASUREMENT
GOV01_STATUS = UNRESOLVED
FULL_PYTEST = PENDING_REVALIDATION
S1D_CONTRACT = DRAFT / NOT_FROZEN
S1D_IMPLEMENTATION = NOT_AUTHORIZED
SOURCE_CHANGES = NONE
TEST_CHANGES = NONE
AUDIT_DOCUMENT = CREATED_BY_EXPLICIT_USER_REQUEST
GOVERNANCE_AND_CONTINUITY_WRITES = NONE
PROJECT_STATE_RECONCILIATION = NOT_PERFORMED / no decision adopted; read-only authority scope
REAL_TELEGRAM_ACCESS = NO
REAL_SESSION_AND_CREDENTIAL_ACCESS = NO
EXECUTION_PROBES = NONE
GIT_WRITES = NONE / no staging, commit, push or other Git mutation
FINAL_VERDICT = REVIEW_COMPLETE / current flags and session swap do not establish zero differences
NEXT_ACTION = User adjudicates OPEN-04 scope; then authorizes bounded validation separately
```

### Fontes locais principais

- [Estado e safe resume](../continuity/PROJECT_STATE.md), [mapa de authorities](../continuity/ACTIVE_AUTHORITY_MAP.md), [binding](../continuity/PROJECT_GOVERNANCE_BINDING.json), [continuidade](../continuity/CONTINUITY_RECORD.md), [handoff](../continuity/handoff/LAST_HANDOFF.md).
- [Contrato S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md), [decisões](../governance/APPROVALS_AND_DECISIONS.md), [arquitetura](../architecture/ARCHITECTURE.md), [roadmap](../continuity/planning/ROADMAP.md), [sprints](../continuity/planning/SPRINTS.md).
- [Investigação OPEN-04](../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md), [diagnóstico S1-TEST-01](../reports/S1_TEST_01_PYTEST_ENVIRONMENT_DIAGNOSIS_2026-10-08.md).
- [Gateway](../../src/telegram_courses/telethon_gateway.py), [vault](../../src/telegram_courses/telethon_session.py), [testes do gateway](../../tests/unit/test_telethon_gateway.py).
- Código instalado em `.venv-replay/Lib/site-packages/telethon/`, arquivos/métodos/linhas identificados na seção B. A instalação local não é artefato versionado; os hashes dos três arquivos centrais foram registrados acima.
