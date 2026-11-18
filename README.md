# AzulForge Estoque

Aplicação de demonstração para cadastrar, consultar, editar e excluir produtos. A API e a interface usam FastAPI; o armazenamento local usa SQLite. Na Azure, três Azure Container Apps compartilham um ambiente Consumption e cada app usa seu próprio container no Azure Cosmos DB.

## Decisões de hospedagem e custos

Esta configuração foi pensada para uma demonstração de baixo custo, não para produção real:

- **Azure Container Apps Consumption:** hospeda três apps e URLs independentes. As réplicas podem escalar a zero; quando não há réplicas, não há cobrança de consumo de compute. A franquia mensal, compartilhada com outros usos de Container Apps da assinatura, inclui os primeiros 180.000 vCPU-segundos, 360.000 GiB-segundos e 2 milhões de requisições. O uso acima da franquia, tráfego e outros serviços podem gerar custos. Com a configuração deste projeto, os logs são transmitidos, mas não armazenados em Log Analytics.
- **Azure Container Registry Basic:** armazena a imagem privada publicada pela pipeline e permite que os Container Apps a baixem usando identidade gerenciada. O preço público consultado para Brazil South é aproximadamente **R$ 0,8956 por dia**: cerca de **R$ 2,69 por 3 dias** ou **R$ 26,87 por 30 dias**, enquanto o registry existir. A estimativa usa o preço do registry Basic e não inclui armazenamento acima dos 10 GiB incluídos, tráfego ou mudanças da oferta/impostos. Consulte o [preço atual do Container Registry](https://azure.microsoft.com/pricing/details/container-registry/) antes de criar.
- **Azure Cosmos DB for NoSQL, free tier:** um único account por assinatura pode receber até 1.000 RU/s e 25 GB de armazenamento sem custo, enquanto permanecer dentro desses limites. O free tier precisa ser habilitado ao criar a conta; não está disponível para contas serverless. O Terraform cria um banco com throughput compartilhado de 1.000 RU/s e containers `products-dev`, `products-hml` e `products-prod`. Os dados ficam separados por container, mas throughput e armazenamento são compartilhados entre os três ambientes.
- **Custos que ainda podem ocorrer:** o que exceder as franquias do Container Apps, o armazenamento adicional do registry, o que exceder os limites do Cosmos DB, tráfego e cobranças específicas da oferta/região. A solução inteira não é garantidamente gratuita.
- **`prod` significa demonstração:** esta arquitetura econômica não foi dimensionada ou validada para produção real. Um uso real precisa de segurança/autenticação, monitoramento, backup, recuperação, orçamento e arquitetura revisada. Não publique dados reais nesta versão.

Antes de criar qualquer recurso, confirme:

1. No Portal Azure, selecione a assinatura correta e confira **Subscriptions → Usage + quotas**, políticas, permissões e orçamento.
2. Em **Cosmos DB → Create**, veja se a opção **Free Tier** está disponível. O free tier é limitado a um account por assinatura. Uma conta existente pode já consumir essa elegibilidade.
3. O padrão coloca o grupo de recursos, Cosmos DB, Azure Container Apps e Container Registry em `brazilsouth` (`location` e `app_location`). A Azure CLI listou Brazil South nos tipos de recurso `Microsoft.App/managedEnvironments`, `Microsoft.ContainerRegistry/registries` e `Microsoft.DocumentDB/databaseAccounts`. Isso confirma que os provedores listam a região, mas não garante cota, elegibilidade ou que a criação será aceita pela assinatura.
4. Consulte [cobrança do Azure Container Apps](https://learn.microsoft.com/azure/container-apps/billing), [preços do Container Registry](https://azure.microsoft.com/pricing/details/container-registry/), [limites do Cosmos DB free tier](https://learn.microsoft.com/azure/cosmos-db/free-tier) e a [Calculadora de preços Azure](https://azure.microsoft.com/pricing/calculator/) usando sua região e oferta. A calculadora e o portal são a referência para sua assinatura.
5. A criação do Cosmos DB em East US falhou por alta demanda/acesso regional. O comando para excluir a conta com falha foi executado; confirme que ela não aparece mais com `az cosmosdb show` e confira que o resource group não contém recursos inesperados. A mudança da localização do resource group de East US para Brazil South pode substituí-lo no Terraform; revise o plano cuidadosamente.
6. Opcionalmente, sem provisionar recursos, use a Azure CLI:

   ```powershell
   az login
   az account show --query "{subscription:name, id:id, tenant:tenantId}" --output table
   az provider show --namespace Microsoft.App --query registrationState --output tsv
   az provider show --namespace Microsoft.ContainerRegistry --query registrationState --output tsv
   az provider show --namespace Microsoft.DocumentDB --query registrationState --output tsv
   az cosmosdb list --query "[].{name:name, resourceGroup:resourceGroup, freeTier:enableFreeTier}" --output table
   ```

   `az provider show` apenas consulta o registro. Se `Microsoft.App` retornar `NotRegistered`, registre-o antes de implantar Container Apps com `az provider register --namespace Microsoft.App --wait`; confirme que o estado ficou `Registered`. O registro do provider habilita a assinatura a usar o serviço, mas não cria os recursos da aplicação. `terraform plan` também é apenas uma prévia, não reserva capacidade nem garante que o `apply` será aceito. O `apply` só deve ser executado depois de conferir o custo estimado, a região, a elegibilidade do free tier e as permissões.

## Estrutura

```text
app/
  main.py                 # Rotas web e API
  models.py               # Validação dos dados
  storage.py              # SQLite local e Cosmos DB na Azure
  static/index.html       # Interface de cadastro e estoque
infra/terraform/          # Recursos Azure e isolamento de dados
tests/                    # Testes da API com SQLite temporário
Dockerfile                # Imagem publicada no Azure Container Registry
azure-pipelines.yml       # Build, dev, hml e prod
```

## Rodar localmente (Windows PowerShell)

Requer Python 3.12 ou superior.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

Abra <http://127.0.0.1:8000>. A documentação interativa da API fica em <http://127.0.0.1:8000/docs>. Por padrão, os dados são gravados em `data/dev.sqlite3`. Para rodar outro ambiente localmente, use outro nome:

```powershell
$env:APP_ENV = "hml"
python -m uvicorn app.main:app --reload
```

O SQLite será `data/hml.sqlite3`; `prod` também tem seu arquivo local próprio. Limpar um desses arquivos apaga apenas os dados locais daquele ambiente.

O cabeçalho da página identifica o ambiente atual (`DEV`, `HML` ou `PROD — DEMONSTRAÇÃO`), consultando `/health`. Na Azure, `APP_ENV` é configurado separadamente em cada Container App.

Testes:

```powershell
python -m pytest -q
```

## Preparar a Azure (sem segredos no repositório)

Ferramentas necessárias: Azure CLI, Terraform 1.8+ e acesso à assinatura. No diretório do projeto:

```powershell
az login
az account set --subscription "<id-ou-nome-da-assinatura>"
Set-Location infra\terraform
Copy-Item terraform.tfvars.example terraform.tfvars
# Edite terraform.tfvars e informe subscription_id; location e app_location usam brazilsouth.
terraform init
terraform validate
terraform plan -out=tfplan
terraform show tfplan
```

Revise o plano. O padrão cria o grupo de recursos, Cosmos DB (banco e containers), Container Registry Basic e três Container Apps em Brazil South. Mudar a região ou trocar os recursos pode substituir a infraestrutura; a substituição do Cosmos DB apaga os dados. Não execute `terraform apply` até confirmar a remoção da conta Cosmos com falha, verificar que o resource group contém apenas os recursos esperados, validar o plano, custos e elegibilidade do free tier.

```powershell
terraform apply tfplan
terraform output
```

O arquivo `tfplan` é local e está ignorado pelo Git.

Os nomes para a variável group ficam disponíveis após a criação:

```powershell
terraform output -json container_app_names
terraform output -json urls
terraform output container_registry_name
terraform output resource_group_name
```

O estado do Terraform contém detalhes da infraestrutura e deve ficar local ou em um backend remoto protegido. Não o publique no repositório. O `terraform.tfvars` está ignorado pelo Git; não inclua credenciais nele.

Cada Container App usa uma identidade gerenciada dedicada. Ela recebe `AcrPull` no registry e acesso de dados apenas ao container Cosmos DB daquele ambiente. A identidade que executa o Terraform precisa criar recursos, identidades gerenciadas e atribuições de papel para esses acessos. Isso pode exigir permissões de atribuição de papéis no escopo adequado; peça ao administrador da assinatura para conceder o menor privilégio possível, sem dar `Owner` amplo por conveniência. A autenticação local continua em SQLite e não precisa de credenciais Azure.

Para remover os recursos:

```powershell
terraform destroy
```

**Atenção:** destruir o Cosmos DB apaga os dados armazenados na Azure. Confirme a assinatura e o plano antes de aprovar a destruição. Remova também manualmente service connections e variáveis de pipeline se não forem mais necessárias.

## Azure DevOps: repositório e publicação

1. Crie uma organização/projeto no Azure DevOps e importe ou envie este repositório para o Azure Repos. Adicione `azure-pipelines.yml` como pipeline.
2. Crie uma Azure Resource Manager service connection chamada `azulforge-estoque-azure`, preferencialmente com **Workload identity federation**. Autorize o uso pela pipeline. Conceda o mínimo necessário: `AcrPush` no registry e permissão para atualizar os Container Apps do resource group. Não coloque client secrets, senhas nem chaves no YAML.
3. Crie a variável group `estoque-deploy` com:
   - `azureServiceConnection`: nome da service connection;
   - `resourceGroupName`: output `resource_group_name`;
   - `containerRegistryName`: output `container_registry_name`;
   - `containerAppDev`, `containerAppHml`, `containerAppProd`: valores `dev`, `hml` e `prod` do output `container_app_names`;
   - `urlHml`: URL HTTPS `hml` do output `urls`.
   São nomes/URLs, não segredos. Não marque credenciais como variáveis de texto no YAML.
4. Crie os environments Azure DevOps `estoque-dev`, `estoque-hml` e `estoque-prod`. Em `estoque-prod`, configure **Approvals and checks → Approvals** e escolha os aprovadores. A aprovação manual é uma configuração protegida no Azure DevOps, não um segredo ou uma aprovação codificada em YAML.
5. Faça push para `main`. O pipeline executa os testes, constrói uma única imagem Docker identificada pelo build e publica-a no ACR. A mesma imagem é promovida para dev, depois hml; o pipeline verifica o endpoint de saúde de hml e pausa para validação manual. O stage prod só prossegue após a aprovação configurada no environment.

As permissões da service connection devem ser concedidas por um administrador da assinatura; não as amplie para Owner sem necessidade. Consulte os limites atuais de jobs paralelos do Azure DevOps para sua organização antes de executar a pipeline.

## API

- `GET /api/products` — listar
- `POST /api/products` — cadastrar
- `GET /api/products/{id}` — consultar um item
- `PUT /api/products/{id}` — editar
- `DELETE /api/products/{id}` — excluir
- `GET /health` — verificação de saúde

Produto: `name`, `sku`, `quantity` (inteiro não negativo), `category` e `description`.
