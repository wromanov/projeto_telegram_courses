# S6 V2 TRUSTED_REFERENCE — contrato de homologação isolada

**Data:** 2026-10-18  
**Atividade:** `S6_V2_TRUSTED_REFERENCE_ENABLEMENT`  
**Status documental:** contrato delimitado para homologação offline do cenário `TRUSTED_REFERENCE`.  
**Autoridade:** adjudicação técnica do Architect registrada para esta atividade.  
**V1:** permanece canônico e ativo.  
**V2:** não promovido a canônico e não efetivo globalmente.  
**Prova real:** não autorizada por este contrato.

## 1. Finalidade e limites

Este contrato fixa os requisitos técnicos do perfil isolado `TRUSTED_REFERENCE` no harness, para preparar uma futura prova real controlada. A homologação coberta por ele é offline e sintética. Não autoriza conexão real ao Telegram, download real, uso operacional da referência, nem prova de origem real.

A única implementação coberta é o suporte explícito a este perfil no harness e no launcher protegido, com prefixo configurável, orçamento calculado, proteção da referência, confirmação nativa restrita, relatórios/ledger/reconciliação e comparação final. O escopo não altera o contrato canônico V1 nem ativa V2 globalmente.

Valores de orçamento abaixo são limites de homologação calculados a partir dos parâmetros adjudicados. Eles não são evidência de execução, aprovação de gates ou autorização de execução real. `GetMessages` em streaming não é contabilizado pelo contador de requests existente; relatórios devem declarar essa contagem como parcial/desconhecida e não apresentá-la como total.

## 2. Alvo fixo e referência original

A identidade controlada é fixa:

| Campo | Valor adjudicado |
|---|---|
| Canal | `-1002368271467` |
| Mensagem | `7603` |
| Ordinal do arquivo | `0` |
| Documento | `DOCUMENT` |
| Mídia | `5089068167339181674` |
| Tamanho total `E` | `1,119,129,690` bytes |
| SHA-256 original | `3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c` |

A referência original deve existir antes do upload e ser tratada como imutável e somente leitura durante a preparação, execução e comparação. O processo registra seu caminho canônico, identidade do arquivo, tamanho e SHA-256 antes de iniciar. A proveniência está documentada, mas não foi atestada independentemente; não declarar atestação externa ou origem autenticada.

Antes e depois do fluxo, a referência precisa continuar acessível no mesmo objeto/path protegido, com tamanho e SHA-256 idênticos aos valores acima. A comparação final deve ler todos os bytes recebidos e todos os bytes da referência, comparar o conteúdo integral, e ainda confirmar igualdade exata de tamanho e SHA-256. Hash e tamanho isolados não substituem comparação integral. A referência não pode ser substituída por um arquivo de saída, por um caminho derivado de entrada não confiável ou por um artefato intermediário.

## 3. Fluxo e gates de ciclo de vida

O perfil exige dois processos distintos, ligados por checkpoint persistente validado. A primeira fase baixa o prefixo configurado, salva estado e checkpoint e encerra. A segunda fase inicia em novo processo, valida identidade e propriedade do checkpoint, retoma o restante e só conclui após aplicar os gates de integridade e comparação. O checkpoint deve conter dados suficientes para reabrir a mesma operação e deve rejeitar identidade, estado, caminho, tamanho, prefixo ou propriedade conflitantes. Erro de leitura, escrita, parse, integridade, ownership ou recuperação do checkpoint é fail-closed.

O resultado local só pode ser marcado `COMPLETED_V2` quando todos os bytes e todos os gates de lifecycle foram concluídos: prefixo e retomada válidos, arquivo final íntegro, comparação de conteúdo integral com a referência, tamanho e SHA-256 exatos, referência inalterada antes/depois e evidência persistida. `COMPLETED_V2` significa conclusão técnica local do perfil V2; não promove V2 globalmente, não prova a autenticidade da procedência da referência e não equivale a autorização de prova real.

A evidência deve registrar pelo menos: perfil e parâmetros; identidade controlada; tamanho/hash da referência antes e depois; caminho relativo/canônico dos artefatos sem expor caminhos fora da raiz permitida; resultados de comparação integral, tamanho e SHA-256; checkpoint e transição de processos; `COMPLETED_V2` ou outcome terminal; requests observados e limites; contagem parcial/desconhecida de streaming; hashes remotos e respectivos resultados; violações/bloqueios; reconciliação final do ledger. O relatório individual de cada tentativa, ledger agregado e reconciliação devem concordar. Evidência incompleta nunca se converte em sucesso.

## 4. Outcomes obrigatórios

Cada execução termina em exatamente um destes outcomes:

