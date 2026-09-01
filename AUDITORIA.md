# Auditoria do delivery-system

## Resumo

O projeto é um protótipo funcional de entregas locais com três interfaces: cliente, motoboy e administrador. O backend possui autenticação, pedidos, endereços, área piloto e GPS em tempo real. A base está organizada, mas havia alguns pontos que poderiam causar falhas em uso real.

## Problemas encontrados e tratamento previsto

| Área | Observação | Ação |
|---|---|---|
| Validação | Vários textos, valores e coordenadas tinham limites incompletos. | Adicionar limites e rejeitar valores infinitos ou inválidos. |
| Pedidos | Um motoboy offline podia tentar aceitar pedido; cancelamentos não libertavam sempre o motoboy. | Reforçar regras de estado e libertar o motoboy ao cancelar. |
| Concorrência | Dois motoboys poderiam tentar aceitar o mesmo pedido em condições de corrida. | Usar bloqueio da linha durante a aceitação. |
| Endereços | Remover um endereço já usado por pedido poderia resultar em erro interno. | Retornar conflito compreensível. |
| GPS | O frontend usava o identificador da conta no caminho que espera o identificador do perfil de motoboy. | Buscar `/motoboys/me` após login e usar o ID correto. |
| WebSocket | Payloads malformados podiam encerrar a ligação; mensagens de validação expunham detalhes internos. | Tratar erros de formato de forma controlada e devolver mensagem genérica. |
| CORS | Métodos e cabeçalhos estavam mais abertos do que o necessário. | Restringir aos métodos e cabeçalhos usados pela aplicação. |
| Frontend | Alguns fluxos dependiam de `innerHTML` e o resumo podia mostrar o primeiro endereço, não o selecionado. | Escapar valores e ligar o resumo ao endereço escolhido. |
| Produção | Rate limit e tokens temporários ficam em memória, o que limita múltiplas instâncias. | Manter para o piloto e documentar como limitação futura. |

## Limitações mantidas de propósito

Não serão introduzidos pagamentos, migração de banco, mudança de autenticação ou alteração de contratos de API sem necessidade. O objetivo é corrigir falhas reais, reforçar validações e manter compatibilidade com as interfaces existentes.

## Correções aplicadas nesta revisão

- Limites e formatos foram adicionados aos textos, coordenadas, velocidade, precisão, valores e senha.
- O cadastro público passou a criar apenas clientes; a criação de motoboys permanece reservada ao fluxo administrativo.
- A aceitação de pedidos agora exige motoboy disponível e bloqueia o pedido durante a operação.
- Cancelamento e conclusão libertam o motoboy quando aplicável.
- Endereços associados a pedidos não podem ser apagados e devolvem conflito explicativo.
- O WebSocket de GPS aceita somente o próprio motoboy, trata mensagens inválidas e protege sessões concorrentes.
- O painel do motoboy busca o ID correto do perfil e restaura pedido ativo depois de novo login.
- O cliente restaura pedido ativo, mostra o endereço escolhido corretamente e encerra polling/WebSocket com limpeza.
- A renderização dinâmica do cliente, motoboy e administrador passou a escapar valores antes de os inserir em HTML.
- CORS foi reduzido aos métodos e cabeçalhos utilizados.
- Os scripts auxiliares foram corrigidos para criação de administrador e simulação de GPS configurável.
- Foram adicionados testes automatizados de contratos, rotas, cabeçalhos, páginas estáticas e saúde da aplicação.

## Validação

Foram executados com sucesso os testes automatizados, a compilação dos módulos Python, a verificação de sintaxe dos scripts JavaScript, a importação dos módulos do backend, a verificação do esquema de rotas e o carregamento visual das páginas inicial, cliente, motoboy e administrador no preview local.

A validação não incluiu uma operação completa com base de dados PostgreSQL nem GPS de um dispositivo real, porque o ambiente local não possui uma base configurada nem deve receber dados pessoais reais durante esta revisão.

## Revisão final de segurança e privacidade

A sessão do cliente deixou de ser mantida no armazenamento permanente do navegador e passou a existir apenas enquanto o separador estiver aberto. Isso reduz a exposição de um token abandonado em computadores partilhados, embora a proteção ideal para uma aplicação pública continue a ser uma sessão baseada em cookie seguro e HttpOnly.

Foi adicionada uma política de segurança de conteúdo ao backend. Ela limita scripts, estilos, imagens, ligações e frames aos recursos necessários do próprio sistema, do Leaflet e dos mapas OpenStreetMap. Também foi corrigido o módulo de tokens temporários do WebSocket, que precisava de importar o gerador criptográfico e agora limpa tokens expirados antes de criar novos.

A revisão final confirmou que a aplicação não contém ficheiros `.env` rastreados nem credenciais no repositório. Os logs encontrados registam identificadores operacionais de motoboys e pedidos, mas não registam palavras-passe ou tokens de autenticação.

A bateria final passou com **10 testes automatizados aprovados**. Ela cobre a saúde da aplicação, páginas estáticas, cabeçalhos de segurança, contratos de entrada, transições de pedidos, concorrência de sessões WebSocket e uso único/expiração dos tokens temporários. A sintaxe dos três scripts JavaScript e a compilação dos módulos Python também foram aprovadas.
