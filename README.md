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

### Pré-requisitos

- Python 3.11 ou superior
- PostgreSQL instalado e rodando
- Git (para clonar o repositório)

### Passo a passo

#### 1. Clone o repositório (se ainda não tiver)

```bash
git clone <url-do-repositorio>
cd Projeto-Tecnico-Astrocode-Backend
```

#### 2. Crie e ative um ambiente virtual

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Verificação:** Você deve ver `(.venv)` no início do prompt do terminal.

#### 3. Instale as dependências

```bash
pip install --upgrade pip
pip install -e .
```

**Importante:** Se você encontrar erros relacionados a `email-validator`, execute:
```bash
pip install email-validator
```

#### 4. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

**Windows:**
```bash
copy .env.example .env
```

**Linux/Mac:**
```bash
cp .env.example .env
```

Edite o arquivo `.env` e configure pelo menos:

```env
# Database
DATABASE_URL=postgresql://usuario:senha@localhost:5432/real_estate_attendance

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-change-in-production-use-long-random-string
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Google OAuth (opcional para começar)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

#### 5. Configure o banco de dados PostgreSQL

1. Acesse o PostgreSQL (via psql ou pgAdmin)
2. Crie o banco de dados:

```sql
CREATE DATABASE real_estate_attendance;
```

3. Verifique se o usuário tem permissões:

```sql
GRANT ALL PRIVILEGES ON DATABASE real_estate_attendance TO seu_usuario;
```

#### 6. Aplique as migrations

```bash
alembic upgrade head
```

**Verificação:** Você deve ver mensagens de sucesso para cada migration aplicada.

#### 7. Inicie o servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Verificação:** Você deve ver algo como:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

#### 8. Teste se está funcionando

Abra seu navegador e acesse:

- **API Base:** http://localhost:8000
- **Healthcheck:** http://localhost:8000/health
- **Database Health:** http://localhost:8000/health/db
- **Documentação Swagger:** http://localhost:8000/docs
- **Documentação ReDoc:** http://localhost:8000/redoc

**Teste rápido via terminal:**

```bash
# Healthcheck básico
curl http://localhost:8000/health

# Deve retornar: {"status":"ok"}
```

### Solução de problemas comuns

#### Erro: `ModuleNotFoundError: No module named 'email_validator'`

**Solução:**
```bash
pip install email-validator
```

Ou reinstale todas as dependências:
```bash
pip install -e . --force-reinstall
```

#### Erro: `sqlalchemy.exc.OperationalError: could not connect to server`

**Solução:**
1. Verifique se o PostgreSQL está rodando
2. Verifique se a `DATABASE_URL` no `.env` está correta
3. Teste a conexão manualmente:
   ```bash
   psql -U seu_usuario -d real_estate_attendance
   ```

#### Erro: `alembic.util.exc.CommandError: Target database is not up to date`

**Solução:**
```bash
# Verifique o status atual
alembic current

# Aplique todas as migrations pendentes
alembic upgrade head
```

#### Erro: `ImportError: cannot import name 'X' from 'app.Y'`

**Solução:**
1. Verifique se todas as dependências estão instaladas:
   ```bash
   pip install -e . --force-reinstall
   ```
2. Verifique se o ambiente virtual está ativado
3. Reinicie o servidor

#### Porta 8000 já está em uso

**Solução:**
Use outra porta:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Ou encontre e encerre o processo usando a porta 8000:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill
```

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

## Google OAuth

O sistema suporta autenticação via Google OAuth2.

### Endpoints OAuth

- `GET /auth/google/login` - Inicia o fluxo OAuth (redireciona para Google)
- `GET /auth/google/callback` - Processa o callback do Google

### Como Configurar Google OAuth

#### 1. Criar credenciais no Google Cloud Console

1. Acesse: https://console.cloud.google.com/
2. Crie um projeto ou selecione um existente
3. Ative a API "Google+ API" ou "Google Identity"
4. Vá em **Credenciais** → **Criar credenciais** → **ID do cliente OAuth 2.0**
5. Configure:
   - **Tipo:** Aplicativo Web
   - **Nome:** Real Estate Attendance Backend (ou qualquer nome)
   - **URIs de redirecionamento autorizados:** 
     ```
     http://localhost:8000/auth/google/callback
     ```
     ⚠️ **IMPORTANTE:** A URI deve ser EXATAMENTE esta (incluindo protocolo, porta e path)

6. Copie o **Client ID** e **Client Secret**

#### 2. Configurar no `.env`

Adicione ao seu arquivo `.env`:

```env
GOOGLE_CLIENT_ID=seu-client-id-aqui.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu-client-secret-aqui
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

⚠️ **CRÍTICO:** A `GOOGLE_REDIRECT_URI` deve corresponder **EXATAMENTE** à URI configurada no Google Cloud Console, incluindo:
- Protocolo (`http://` ou `https://`)
- Domínio completo
- Porta (se aplicável)
- Path completo (`/auth/google/callback`)
- Sem trailing slash

#### 3. Testar OAuth

1. Acesse: `http://localhost:8000/auth/google/login`
2. Você será redirecionado para o Google
3. Faça login e autorize o acesso
4. Você será redirecionado de volta e receberá um token JWT

### Erro: `redirect_uri_mismatch`

Se você receber o erro `{"detail":"OAuth authentication failed: redirect_uri_mismatch: Bad Request"}`, significa que a URI de redirecionamento não corresponde exatamente à configurada no Google Cloud Console.

**Solução:**

1. Verifique a URI no Google Cloud Console:
   - Vá em **Credenciais** → Seu OAuth 2.0 Client ID
   - Verifique a seção **URIs de redirecionamento autorizados**
   - Deve conter exatamente: `http://localhost:8000/auth/google/callback`

2. Verifique a URI no seu `.env`:
   ```env
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   ```

3. Certifique-se de que:
   - Protocolo está correto (`http://` para localhost, `https://` para produção)
   - Não há trailing slash (`/auth/google/callback` e não `/auth/google/callback/`)
   - Porta está correta (`8000` se for o padrão)
   - Path está correto (`/auth/google/callback`)

4. Após alterar no Google Cloud Console, pode levar alguns minutos para propagar

5. Reinicie a aplicação após alterar o `.env`

**Exemplo de URIs válidas:**
- ✅ `http://localhost:8000/auth/google/callback`
- ✅ `https://seusite.com/auth/google/callback`
- ❌ `http://localhost:8000/auth/google/callback/` (trailing slash)
- ❌ `http://127.0.0.1:8000/auth/google/callback` (IP diferente)
- ❌ `https://localhost:8000/auth/google/callback` (protocolo diferente)

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
