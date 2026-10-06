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
   [S0_SETUP](../development/S0_SETUP.md) e execute
   `SP01-PREFLIGHT-ROOT`; qualquer falha encerra os passos dependentes.
6. Somente com PASS no preflight, prossiga para SP01-01.
7. Para qualquer publicação Git, exija autorização específica para a
   atividade e operação.

Histórico de chat pode servir como contexto adicional, mas não é necessário
para descobrir o estado e retomar a partir das authorities governadas.
