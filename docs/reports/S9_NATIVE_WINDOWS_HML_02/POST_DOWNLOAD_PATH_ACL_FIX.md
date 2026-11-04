# S9 — diretório privado após download

## Evidência nativa somente leitura

Um arquivo `.mp4` foi localizado sob `%LOCALAPPDATA%\telegram_courses\S9-HML-02\runs\<run>\downloads\<pasta>\<arquivo>.mp4`. Ele existe, resolve dentro da raiz `downloads`, não apresenta reparse no diretório pai e tem 12.087.200 bytes. O SHA-256 calculado localmente coincide com o valor gravado na linha `DOWNLOADED` do SQLite. A leitura não alterou o arquivo ou sua ACL.

O recibo G5 declara `PASS`, origem `REAL_CONTRACTUAL` e 12.087.200 bytes observados; o SHA-256 do recibo do supervisor coincide com o valor referenciado por G5. O supervisor registra `COMPLETED`, saída zero e limites `PASS`. Esses dados e a correspondência do hash local não comprovam, isoladamente, validação de hash remoto ou aceite final S9. Não foi encontrado recibo de evidência S6 V2; V2 permanece fora do escopo. G6/G9 e a verificação final completa não foram declarados.

## Causa

A raiz `downloads` tem DACL protegida e explícita e passa no guard. A pasta intermediária foi criada por `Path.mkdir` no fluxo S4 e herdou três ACEs de controle total para o usuário, SYSTEM e Administradores; proprietário correto, sem reparse, mas DACL não protegida e ACEs herdadas. O guard S9 exige DACL protegida com ACEs explícitas e rejeitou essa pasta. O caminho, por sua vez, está dentro da raiz e coincide com o caminho resolvido. Trata-se de incompatibilidade entre a criação herdada e o contrato do guard, sem evidência de concessão a identidades não confiáveis nessa pasta.

## Correção

Somente no fluxo de fila supervisionada S9, depois da confirmação G4, o CLI cria as pastas dos itens pendentes com `_create_private_directory` e mantém os guards existentes abertos durante a fila. Pastas previamente existentes devem passar o mesmo guard; uma ACL herdada ou caminho inseguro bloqueia sem reparo ou alteração. A criação é limitada às pastas do plano sob a raiz privada e ocorre antes de inicializar o gateway da fila. O arquivo e as ACLs do run encerrado não foram alterados; o run não foi retomado.

## Testes offline

Passaram 19 testes da fila S9 e um teste de integração de fila com gateway sintético. Quatro testes focados passaram para criação, renomeação sem overwrite com guards abertos e verificação final em arquivos temporários, idempotência, bloqueio sem alteração de ACL herdada e ordenação após G4, incluindo recusa. A primeira execução de um teste falhou apenas porque a mensagem de `DownloadError` é normalizada; a asserção foi corrigida para verificar a categoria, e os testes focados passaram. Ruff e compileall passaram; o contrato S9 mantém SHA256 `BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2`.

Nenhuma transferência real adicional, alteração de ACL nativa, S10 ou publicação Git foi executada. O bloqueio do run encerrado continua registrado como ocorrido; esta correção prepara a criação segura de diretórios em execuções futuras e ainda não foi validada por nova operação real.
