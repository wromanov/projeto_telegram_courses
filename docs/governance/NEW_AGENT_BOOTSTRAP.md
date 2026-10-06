# Bootstrap de recuperação do projeto

DOCUMENT_ROLE = BOOTSTRAP  
PROJECT_ID = projeto_telegram_courses  
FIRST_RESPONSE_MODE = READ_ONLY_RECOVERY

1. Verifique workspace e leia [PROJECT_STATE.md](PROJECT_STATE.md), [AUTHORITY_MAP.md](AUTHORITY_MAP.md) e [START_HERE.md](../START_HERE.md). A raiz é docs/; o ambiente atual registrado é HOME.
2. Valide [PROJECT_GOVERNANCE_BINDING.json](PROJECT_GOVERNANCE_BINDING.json) pelo schema canônico Draft 2020-12 do Continuity 3.0; resolva cada pin por id + version + sha256. O binding atual adota GOVERNANCE_BASELINE V1 / contract 1 e Continuity 3.0.
3. Resolva current global por Matrix/Registry separadamente. Não migre baseline adotado nem use policies antigas como defaults. O estado atual registra GLOBAL_BASELINE_RELATION = CURRENT.
4. Leia [CONTINUITY_RECORD.md](CONTINUITY_RECORD.md), authorities de domínio e planos do mapa; confira evidências, readiness, autorização e safe resume no PROJECT_STATE.
5. Confirme Git facts no checkout HOME: master, HEAD e upstream conforme PROJECT_STATE; inspecione alterações locais antes de novas edições. Não faça init/clone, stage, commit ou push sem autorização específica.
6. Reexecute Continuity e VP-01 read-only se binding, authorities, estado, branch ou HEAD mudarem. O Opening Gate e o Continuity Recovery Gate atuais passaram; isso não autoriza S0, implementação ou publicação.

Este bootstrap é procedimento. Não implemente, inicie unidade ou publique sob autorização apenas de recuperação. READINESS != AUTHORIZATION; recuperação PASS não concede implementação/publicação. Leia prontidão, autorização e ponto seguro atuais em [PROJECT_STATE.md](PROJECT_STATE.md). O [contrato S0](../contracts/S0_IMPLEMENTATION_CONTRACT.md) existe como draft bloqueado; feche os gaps, obtenha aprovação do contrato e autorização da sprint antes de implementar. S0 não foi iniciado. A autorização posterior de stage/commit do pacote documental não aprova contrato, implementação ou push.
