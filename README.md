# Ranking de Vendedores - Gamificação & Automação

Projeto de automação para geração de rankings de vendas, gamificação de equipe e distribuição de metas, com integração via WhatsApp e Dashboard interativo.

## 📋 Visão Geral

Este software automatiza o cálculo e a divulgação do desempenho comercial da equipe. Ele ingere planilhas de metas diárias, calcula indicadores de gamificação (dias de meta batida, alcance, medalhas) e gera visualizações profissionais que são enviadas automaticamente nos grupos de WhatsApp da loja.

**Objetivo:** Engajamento, transparência de resultados e motivação da equipe de vendas.

---

## 🚀 Principais Funcionalidades

### 1. Rankings Automatizados

- **Diário:** Exibe performance do dia com indicadores visuais (% alcance, barras de progresso).
- **Semanal:** Foca em consistência (número de dias com meta batida) e alcance acumulado.
- **Mensal:** Ranking principal para premiação de medalhas.
- **Quadro de Medalhas:** Histórico acumulado de conquistas (Ouro/Prata/Bronze).

### 2. Gamificação

- **Metas Batidas:** Indicadores visuais (quadrados verdes) para dias de sucesso.
- **Sistema de Medalhas:**
  - 🥇 **Ouro:** Meta mensal batida.
  - 🥈 **Prata:** Meta semanal batida.
  - 🥉 **Bronze:** Meta diária batida.

### 3. Comunicação

- **WhatsApp Bot:** Envio automático das imagens geradas para grupos configurados.
- **Idempotência:** Sistema inteligente que evita envios duplicados no mesmo dia/turno.

### 4. Visualização

- **Geração de Imagens:** HTML/CSS renderizado via engine Chromium para alta qualidade visual.
- **Dashboard Web:** Interface Streamlit para visualização de dados históricos e acompanhamento em tempo real (local ou cloud).

---

## 🏗️ Arquitetura

- **Linguagem:** Python 3.10+
- **Banco de Dados:** SQLite (`gamificacao_vendedores.db`) - Armazena histórico, metas e troféus.
- **Engine de Renderização:** Jinja2 (Templates) + Playwright (Headless Browser) -> PNG.
- **Automação Web:** Selenium WebDriver (Edge) para integrações específicas de WhatsApp Web.
- **Interface:** Streamlit (Dashboard) e Tkinter (Logs/Monitoramento).

---

## ⚙️ Como Executar

### 1. Modo Local (Desenvolvimento)

Para rodar scripts manualmente ou testar alterações:

```bash
# Ativar ambiente virtual
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# Rodar bot principal
python main.py

# Rodar Dashboard
streamlit run dashboard/app.py
```

### 2. Modo Produção (Scheduler)

O sistema é projetado para rodar via **Agendador de Tarefas do Windows** (Task Scheduler) através do executável compilado.

- **Executável:** `dist/RankingVendedoresBot/RankingVendedores.exe`
- **Configuração:** O arquivo `config.ini` deve estar na mesma pasta do executável.
- **Observação:** O processo depende de uma sessão ativa do WhatsApp Web.

⚠️ **Importante:** Feche todas as janelas do navegador Edge/Chrome controladas por automação antes de iniciar um novo ciclo para evitar conflitos de driver.

---

## 🔒 Segurança & Dados

- **Dados Sensíveis:** O arquivo `vendedores_contato.csv` (telefones reais) **NÃO** é versionado.
- **Exemplo:** Utilize `vendedores_contato.example.csv` como modelo para criar o arquivo real localmente.
- **Dados de Venda:** Armazenados localmente no SQLite. Não commite backups de banco de dados (`.db`) ou planilhas de venda (`.xls`/`.xlsx`) no repositório.

---

## ⚠️ Avisos Importantes

1.  **Ambiente Virtual:** Nunca suba a pasta `venv/` para o controle de versão.
2.  **CSVs Reais:** Mantenha os arquivos de dados na pasta `data/` localmente, mas validando o `.gitignore`.
3.  **Logs:** A pasta `logs/` contém histórico de execução útil para debug, mas deve ser limpa periodicamente.

---

**Desenvolvido para uso interno | Equipe Comercial**
