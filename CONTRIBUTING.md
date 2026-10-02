# Contributing to Orka

Obrigado pelo interesse em contribuir! A Orka e open-core: os SDKs sao MIT, o backend e managed.

## Como contribuir

### 1. Reportar bugs
- Abra uma issue
- Inclua: versao do Python, versao do orkaia, traceback completo

### 2. Sugerir features
- Abra uma issue com label enhancement
- Descreva o caso de uso e o problema que resolve

### 3. Enviar codigo (SDKs)

```bash
# Fork o repo
git clone https://github.com/SEU_USUARIO/orka.git
cd orka

# Crie uma branch
git checkout -b feat/minha-feature

# Instale em modo dev
cd python
pip install -e ".[dev]"

# Rode os testes
pytest

# Commit e push
git commit -m "feat: descricao clara"
git push origin feat/minha-feature
```

## Guidelines

- Python: siga PEP 8, use type hints
- Testes: todo PR precisa de teste
- Docs: atualize o README se mudar API
- Commits: use Conventional Commits

## Labels de issue

| Label | Descricao |
|-------|-----------|
| good first issue | ideal para quem esta comecando |
| bug | algo esta quebrado |
| enhancement | nova feature |
| documentation | docs precisam de ajuda |
| integration | nova integracao com framework |

## Duvidas?

- Abra uma discussion no GitHub
- Ou envie: contato@orka.ia.br
