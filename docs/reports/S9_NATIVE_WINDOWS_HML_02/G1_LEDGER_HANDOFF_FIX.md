# S9 HML — bloqueio de G1 antes de G0

O operador confirmou que o prompt interativo G0 não apareceu na tentativa nativa. O launcher chamava o subcomando `g1`; a mensagem `offline supervisor blocked` era genérica e não indicava uso do smoke test.

O launcher mantinha uma instância do ledger com posse exclusiva de escrita enquanto lançava o supervisor em outro processo. Ao carregar o contexto, o supervisor precisa adquirir a mesma posse. Um teste offline com dois processos reproduziu `exit 2`, a mensagem original e a ausência de `queue-run.lock`; após liberar a posse, o processo conseguiu carregar o contexto. A evidência nativa é compatível com essa causa, mas a exceção interna daquela execução não foi registrada; portanto a identificação do erro nativo permanece inferência corroborada, não prova direta.

A correção libera a posse do ledger antes de lançar os subprocessos G1, G2, G3 e a fila G5, e a readquire com replay após término bem-sucedido. Falhas ou interrupções não readmitem o processo pai enquanto o término do subprocesso não estiver comprovado. G0 e G4 permanecem obrigatórios.

Validação offline: 10 testes focados passaram, incluindo gateway sintético e bloqueio antes de G0; o teste de dois processos foi ampliado para reproduzir a mensagem original e passou novamente; dois testes de proteção do plano G4 passaram. Ruff e compileall passaram. O contrato S9 mantém SHA256 `BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2`. Nenhuma RPC real, credencial ou download foi usado.

O launcher corrigido precisa ser validado no PowerShell 5.1 nativo, com nova run e novo deadline:

```powershell
Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
& '.\tools\RUN_S9_NATIVE_WINDOWS_HML_02.ps1'
```

O prompt G0 no terminal nativo e a execução real de G1 ainda não foram observados após a correção. O operador deve revisar o manifesto e decidir em G0 antes de qualquer RPC; G4 precede o download. O run anterior não deve ser reiniciado nem reutilizado.
