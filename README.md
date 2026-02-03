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

## Autenticação

O sistema usa JWT (JSON Web Tokens) para autenticação.

### Endpoints de Autenticação

- `POST /auth/login` - Login com email e senha
- `GET /auth/me` - Obter informações do usuário autenticado

### Como Testar a Autenticação

#### 1. Criar um usuário de teste

**Opção A: Via script (recomendado)**

```bash
python scripts/create_test_user.py
```

Ou com parâmetros customizados:

```bash
python scripts/create_test_user.py --email "admin@example.com" --password "minhasenha123" --name "Admin User"
```

**Opção B: Via Python interativo**

```python
from app.db import SessionLocal
from app.users.repository import UserRepository
from app.users.schemas import UserCreate
from app.auth.password import hash_password

db = SessionLocal()
user_repo = UserRepository(db)

user_data = UserCreate(
    email="test@example.com",
    password="senha123456",
    full_name="Usuário Teste"
)

hashed = hash_password(user_data.password)
user = user_repo.create(user_data, hashed)
print(f"Usuário criado: {user.email}")
```

#### 2. Fazer login

**Via Swagger UI (http://localhost:8000/docs):**

1. Acesse `/docs`
2. Encontre o endpoint `POST /auth/login`
3. Clique em "Try it out"
4. Preencha:
   ```json
   {
     "email": "test@example.com",
     "password": "senha123456"
   }
   ```
5. Clique em "Execute"
6. Copie o `access_token` retornado

**Via cURL:**

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "senha123456"
  }'
```

**Resposta esperada:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### 3. Usar o token para acessar rotas protegidas

**Via Swagger UI:**

1. Clique no botão "Authorize" no topo da página
2. Cole o token no campo "Value" (sem a palavra "Bearer")
3. Clique em "Authorize"
4. Agora você pode testar endpoints protegidos como `GET /auth/me` ou `GET /health/protected`

**Via cURL:**

```bash
# Obter informações do usuário autenticado
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"

# Testar endpoint protegido
curl -X GET "http://localhost:8000/health/protected" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"
```

#### 4. Testar proteção de rotas

**Sem token (deve retornar 401):**
```bash
curl -X GET "http://localhost:8000/health/protected"
```

**Com token inválido (deve retornar 401):**
```bash
curl -X GET "http://localhost:8000/health/protected" \
  -H "Authorization: Bearer token_invalido"
```

**Com token válido (deve retornar 200):**
```bash
curl -X GET "http://localhost:8000/health/protected" \
  -H "Authorization: Bearer SEU_TOKEN_VALIDO"
```

### Variáveis de Ambiente para JWT

Adicione ao seu `.env`:

```env
JWT_SECRET_KEY=your-secret-key-change-in-production-use-long-random-string
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

**Importante:** Em produção, use uma chave secreta forte e aleatória!

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
