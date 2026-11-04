# Telegram Courses — uso no Windows 11

Este guia usa o checkout e a `.venv` já preparados. Não é um instalador nem o pacote S10. Os comandos que acessam o Telegram ou iniciam uma fila para além da homologação S9 exigem a autorização específica do operador para canal, seleção e limites. A fila de produto descrita abaixo não é o supervisor S9 e não produz recibos G0–G9.

## Preparar uma vez

No PowerShell 5.1 ou superior, abra a raiz do projeto e execute:

```powershell
Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
$Py = (Resolve-Path -LiteralPath '.\.venv\Scripts\python.exe').Path
& $Py -B '.\tools\prepare_telegram_windows.py'
if ($LASTEXITCODE -ne 0) { throw 'Preparação privada bloqueada; preserve os dados existentes.' }
$Produto = Join-Path $env:LOCALAPPDATA 'telegram_courses_product'
$Banco = Join-Path $Produto 'db\catalog.sqlite3'
$Destino = Join-Path $Produto 'downloads'
& $Py -B -m telegram_courses smoke
```

O preparador cria apenas diretórios ausentes com o guard privado existente e verifica os já existentes; não altera ACLs existentes nem abre credenciais ou o Telegram. Se um diretório existente não passar, ele para sem repará-lo. A sessão e as credenciais DPAPI continuam em sua localização própria, separada do banco e dos downloads. Repita as atribuições `$Py`, `$Produto`, `$Banco` e `$Destino` ao abrir outro terminal.

Para ver as opções sem acessar o Telegram:

```powershell
& $Py -B -m telegram_courses --help
```

## Acesso e catálogo

Após autorização específica para o acesso real, os comandos abaixo usam a conta do próprio operador. Se as credenciais e a sessão já estiverem configuradas, não as recrie. Nunca compartilhe códigos, senhas, hashes de API ou sessão.

```powershell
& $Py -B -m telegram_courses credentials status
# Só na primeira configuração, se necessário:
& $Py -B -m telegram_courses credentials setup
& $Py -B -m telegram_courses auth
& $Py -B -m telegram_courses channels
```

Selecione um canal acessível. O terminal exibe o ID selecionado; mantenha-o privado. Para continuar, atribua esse ID ao valor `$Canal` no próprio terminal. Com autorização para a varredura e limites apropriados:

```powershell
$Canal = Read-Host 'ID do canal autorizado'
& $Py -B -m telegram_courses scan --channel-id $Canal --max-messages 200 --timeout-seconds 120 --database $Banco
& $Py -B -m telegram_courses catalog build --channel-id $Canal --parser-key rasmoo --database $Banco
& $Py -B -m telegram_courses catalog list --database $Banco
```

A varredura limitada pode ser parcial: o catálogo mostra apenas o que foi observado. O parser `rasmoo` é apropriado ao formato RASMOO; para outro canal, confirme o parser suportado. O banco de produto começa separado das cópias de homologação; nenhuma run encerrada é reutilizada.

## Planejar e baixar um curso

Após autorização específica de execução em lote, defina no terminal os limites de itens e bytes abrangidos por essa autorização:

```powershell
$LimiteItens = Read-Host 'Máximo autorizado de arquivos'
$LimiteBytes = Read-Host 'Máximo autorizado de bytes transferidos'
& $Py -B -m telegram_courses download plan --channel-id $Canal --scope course --database $Banco --download-dir $Destino --workers 1 --attempts-per-media 1 --max-media-items $LimiteItens --max-transfer-bytes $LimiteBytes
```

Revise curso, arquivos, exclusões, estimativa de bytes e limites. Para executar a seleção autorizada, a fila apresenta um novo plano e pede confirmação; selecione novamente o curso correto e confira o plano fresco:

```powershell
& $Py -B -m telegram_courses download queue --channel-id $Canal --scope course --database $Banco --download-dir $Destino --workers 1 --attempts-per-media 1 --max-media-items $LimiteItens --max-transfer-bytes $LimiteBytes --private-downloads
```

`--private-downloads` exige destino explícito e confirmação interativa. A fila cria e verifica os diretórios planejados com o guard privado, após a confirmação. Arquivos são organizados pela hierarquia observada; arquivos existentes são conferidos por tamanho e hash antes de serem considerados válidos. Não use `--confirm` para pular a revisão.

Em uma transferência inicial V1, tamanho e SHA-256 são conferidos localmente; isso não comprova, por si só, um hash remoto independente. Um parcial existente também deve ter ACL privada verificável e um único link; caso contrário a fila bloqueia sem alterá-lo. Uma retomada exige prova remota do prefixo e da continuação, além de identidade e limites válidos. Se a prova não estiver disponível, a retomada bloqueia e preserva o parcial. A prova real completa de retomada continua pendente.

## Quando algo parar

- **Preparação privada bloqueada:** preserve o diretório existente; não modifique ACLs nem apague arquivos para forçar a execução.
- **Sessão inválida ou autenticação necessária:** siga a indicação da CLI; faça login interativo somente na conta autorizada.
- **Limite ou espaço insuficiente:** revise o plano, os limites autorizados e o espaço disponível antes de tentar outra fila.
- **FloodWait:** respeite a espera ou o bloqueio informado; não tente contornar o limite do Telegram.
- **Retomada ou integridade bloqueada:** mantenha o `.part` e o banco; ausência de prova não equivale a arquivo íntegro.
- **Arquivo já válido:** confira o plano; a fila deve classificá-lo como válido e não transferi-lo novamente.

Para relatar um erro, remova títulos privados, IDs, caminhos pessoais, códigos, credenciais e sessão da saída compartilhada. Não cole logs completos sem revisão.
