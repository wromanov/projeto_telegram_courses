# S6 V2 Trusted Reference Preflight Amendment — 2026-10-19

## Resultado

Ajustado o preflight offline para aceitar os dois estados do atributo Windows
`IsReadOnly`, exigindo em ambos leitura binária, arquivo regular, caminho seguro,
tamanho e SHA-256 esperados, identidade/ausência de alias e revalidação da
referência. A referência não é aberta para escrita. Divergência conhecida
bloqueia; pós-verificação ausente ou não verificável permanece `INCOMPLETE` e
não pode produzir `TRUSTED_REFERENCE_MATCH`.

O launcher agora confere a identidade declarada do alvo e a fingerprint local
antes de pedir confirmação, sem RPC. A execução exige confirmação nativa e a
identidade Telegram remota é verificada antes de qualquer stream GetFile. A
criação/validação do diretório de evidência da prova real fica na sessão
PowerShell nativa; o sandbox não precisa antecipar essa raiz.

## Validação executada

- Testes focados: 20 passed, 156 deselected. Cobrem preflight de referência,
  mudança entre verificações, pós-verificação, raiz inválida, preconfirmação,
  ausência de confirmação e bloqueio de GetFile quando identidade remota diverge.
- Ruff: PASS.
- `compileall`: PASS.
- Parser Windows PowerShell 5.1: PASS.
- DryRun TRUSTED_REFERENCE 8MiB: PASS; `REAL_TELEGRAM_CALLS=0`, sem download.
- Original antes/depois: 1.119.129.690 bytes e SHA-256
  `3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c`; atributos
  Windows e ACL inalterados.
- O E2E sintético de dois processos foi tentado e interrompido porque o loop
  Proactor do sandbox bloqueou antes da entrada da coroutine. Isso não é
  classificado como PASS; a regressão completa permanece parcial.
- `git diff --check` passou sem erros de whitespace; a inspeção dos arquivos novos e alterados também passou. Os avisos Git restantes informam normalização LF/CRLF em arquivos preexistentes.

## Estado e limites

```text
ACTIVITY = S6_V2_REFERENCE_PREFLIGHT_AMENDMENT
ACTIVITY_COMPLETION_PERCENT = 100 / OFFLINE AMENDMENT SCOPE
REFERENCE_PREFLIGHT_FIX = PASS
REFERENCE_ORIGINAL_MODIFIED = NO
READ_ONLY_ACCESS_VERIFIED = PASS / binary read-only path and both IsReadOnly cases
PREHASH_VERIFIED = PASS / expected size and SHA-256
POSTHASH_CONTROL_VERIFIED = PASS / change and unverifiable cases fail closed; actual proof not run
IDENTITY_GATE_VALIDATED = PASS / static zero-RPC gate and synthetic remote mismatch blocks GetFile
NATIVE_ROOT_GATE_VALIDATED = PASS / path/reparse/containment checks; actual proof root creation deferred to native PowerShell
FOCUSED_TESTS = 20 passed, 156 deselected
REGRESSION_RESULT = PARTIAL / sandbox Proactor blocked two-process E2E before coroutine entry
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_PROOF_EXECUTION = NO
V1_ACTIVE = YES
V2_GLOBAL = OFF
REAL_PROOF_STATUS = BLOCKED_PENDING_NEW_AUTHORIZATION
S6_FORMAL_ACCEPTANCE = PENDING
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
```

Evidência do DryRun isolado:
`.s6-v2-reference-preflight-dryrun-20261019/s6t-0c199a2b2dbd4848b4c677c21c24b4d2/`.

## Safe resume point

Uma prova real exige nova autorização específica e deve ser executada somente
no PowerShell Windows nativo, após confirmação humana e gates de identidade,
raiz isolada, caps e timeout passarem. Não reutilizar evidência parcial. Esta
alteração offline não constitui aceite formal S6.
