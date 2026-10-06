# AGENTS.md — Projeto Telegram

## 1. Finalidade

Este arquivo é o entrypoint e guardrail operacional para agentes do Projeto Telegram.

Ele deve permanecer curto: resume regras estáveis, orienta a descoberta das authorities aplicáveis e aponta para as fontes canônicas. Policies, protocolos, contratos e authorities específicas do projeto prevalecem em caso de conflito.

`AGENTS.md` não é uma segunda policy.

---

## 2. Inicialização e ordem mínima de leitura

Em nova sessão, novo agente ou retomada após interrupção:

1. confirmar factual state do repositório quando Git estiver disponível:
   - repo root;
   - branch;
   - `HEAD`;
   - worktree/staging;
2. localizar o pacote de continuidade do projeto por papel semântico, preferindo `docs/continuity/` quando essa for a convenção ativa;
3. resolver, conforme disponibilidade e aplicabilidade:
   - `PROJECT_GOVERNANCE_BINDING`;
   - `PROJECT_STATE`;
   - `ACTIVE_AUTHORITY_MAP`;
   - `CONTINUITY_RECORD`;
   - `ROADMAP`;
   - `EXECUTION_PLAN` / `SPRINTS`, quando aplicável;
   - `NEW_AGENT_BOOTSTRAP`;
   - `LAST_HANDOFF`, quando aplicável;
   - `SAFE_RESUME_POINT`;
4. resolver a Governance Baseline adotada pelo projeto por meio do binding/authority map;
5. carregar somente as policies materialmente aplicáveis à atividade;
6. usar o protocolo canônico de continuidade vigente para recuperação/reconciliação quando aplicável;
7. somente então retomar a atividade autorizada.

Não depender do histórico de chat para reconstruir o estado do projeto.

Se existir uma authority específica do Telegram para continuidade/handoff, como
`docs/projeto/Telegram_CONTINUITY_AND_HANDOFF_RULES_V1.md`, sua vigência deve ser confirmada pelo `ACTIVE_AUTHORITY_MAP` antes de tratá-la como authority ativa.

---

## 3. Authority

- O usuário é a autoridade final sobre produto, escopo, arquitetura, roadmap, commits, push, LIVE, encerramento de sprint/delivery unit e governança.
- Agentes, modelos, skills, plugins e runtime não criam authority.
- Ausência de authority deve ser explicitada; usar `DEFERRED_NO_AUTHORITY` quando aplicável.
- Falsa authority e falsa capability são proibidas.
- Readiness, recovery ou validação técnica não equivalem automaticamente a autorização de implementação, avanço ou publicação Git.

---

## 4. Independência analítica

Não concordar automaticamente.

Quando material, distinguir:

`FATO`
`EVIDÊNCIA`
`INFERÊNCIA`
`HIPÓTESE`
`PREFERÊNCIA`
`RECOMENDAÇÃO`
`DECISÃO`

Seguir a policy canônica de independência analítica vigente.

---

## 5. Model / Effort / Multiagent / Skills

Os eixos são independentes:

`ROLE != MODEL != EFFORT != TOOL_SURFACE`

`MODEL / EFFORT` define capacidade e deliberação.

`MULTIAGENT` define estratégia de execução.

`SKILLS / PLUGINS / TOOLS` definem capacidades especializadas disponíveis no runtime.

Regras operacionais:

- usar a menor capacidade suficiente;
- `DIRECT` é o modo padrão;
- mudar de `DIRECT` para `MULTIAGENT` durante a execução requer autorização do usuário;
- após `MULTIAGENT` já estar autorizado, o root pode criar subagentes bounded dentro do escopo aprovado quando houver ganho material, sem pedir aprovação por spawn individual;
- delegação recursiva permanece desabilitada por padrão;
- a disponibilidade de um role não garante modelo, effort ou ferramenta específica;
- verificar capabilities reais no runtime quando forem necessárias;
- não alegar economia de tier sem evidência do modelo realmente usado;
- carregar somente authorities e instruções materialmente relevantes;
- evitar repetir policies inteiras no prompt quando referência suficiente resolver.

Roteamento cognitivo e efforts devem seguir as policies canônicas vigentes, atualmente baseadas no baseline GPT-6.

---

## 6. Work / Codex

Escolher o ambiente pela natureza da atividade e pelas capabilities realmente disponíveis.

Usar Codex para engenharia, repositório, testes e Git quando apropriado.

Usar Work quando browser/computer use, arquivos, artifacts, workflows persistentes ou outras capacidades desse ambiente trouxerem benefício material.

A capability real do runtime prevalece sobre suposições baseadas no nome do agente ou ambiente.

---

## 7. Git e segurança

Antes de operações Git consequenciais:

- confirmar repo root, branch, `HEAD`, upstream e worktree;
- fazer staging explícito;
- nunca usar `git add .` como padrão;
- não executar automaticamente `reset`, `restore`, `clean`, `stash`, `amend` ou force push;
- commit e push exigem autorização explícita.

Nunca expor passwords, master keys, TOTP, recovery codes, tokens ou secrets.

Segredos locais permanecem fora do Git.

---

## 8. Continuidade

Git é a fonte factual para repo root, branch, `HEAD` e worktree quando disponível.

O estado lógico/técnico do projeto deve ser recuperado pelas authorities de continuidade vigentes, resolvidas pelo `PROJECT_GOVERNANCE_BINDING` e `ACTIVE_AUTHORITY_MAP`.

A documentação canônica mais recente adotada pelo projeto prevalece sobre memória conversacional.

Divergências devem ser investigadas, não reconciliadas silenciosamente.

`CONTINUITY_RECOVERY_GATE = PASS`
não significa automaticamente:

`IMPLEMENTATION_AUTHORIZATION = YES`

`GIT_PUBLICATION_AUTHORIZATION = YES`

`PHASE_ADVANCEMENT_AUTHORIZATION = YES`

A retomada deve partir do `SAFE_RESUME_POINT` validado.

---

## 9. Estado do projeto e fechamento de atividade

Atualizar/reconciliar `PROJECT_STATE` quando a atividade materialmente alterar o estado canônico do projeto.

Não criar microgate de atualização documental para ações triviais que não mudem estado, authority, planning, risco, decisão ou safe resume point.

Antes de declarar uma atividade formal concluída, quando houver alteração material de estado:

`PROJECT_STATE_RECONCILIATION = PASS`

evidência correspondente deve existir.

---

## 10. Comunicação

Responder em português do Brasil.

Preferir comunicação humana e intuitiva primeiro e estado técnico depois quando útil.

Preservar rigor, rastreabilidade e transparência sobre incerteza.

---

## 11. Prevalência

Ordem prática:

1. instrução explícita atual do usuário;
2. authorities canônicas específicas do projeto;
3. Governance Baseline adotada pelo projeto;
4. policies aplicáveis;
5. protocolo operacional aplicável;
6. este `AGENTS.md`;
7. convenções, templates e exemplos.

Em caso de conflito, não reconciliar silenciosamente.

`AGENTS.md` permanece entrypoint/guardrail e não deve reproduzir extensamente as policies canônicas.
