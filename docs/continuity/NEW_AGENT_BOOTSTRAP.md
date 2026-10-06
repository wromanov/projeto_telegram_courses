# Bootstrap de novo agente

Este arquivo define o procedimento de retomada; não é uma authority de estado
ou de produto.

1. Leia [PROJECT_STATE.md](PROJECT_STATE.md),
   [ACTIVE_AUTHORITY_MAP.md](ACTIVE_AUTHORITY_MAP.md) e
   [START_HERE.md](START_HERE.md).
2. Verifique em runtime o root, branch, HEAD, upstream e worktree. Compare os
   fatos com `PROJECT_STATE`; não confie em hashes salvos sem consultá-los.
3. Carregue apenas as authorities necessárias à atividade, conforme o mapa.
   O binding e pins atuais estão em
   [PROJECT_GOVERNANCE_BINDING.json](PROJECT_GOVERNANCE_BINDING.json).
4. Confira readiness, autorização, blockers e o
   [SAFE_RESUME_POINT](PROJECT_STATE.md). Preserve os checkpoints válidos e
   decisões fechadas.
5. Para S0, consulte o contrato aprovado e
   [S0_SETUP](../development/S0_SETUP.md). Refaça
   `SP01-PREFLIGHT-ROOT`; se passar, siga somente para SP01-01. Qualquer
   falha encerra os passos dependentes.
6. Continue somente dentro da autorização vigente. O Card B atual autoriza
   um stage seletivo, um commit e um push somente para este checkpoint de
   continuidade; não autoriza implementação, testes, SP-01 ou publicação
   adicional.

Histórico de chat pode servir como contexto adicional, mas não é necessário
para descobrir o estado e retomar a partir das authorities governadas.
