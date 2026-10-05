# Bootstrap de recuperação do projeto

DOCUMENT_ROLE = BOOTSTRAP  
PROJECT_ID = projeto_telegram_courses  
FIRST_RESPONSE_MODE = READ_ONLY_RECOVERY

1. Verifique workspace e leia [PROJECT_STATE.md](PROJECT_STATE.md), [AUTHORITY_MAP.md](AUTHORITY_MAP.md) e [START_HERE.md](../START_HERE.md). A raiz equivalente é docs/; caminhos WORK/HOME dependem do ambiente.
2. Localize docs/governance/PROJECT_GOVERNANCE_BINDING.json quando existente; valide pelo schema externo real do Continuity 3.0 e verifique todos os pins por id + version + sha256. Ausência/falha é reportada; não invente binding/pins.
3. Resolva current global por Matrix/Registry separadamente. Não migre baseline adotado nem use policies antigas como defaults.
4. Leia [CONTINUITY_RECORD.md](CONTINUITY_RECORD.md), authorities de domínio e planos do mapa; confira blocker/evidências, autorização e safe resume no estado primário.
5. Faça inspeção Git read-only quando disponível; ausência de Git não autoriza init/clone nem criação de branch/HEAD fictício.
6. Execute Continuity no modo FIRST_ADOPTION_OR_AGENT_CHANGE e VP-01 read-only quando pertinente; reporte limites/contradições e solicite validação humana quando exigida, depois de concluir o trabalho de recuperação possível.

Este bootstrap é procedimento. Não edite estado, implemente, inicie unidade ou publique sob autorização apenas de recuperação. Uma nova instrução explícita pode autorizar atividade documental distinta; mantenha seu escopo separado. READINESS != AUTHORIZATION; recuperação PASS não concede implementação/publicação.
