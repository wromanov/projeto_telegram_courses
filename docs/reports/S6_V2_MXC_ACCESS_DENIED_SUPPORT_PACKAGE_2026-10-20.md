# Pacote sanitizado de suporte — MXC `STATUS_ACCESS_DENIED` — 2026-10-20

## Finalidade e sanitização

Resumo documental destinado a apoiar eventual encaminhamento ao administrador
do executor. Este arquivo não foi enviado a terceiros. Usuário, raiz do
repositório, diretórios locais, caminhos de runtime e de snapshot foram
substituídos por placeholders. Não inclui credenciais, conteúdo de sessão nem
dados pessoais.

```text
HOST_USER = <HOST_USER>
REPOSITORY_ROOT = <REPOSITORY_ROOT>
JOB_RUNTIME_PATH = <JOB_RECORDED_RUNTIME_PATH>
JOB_SNAPSHOT_PATH = <JOB_RECORDED_SNAPSHOT_PATH>
JOB_RUN_ROOT = <EXCLUSIVE_JOB_RUN_ROOT>
INCIDENT_TIMESTAMP = UNKNOWN / exact timestamp not supplied
```

## Resultado observado

O job `61295a78efe340ea902b73848f303ab8` encerrou com exit decimal
`3221225506` / hexadecimal `0xC0000022 STATUS_ACCESS_DENIED`. stdout e stderr
vieram vazios; `WORKER_IDENTITY_NOT_PUBLISHED`; não havia
`.sandbox/sandbox.log`. O contador ativo reportado como zero deriva da ausência
de identidade publicada e não é evidência de início ou encerramento da árvore.
O worker canary informou zero conexões; houve somente controle positivo do
listener no host, insuficiente para provar isolamento de rede.

Em jobs anteriores `SystemDrive` e `LOCALAPPDATA` estavam ausentes. Depois de
incluídos, o erro `C0000022` apareceu. A sequência não determina causa-raiz.
ACLs dos caminhos exatos de runtime/snapshot registrados pelo job e eventos OS
existentes foram correlacionados em leitura somente; o material recebido não
atribui a falha a uma ACL/evento específico. `ROOT_CAUSE = UNKNOWN`.

## Superfície de host informada

- Windows 10 Pro, DisplayVersion `25H2`, CurrentBuild `26200.9711`.
- PowerShell executor `7.6.5`; difere do PowerShell 5.1 esperado no checkpoint
  anterior.
- CIM indisponível; consulta `Get-NetFirewallProfile` via CIM negada.
- DISM read-only retornou `740` (elevação necessária).
- `WindowsSandbox.exe` não foi encontrado nos caminhos consultados.
- `vmcompute.exe` e `hcsdiag.exe` estavam presentes; serviço não encontrado
  nesta superfície.
- `Get-LocalUser` falhou com `NullReference`.

São limitações/resultados da superfície atualmente visível, não prova de
ausência no host real ou de estado global do sistema.

## Digests comprovados e lacunas

Os únicos digests incluídos abaixo são os já registrados no relatório de gate
existente e correspondem a artefatos históricos preservados. Não são logs do
incidente nem prova de execução nesta atividade.

| Artefato lógico | SHA-256 confirmado no relatório de gate | Resultado histórico |
|---|---|---|
| `<HISTORICAL_RECEIPT_163_PASS>` | `E1CE23D717622DCF4F2817E5CF42C65A65EF3F26EE09B83F7AE8B27E7E2CB61F` | 163/163 PASS |
| `<PRIOR_AUDIT_RECEIPT_176_CASES>` | `5EA51E64FB113A46AABA906A275DB656E8E09373C71527EEC30A75EBB51E2628` | 176 coletados / 173 pass / 3 fail |

Digests/timestamps exatos para eventos OS, ACLs e o job de falha não foram
fornecidos; ficam `UNKNOWN` e não são inferidos. Os históricos permanecem
separados e intactos. Nenhum teste foi repetido para compor este pacote.

## Estado de decisão e uso

MXC continua proibido para nova tentativa; `MXC_ON_ACTUAL_WINDOWS_HOST` foi
somente a seleção histórica do gate anterior, não o backend selecionado para
uma execução Option B. Nesta atividade nenhum backend Option B foi selecionado
ou implementado porque o gate de segurança está `BLOCKED`: `G=NO`, `F=NO`,
`E=NO`, isolamento de credenciais `NO`, e fronteiras de identidade, rede,
filesystem e árvore não demonstradas. Os rótulos G/F/E são transcritos sem
redefinição. Fallback legacy não foi provado.

Nenhum executor foi implementado, nenhum pytest funcional começou, não houve
segundo submit, cancel/timeout real nem E2E autônomo. Nenhuma mudança de
permissão, policy, ACL ampla ou configuração global foi feita. V1 permanece
ativa; V2 global desligada. Não houve Telegram, download, prova real, SQLite de
produção ou Git.

Safepoint: obter evidência suportada no host e autorização separada para
qualquer mudança scoped de admin/provisioning; provar identidade, isolamento de
rede/filesystem e término da árvore usando canary fixo inofensivo. Somente
depois considerar implementação ou testes do repositório. Sem retry MXC.

Fontes de continuidade: [PROJECT_STATE](../continuity/PROJECT_STATE.md),
[CONTINUITY_RECORD](../continuity/CONTINUITY_RECORD.md), [relatório de gate
anterior](S6_V2_NATIVE_EXECUTION_GATE_2026-10-20/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20.md)
e [diagnóstico de recuperação](S6_V2_NATIVE_EXECUTION_RECOVERY_2026-10-20.md).
