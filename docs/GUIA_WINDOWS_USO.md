# Telegram Courses — uso no Windows 11

## Demonstração offline

Na raiz do projeto, escolha um caminho novo e execute:

```powershell
.\.venv\Scripts\telegram-courses.exe demo --workspace "$env:LOCALAPPDATA\TelegramCoursesDemo"
```

Escolha canal `1` e curso `1`; marque arquivos por número, lista ou `T`, use `V` para revisar e `P` para planejar. Confirme o plano com `s` e autorize separadamente a execução sintética com `s`. O workspace é preservado: execute o mesmo comando novamente para conferir arquivos já válidos. Um diretório existente sem o marcador da demonstração é recusado. O gateway serve apenas bytes fictícios em memória e não usa Telegram.

Para consultar o catálogo local: `.\.venv\Scripts\telegram-courses.exe interactive --database <caminho>`. O modo interativo abre a interface real; navegar não inicia downloads. Com itens elegíveis, a execução ao vivo exige revisão do plano e uma segunda autorização explícita do operador.

Este guia usa o checkout e a `.venv` já preparados. Não é um instalador nem o pacote S10. Os comandos que acessam o Telegram ou iniciam uma fila para além da homologação S9 exigem a autorização específica do operador para canal, seleção e limites. A fila de produto descrita abaixo não é o supervisor S9 e não produz recibos G0–G9.

## Preparar uma vez

No PowerShell 5.1 ou superior, abra a raiz do projeto e execute:

```powershell
$Repo = Read-Host 'Caminho da raiz do repositório'
Set-Location -LiteralPath $Repo
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

Para consultar o catálogo local e marcar arquivos observados de um curso, use o modo interativo em um terminal. Ele abre o banco somente para leitura; a tela informa quando o catálogo é parcial e mostra mídias sem associação classificável. A lista usa páginas simples de 20 itens e mantém os índices globais ao navegar:

```powershell
& $Py -B -m telegram_courses interactive --database $Banco
```

Na lista do curso, use números, listas (`1,3`) ou intervalos (`2-5`) para marcar itens; `T` marca todos os itens associados e selecionáveis do curso, `R` remove itens, `L` limpa a seleção, `V` revisa e `Q` volta. `A` e `N` navegam entre páginas. `P` prepara um plano para a seleção exata; `B` prepara um plano para todos os arquivos elegíveis catalogados daquele curso. “Todos” não significa todo o canal nem prova que o catálogo remoto está completo.

Antes da confirmação, o plano mostra a sequência determinística S5, as identidades locais, os estados atuais, tamanhos conhecidos e desconhecidos, limites, destino e exclusões. A ordem não afirma sequência pedagógica; ambiguidades de ordinal são sinalizadas. Tamanho desconhecido nunca é omitido silenciosamente: permanece visível e, com limite de bytes configurado, bloqueia a confirmação quando pertence ao plano. Também são exibidos itens observados que não são elegíveis para seleção.

O modo interativo aceita `--download-dir`, `--max-media-items` e `--max-transfer-bytes` para revisar destino e limites. A confirmação inicial revalida o plano e não transfere mídia. Para executar a fila real, a CLI exige **outra autorização separada** antes de abrir a sessão e transferir bytes. Recusar ou cancelar essa segunda autorização não transfere payload.

Se houver itens pendentes, a confirmação é bloqueada quando o espaço disponível não puder ser verificado ou for insuficiente. Uma variação de espaço livre de pelo menos 1 GiB após a revisão descarta a confirmação e exige nova revisão; variações menores são aceitas somente se o espaço continuar suficiente. O espaço pode mudar novamente depois da revisão.

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

Em uma transferência inicial V1, tamanho e SHA-256 são conferidos localmente; isso não comprova, por si só, um hash remoto independente. Um parcial existente também deve ter ACL privada verificável e um único link; caso contrário a fila bloqueia sem alterá-lo. Uma retomada exige prova remota do prefixo e da continuação, além de identidade e limites válidos. Se a prova não estiver disponível, a retomada bloqueia e preserva o parcial. A campanha isolada G4 demonstrou Ctrl+C real, checkpoint, retomada, integridade remota e deduplicação em uma mídia autorizada; os dois roteiros compostos originais ainda não foram executados integralmente.

## Quando algo parar

- **Preparação privada bloqueada:** preserve o diretório existente; não modifique ACLs nem apague arquivos para forçar a execução.
- **Sessão inválida ou autenticação necessária:** siga a indicação da CLI; faça login interativo somente na conta autorizada.
- **Limite ou espaço insuficiente:** revise o plano, os limites autorizados e o espaço disponível antes de tentar outra fila.
- **FloodWait:** respeite a espera ou o bloqueio informado; não tente contornar o limite do Telegram.
- **Retomada ou integridade bloqueada:** mantenha o `.part` e o banco; ausência de prova não equivale a arquivo íntegro.
- **Arquivo já válido:** confira o plano; a fila deve classificá-lo como válido e não transferi-lo novamente.

Para relatar um erro, remova títulos privados, IDs, caminhos pessoais, códigos, credenciais e sessão da saída compartilhada. Não cole logs completos sem revisão.
