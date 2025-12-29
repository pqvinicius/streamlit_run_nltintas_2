# Guia de Deploy - Streamlit Cloud

## Checklist Pré-Deploy

- [ ] Repositório GitHub criado e código commitado
- [ ] `data/gamificacao_vendedores.db` está no repositório
- [ ] `config.ini` está no repositório
- [ ] `dashboard/requirements.txt` existe e está correto
- [ ] `dashboard/app.py` é o arquivo principal
- [ ] Testado localmente com `streamlit run dashboard/app.py`

## Passo a Passo

### 1. Preparar Repositório

```bash
# Verificar estrutura
ls -la dashboard/
ls -la data/gamificacao_vendedores.db
ls -la config.ini

# Commit e push
git add .
git commit -m "Preparar dashboard para deploy"
git push origin main
```

### 2. Criar App no Streamlit Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io)
2. Faça login com GitHub
3. Clique em "New app"
4. Preencha:
   - **Repository**: Seu repositório
   - **Branch**: `main` (ou `master`)
   - **Main file path**: `dashboard/app.py`
   - **App URL**: Escolha um nome único

### 3. Configurações Avançadas (Opcional)

Se necessário, configure:
- **Python version**: 3.8, 3.9, 3.10 ou 3.11
- **Secrets**: Para configurações sensíveis (não necessário se usar config.ini)

### 4. Deploy

1. Clique em "Deploy"
2. Aguarde o build (pode levar 2-5 minutos)
3. Verifique os logs se houver erros

## Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'dashboard'"

**Solução**: Verifique se a estrutura de pastas está correta:
```
projeto/
├── dashboard/
│   ├── app.py
│   ├── config/
│   ├── database/
│   └── ...
```

### Erro: "FileNotFoundError: Banco de dados não encontrado"

**Solução**: 
1. Verifique se `data/gamificacao_vendedores.db` está no Git
2. Verifique o tamanho do arquivo (Git tem limite de 100MB)
3. Se necessário, use Git LFS para arquivos grandes

### Erro: "ImportError: cannot import name 'X'"

**Solução**: Verifique se todos os `__init__.py` existem nas pastas

### Build Falha

**Solução**:
1. Verifique os logs do build no Streamlit Cloud
2. Verifique se `dashboard/requirements.txt` está correto
3. Teste localmente primeiro

## Atualizações

Para atualizar o app:
1. Faça alterações no código
2. Commit e push para o repositório
3. O Streamlit Cloud detecta automaticamente e faz redeploy

## Monitoramento

- Acesse os logs em tempo real no Streamlit Cloud
- Verifique métricas de uso
- Configure alertas se necessário

## Segurança

- Não commite dados sensíveis
- Use `st.secrets` para informações confidenciais
- Mantenha dependências atualizadas

