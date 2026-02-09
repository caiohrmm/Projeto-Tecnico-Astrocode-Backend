# Desafio Técnico - Astrocode

<div align="center">

**CRM Imobiliário com Inteligência Artificial**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org)

[Funcionalidades](#-funcionalidades) • [Arquitetura](#-arquitetura) • [Instalação](#-instalação) • [API](#-referência-da-api) • [IA](#-capacidades-de-ia)

</div>

---

## 🎯 Sobre o Projeto

Sistema de CRM (Customer Relationship Management) desenvolvido para imobiliárias e corretores de imóveis. A aplicação resolve os principais desafios do setor:

- **Gestão de Leads** — Acompanhamento completo do cliente desde o primeiro contato até o fechamento
- **Insights Inteligentes** — IA analisa automaticamente cada atendimento, extraindo informações-chave e sugerindo próximos passos
- **Histórico de Atendimentos** — Registro completo de todas as comunicações via WhatsApp, telefone, e-mail e presencial
- **Match de Imóveis** — Recomendações inteligentes vinculando preferências do cliente aos imóveis disponíveis
- **Analytics de Performance** — Acompanhamento de vendas, perdas e desempenho com análise de padrões por IA

> Desenvolvido para equipes que querem gastar menos tempo com cadastros e mais tempo fechando negócios.

---

## ✨ Funcionalidades

### CRM Principal
| Funcionalidade | Descrição |
|----------------|-----------|
| **Gestão de Clientes/Leads** | Acompanhamento completo do ciclo de vida com funil personalizável |
| **Registro de Atendimentos** | Log de toda interação com clientes em todos os canais |
| **Catálogo de Imóveis** | Gerenciamento de anúncios com fotos, detalhes e status |
| **Agendamento de Visitas** | Agendar, confirmar e acompanhar visitas a imóveis |
| **Gestão de Vendas** | Registro de transações com acompanhamento de comissões |
| **Análise de Perdas** | Documentação de negócios perdidos para identificar melhorias |

### Inteligência Artificial
| Funcionalidade | Descrição |
|----------------|-----------|
| **Resumo Automático** | Todo atendimento é automaticamente resumido pela IA |
| **Detecção de Intenção** | IA identifica intenções do cliente (comprar, alugar, agendar visita, negociar) |
| **Enriquecimento de Perfil** | Extrai automaticamente orçamento, preferências de localização e tipo de imóvel |
| **Lead Scoring** | Pontuação dinâmica baseada na análise das interações |
| **Assistente em Tempo Real** | Sugestões ao vivo durante o atendimento (perguntas, imóveis para mostrar) |
| **Classificação de Leads** | Novos leads são automaticamente pontuados e priorizados |
| **Análise de Padrões de Perda** | IA identifica tendências em negócios perdidos |

### Segurança e Autenticação
- Autenticação JWT com expiração configurável
- Integração com Google OAuth 2.0
- Controle de acesso por papéis (Gestor, Corretor, Atendente)

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                       Aplicação FastAPI                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │   Auth   │ │ Clientes │ │Atendimen.│ │ Imóveis  │           │
│  │  Módulo  │ │  Módulo  │ │  Módulo  │ │  Módulo  │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
│       │            │            │            │                   │
│  ┌────┴────────────┴────────────┴────────────┴─────┐            │
│  │                 Serviços de IA                   │            │
│  │  • Integração Gemini    • Análise em Tempo Real │            │
│  │  • Jornada do Cliente   • Classificação de Lead │            │
│  └─────────────────────────────────────────────────┘            │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────┐          │
│  │              SQLAlchemy ORM + Alembic             │          │
│  └───────────────────────────────────────────────────┘          │
│                              │                                   │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │    PostgreSQL       │
                    │    Banco de Dados   │
                    └─────────────────────┘
```

### Estrutura do Projeto

```
app/
├── ai/                 # Serviços de IA e integração Gemini
│   ├── gemini_service.py      # Cliente da API Google Gemini
│   ├── realtime_assistant.py  # Análise em tempo real durante atendimento
│   ├── lead_classifier.py     # Pontuação automática de leads
│   ├── journey_service.py     # Análise da jornada do cliente
│   └── service.py             # Sumarização de atendimentos
├── auth/               # Autenticação e autorização
│   ├── jwt.py                 # Geração/validação de tokens
│   ├── oauth_service.py       # Integração Google OAuth
│   └── dependencies.py        # Dependências de auth FastAPI
├── clients/            # Domínio de Clientes/Leads
│   ├── models.py              # Modelos SQLAlchemy
│   ├── timeline_models.py     # Eventos da jornada do cliente
│   └── score_service.py       # Lógica de pontuação de leads
├── attendances/        # Domínio de Atendimentos
├── properties/         # Domínio de Imóveis
├── visits/             # Domínio de Visitas
├── sales/              # Domínio de Vendas
├── losses/             # Domínio de Perdas e Análise
├── users/              # Gestão de Usuários e Papéis
├── config/             # Configurações da aplicação
├── db/                 # Sessão do banco e modelos base
└── main.py             # Ponto de entrada da aplicação
```

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.11 ou superior
- PostgreSQL 13+
- Chave da API Google Gemini (para recursos de IA)

### Passo a Passo

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd Projeto-Tecnico-Astrocode-Backend

# Crie o ambiente virtual
python -m venv .venv

# Ative o ambiente
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instale as dependências
pip install -e .
```

### Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
# Banco de Dados
DATABASE_URL=postgresql://usuario:senha@localhost:5432/real_estate_crm

# Autenticação JWT
JWT_SECRET_KEY=sua-chave-secreta-mude-em-producao
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# IA (Google Gemini)
GEMINI_API_KEY=sua-chave-gemini

# Google OAuth (opcional)
GOOGLE_CLIENT_ID=seu-google-client-id
GOOGLE_CLIENT_SECRET=seu-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Cloudinary (opcional, para upload de imagens)
CLOUDINARY_CLOUD_NAME=seu-cloud-name
CLOUDINARY_API_KEY=sua-api-key
CLOUDINARY_API_SECRET=seu-api-secret

# URL do Frontend
FRONTEND_URL=http://localhost:5173
```

### Configurar Banco de Dados

```bash
# Criar banco de dados
psql -U postgres -c "CREATE DATABASE real_estate_crm;"

# Executar migrações
alembic upgrade head
```

### Executar o Servidor

```bash
uvicorn app.main:app --reload --port 8000
```

A API estará disponível em:
- **Base da API:** http://localhost:8000
- **Documentação Interativa (Swagger):** http://localhost:8000/docs
- **Documentação Alternativa (ReDoc):** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

### Criar Primeiro Usuário

```bash
# Criar usuário gestor
python scripts/create_manager.py --email admin@exemplo.com --password senha123 --name "Admin"

# Ou criar usuário de teste
python scripts/create_test_user.py
```

---

## 📚 Referência da API

### Autenticação

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/auth/login` | Login com email/senha |
| `GET` | `/auth/me` | Obter info do usuário atual |
| `GET` | `/auth/google/login` | Iniciar fluxo Google OAuth |
| `GET` | `/auth/google/callback` | Callback do OAuth |

### Clientes

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/clients/` | Listar clientes com filtros |
| `POST` | `/clients/` | Criar cliente (classificação automática por IA) |
| `GET` | `/clients/{id}` | Obter detalhes do cliente |
| `PUT` | `/clients/{id}` | Atualizar cliente |
| `DELETE` | `/clients/{id}` | Excluir cliente e dados relacionados |

### Atendimentos

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/attendances/` | Listar atendimentos |
| `POST` | `/attendances/` | Criar atendimento (dispara análise IA) |
| `GET` | `/attendances/{id}` | Obter atendimento com resumo IA |
| `PUT` | `/attendances/{id}` | Atualizar atendimento |

### Endpoints de IA

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/ai/realtime/analyze` | Análise de texto em tempo real |
| `GET` | `/ai/journey/{client_id}` | Contexto da jornada do cliente por IA |
| `POST` | `/ai/chat` | Assistente de IA conversacional |
| `GET` | `/losses/patterns` | Análise de padrões de perda por IA |

### Imóveis, Visitas, Vendas, Perdas

Operações CRUD completas disponíveis. Veja `/docs` para referência completa.

---

## 🤖 Capacidades de IA

### Como a IA Melhora Cada Interação

```
┌─────────────────────────────────────────────────────────────┐
│                   ATENDIMENTO CRIADO                         │
│  "Cliente quer apartamento 3 quartos no centro,              │
│   orçamento em torno de 500 mil, precisa mudar em 2 meses"  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    🤖 PROCESSAMENTO IA                       │
├─────────────────────────────────────────────────────────────┤
│  ✓ Resumo: "Interessado em apto centro, 3 quartos, 500k"   │
│  ✓ Intenção: SOLICITAÇÃO_INFORMAÇÕES                        │
│  ✓ Tipo de Interesse: COMPRA                                │
│  ✓ Tipo de Imóvel: APARTAMENTO                              │
│  ✓ Orçamento: R$ 450.000 - R$ 550.000                       │
│  ✓ Urgência: ALTA (prazo de 2 meses)                        │
│  ✓ Lead Score: 85/100                                        │
│  ✓ Próximos Passos Sugeridos:                               │
│    1. Agendar visitas em 3 imóveis compatíveis              │
│    2. Discutir opções de financiamento                       │
│  ✓ Imóveis Recomendados: [Apto 301, Apto 412, Apto 205]     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              PERFIL DO CLIENTE ATUALIZADO                    │
│  • Status: NEW_LEAD → QUALIFIED                              │
│  • Orçamento: R$ 450k - 550k                                 │
│  • Cidade: Centro                                            │
│  • Tipo de Imóvel: Apartamento                               │
│  • Urgência: ALTA                                            │
│  • Lead Score: 85                                            │
└─────────────────────────────────────────────────────────────┘
```

### Assistente em Tempo Real

Durante a criação do atendimento, a IA fornece sugestões ao vivo:

- **Detecção de Informações** — Orçamento, localização, preferências de imóvel
- **Sugestões de Perguntas** — "Perguntar sobre preferência de financiamento", "Esclarecer prazo de mudança"
- **Match de Imóveis** — "3 imóveis compatíveis: clique para adicionar"
- **Reconhecimento de Intenção** — Detecta quando cliente quer agendar visita ou negociar

---

## 🗃️ Migrações do Banco de Dados

```bash
# Ver status atual das migrações
alembic current

# Aplicar todas as migrações pendentes
alembic upgrade head

# Criar nova migração (após alterar modelos)
alembic revision --autogenerate -m "Descrição das alterações"

# Reverter última migração
alembic downgrade -1

# Ver histórico de migrações
alembic history
```

---

## 🔐 Segurança

### Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | ✅ | String de conexão PostgreSQL |
| `JWT_SECRET_KEY` | ✅ | Segredo para assinatura JWT (use valor aleatório forte) |
| `GEMINI_API_KEY` | ⚠️ | Necessária para recursos de IA |
| `GOOGLE_CLIENT_ID` | ❌ | Para Google OAuth |
| `GOOGLE_CLIENT_SECRET` | ❌ | Para Google OAuth |
| `CLOUDINARY_*` | ❌ | Para upload de imagens |

### Controle de Acesso por Papéis

| Papel | Permissões |
|-------|------------|
| **Gestor** | Acesso total, gestão de usuários, relatórios |
| **Corretor** | Gerenciar clientes, atendimentos, imóveis, vendas |
| **Atendente** | Criar atendimentos, visualizar clientes |

---

## 🧪 Testes

```bash
# Instalar dependências de desenvolvimento
pip install -e ".[dev]"

# Executar testes
pytest

# Executar com cobertura
pytest --cov=app
```

---

## 📖 Documentação Adicional

- [Guia de Autenticação](docs/AUTHENTICATION.md) — Documentação detalhada do fluxo de auth
- [Vinculação de Usuários OAuth](docs/OAUTH_USER_LINKING.md) — Como contas OAuth são vinculadas
- [Documentação do Sistema](docs/DOCUMENTACAO_SISTEMA.md) — Fluxo completo do sistema

---

## 🛠️ Solução de Problemas

<details>
<summary><strong>Erro de conexão com banco de dados</strong></summary>

Verifique se o PostgreSQL está rodando e se `DATABASE_URL` está correta:
```bash
psql -U seu_usuario -d real_estate_crm -c "SELECT 1;"
```
</details>

<details>
<summary><strong>ModuleNotFoundError</strong></summary>

Certifique-se de que o ambiente virtual está ativado e dependências instaladas:
```bash
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -e . --force-reinstall
```
</details>

<details>
<summary><strong>Recursos de IA não funcionando</strong></summary>

Verifique se `GEMINI_API_KEY` está definida no `.env` e é válida. O sistema fará fallback para análise básica se a IA estiver indisponível.
</details>

<details>
<summary><strong>Porta já em uso</strong></summary>

Use uma porta diferente:
```bash
uvicorn app.main:app --reload --port 8001
```
</details>

---

<div align="center">

**Desenvolvido como Desafio Técnico para a vaga na Astrocode**

[⬆ Voltar ao topo](#desafio-técnico---astrocode)

</div>