- **`TRUSTED_REFERENCE_MATCH`** — somente após igualdade integral dos bytes, tamanho e SHA-256, referência preservada, lifecycle completo em dois processos, checkpoint válido, estado `COMPLETED_V2`, evidência reconciliada e ausência de veto remoto. É o único outcome que demonstra correspondência com a referência neste perfil.
- **`TRUSTED_REFERENCE_MISMATCH`** — comparação integral concluída e demonstra divergência real de conteúdo, tamanho ou hash. É um resultado explícito de não correspondência; nunca pode ser reclassificado como `UNVERIFIED_ORIGIN`, `MATCH`, sucesso, nem omitido por retry.
- **`INCOMPLETE`** — a execução foi interrompida ou terminou sem evidência suficiente para concluir igualdade, divergência ou bloqueio. Não é sucesso, mismatch presumido ou autorização para prosseguir.
- **`BLOCKED`** — uma precondição, proteção, integridade, identidade, ownership, orçamento ou veto impede execução/conclusão segura. Não é sucesso nem mismatch presumido.

Referência ausente, alterada, ilegível ou não verificável; caminho inseguro; divergência de identidade; checkpoint incompatível/corrompido ou conflito de ownership; budget excedido ou inconsistente; falha de reconciliação; ou veto remoto resulta em `BLOCKED`. Se uma comparação integral efetivamente concluiu divergência, registrar `TRUSTED_REFERENCE_MISMATCH`, mesmo que também se conheça uma divergência real; não a rebaixar para origem não verificada. Se não foi possível chegar a uma conclusão devido a interrupção sem precondição violada, registrar `INCOMPLETE`. Nenhuma dessas condições pode produzir `PASS` ou `TRUSTED_REFERENCE_MATCH`.

## 5. Hashes remotos e separação das evidências

`GetFileHashes` permanece no envelope de orçamento de `TRUSTED_REFERENCE` porque o downloader atual o executa também neste modo e os resultados remotos podem funcionar como veto de integridade. Suprimi-lo nesta homologação poderia esconder um veto que existe no comportamento atual. Esses hashes formam um eixo de evidência remoto separado; não são necessários para decidir a igualdade local com a referência original, que é decidida pela comparação integral, tamanho e SHA-256 locais.

Portanto, `GetFileHashes` não substitui a comparação da referência. Qualquer erro, hash remoto inconsistente ou veto aplicável bloqueia o resultado `MATCH`. A contagem de planejamento é envelope conservador, não afirmação de que cada janela/camada fará exatamente esse número de chamadas.

O orçamento auxiliar de identidade `GetMessages` é limitado a **5** chamadas: uma leitura na fase 1 e até duas chamadas em cada uma das duas tentativas da fase 2. Contadores que não incluem leituras de `GetMessages` executadas pelo fluxo de streaming devem permanecer identificados como parciais/desconhecidos. Não declarar orçamento total de RPC com base somente nesse contador.

## 6. Prefixo e fórmulas do orçamento

Seja `C = 262,144` bytes (256 KiB), `E = 1,119,129,690` bytes e `P` o prefixo. Valores aceitos satisfazem `P % C == 0` e `0 < P < E`. Não existe regra adicional de alinhamento em 1 MiB. O perfil oferece `P = 8 MiB` e `P = 128 MiB`, com **8 MiB como default**; configuração deve ser explícita no relatório.

O envelope calculado usa duas tentativas de fase 2 (incluindo reserva para tentativas/recovery S5):

- `H = ceil(E / C) + 1 = 4,271` — limite conservador de `GetFileHashes` por tentativa de fase 2.
- `F1 = ceil(P / C)` — orçamento de `GetFile` da fase 1.
- `F2 = ceil((E - P) / C)` — chunks úteis e cap de chamadas `GetFile` em uma tentativa de fase 2.
- `GetFileHashes_attempt_cap = H` — cap de hashes remotos por tentativa de fase 2, incluindo a reserva conservadora de overhead/tentativa.
- `GetFile_aggregate = F1 + 2 × F2` — chunks úteis agregados das fases e duas tentativas fase 2.
- `GetFileHashes_aggregate = 2 × H = 8,542` — envelope conservador por duas tentativas de fase 2, incluindo margem de tentativa; contabilizado separadamente do equality check local.
- `payload_reserve = F1 × C + 2 × F2 × C` (equivalentemente, `F1 × C + 2 × ceil((E - P)/C) × C`) — bytes reservados em blocos inteiros para a fase 1 e cada uma das duas tentativas de fase 2.

O cap efetivo não pode exceder o perfil calculado aplicável. Para configuração intermediária alinhada, recalcular as fórmulas; não interpolar contagens. Caps explicitamente adotáveis no launcher protegido são no máximo: `GetFile` da fase 1 `F1=ceil(P/C)`, `GetFile` em cada tentativa da fase 2 `F2=ceil((E-P)/C)`, `GetFile` agregado `F1 + 2×F2`, `GetFileHashes` em cada tentativa da fase 2 `H`, hashes remotos agregados `2×H`, identidade `GetMessages=5`, e reserva de payload quantizada da fórmula. Uma violação em qualquer fase ou no agregado bloqueia a execução, mesmo que o outro limite ainda tenha folga.

