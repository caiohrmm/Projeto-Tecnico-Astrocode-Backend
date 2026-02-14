# 🏠 Sistema CRM Imobiliário com Inteligência Artificial

<div align="center">

**Sistema completo de gestão imobiliária com IA integrada para otimização de vendas e atendimento**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Google Gemini AI](https://img.shields.io/badge/Google%20Gemini-AI-4285F4?logo=google&logoColor=white)](https://ai.google.dev)

</div>

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura e Tecnologias](#-arquitetura-e-tecnologias)
- [Funcionalidades da IA](#-funcionalidades-da-inteligência-artificial)
- [Fluxo Completo do Sistema](#-fluxo-completo-do-sistema)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Instalação e Configuração](#-instalação-e-configuração)
- [API Endpoints](#-api-endpoints)
- [Funcionalidades Principais](#-funcionalidades-principais)
- [Segurança e Autenticação](#-segurança-e-autenticação)
- [Banco de Dados](#-banco-de-dados)

---

## 🎯 Visão Geral

Sistema completo de CRM (Customer Relationship Management) desenvolvido especificamente para imobiliárias, com integração profunda de Inteligência Artificial para automatizar e otimizar processos de vendas, atendimento e gestão de clientes.

### Objetivos do Sistema

- **Automatizar** a análise de conversas e interações com clientes
- **Otimizar** a priorização de leads baseada em inteligência artificial
- **Acelerar** o processo de matching entre clientes e imóveis
- **Aumentar** a taxa de conversão através de insights acionáveis
- **Rastrear** todo o ciclo de vida do cliente desde o primeiro contato até a venda/perda

---

## 🏗️ Arquitetura e Tecnologias

### Stack Tecnológico

#### Backend
- **Python 3.11+** - Linguagem principal
- **FastAPI** - Framework web moderno e de alta performance
- **SQLAlchemy 2.0** - ORM para gerenciamento de banco de dados
- **PostgreSQL** - Banco de dados relacional robusto
- **Alembic** - Migrações de banco de dados
- **Pydantic** - Validação de dados e schemas
- **Google Gemini AI** - Motor de inteligência artificial

#### Autenticação e Segurança
- **JWT (JSON Web Tokens)** - Autenticação stateless
- **bcrypt** - Hash de senhas
- **OAuth 2.0** - Login com Google
- **RBAC (Role-Based Access Control)** - Controle de acesso baseado em roles

#### Integrações
- **Cloudinary** - Gerenciamento de imagens de imóveis
- **Google Generative AI** - Processamento de linguagem natural

### Arquitetura do Sistema

```
┌─────────────────┐
│   Frontend      │  Vue.js + Vuetify
│   (Vue.js)      │
└────────┬────────┘
         │ HTTP/REST
         │
┌────────▼────────┐
│   Backend       │  FastAPI
│   (Python)      │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
┌───▼───┐ ┌──▼───┐ ┌───▼───┐ ┌───▼───┐
│PostgreSQL│ │Gemini AI│ │Cloudinary│ │ OAuth  │
│Database │ │   API   │ │  Images  │ │ Google │
└────────┘ └─────────┘ └──────────┘ └────────┘
```

---

## 🤖 Funcionalidades da Inteligência Artificial

O sistema utiliza **Google Gemini AI** para processar e analisar todas as interações com clientes, fornecendo insights acionáveis em tempo real.

### 1. Atualização Automática de Perfil do Cliente

**Quando:** Automaticamente a cada atendimento registrado ou atualizado

**O que faz:**
- **Valores iniciais padrão** ao criar cliente:
  - Status: `NEW_LEAD`
  - Lead Score: `30` (base)
  - Urgência: `MEDIUM`
- **Atualização contínua** através de atendimentos:
  - Analisa cada conversa no ciclo ACTIVE
  - Detecta mudanças em interesse, orçamento, urgência
  - Atualiza perfil incrementalmente conforme o ciclo progride
  - **Lead Score** aumenta gradualmente conforme mais dados são coletados

**⚠️ IMPORTANTE:** O sistema não utiliza mais classificação inicial explícita. Todos os campos do perfil são atualizados automaticamente pela IA através da análise de atendimentos no ciclo ACTIVE.

**Implementação:** `app/clients/state_derivation_service.py` e `app/attendances/repository.py`

### 2. Análise de Atendimentos (AI Summary)

**Quando:** A cada novo atendimento registrado ou atualizado

**O que faz:**
- **Gera resumo profissional** do atendimento em português brasileiro
- **Extrai pontos-chave** da conversa (requisitos, preferências, menções)
- **Detecta intenção** do cliente:
  - `SCHEDULE_VISIT` - Cliente quer agendar visita
  - `PRICE_NEGOTIATION` - Cliente está negociando preço
  - `PROPERTY_SEARCH` - Cliente está buscando imóveis
  - `DOCUMENTATION_REQUEST` - Cliente precisa de documentos
  - `COMPLAINT` - Cliente está reclamando
  - `GENERAL_INQUIRY` - Consulta geral
- **Detecta sentimento** (POSITIVE, NEUTRAL, NEGATIVE)
- **Calcula score de confiança** da análise
- **Sugere Lead Score** atualizado baseado na conversa
- **Recomenda propriedades** que combinam com o perfil do cliente

**Implementação:** `app/ai/service.py` - `AISummaryService`

### 3. Detecção Automática de Visitas

**Quando:** Durante o processamento de um atendimento

**O que faz:**
- Analisa o conteúdo do atendimento procurando por intenção de agendar visita
- Extrai automaticamente:
  - **Data e hora** da visita desejada
  - **Imóvel** mencionado (se houver)
  - **Notas** adicionais sobre a visita
- **Valida** se a data/hora está no futuro e dentro do horário comercial
- Retorna informações estruturadas para o frontend criar a visita automaticamente

**Exemplo de detecção:**
```
"Cliente deseja marcar uma visita para o apartamento no dia 15/02/2026 às 14h"
→ Detecta: scheduled_at=2026-02-15 14:00, property_id=<id_do_apartamento>
```

**Implementação:** `app/ai/service.py` - `detect_visit_intent()`

### 4. Detecção e Vinculação Automática de Imóveis

**Quando:** Durante o processamento de um atendimento

**O que faz:**
- Analisa o conteúdo procurando por menções a imóveis específicos
- Busca imóveis por:
  - **Código do imóvel** (ex: "AP-123")
  - **Endereço** mencionado
  - **Características** (tipo, quartos, localização)
- **Vincula automaticamente** o imóvel ao atendimento
- **Detecta confirmação** quando o cliente confirma interesse em um imóvel já vinculado
- Cria eventos na timeline do cliente quando um imóvel é selecionado ou confirmado

**Implementação:** `app/ai/service.py` - `detect_property_mention()`

### 5. Derivação de Estado do Cliente (State Derivation)

**Quando:** Após cada análise de atendimento pela IA no ciclo ACTIVE

**O que faz:**
- **Consolida sinais** apenas do ciclo ACTIVE atual (não histórico)
- **Atualiza incrementalmente** o perfil do cliente:
  - Tipo de interesse (BUY, RENT, SELL, INVEST)
  - Tipo de imóvel preferido
  - Cidade de interesse
  - Orçamento mínimo e máximo
  - Nível de urgência
  - **Lead Score** (atualizado gradualmente conforme o ciclo de atendimento)
  - **Status** (detectado baseado em intent, sentiment, visits, lead_score)
- **Anti-flip logic**: Previne oscilações bruscas nos valores (exceto lead_score e status)
- **Rastreabilidade**: Cada valor tem origem rastreável (qual atendimento gerou)
- **Priorização**: Sinais mais recentes e com maior confiança têm mais peso
- **Cluster logic**: Agrupa sinais por Attendance para evitar misturar contextos diferentes

**⚠️ CRÍTICO - Proteções Implementadas:**
1. **Nunca pode existir 2 ACTIVE**: Sistema garante apenas um ciclo ACTIVE por cliente
2. **Não atualiza de ciclo fechado**: Perfil só é atualizado a partir de ciclos ACTIVE
3. **Toda atualização passa pelo ciclo**: Campos AI-controlados só podem ser atualizados via atendimentos
4. **Mantém estado se não houver ACTIVE**: Se não houver ciclo ACTIVE, perfil mantém último estado até novo ciclo surgir

**Campos controlados exclusivamente pela IA:**
- `current_interest_type` - Tipo de interesse (BUY, RENT, SELL, INVEST)
- `current_property_type` - Tipo de imóvel preferido
- `current_city_interest` - Cidade de interesse
- `current_budget_min` - Orçamento mínimo
- `current_budget_max` - Orçamento máximo
- `current_urgency_level` - Nível de urgência (LOW, MEDIUM, HIGH, IMMEDIATE)
- `current_lead_score` - Score do lead (0-100)
- `current_status` - Status no funil de vendas (NEW_LEAD, CONTACTED, QUALIFIED, etc.)

**⚠️ CRÍTICO:** O perfil do cliente reflete **APENAS o ciclo ACTIVE atual**, não histórico consolidado:
- Quando um novo ciclo ACTIVE começa, o perfil é atualizado baseado **APENAS nesse ciclo**
- Ciclos anteriores (COMPLETED, LOST, ABANDONED) **NÃO são considerados**
- Isso garante que o perfil sempre reflita o objetivo e contexto atual do cliente

**Implementação:** `app/clients/state_derivation_service.py`

### 6. Análise de Jornada do Cliente (Journey Analysis)

**Quando:** Solicitado via API para análise completa

**O que faz:**
- Analisa **todo o histórico** do cliente:
  - Todos os atendimentos
  - Todas as visitas
  - Propriedades visualizadas
  - Status atual
- **Identifica estágio** da jornada:
  - Descoberta
  - Consideração
  - Decisão
  - Pós-venda
- **Sugere próximas ações** baseadas no contexto completo
- **Calcula saúde do relacionamento** com o cliente
- **Detecta padrões** e tendências

**Implementação:** `app/ai/journey_service.py`

### 7. Chat Assistente com IA

**Quando:** Solicitado via API

**O que faz:**
- Permite conversação natural com a IA sobre clientes
- Contexto completo do cliente é fornecido à IA
- Respostas baseadas em todo o histórico disponível
- Sugestões acionáveis para o corretor

**Implementação:** `app/ai/chat_service.py`

### 8. Recomendação Inteligente de Imóveis

**Quando:** Durante análise de atendimento

**O que faz:**
- Analisa perfil do cliente (orçamento, preferências, localização)
- Busca imóveis no banco de dados que correspondem aos critérios
- **Rankeia** imóveis por relevância
- Retorna lista de propriedades recomendadas vinculadas ao atendimento

**Implementação:** `app/ai/service.py` - `_recommend_properties()`

---

## 🔄 Fluxo Completo do Sistema

### Fluxo: Cliente → Imóvel → Atendimento → IA → Visita → Venda/Perda

```
┌─────────────────────────────────────────────────────────────────┐
│                    1. CRIAÇÃO DO CLIENTE                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Cliente Criado │
                    │  (Nome, Tel,    │
                    │   Email, Origem)│
                    │                 │
                    │  Valores Padrão:│
                    │  - Status:      │
                    │    NEW_LEAD     │
                    │  - Lead Score:  │
                    │    30 (base)    │
                    │  - Urgência:    │
                    │    MEDIUM       │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  2. REGISTRO DE ATENDIMENTO                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Atendimento     │
                    │ - Canal         │
                    │ - Conteúdo      │
                    │ - Objetivo      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  IA Processa    │
                    │  - Resumo       │
                    │  - Intenção     │
                    │  - Sentimento   │
                    │  - Propriedades │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  IA Detecta:    │
                    │  - Visita?      │
                    │  - Imóvel?      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Atualiza Cliente│
                    │  (Ciclo ACTIVE) │
                    │  - Lead Score   │
                    │  - Perfil       │
                    │  - Status       │
                    │  - Timeline     │
                    │                 │
                    │  ⚠️ Perfil reflete│
                    │  APENAS ciclo   │
                    │  ACTIVE atual   │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  3. VINCULAÇÃO DE IMÓVEL                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  IA Detecta     │
                    │  Menção de      │
                    │  Imóvel         │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Vincula Imóvel │
                    │  ao Atendimento │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Timeline Event: │
                    │  PROPERTY_       │
                    │  SELECTED       │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  4. AGENDAMENTO DE VISITA                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  IA Detecta     │
                    │  Intenção de    │
                    │  Visita         │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Extrai:        │
                    │  - Data/Hora    │
                    │  - Imóvel       │
                    │  - Notas        │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Frontend:      │
                    │  Modal de       │
                    │  Confirmação    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Visita Criada  │
                    │  - Agendada     │
                    │  - Vinculada    │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  5. RESULTADO FINAL                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
          ┌─────────────────┐  ┌─────────────────┐
          │   VENDA         │  │   PERDA         │
          │   FECHADA      │  │   REGISTRADA    │
          └────────┬────────┘  └────────┬────────┘
                   │                   │
                   ▼                   ▼
          ┌─────────────────┐  ┌─────────────────┐
          │  Sale Criado     │  │  Loss Criado    │
          │  - Valor         │  │  - Motivo       │
          │  - Comissão      │  │  - Feedback     │
          │  - Métodos Pag.  │  └─────────────────┘
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │  Atendimento    │
          │  COMPLETED      │
          └─────────────────┘
```

### Ciclo de Atendimento (Attendance Cycle)

O sistema implementa um conceito de **ciclo de atendimento** onde:

- **Um Attendance = Um ciclo completo de decisão do cliente**
- **Ciclo começa quando:** Cliente inicia um objetivo (ex: comprar imóvel em X cidade)
- **Ciclo termina quando:**
  - Cliente compra (WON / COMPLETED)
  - Cliente desiste (LOST)
  - Cliente abandona (ABANDONED)
- **Durante o ciclo:**
  - Múltiplas conversas são acumuladas no mesmo Attendance
  - Visitas são agendadas
  - Propostas são atualizadas
  - Orçamento é refinado
  - Família é envolvida
  - Tudo pertence ao mesmo ciclo enquanto o objetivo estratégico não mudar

**Regras:**
- Um cliente pode ter apenas **um ciclo ACTIVE** por vez
- Refinamentos (mudança de orçamento, urgência, tipo de imóvel) **NÃO** criam novo ciclo
- Novo ciclo é criado apenas quando há **mudança estratégica real** (BUY → RENT, mudança de cidade) ou **reativação após longo período**

**⚠️ CRÍTICO - Proteções Implementadas:**
1. **Nunca pode existir 2 ACTIVE**: Sistema garante apenas um ciclo ACTIVE por cliente (com locks de banco)
2. **Não atualiza de ciclo fechado**: Perfil do cliente só é atualizado a partir de ciclos ACTIVE
3. **Toda atualização passa pelo ciclo**: Campos AI-controlados só podem ser atualizados via atendimentos
4. **Mantém estado se não houver ACTIVE**: Se não houver ciclo ACTIVE, perfil mantém último estado até novo ciclo surgir

**Perfil do Cliente:**
- O perfil do cliente reflete **APENAS o ciclo ACTIVE atual**
- Quando um novo ciclo ACTIVE começa, o perfil é atualizado baseado **APENAS nesse ciclo**
- Ciclos anteriores (COMPLETED, LOST, ABANDONED) **NÃO são considerados** na derivação do perfil
- Isso garante que o perfil sempre reflita o objetivo e contexto atual do cliente

**Implementação:** `app/attendances/objective_service.py` e `app/attendances/repository.py`

---

## 📁 Estrutura do Projeto

```
Projeto-Tecnico-Astrocode-Backend/
│
├── app/                          # Código principal da aplicação
│   ├── ai/                       # Módulo de Inteligência Artificial
│   │   ├── chat_service.py      # Serviço de chat com IA
│   │   ├── chat_router.py        # Rotas de chat
│   │   ├── gemini_service.py     # Integração com Google Gemini
│   │   ├── journey_service.py    # Análise de jornada do cliente
│   │   ├── journey_routes.py     # Rotas de jornada
│   │   ├── models.py             # Modelos de dados (AISummary, etc)
│   │   ├── prompts.py            # Prompts para a IA
│   │   ├── repository.py         # Repositório de AI Summaries
│   │   ├── routes.py              # Rotas de AI Summaries
│   │   ├── schemas.py             # Schemas Pydantic
│   │   └── service.py             # Serviço principal de análise
│   │
│   ├── attendances/               # Módulo de Atendimentos
│   │   ├── models.py             # Modelo Attendance
│   │   ├── objective_service.py  # Detecção e comparação de objetivos
│   │   ├── repository.py         # Lógica de negócio de atendimentos
│   │   ├── routes.py             # Rotas de atendimentos
│   │   └── schemas.py            # Schemas de atendimentos
│   │
│   ├── clients/                   # Módulo de Clientes
│   │   ├── models.py             # Modelo Client
│   │   ├── repository.py         # Repositório de clientes
│   │   ├── routes.py              # Rotas de clientes
│   │   ├── schemas.py             # Schemas de clientes
│   │   ├── score_service.py       # Serviço de cálculo de lead score
│   │   ├── state_derivation_service.py  # Derivação de estado do cliente
│   │   └── timeline_models.py     # Modelos de timeline
│   │
│   ├── properties/                # Módulo de Imóveis
│   │   ├── models.py             # Modelo Property
│   │   ├── repository.py         # Repositório de imóveis
│   │   ├── routes.py              # Rotas de imóveis
│   │   └── schemas.py             # Schemas de imóveis
│   │
│   ├── visits/                    # Módulo de Visitas
│   │   ├── models.py             # Modelo Visit
│   │   ├── repository.py         # Repositório de visitas
│   │   ├── routes.py              # Rotas de visitas
│   │   └── schemas.py             # Schemas de visitas
│   │
│   ├── sales/                     # Módulo de Vendas
│   │   ├── models.py             # Modelo Sale
│   │   ├── repository.py         # Repositório de vendas
│   │   ├── routes.py              # Rotas de vendas
│   │   └── schemas.py             # Schemas de vendas
│   │
│   ├── losses/                    # Módulo de Perdas
│   │   ├── models.py             # Modelo ClientLoss
│   │   ├── repository.py         # Repositório de perdas
│   │   ├── routes.py              # Rotas de perdas
│   │   └── schemas.py             # Schemas de perdas
│   │
│   ├── users/                     # Módulo de Usuários
│   │   ├── models.py             # Modelo User
│   │   ├── repository.py         # Repositório de usuários
│   │   ├── role_repository.py     # Repositório de roles
│   │   ├── routes.py              # Rotas de usuários
│   │   └── schemas.py             # Schemas de usuários
│   │
│   ├── auth/                      # Módulo de Autenticação
│   │   ├── dependencies.py       # Dependências de autenticação
│   │   ├── jwt.py                # Utilitários JWT
│   │   ├── models.py             # Modelos de autenticação
│   │   ├── oauth_service.py      # Serviço OAuth Google
│   │   ├── password.py           # Utilitários de senha
│   │   ├── routes.py              # Rotas de autenticação
│   │   ├── schemas.py             # Schemas de autenticação
│   │   └── service.py             # Serviço de autenticação
│   │
│   ├── config/                    # Configurações
│   │   └── settings.py           # Configurações da aplicação
│   │
│   ├── core/                      # Código core
│   │   └── logging.py            # Configuração de logging
│   │
│   ├── db/                        # Banco de dados
│   │   ├── base.py               # Base do SQLAlchemy
│   │   └── session.py            # Sessão do banco
│   │
│   ├── services/                  # Serviços externos
│   │   └── cloudinary_service.py  # Integração Cloudinary
│   │
│   └── main.py                    # Aplicação FastAPI principal
│
├── alembic/                       # Migrações do banco de dados
│   ├── versions/                 # Arquivos de migração
│   └── env.py                    # Configuração Alembic
│
├── scripts/                       # Scripts utilitários
│   ├── create_manager.py         # Criar usuário gestor
│   ├── create_test_user.py      # Criar usuário de teste
│   └── assign_role.py            # Atribuir role a usuário
│
├── tests/                         # Testes automatizados
│
├── docs/                          # Documentação
│   ├── AUTHENTICATION.md         # Documentação de autenticação
│   ├── DOCUMENTACAO_SISTEMA.md    # Documentação do sistema
│   ├── FLUXO_CLIENTE_IMOVEL_ATENDIMENTO.md
│   └── GUIA_TESTES_COMPLETO.md   # Guia de testes
│
├── pyproject.toml                  # Configuração do projeto
├── alembic.ini                    # Configuração Alembic
└── README.md                       # Este arquivo
```

---

## 🚀 Instalação e Configuração

### Pré-requisitos

- **Python 3.11+**
- **PostgreSQL 13+**
- **Chave da API Google Gemini** ([Obter aqui](https://ai.google.dev/))

### 1. Clone o Repositório

```bash
git clone <url-do-repositorio>
cd Projeto-Tecnico-Astrocode-Backend
```

### 2. Criar Ambiente Virtual

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar Dependências

```bash
pip install -e .
```

### 4. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Banco de Dados
DATABASE_URL=postgresql://usuario:senha@localhost:5432/real_estate_crm

# JWT
JWT_SECRET_KEY=sua-chave-secreta-mude-em-producao
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Google Gemini AI
GEMINI_API_KEY=sua-chave-gemini

# OAuth Google (Opcional)
GOOGLE_CLIENT_ID=seu-google-client-id
GOOGLE_CLIENT_SECRET=seu-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Frontend
FRONTEND_URL=http://localhost:5173

# Ambiente
ENVIRONMENT=development
```

### 5. Configurar Banco de Dados

```bash
# Criar banco de dados
psql -U postgres -c "CREATE DATABASE real_estate_crm;"

# Executar migrações
alembic upgrade head
```

### 6. Criar Primeiro Usuário (Gestor)

```bash
python scripts/create_manager.py \
  --email admin@exemplo.com \
  --password senha123456 \
  --name "Administrador"
```

### 7. Executar a Aplicação

```bash
uvicorn app.main:app --reload --port 8000
```

A aplicação estará disponível em:
- **API:** http://localhost:8000
- **Documentação Swagger:** http://localhost:8000/docs
- **Documentação ReDoc:** http://localhost:8000/redoc

---

## 📡 API Endpoints

### Autenticação

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| POST | `/auth/login` | Login com email/senha | Público |
| GET | `/auth/google/login` | Iniciar OAuth Google | Público |
| GET | `/auth/google/callback` | Callback OAuth Google | Público |
| GET | `/auth/me` | Informações do usuário atual | Protegido |
| POST | `/auth/register` | Criar novo usuário | Gestor |

### Clientes

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| POST | `/clients` | Criar cliente (com classificação IA) | Protegido |
| GET | `/clients` | Listar clientes (com filtros) | Protegido |
| GET | `/clients/{id}` | Buscar cliente por ID | Protegido |
| PUT | `/clients/{id}` | Atualizar cliente | Protegido |
| DELETE | `/clients/{id}` | Deletar cliente | Protegido |
| GET | `/clients/{id}/timeline` | Timeline do cliente | Protegido |
| GET | `/clients/{id}/recommended-properties` | Propriedades recomendadas | Protegido |

### Atendimentos

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| POST | `/attendances` | Criar atendimento (com análise IA) | Protegido |
| GET | `/attendances` | Listar atendimentos | Protegido |
| GET | `/attendances/{id}` | Buscar atendimento | Protegido |
| PUT | `/attendances/{id}` | Atualizar atendimento | Protegido |
| DELETE | `/attendances/{id}` | Deletar atendimento | Protegido |
| GET | `/attendances/client/{client_id}` | Atendimentos de um cliente | Protegido |

### Imóveis

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| POST | `/properties` | Criar imóvel | Protegido |
| GET | `/properties` | Listar imóveis (com filtros) | Protegido |
| GET | `/properties/{id}` | Buscar imóvel | Protegido |
| PUT | `/properties/{id}` | Atualizar imóvel | Protegido |
| DELETE | `/properties/{id}` | Deletar imóvel | Protegido |

### Visitas

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| POST | `/visits` | Criar visita | Protegido |
| GET | `/visits` | Listar visitas | Protegido |
| GET | `/visits/{id}` | Buscar visita | Protegido |
| PUT | `/visits/{id}` | Atualizar visita | Protegido |
| DELETE | `/visits/{id}` | Deletar visita | Protegido |

### Vendas

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| POST | `/sales` | Criar venda | Protegido |
| GET | `/sales` | Listar vendas | Protegido |
| GET | `/sales/{id}` | Buscar venda | Protegido |
| PUT | `/sales/{id}` | Atualizar venda | Protegido |
| GET | `/sales/stats` | Estatísticas de vendas | Protegido |

### Perdas

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| POST | `/losses` | Registrar perda | Protegido |
| GET | `/losses` | Listar perdas | Protegido |
| GET | `/losses/{id}` | Buscar perda | Protegido |
| GET | `/losses/stats` | Estatísticas de perdas | Protegido |

### Inteligência Artificial

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| GET | `/ai/summaries` | Listar AI Summaries | Protegido |
| GET | `/ai/summaries/{id}` | Buscar AI Summary | Protegido |
| POST | `/ai/chat` | Chat com IA sobre cliente | Protegido |
| GET | `/ai/journey/{client_id}` | Análise completa de jornada | Protegido |
| GET | `/ai/journey/{client_id}/next-actions` | Próximas ações sugeridas | Protegido |

### Usuários (Apenas Gestores)

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| GET | `/users` | Listar usuários | Gestor |
| GET | `/users/{id}` | Buscar usuário | Gestor |
| PUT | `/users/{id}/roles` | Atualizar roles do usuário | Gestor |
| GET | `/users/corretores` | Listar corretores | Protegido |

---

## ⚙️ Funcionalidades Principais

### 1. Gestão de Clientes

- **Cadastro completo** com informações de contato
- **Valores padrão** ao criar (Status: NEW_LEAD, Lead Score: 30, Urgência: MEDIUM)
- **Atualização automática** pela IA através de atendimentos no ciclo ACTIVE
- **Lead Score dinâmico** atualizado gradualmente conforme interações no ciclo
- **Status controlado pela IA** baseado em intent, sentiment, visits, lead_score
- **Timeline completa** de eventos do cliente
- **Perfil derivado** automaticamente pela IA (não editável manualmente)
- **Perfil reflete apenas ciclo ACTIVE** atual, não histórico consolidado
- **Rastreamento de origem** do lead (WhatsApp, Site, Telefone)

### 2. Gestão de Atendimentos

- **Ciclo de atendimento** inteligente (um ciclo = um objetivo)
- **Análise automática** pela IA a cada atendimento
- **Detecção automática** de intenção de visita
- **Vinculação automática** de imóveis mencionados
- **Resumo profissional** gerado pela IA
- **Recomendação de imóveis** baseada no perfil

### 3. Gestão de Imóveis

- **Cadastro completo** com fotos, preços, características
- **Suporte a venda e aluguel**
- **Upload de imagens** via Cloudinary
- **Busca e filtros** avançados
- **Recomendação inteligente** para clientes

### 4. Gestão de Visitas

- **Agendamento** de visitas a imóveis
- **Detecção automática** de intenção de visita pela IA
- **Status tracking** (AGENDADA, REALIZADA, CANCELADA, REMARCADA)
- **Vinculação** com cliente e imóvel
- **Notas e feedback** da visita

### 5. Gestão de Vendas

- **Registro completo** de vendas
- **Múltiplos métodos de pagamento** (À vista, Financiamento, Parcelado, Misto)
- **Cálculo automático** de comissão
- **Vinculação** com cliente, imóvel e corretor
- **Estatísticas** de vendas

### 6. Gestão de Perdas

- **Registro de perdas** com motivo e feedback
- **Análise** de razões de perda
- **Estatísticas** de perdas
- **Aprendizado** para melhorar processos

### 7. Sistema de Autenticação

- **JWT** para autenticação stateless
- **OAuth 2.0** com Google
- **RBAC** (Role-Based Access Control)
- **Roles:** Atendente, Corretor, Gestor
- **Proteção de rotas** por role

### 8. Timeline de Clientes

- **Eventos automáticos** criados pelo sistema:
  - Criação de cliente
  - Atendimentos criados/finalizados
  - Visitas agendadas/realizadas
  - Imóveis selecionados/confirmados
  - Vendas registradas
  - Perdas registradas
- **Rastreabilidade completa** de todas as ações

---

## 🔒 Segurança e Autenticação

### Autenticação JWT

- Tokens JWT com expiração configurável
- Refresh tokens (opcional)
- Validação de assinatura
- Proteção contra replay attacks

### OAuth 2.0

- Login com Google
- Criação automática de usuários
- Vinculação de contas

### Controle de Acesso (RBAC)

- **Atendente:** Acesso básico (clientes, atendimentos)
- **Corretor:** Acesso intermediário (clientes, atendimentos, vendas)
- **Gestor:** Acesso completo (incluindo gerenciamento de usuários)

### Segurança de Dados

- Senhas hasheadas com bcrypt
- Validação de entrada com Pydantic
- Proteção contra SQL Injection (SQLAlchemy ORM)
- CORS configurado
- Headers de segurança

---

## 🗄️ Banco de Dados

### Modelos Principais

#### Client
- Informações de contato
- Perfil derivado pela IA (não editável manualmente)
- **Campos AI-controlados:**
  - `current_interest_type`, `current_property_type`, `current_city_interest`
  - `current_budget_min`, `current_budget_max`, `current_urgency_level`
  - `current_lead_score`, `current_status`
- Lead Score dinâmico (atualizado gradualmente no ciclo ACTIVE)
- Status no funil de vendas (detectado automaticamente pela IA)
- Timeline de eventos
- **Perfil reflete apenas ciclo ACTIVE atual**

#### Attendance
- Conteúdo da conversa (raw_content)
- Canal de atendimento
- Status do ciclo (ACTIVE, COMPLETED, LOST, ABANDONED)
- Objetivo do ciclo
- Vinculação com imóvel

#### AISummary
- Resumo gerado pela IA
- Pontos-chave extraídos
- Intenção detectada
- Sentimento
- Propriedades recomendadas
- Score de confiança

#### Property
- Informações do imóvel
- Preços (venda e aluguel)
- Características
- Fotos (Cloudinary)
- Status de disponibilidade

#### Visit
- Data e hora agendada
- Status
- Vinculação com cliente e imóvel
- Notas e feedback

#### Sale
- Valor da venda
- Métodos de pagamento (JSONB)
- Comissão
- Vinculação com cliente, imóvel e corretor

#### ClientLoss
- Motivo da perda
- Feedback
- Vinculação com cliente

### Migrações

O sistema utiliza **Alembic** para gerenciar migrações do banco de dados. Todas as mudanças no schema são versionadas e podem ser aplicadas/revertidas facilmente.

```bash
# Criar nova migração
alembic revision --autogenerate -m "descrição da mudança"

# Aplicar migrações
alembic upgrade head

# Reverter migração
alembic downgrade -1
```

---

## 🧪 Testes

### Executar Testes

```bash
# Instalar dependências de desenvolvimento
pip install -e ".[dev]"

# Executar todos os testes
pytest

# Executar com cobertura
pytest --cov=app

# Executar testes específicos
pytest tests/test_clients.py
```

---

## 📚 Documentação Adicional

- [Documentação de Autenticação](docs/AUTHENTICATION.md)
- [Documentação Completa do Sistema](docs/DOCUMENTACAO_SISTEMA.md)
- [Fluxo Cliente-Imóvel-Atendimento](docs/FLUXO_CLIENTE_IMOVEL_ATENDIMENTO.md)
- [Guia Completo de Testes](docs/GUIA_TESTES_COMPLETO.md)

---

## 🎯 Destaques Técnicos

### Arquitetura

- **Clean Architecture** com separação clara de responsabilidades
- **Repository Pattern** para abstração de dados
- **Service Layer** para lógica de negócio
- **Dependency Injection** com FastAPI

### Performance

- **Async/await** para operações I/O
- **Connection pooling** no PostgreSQL
- **Lazy loading** no SQLAlchemy
- **Caching** de serviços (opcional)

### Qualidade de Código

- **Type hints** em todo o código
- **Pydantic** para validação de dados
- **Logging** estruturado
- **Error handling** robusto

### Integração com IA

- **Fallback** quando Gemini não está configurado
- **Tratamento de erros** da API
- **Rate limiting** (implementável)
- **Cache** de respostas (implementável)

### Proteções Críticas do Sistema

O sistema implementa **4 proteções críticas** para garantir integridade dos dados:

1. **Nunca pode existir 2 ACTIVE**
   - Sistema garante apenas um ciclo ACTIVE por cliente
   - Usa locks de banco de dados para prevenir race conditions
   - Fecha automaticamente múltiplos ACTIVE se detectados

2. **Não atualiza de ciclo fechado**
   - Perfil do cliente só é atualizado a partir de ciclos ACTIVE
   - Ciclos fechados (COMPLETED, LOST, ABANDONED) não atualizam o perfil
   - Verificação explícita antes de cada atualização

3. **Toda atualização passa pelo ciclo**
   - Campos AI-controlados só podem ser atualizados via atendimentos
   - Bloqueio explícito de atualizações manuais desses campos
   - Apenas `ClientStateDerivationService` pode atualizar via `allow_ai_updates=True`

4. **Mantém estado se não houver ACTIVE**
   - Se não houver ciclo ACTIVE, perfil mantém último estado
   - Não tenta atualizar quando não há contexto ativo
   - Novo ciclo ACTIVE atualiza baseado apenas nesse ciclo

### Perfil do Cliente e Ciclo ACTIVE

**Conceito Fundamental:**
- O perfil do cliente reflete **APENAS o ciclo ACTIVE atual**
- Não é um histórico consolidado de todos os ciclos
- Quando um novo ciclo ACTIVE começa, o perfil é atualizado baseado **APENAS nesse ciclo**
- Ciclos anteriores (COMPLETED, LOST, ABANDONED) **NÃO são considerados**

**Benefícios:**
- Perfil sempre reflete o objetivo atual do cliente
- Evita misturar contextos de diferentes objetivos
- Facilita identificação de mudanças estratégicas
- Garante consistência entre perfil e ciclo ativo

**Exemplo:**
```
Ciclo 1 ACTIVE: Comprar casa em SP, R$ 500k
  → Perfil: city=SP, budget=500k, interest=BUY

Ciclo 1 FECHADO (COMPLETED)
Ciclo 2 ACTIVE criado: Alugar apartamento em RJ, R$ 2k/mês
  → Perfil ATUALIZADO: city=RJ, budget=2k, interest=RENT
  → Ciclo 1 NÃO é mais considerado!
```

---

## 🚀 Próximos Passos / Melhorias Futuras

- [ ] Dashboard com métricas em tempo real
- [ ] Notificações push para eventos importantes
- [ ] Integração com WhatsApp Business API
- [ ] Relatórios avançados e exportação
- [ ] Machine Learning para previsão de vendas
- [ ] Integração com sistemas de CRM externos
- [ ] App mobile (React Native)

---

## 📝 Licença

Este projeto foi desenvolvido como **Desafio Técnico** para a vaga na **Astrocode**.

---

<div align="center">

**Desenvolvido com ❤️ usando FastAPI, PostgreSQL e Google Gemini AI**

[⬆ Voltar ao topo](#-sistema-crm-imobiliário-com-inteligência-artificial)

</div>
