# Dashboard de Olimpíadas de Vendas

Dashboard interativo para visualização de rankings e medalhas do sistema de gamificação de vendedores.

## Estrutura do Projeto

```
dashboard/
├── app.py                    # Entry point principal (Streamlit)
├── config/                   # Configurações
│   ├── settings.py          # Configurações centralizadas
│   └── paths.py             # Gerenciamento de caminhos
├── database/                 # Acesso a dados
│   ├── connection.py        # Gerenciador de conexão SQLite
│   └── queries.py           # Queries centralizadas
├── services/                 # Lógica de negócio
│   ├── medal_service.py     # Serviço de medalhas
│   └── period_service.py     # Serviço de períodos comerciais
├── ui/                       # Componentes visuais
│   ├── components.py        # Componentes reutilizáveis
│   └── styles.py            # CSS e estilos
└── utils/                    # Utilitários
    └── helpers.py           # Funções auxiliares
```

## Funcionalidades

- **Quadro de Medalhas**: Visualização geral do ranking com top 3 destacados
- **Perfil do Atleta**: Histórico individual de conquistas
- **Conquistas por Semana**: Agrupamento e visualização de medalhas por semana
- **Gráficos Interativos**: Visualização de pontos por semana

## Requisitos

- Python 3.8+
- Streamlit 1.28.0+
- Pandas 2.0.0+
- Banco de dados SQLite (`data/gamificacao_vendedores.db`)
- Arquivo de configuração (`config.ini`)

## Instalação Local

1. Instale as dependências:
```bash
pip install -r dashboard/requirements.txt
```

2. Execute o dashboard:
```bash
streamlit run dashboard/app.py
```

## Deploy no Streamlit Cloud

### Pré-requisitos

1. **Repositório GitHub**: O código deve estar em um repositório GitHub público ou privado
2. **Banco de Dados**: O arquivo `data/gamificacao_vendedores.db` deve estar versionado no Git
3. **Configuração**: O arquivo `config.ini` deve estar versionado no Git

### Passo a Passo

1. **Preparar o Repositório**:
   - Certifique-se de que `data/gamificacao_vendedores.db` está no Git
   - Certifique-se de que `config.ini` está no Git
   - Certifique-se de que `dashboard/requirements.txt` existe

2. **Criar App no Streamlit Cloud**:
   - Acesse [share.streamlit.io](https://share.streamlit.io)
   - Faça login com sua conta GitHub
   - Clique em "New app"
   - Selecione o repositório
   - Configure:
     - **Main file path**: `dashboard/app.py`
     - **Python version**: 3.8 ou superior

3. **Deploy**:
   - Clique em "Deploy"
   - Aguarde o build e deploy automático

### Configuração do Streamlit Cloud

O Streamlit Cloud detecta automaticamente:
- `requirements.txt` na raiz ou em `dashboard/requirements.txt`
- Python version do arquivo `.python-version` (opcional)

### Troubleshooting

**Erro: "Banco de dados não encontrado"**
- Verifique se `data/gamificacao_vendedores.db` está no repositório
- Verifique se o caminho está correto (deve ser relativo à raiz)

**Erro: "Config.ini não encontrado"**
- Verifique se `config.ini` está no repositório
- O sistema usa valores padrão se não encontrar

**Erro de dependências**
- Verifique se `dashboard/requirements.txt` está correto
- Verifique se as versões são compatíveis

## Arquitetura

### Separação de Responsabilidades

- **config/**: Configurações e caminhos
- **database/**: Acesso ao banco de dados (isolado)
- **services/**: Lógica de negócio (cache, processamento)
- **ui/**: Componentes visuais reutilizáveis
- **utils/**: Funções auxiliares

### Cache Strategy

- `@st.cache_data`: Para dados (TTL de 60s)
- `@st.cache_resource`: Para serviços (singleton)
- Cache invalidado manualmente via botão "Atualizar"

### Tratamento de Erros

- Todas as operações de banco têm try/except
- Mensagens amigáveis para o usuário
- Fallback para DataFrames vazios
- Validação de existência do banco antes de usar

## Manutenção

### Adicionar Nova Query

1. Adicione a função em `database/queries.py`
2. Adicione método correspondente em `services/medal_service.py`
3. Use `@st.cache_data` para cache

### Adicionar Novo Componente UI

1. Crie função em `ui/components.py`
2. Importe e use em `app.py`

### Atualizar Configurações

1. Modifique `config/settings.py`
2. Use `AppSettings` para acessar configurações

## Licença

Este projeto faz parte do sistema de Ranking e Gamificação de Vendedores v2.0.

