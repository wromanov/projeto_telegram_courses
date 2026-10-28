# Mapa público de authorities ativas

```text
DOCUMENT_TYPE = PUBLIC_SANITIZED_DERIVATIVE
AUTHORITATIVE_SOURCE = LOCAL_CANONICAL
CANONICAL_SOURCE_AVAILABILITY = LOCAL_ONLY / OMITTED_FROM_PUBLIC_TREE
NOT_A_REPLACEMENT_FOR_LOCAL_AUTHORITY = YES
```

Este resumo identifica as fontes locais que governam o estado e as decisões do
projeto. Ele é informativo e não concede autoridade, acesso, aprovação ou
permissão. Em caso de divergência, prevalecem as authorities canônicas locais.

## Mapa por responsabilidade

| Responsabilidade | Fonte canônica local | Limite |
|---|---|---|
| Estado, gates, autorizações e ponto seguro de retomada | PROJECT_STATE canônico, mantido localmente | Fonte única do estado corrente do projeto. |
| Continuidade para retomada | CONTINUITY_RECORD canônico, mantido localmente | Referencia o estado; não cria um segundo estado. |
| Handoff vigente | LAST_HANDOFF canônico, mantido localmente | Resume a atividade mais recente e aponta para as authorities. |
| Baseline de governança adotada | PROJECT_GOVERNANCE_BINDING canônico, mantido localmente | Identifica a baseline; este derivado não altera seu binding. |
| Aprovações e decisões registradas | APPROVALS_AND_DECISIONS canônico, mantido localmente | Fonte decisória registrada. |
| Integridade e recuperação S6 | `docs/contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md` | V1 continua ativa; exceções de aceite não removem controles. |
| Baseline integrada S7/S8 | `docs/contracts/S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT.md` | Congelamento do contrato não autoriza iniciar S8. |
| Limites da seleção e execução S5 | `docs/contracts/S5_COURSE_SELECTION_PLANNER_QUEUE_CONTRACT.md` | Orçamentos e limites aprovados permanecem aplicáveis. |

O mapa completo, a navegação e as authorities adicionais permanecem nos
documentos canônicos locais, intencionalmente omitidos da baseline pública. Os
rótulos acima identificam fontes locais; não são links publicados. Este derivado
é informativo e não substitui essas authorities.

## Estado de alto nível

- S6: `CLOSED_WITH_EXCEPTIONS`; seu aceite não declara conformidade integral
  com V1.
- S7: `CLOSED_WITH_EXCEPTIONS`; critérios parciais e exceções permanecem
  registrados na authority decisória.
- V1 está ativa; V2 permanece globalmente desligada.
- S8 está diferida e sem autorização de implementação.

Este derivado não substitui qualquer fonte canônica nem altera decisões,
contratos ou limites do projeto.

## Artefatos da remediação de publicação

O relatório técnico da remediação offline e o manifesto integrado registram a
composição S6→S7. Para esta atividade, a decisão do usuário é
`OPTION_A_APPROVED`: stage, commit e push estão autorizados somente após os gates
previstos. A atividade está em andamento; nenhum commit ou push é declarado
concluído neste snapshot. `HISTORICAL_EXPOSURE` cobre somente metadados de
caminhos locais já presentes no histórico. Segredos ou novos dados sensíveis
não foram aceitos, e o histórico não foi sanitizado.
