# S9 HML — análise do recibo G1

Run identificado pelo `run_id` informado na saída do operador. A leitura dos recibos, nomes de arquivos e ledger foi somente leitura; nenhuma credencial foi acessada e nenhuma execução foi retomada.

G0: recibo com `status=PASS`, `evidence_origin=HUMAN_INTERACTIVE` e `confirmation_source=INTERACTIVE_TTY`. Existe um evento de confirmação consumida; os eventos de preparação e persistência têm hashes iguais ao SHA256 dos bytes do recibo. Esta comparação não constitui, por si só, validação integral da cadeia do ledger.

G1: recibo do supervisor `stage=discovery`, `result=FAILED`, `reason=CHILD_EXIT_NONZERO`, `external_exit_code=125`; controles de processo, memória e auditoria passaram e o recibo foi persistido. O recibo de gate G1 informa `SUPERVISED_DISCOVERY_NOT_PASSED`. O arquivo `g1-worker-evidence.json` não existe; a pasta de trabalho G1 e a pasta HML de logs não apresentaram arquivos de log. O supervisor registra `network_observation=NOT_INSTRUMENTED_BY_SUPERVISOR`.

O código 125 tem mais de uma origem no bootstrap: rejeição da origem do módulo ou do ambiente, ou falha de finalização de logging. Uma falha anterior no worker também pode resultar em 125 se o logging ainda não tiver sido configurado. O recibo não identifica qual ramo ocorreu. Logo autenticação, rede, alias, manifesto e admissão do ledger não podem ser classificados como causa deste run. A existência ou ausência de RPC Telegram não é demonstrada por essa telemetria; ausência de evidência do worker não prova ausência de RPC.

```text
G1_ROOT_CAUSE = UNDETERMINED / CHILD_EXIT_125 / REASON_NOT_RECORDED
G0_PERSISTENCE = PASS_HASH_MATCH_AND_CONSUMED_EVENT / FULL_AUDIT_NOT_REPLAYED
REAL_TELEGRAM_RPC_OBSERVED = NOT_EVIDENCED / NETWORK_NOT_INSTRUMENTED
FIX_REQUIRED = UNDETERMINED / NO_CODE_CHANGE_WITHOUT_PROVEN_DEFECT
NEXT_NATIVE_COMMAND = NOT_RELEASED / DIAGNOSIS_INCOMPLETE
```

Não reiniciar o launcher para reproduzir. Nenhum código de produção ou contrato foi alterado nesta análise.
