# Telegram Courses para Windows — candidato

**Estado:** `CANDIDATE / UNVERIFIED`. Este pacote ainda não foi homologado com uma sessão ou canal Telegram real.

O pacote contém um runtime CPython 3.14.7 x64 isolado, o aplicativo e as dependências fixadas em `DEPENDENCY-VERSIONS.txt`. Ele não inclui sessão, credenciais, banco do usuário, conteúdo de canal ou arquivos de log.

## Iniciar

Extraia `telegram-courses-windows-x64-candidate.zip` para uma pasta do usuário e execute `launch.cmd`. A janela mostra os comandos disponíveis. Também é possível abrir o Prompt de Comando nessa pasta e executar, por exemplo, `launch.cmd smoke` ou `launch.cmd --help`.

Na primeira execução, o aplicativo cria configurações sem segredos em `%LOCALAPPDATA%\telegram_courses_data\settings.toml`. O banco persistente fica em `%LOCALAPPDATA%\telegram_courses_data\catalog.sqlite3`; a pasta padrão para downloads é `%USERPROFILE%\Downloads\TelegramCourses`. Credenciais continuam no cofre DPAPI do usuário e a sessão fica protegida separadamente em `%LOCALAPPDATA%\telegram_courses`. Nenhum desses dados é gravado dentro da pasta do pacote.

## Primeiros passos

1. Execute `launch.cmd credentials setup` para cadastrar o ID e o API hash da sua aplicação Telegram. Eles são protegidos pelo Windows DPAPI; não os coloque no arquivo de configurações.
2. Execute `launch.cmd auth` e conclua a autenticação interativa. O código de login e qualquer senha adicional são digitados no terminal.
3. Execute `launch.cmd channels` para localizar e selecionar o canal autorizado.
4. Execute `launch.cmd scan --channel-id ID --max-messages 200` para criar ou atualizar o catálogo observado.
5. Execute `launch.cmd catalog build --channel-id ID` e depois `launch.cmd catalog list` para organizar e consultar o catálogo.
6. Use `launch.cmd download plan --channel-id ID --scope course` para revisar opções; escolha um curso no prompt. Quando estiver pronto, repita com `launch.cmd download queue --channel-id ID --scope course` e confirme a seleção no próprio terminal.

Para escolher outro destino, acrescente `--download-dir "D:\\Cursos"` ao comando `download plan` ou `download queue`. O plano permite conferir os itens e bytes estimados antes do download. A fila baixa somente a seleção confirmada.

## Atualizar

Preserve `%LOCALAPPDATA%\telegram_courses_data` (configurações e banco) e `%LOCALAPPDATA%\telegram_courses` (cofre DPAPI e sessão). Extraia a nova versão candidata em outra pasta e inicie o novo `launch.cmd`; não copie banco, configurações, credenciais ou sessão para dentro do pacote. Compare `package-manifest.json` entre versões antes de substituir a pasta antiga.

O pacote foi preparado para execução por uma conta Windows comum e não solicita privilégios de administrador. O comando `launch.cmd` abre um processo CLI no terminal; mantenha o terminal aberto enquanto o aplicativo estiver em uso.
