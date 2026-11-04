# S9 G1 — identidade do subprocesso e T24

## Evidência e causa

A execução nativa apresentou `context_manifest=FAILURE/RUNTIME_ERROR` antes da segunda marca de inicialização T24. A leitura de recibos e ledger em modo somente leitura confirmou G0 humano, run_id, hash do manifesto e do escopo vinculados; migrations 1–7 e `PENDING_G3` presentes. O evento `CHILD_PROCESS_CONFIRMED` corresponde ao PID e instante de criação do processo raiz no recibo do supervisor. A árvore observada contém dois processos.

No mesmo Windows, uma reprodução offline mostrou que o `python.exe` da venv cria um processo lançador e um interpretador com PID distinto. Com o evento de handoff vinculado ao PID do lançador, a admissão do ledger pelo interpretador retorna `LEDGER_CHILD_IDENTITY_INVALID`. Com o interpretador efetivo como processo supervisionado, a admissão passa; um PID confirmado incorreto continua bloqueado. O recibo nativo original registrou apenas `RUNTIME_ERROR`, não o código interno do ledger. Portanto a causa específica foi reproduzida e é fortemente corroborada pelos registros nativos, mas o código interno daquela tentativa não foi capturado diretamente.

A falha T24 é secundária no caminho reproduzido: a admissão do ledger falha antes de `configure_operational_logging`, então a finalização sem handler válido retorna 125. Teste offline reproduziu os dois diagnósticos na ordem correta. O identificador primário `LEDGER_CHILD_IDENTITY_INVALID` agora é permitido em uma lista fixa, seguido separadamente por `FINALIZATION_FAILED`, sem registrar texto arbitrário de exceções ou dados privados.

## Correção

Em venv Windows, os estágios G1, G2/G3 e filas supervisionadas usam diretamente o interpretador base de onde a venv foi criada, evitando o processo lançador intermediário. `-IS` mantém isolamento e impede carregar site-packages globais; o bootstrap adiciona a pasta de site-packages da venv após validar seu local, preservando suas dependências e a checagem existente de origem do módulo. O guard de PID e criação não foi flexibilizado. Em demais ambientes, mantém-se o comando anterior.

## Validação offline

146 testes focados de identidade, supervisão, manifesto, G0, handoff, T24 e proteções da fila passaram. Mais oito testes confirmaram a rejeição de PID incorreto, o isolamento da venv, origem confiável e a distinção entre erro primário e falha secundária. A conexão Telegram e as credenciais não foram usadas. O contrato S9 está congelado e inalterado.

## Retomada

Nenhuma nova run real foi iniciada nesta análise. Uma nova execução nativa, com novo deadline e G0 antes de RPC, deve ser conduzida pelo operador; G4 segue obrigatório antes do payload:

```powershell
Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
& '.\tools\RUN_S9_NATIVE_WINDOWS_HML_02.ps1'
```

O êxito nativo de G1 e a existência de RPC anterior permanecem não comprovados. Não reutilizar qualquer run anterior.
