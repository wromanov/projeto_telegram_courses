# Aprovações e decisões públicas — S6/S7

```text
DOCUMENT_TYPE = PUBLIC_SANITIZED_DERIVATIVE
AUTHORITATIVE_SOURCE = LOCAL_CANONICAL
CANONICAL_SOURCE_AVAILABILITY = LOCAL_ONLY / OMITTED_FROM_PUBLIC_TREE
NOT_A_REPLACEMENT_FOR_LOCAL_AUTHORITY = YES
```

Este resumo registra decisões já aprovadas na authority canônica local. Ele não
cria, amplia ou transfere autoridade, aprovação, permissão ou acesso. A versão
canônica local é a fonte decisória.

## S6 — aceite com exceções de escopo

Em 2026-10-25, o usuário aceitou S6 com exceções de escopo. O estado resultante
é `CLOSED_WITH_EXCEPTIONS`, sem declaração de conformidade integral V1.

- Gate A permanece `PARTIAL`; a exceção de evidência processual aceita para o
  encerramento não converte a evidência faltante em PASS.
- Gate B permanece `BLOCKED_BY_REMOTE_EVIDENCE`.
- Foram aceitos somente os limites de evidência documentados para o caso de
  retomada alinhada observado. Provas não realizadas ou incompletas continuam
  diferidas, incluindo validação remota integral do prefixo/EOF, cenário
  desalinhado, janelas de crash/ownership, deduplicação em segunda execução,
  reconciliação completa de orçamento/checkpoint, medição de disco e de memória.
- V1 permanece ativa, com `REMOTE_HASH_REQUIRED`, fail-closed e limites de
  orçamento S5 preservados. V2 global permanece desligada.
- O aceite administrativo não autoriza enfraquecer os controles de integridade,
  declarar produção homologada ou reescrever evidências históricas.

## S7 — aceite com quatro exceções

Em 2026-10-26, o usuário aprovou o aceite de S7 com exceções. O estado é
`CLOSED_WITH_EXCEPTIONS` / `APPROVED_WITH_EXCEPTIONS`; não significa
conformidade integral nem confirmação positiva de exclusão remota.

| Exceção | Limite preservado |
|---|---|
| S7-EX-01 | Evidência direta de cancelamento/crash e ausência de avanço parcial não foi integralmente demonstrada; critério permanece parcial. |
| S7-EX-02 | Exclusão remota positiva e tombstones permanecem fora do escopo homologado; não excluir por inferência nem apagar arquivos automaticamente. |
| S7-EX-03 | A asserção do caminho de falha global do catálogo está incompleta; não declarar esse critério integralmente provado. |
| S7-EX-04 | Resultados históricos não foram reconciliados individualmente; resultados atuais não os substituem. |

S7-A1, S7-A3 e S7-A5 foram provados somente no escopo offline documentado.
S7-A2, S7-A4 e S7-A6 permanecem parciais sob as exceções aprovadas. Os
controles de S5/S6, `REMOTE_HASH_REQUIRED` e fail-closed permanecem obrigatórios.

## S8 e publicação

O contrato integrado S7/S8 foi ratificado como baseline, mas isso não autorizou
implementação S8. S8 continua `DEFERRED` e `NOT_GRANTED`. Operações Telegram/RPC
e downloads reais continuam sem autorização.

## Opção A — saneamento do HEAD público

Em 2026-10-27, o usuário aprovou `OPTION_A` para remover do próximo tree Git
cinco documentos canônicos, preservando os arquivos locais e o histórico
existente, e publicar seus derivados sanitizados. Stage, commit e push foram
autorizados somente após os gates aplicáveis. Reescrita de histórico e force
push não foram autorizados. Esta aprovação não inicia S8.

`HISTORICAL_EXPOSURE=ACCEPTED_RESIDUAL_LOCAL_PATH_METADATA` aceita somente o
risco residual conhecido de metadados de caminhos locais já presentes no
histórico. Não cobre segredos nem novos dados sensíveis e não significa que o
histórico foi sanitizado. O resultado de commit/push ainda não está confirmado
neste snapshot.

## Atividade corretiva de publicação — resultado técnico

A remediação offline de 2026-10-27 não reabre nem altera as decisões de aceite
S6/S7 descritas acima. Seu resultado técnico está registrado em
`docs/reports/S6_S7_PUBLICATION_SECURITY_REMEDIATION_2026-10-27/REPORT.md` e no
manifesto integrado. `READY_FOR_USER_APPROVAL` é uma classificação técnica de
prontidão; não constitui autorização Git. Nenhuma autorização de S8 foi criada.

## Omissões

Foram omitidos textos pessoais de aprovação, identificadores de sessão/alvo,
paths privados, destinos externos, hashes e provas brutas. As omissões limitam
os detalhes públicos; não alteram o conteúdo, escopo ou vigência das decisões
canônicas.