| Perfil | `P` | Fase 1 `F1` GetFile | Fase 2 útil/cap `F2` GetFile por tentativa | `H` cap GetFileHashes por tentativa fase 2 | GetFile agregado | GetFileHashes agregado | Reserva de payload |
|---|---:|---:|---:|---:|---:|---:|---:|
| Default | 8 MiB (8,388,608 B) | 32 | 4,238 | 4,271 | 8,508 | 8,542 | 2,230,321,152 B |
| Alternativo | 128 MiB (134,217,728 B) | 512 | 3,758 | 4,271 | 8,028 | 8,542 | 2,104,492,032 B |

Com duas tentativas fase 2, o perfil de 8 MiB reserva **480 chamadas úteis GetFile agregadas a mais** e **125,829,120 bytes a mais** que 128 MiB. Em ambos, se uma retomada resolver a execução, o trabalho útil de payload corresponde a 4,270 chunks (`F1 + F2`); o envelope de duas tentativas é uma reserva, não uma previsão de que haverá duas execuções completas. O prefixo menor reduz transferência antes do checkpoint, mas **não** reduz necessariamente o orçamento agregado; aqui, aumenta-o. O default de 8 MiB é recomendado para limitar a parcela inicial pré-checkpoint. A escolha é local a este perfil e não implica autorização operacional.

## 7. Proteção de paths e confirmação nativa

A raiz temporária deve usar caminho TEMP nativo curto, exclusivo da execução e validado antes de qualquer escrita. Os caminhos resolvidos de raiz, checkpoint, artefatos e saídas devem permanecer dentro da raiz esperada e respeitar limite máximo de **240 caracteres**. Rejeitar traversal, reparse/symlink quando aplicável, redirecionamento para fora da raiz, colisões, caminho inexistente/ambíguo ou arquivo protegido apontando para output. A referência permanece separada da raiz de saída e somente leitura.

A confirmação nativa é exclusiva para `TRUSTED_REFERENCE` e para o alvo fixo desta seção. A UI/launcher deve apresentar modo, identidade do alvo, identidade da referência e parâmetros calculados, e recusar modo ou alvo diferente. A confirmação ainda **não está aberta** por este contrato: sua implementação/verificação é gate pendente do trabalho autorizado, não autorização para iniciar uma prova real.

## 8. Matriz fail-closed

| Condição observada | Resultado exigido | Pode produzir MATCH? |
|---|---|---|
| Todos os gates concluem e bytes, tamanho e SHA-256 são iguais; evidência e ledger reconciliados; sem veto | `TRUSTED_REFERENCE_MATCH` | Sim |
| Comparação integral conclui conteúdo/tamanho/hash diferente | `TRUSTED_REFERENCE_MISMATCH` | Não |
| Execução interrompida sem conclusão | `INCOMPLETE` | Não |
| Referência ausente, alterada ou ilegível | `BLOCKED` | Não |
| Path inseguro, fora da raiz, acima de 240 caracteres ou referência redirecionada | `BLOCKED` | Não |
| Identidade/alvo/modo fora do fixado, checkpoint inválido ou conflito de ownership | `BLOCKED` | Não |
| Budget por fase, agregado, hash, payload ou identidade violado/desconhecido além do declarado | `BLOCKED` | Não |
| Hash remoto falha, contradiz evidência ou veta o resultado | `BLOCKED` | Não |
| Relatório, ledger ou reconciliação ausente/inconsistente; lifecycle incompleto | `BLOCKED` ou `INCOMPLETE` conforme haja violação detectada ou apenas interrupção | Não |

Não usar retry para apagar ou converter resultado de uma tentativa. Cada tentativa mantém relatório individual; o ledger conserva o histórico e a reconciliação final considera todas as tentativas.

## 9. Gates de homologação e autoridade

A aprovação offline deste perfil requer evidência dos seguintes gates: testes unitários; E2E sintético com dois processos; igualdade e divergência; falha de referência; erros de checkpoint; violação de budgets; proteções de paths; regressões S5/S6; parser PowerShell; Ruff; compilação Python; dry-run em Windows nativo; e `git diff --check`. A comparação dos prefixos 8 MiB e 128 MiB deve apresentar os cálculos da seção 6 e justificar a opção adotada. Ausência de evidência de qualquer gate não permite declarar `PASS`.

Estado de autoridade e execução para este contrato:

- `V1_CANONICAL = YES` e `V1_ACTIVE = YES`.
- `V2_CANONICAL_PROMOTION = NO` e `V2_EFFECTIVE = NO`.
- `V2_GLOBAL_ACTIVATION = NO`.
- `REAL_TELEGRAM_CALLS = 0` e `REAL_DOWNLOADS = NO`.
- `REAL_PROOF_AUTHORIZATION = NO`.
- `S6_FORMAL_ACCEPTANCE = PENDING` e `SPRINT_CHECKPOINT = DEFERRED`.
- `GIT_ADD = NO`, `GIT_COMMIT = NO` e `GIT_PUSH = NO`.

Os gates acima especificam critérios para homologação; este documento não afirma que foram executados ou passaram. Uma prova real futura depende de autorização controlada explícita do usuário após apresentação de um preflight completo. Nenhum status `READY`, `PASS`, `COMPLETED_V2` ou `TRUSTED_REFERENCE_MATCH` aqui concedido substitui tal autorização.

