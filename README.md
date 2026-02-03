# Real Estate Attendance Backend

Backend de auxílio ao atendimento em imobiliárias, focado em organização de leads, histórico de atendimentos, geração automática de resumos via IA e dashboard gerencial.

## Stack

- **Linguagem:** Python 3.11+
- **Framework:** FastAPI
- **ORM:** SQLAlchemy
- **Banco de dados:** PostgreSQL
- **Migrações:** Alembic
- **Auth:** JWT + OAuth2 (Google)
- **IA:** LLM para resumo e sugestões

## Arquitetura

```
app/
├── core/       # Bootstrap, logging, utilitários
├── config/     # Configuração e variáveis de ambiente
├── db/         # SQLAlchemy, sessões, modelos
├── auth/       # Autenticação
├── users/      # Domínio de usuários
├── clients/    # Domínio de clientes/leads
├── properties/ # Domínio de imóveis
├── attendances/# Domínio de atendimentos
├── ai/         # Integração com LLM
├── dashboard/  # Métricas gerenciais
└── api/        # Rotas e endpoints
```

## Como rodar localmente

1. Crie um ambiente virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

2. Instale as dependências:
   ```bash
   pip install -e .
   ```

3. Copie o arquivo de exemplo e ajuste se necessário:
   ```bash
   copy .env.example .env
   ```

4. Inicie o servidor:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. Crie o banco PostgreSQL e ajuste `DATABASE_URL` no `.env`:
   ```sql
   CREATE DATABASE real_estate_attendance;
   ```

6. Aplique as migrations:
   ```bash
   alembic upgrade head
   ```

7. Acesse:
   - API: http://localhost:8000
   - Healthcheck: http://localhost:8000/health
   - Database health: http://localhost:8000/health/db
   - Docs: http://localhost:8000/docs

## Migrations

O projeto usa Alembic para versionamento do banco de dados.

### Comandos úteis

- **Criar nova migration:**
  ```bash
  alembic revision --autogenerate -m "Description"
  ```

- **Aplicar migrations:**
  ```bash
  alembic upgrade head
  ```

- **Reverter última migration:**
  ```bash
  alembic downgrade -1
  ```

- **Ver histórico:**
  ```bash
  alembic history
  ```

- **Ver status atual:**
  ```bash
  alembic current
  ```

## Variáveis de ambiente

Veja `.env.example` para a lista de variáveis disponíveis.
