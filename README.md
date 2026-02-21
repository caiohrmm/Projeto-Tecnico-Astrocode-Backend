# 🏠 Sistema CRM Imobiliário com Inteligência Artificial

<div align="center">

**Sistema completo de gestão imobiliária com IA integrada para otimização de vendas e atendimento**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Google Gemini AI](https://img.shields.io/badge/Google%20Gemini-AI-4285F4?logo=google&logoColor=white)](https://ai.google.dev)

**API em produção (Render):** [https://projeto-tecnico-astrocode-backend.onrender.com](https://projeto-tecnico-astrocode-backend.onrender.com) · [Docs (Swagger)](https://projeto-tecnico-astrocode-backend.onrender.com/docs)

A **API está totalmente documentada** no Swagger: todos os endpoints possuem descrição, regras de negócio, códigos de resposta e schemas de request/response em português. Use o link **Docs** acima para explorar e testar.

</div>

---

## 📋 Índice

- [1. Visão geral](#1-visão-geral)
  - [Modelo de uso: sob medida para uma imobiliária (não SaaS)](#modelo-de-uso-sob-medida-para-uma-imobiliária-não-saas)
- [2. Arquitetura e tecnologias](#2-arquitetura-e-tecnologias)
- [3. Estrutura do projeto e instalação](#3-estrutura-do-projeto-e-instalação)
  - [Acesso de teste (usuário gestor)](#acesso-de-teste-usuário-gestor)
  - [Variáveis de ambiente (.env)](#variáveis-de-ambiente-env)
- [4. Modelos e banco de dados](#4-modelos-e-banco-de-dados)
- [5. Fluxo central: cliente e ciclos de atendimento](#5-fluxo-central-cliente-e-ciclos-de-atendimento)
- [6. Visitas, vendas e perdas (vinculadas ao cliente)](#6-visitas-vendas-e-perdas-vinculadas-ao-cliente)
- [7. Funcionalidades da IA](#7-funcionalidades-da-ia)
  - [Aviso sobre tempo de resposta](#aviso-sobre-tempo-de-resposta)
- [8. API (endpoints)](#8-api-endpoints)
- [9. Segurança e autenticação](#9-segurança-e-autenticação)
- [10. Destaques técnicos e proteções](#10-destaques-técnicos-e-proteções)
- [Testes](#-testes)
- [Documentação adicional](#-documentação-adicional)
- [Próximos passos](#-próximos-passos--melhorias-futuras)
- [Licença](#-licença)

---

## 1. Visão geral

Sistema de **CRM para imobiliárias** com **IA (Google Gemini)** integrada. Toda a jornada do cliente é centralizada no **cliente**: atendimentos (ciclos), visitas, vendas e perdas ficam vinculados a ele e ao **ciclo de atendimento** ativo.

### Modelo de uso: sob medida para uma imobiliária (não SaaS)

Este projeto foi pensado para **uma imobiliária específica**, como sistema **sob medida**. **Não** segue o modelo **SaaS** em que cada “cliente” (empresa) tem sua própria conta, tenant ou instância isolada. Aqui existe **um único banco de dados** compartilhado por todos os usuários da mesma imobiliária: corretores, gestores e atendentes trabalham sobre os mesmos clientes, imóveis, atendimentos e vendas. Os papéis (gestor, atendente) controlam apenas **quem pode fazer o quê** dentro desse ambiente único — por exemplo, só o gestor pode criar usuários e atribuir funções. Resumindo: é um **CRM dedicado a uma única imobiliária**, com um banco só e múltiplos usuários com diferentes permissões.

### Objetivos do sistema

- **Automatizar** a análise de conversas (resumo, intenção, urgência, próximos passos).
- **Atualizar o perfil do cliente** apenas com base no **ciclo de atendimento ativo** (ACTIVE), evitando misturar contextos antigos.
- **Rastrear** o ciclo desde o primeiro contato até **venda** ou **perda**, com visitas e imóvel vinculados.
- **Garantir** um único ciclo ACTIVE por cliente; fechamento (concluído/perda/venda) aplica lead score de fechamento no cliente.

---

## 2. Arquitetura e tecnologias

### Stack

| Camada | Tecnologia |
|--------|------------|
| **API** | Python 3.11+, FastAPI, Uvicorn |
| **Banco** | PostgreSQL (SQLAlchemy 2.0, Alembic) |
| **IA** | Google Gemini (Google Generative AI) |
| **Validação** | Pydantic |
| **Auth** | JWT, bcrypt, OAuth 2.0 (Google), RBAC |
| **Integrações** | Cloudinary (imagens de imóveis) |

### Arquitetura em camadas

O **frontend** (Vue 3 + Vite + Vuetify) consome a API via **HTTP/REST**. O **backend** (FastAPI) centraliza a lógica e se conecta a quatro integrações: **PostgreSQL** (banco de dados, ex.: Neon), **Google Gemini** (IA para resumos, chat e jornada), **Cloudinary** (upload de imagens de imóveis) e **OAuth Google** (login social). Ou seja: o cliente acessa o frontend, que chama o backend; o backend persiste dados no PostgreSQL, usa a IA (Gemini) para análises e chat, armazena fotos no Cloudinary e delega a autenticação social ao Google.

---

## 3. Estrutura do projeto e instalação

### Estrutura de pastas (principal)

```
app/
├── ai/                    # IA: resumos, chat, jornada, prompts
├── attendances/            # Ciclos de atendimento (repository, routes, objective_service)
├── clients/                # Clientes, state_derivation, timeline, score
├── properties/             # Imóveis
├── visits/                 # Visitas (vinculadas a atendimento/cliente)
├── sales/                  # Vendas (fecham ciclo, aplicam lead score)
├── losses/                 # Perdas (fecham ciclo, aplicam lead score)
├── users/                  # Usuários e roles
├── auth/                   # JWT, OAuth Google
├── config/                 # Settings
├── db/                     # Sessão e base SQLAlchemy
└── main.py
alembic/                    # Migrações
```

### Instalação (resumo)

1. **Pré-requisitos:** Python 3.11+, PostgreSQL (ex.: Neon), chave Google Gemini.
2. **Clone e ambiente:**
   ```bash
   git clone <repo> && cd Projeto-Tecnico-Astrocode-Backend
   python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate no Windows
   pip install -e .
   ```
3. **Variáveis de ambiente:** copie `.env.example` para `.env` na raiz do projeto e preencha os valores. Cada variável está explicada no próprio `.env.example`. Veja também a seção [Variáveis de ambiente (.env)](#variáveis-de-ambiente-env) abaixo.
4. **Banco:** `alembic upgrade head`
5. **Primeiro usuário (gestor):** `python scripts/create_manager.py --email ... --password ... --name "Admin"`
6. **Rodar:** `uvicorn app.main:app --reload --port 8000`  
   - **Local:** API → http://localhost:8000 · Docs → http://localhost:8000/docs  
   - **Produção (Render):** API → https://projeto-tecnico-astrocode-backend.onrender.com · Docs → https://projeto-tecnico-astrocode-backend.onrender.com/docs  

### Acesso de teste (usuário gestor)

Para testar o sistema com perfil de **administrador** (gestor) e controlar o acesso dos demais usuários, use as credenciais abaixo no login (frontend ou API):

| Campo    | Valor              |
|----------|--------------------|
| **E-mail** | `gestor@example.com` |
| **Senha**  | `123456`            |

Com esse usuário você pode registrar novos usuários, atribuir roles (atendente, gestor) e gerenciar permissões. Em produção, altere a senha ou use o script `scripts/create_manager.py` para criar um gestor com credenciais seguras.

### Variáveis de ambiente (.env)

O arquivo **`.env.example`** na raiz do projeto lista todas as variáveis usadas pela API, com comentários explicando cada uma. Copie-o para `.env` e preencha com seus valores (nunca commite o `.env`).

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| **Aplicação** | | |
| `APP_NAME` | Não | Nome exibido na API (ex.: Swagger). |
| `ENVIRONMENT` | Não | `development`, `staging` ou `production`. |
| `DEBUG` | Não | Modo debug (evite `true` em produção). |
| **Servidor** | | |
| `HOST` | Não | Endereço de escuta (ex.: `0.0.0.0`). |
| `PORT` | Não | Porta HTTP (ex.: `8000`). |
| **Banco** | | |
| `DATABASE_URL` | **Sim** | Connection string PostgreSQL (Neon, Render, local). |
| **JWT** | | |
| `JWT_SECRET_KEY` | **Sim** | Chave secreta para tokens (use valor forte em produção). |
| `JWT_ALGORITHM` | Não | Algoritmo JWT (padrão: `HS256`). |
| `JWT_EXPIRATION_HOURS` | Não | Validade do token em horas (ex.: `24`). |
| **Google OAuth** | | |
| `GOOGLE_CLIENT_ID` | Para login Google | Client ID do projeto no Google Cloud. |
| `GOOGLE_CLIENT_SECRET` | Para login Google | Client Secret OAuth 2.0. |
| `GOOGLE_REDIRECT_URI` | Para login Google | URL de callback (ex.: `https://seu-backend.onrender.com/auth/google/callback`). |
| **Google Maps** | | |
| `GOOGLE_API_KEY` | Para geocoding | Chave da API Google Maps (Geocoding). |
| **Gemini (IA)** | | |
| `GEMINI_API_KEY` | **Sim** (para IA) | Chave da API Google Gemini. |
| **Cloudinary** | | |
| `CLOUDINARY_CLOUD_NAME` | Para fotos de imóveis | Nome do cloud no dashboard. |
| `CLOUDINARY_API_KEY` | Para fotos de imóveis | API Key. |
| `CLOUDINARY_API_SECRET` | Para fotos de imóveis | API Secret. |
| **Frontend / CORS** | | |
| `FRONTEND_URL` | Para OAuth | URL do frontend (redirect após login Google). |
| `CORS_ORIGINS` | Recomendado | Origens permitidas (vírgula); inclua a URL do frontend. |
| **SMTP** | | |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, etc. | Para "Esqueci minha senha" | Se não configurado, o link de redefinição é apenas logado no console. |

Para detalhes e exemplos de valor, consulte o **`.env.example`**.

---

## 4. Modelos e banco de dados

### Entidades principais e relações

- **Client** – Núcleo: contato, perfil derivado pela IA (interest_type, property_type, city, budget, urgency, lead_score, status). Um cliente tem vários **Attendance**, **Visit**, **Sale**, **ClientLoss**.
- **Attendance** – Ciclo de atendimento: `client_id`, `agent_id`, `property_id` (opcional), `objective`, `raw_content` (conversas acumuladas), `status` (ACTIVE | COMPLETED | LOST | ABANDONED). Campos preenchidos pela IA: `ai_summary`, `ai_next_steps`. **Apenas um ACTIVE por cliente**; ciclo não é editável (exceto `property_id`).
- **Visit** – Visita agendada: vinculada a **attendance** e opcionalmente a **property**; status (AGENDADA, REALIZADA, CANCELADA, etc.).
- **Sale** – Venda: vinculada a cliente, imóvel, atendimento (fecha o ciclo ACTIVE e aplica lead score de fechamento no cliente).
- **ClientLoss** – Perda: vinculada a cliente e atendimento (fecha o ciclo ACTIVE e aplica lead score).
- **Property** – Imóvel: dados cadastrais, fotos (Cloudinary), preços.
- **AISummary** – Por atendimento: resumo, intenção, sentimento, urgência, key_points (incl. `property_purchased`, `property_lost` em fechamento), propriedades recomendadas.

### Migrações

```bash
alembic revision --autogenerate -m "descrição"
alembic upgrade head
```

---

## 5. Fluxo central: cliente e ciclos de atendimento

### Regras de negócio

- **Um cliente tem no máximo um atendimento ACTIVE.** Ao criar um novo atendimento, o backend verifica objetivo e ciclo ativo: ou anexa a conversa ao ciclo existente (acumulando `raw_content`) ou fecha o ciclo anterior e abre um novo.
- **Atendimento não é editável** após a criação (a API aceita apenas atualização de **property_id** para vincular/alterar imóvel). Cliente, agente, objetivo e conteúdo não são alterados; para incluir mais conversa usa-se **adicionar conversa** (POST que acumula conteúdo no ciclo ACTIVE).
- **Perfil do cliente** é atualizado **somente** a partir de sinais do ciclo **ACTIVE** (State Derivation). Quando o ciclo é fechado (COMPLETED, LOST ou por venda/perda), o perfil não é mais atualizado por aquele ciclo; ao fechar, aplica-se o **lead score de fechamento** no cliente (ex.: 100 em venda).

### Fluxo resumido

1. **Criar cliente** → valores iniciais (ex.: status NEW_LEAD, lead_score 30, urgência MEDIUM).
2. **Criar atendimento** (ou adicionar conversa ao ACTIVE) → IA gera resumo, intenção, urgência, próximos passos; atualiza perfil do cliente com base só no ACTIVE; pode detectar intenção de visita ou menção a imóvel.
3. **Vincular imóvel** → único campo editável do atendimento (PUT com `property_id`).
4. **Fechar ciclo** → por **Registrar venda**, **Registrar perda** ou **Marcar como concluído** (status COMPLETED). Venda/perda aplicam lead score de fechamento no cliente e preenchem key_points (property_purchased / property_lost) no resumo da IA.

---

## 6. Visitas, vendas e perdas (vinculadas ao cliente)

### Visitas

- Criadas manualmente ou a partir da **detecção de intenção de visita** pela IA (data/hora, imóvel sugerido). Ficam vinculadas a um **atendimento** e opcionalmente a um **imóvel**. O contexto do atendimento (resumo IA, visitas) é usado no chat e na jornada.

### Vendas

- **Registrar venda** associa cliente, imóvel, valor, corretor etc. O backend **fecha o atendimento ACTIVE** do cliente (status COMPLETED), aplica o **lead score de fechamento** no cliente (ex.: 100) e atualiza o resumo da IA com **key_points.property_purchased** (descrição do imóvel). Assim a IA e o frontend sabem qual imóvel foi comprado.

### Perdas

- **Registrar perda** associa cliente, motivo, feedback etc. O backend **fecha o atendimento ACTIVE** (status LOST), aplica o lead score de fechamento e atualiza o resumo da IA com **key_points.property_lost** quando houver imóvel vinculado ao ciclo.

### Timeline do cliente

- Eventos automáticos: criação de cliente, atendimentos (criado/concluído), visitas, imóvel selecionado/confirmado, vendas, perdas. Tudo vinculado ao **cliente** para histórico e contexto da IA.

---

## 7. Funcionalidades da IA

O sistema usa **Google Gemini** para análise de texto, resumos e derivação de estado. Principais pontos:

### Aviso sobre tempo de resposta

Alguns **botões ou ações** que disparam processamento pela IA (por exemplo: adicionar conversa, gerar resumo, chat com a IA, atualização de perfil do cliente) podem **demorar alguns segundos** para concluir. O projeto utiliza um **plano de IA mais econômico e menos premium**, com requisições mais lentas. É normal aguardar um pouco após clicar; evite clicar novamente para não duplicar a ação.

### 7.1. Atualização automática de perfil do cliente

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

### 7.2. Análise de atendimentos (AI Summary)

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

**Implementação:** `app/ai/service.py` – `AISummaryService`. Inclui intenções **SALE_COMPLETED** e **LOSS_REGISTERED** quando a conversa indica fechamento.

### 7.3. Detecção automática de visitas

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

**Implementação:** `app/ai/service.py` – `detect_visit_intent()`

### 7.4. Detecção e vinculação de imóveis

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

**Implementação:** `app/ai/service.py` – `detect_property_mention()`

### 7.5. Key points no fechamento (venda/perda)

- Ao **registrar venda** ou **perda**, o resumo da IA é atualizado com **key_points**:
  - **property_purchased**: descrição do imóvel comprado/alugado (quando há venda).
  - **property_lost**: descrição do imóvel do ciclo quando a perda é registrada.
- Esses campos alimentam o contexto do **chat** e dos **insights** no frontend.

### 7.6. Derivação de estado do cliente (State Derivation)

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

**Implementação:** `app/clients/state_derivation_service.py`. Ao fechar ciclo por venda/perda, o **lead score de fechamento** (ex.: 100) é aplicado ao cliente em `apply_closure_lead_score_to_client`.

### 7.7. Análise de jornada (Journey)

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

### 7.8. Chat assistente

**Quando:** Solicitado via API

**O que faz:**
- Permite conversação natural com a IA sobre clientes
- Contexto completo do cliente é fornecido à IA
- Respostas baseadas em todo o histórico disponível
- Sugestões acionáveis para o corretor

Contexto do atendimento (resumo IA, imóvel vinculado, visitas, vendas/perdas) e datas em horário de Brasília são incluídos no prompt. **Implementação:** `app/ai/chat_service.py`

### 7.9. Recomendação de imóveis

**Quando:** Durante análise de atendimento

**O que faz:**
- Analisa perfil do cliente (orçamento, preferências, localização)
- Busca imóveis no banco de dados que correspondem aos critérios
- **Rankeia** imóveis por relevância
- Retorna lista de propriedades recomendadas vinculadas ao atendimento

**Implementação:** `app/ai/service.py` – `_recommend_properties()`

---

## 8. API (endpoints)

A API está **totalmente documentada** no Swagger (`/docs`): cada endpoint tem resumo, descrição (incluindo regras de negócio quando aplicável), códigos de resposta (200, 201, 400, 401, 404, etc.) e schemas de request/response com descrições em português. Abaixo, um resumo dos principais recursos; para a lista completa e para testar as rotas, use a documentação interativa em **[/docs](https://projeto-tecnico-astrocode-backend.onrender.com/docs)**.

O fluxo completo (cliente → atendimento → visita → venda/perda) está descrito nos tópicos **5** e **6**.

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
| PUT | `/attendances/{id}` | Atualizar atendimento (apenas `property_id` editável) | Protegido |
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

As funcionalidades por área (clientes, atendimentos, imóveis, visitas, vendas, perdas, timeline) estão descritas nos tópicos **4 a 7**.

---

## 9. Segurança e autenticação

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

## 10. Destaques técnicos e proteções

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
