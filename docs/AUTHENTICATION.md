# Sistema de Autenticação e Autorização

## 📋 Visão Geral

Este documento explica como funciona o sistema completo de autenticação e autorização da aplicação, incluindo:

- Login com email/senha
- Login com Google OAuth
- Controle de acesso baseado em roles (RBAC)
- Gerenciamento de usuários por gestores

---

## 🔐 Roles (Papéis) do Sistema

O sistema possui três roles principais:

1. **`atendente`** - Atendente imobiliário
   - Pode gerenciar clientes (leads)
   - Acesso básico ao sistema

2. **`corretor`** - Corretor de imóveis
   - Pode gerenciar clientes (leads)
   - Acesso intermediário ao sistema

3. **`gestor`** - Gestor/Administrador
   - Pode criar novos usuários
   - Pode gerenciar roles de usuários
   - Acesso completo ao sistema

---

## 🔑 Fluxos de Autenticação

### 1. Login com Email e Senha

**Endpoint:** `POST /auth/login`

**Descrição:**
- Usuário faz login com email e senha
- Sistema valida credenciais
- Retorna token JWT para autenticação

**Request:**
```json
{
    "email": "usuario@example.com",
    "password": "senha123"
}
```

**Response:**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

**Como usar o token:**
- Adicione no header: `Authorization: Bearer {access_token}`
- Token expira após o tempo configurado em `JWT_EXPIRATION_HOURS`

---

### 2. Login com Google OAuth

**Endpoint:** `GET /auth/google/login`

**Descrição:**
- Usuário é redirecionado para página de autorização do Google
- Após autorizar, Google redireciona para `/auth/google/callback`
- Sistema cria usuário automaticamente se não existir
- **Usuários criados via OAuth recebem role `atendente` por padrão**
- Gestor pode alterar a role depois

**Fluxo:**
1. Usuário acessa `/auth/google/login`
2. Redirecionado para Google
3. Autoriza acesso
4. Google redireciona para `/auth/google/callback?code=...`
5. Sistema cria/autentica usuário
6. Retorna token JWT

**Nota:** Usuários OAuth não podem fazer login com email/senha (usam senha placeholder).

---

## 👥 Gerenciamento de Usuários (Apenas Gestores)

### 1. Criar Novo Usuário

**Endpoint:** `POST /auth/register`

**Permissão:** Apenas usuários com role `gestor`

**Descrição:**
- Gestor cria novo usuário no sistema
- Define email, senha, nome e roles do usuário
- Usuário pode fazer login imediatamente

**Request:**
```json
{
    "email": "novo.usuario@example.com",
    "password": "senha123456",
    "full_name": "Novo Usuário",
    "role_names": ["atendente", "corretor"]
}
```

**Response:**
```json
{
    "id": "uuid-do-usuario",
    "email": "novo.usuario@example.com",
    "full_name": "Novo Usuário",
    "is_active": true,
    "roles": [
        {
            "id": "uuid-role-atendente",
            "name": "atendente",
            "description": "Atendente imobiliário"
        },
        {
            "id": "uuid-role-corretor",
            "name": "corretor",
            "description": "Corretor de imóveis"
        }
    ],
    "created_at": "2026-02-03T10:00:00Z",
    "updated_at": "2026-02-03T10:00:00Z"
}
```

**Roles válidas:**
- `atendente`
- `corretor`
- `gestor`

**Erros possíveis:**
- `403 Forbidden`: Usuário não tem role `gestor`
- `400 Bad Request`: Email já existe
- `400 Bad Request`: Role inválida

---

### 2. Atualizar Roles de um Usuário

**Endpoint:** `PUT /users/{user_id}/roles`

**Permissão:** Apenas usuários com role `gestor`

**Descrição:**
- Gestor pode alterar roles de qualquer usuário
- Útil para promover atendentes a corretores
- Útil para definir roles de usuários OAuth

**Request:**
```json
["corretor", "gestor"]
```

**Response:**
```json
{
    "id": "uuid-do-usuario",
    "email": "usuario@example.com",
    "full_name": "Nome do Usuário",
    "is_active": true,
    "roles": [
        {
            "id": "uuid-role-corretor",
            "name": "corretor",
            "description": "Corretor de imóveis"
        },
        {
            "id": "uuid-role-gestor",
            "name": "gestor",
            "description": "Gestor/Administrador"
        }
    ],
    "created_at": "2026-02-03T10:00:00Z",
    "updated_at": "2026-02-03T10:00:00Z"
}
```

**Exemplo de uso:**
- Usuário OAuth criado como `atendente`
- Gestor promove para `corretor` ou `gestor`

---

### 3. Listar Usuários

**Endpoint:** `GET /users?skip=0&limit=100`

**Permissão:** Apenas usuários com role `gestor`

**Descrição:**
- Lista todos os usuários do sistema
- Suporta paginação

**Response:**
```json
[
    {
        "id": "uuid-1",
        "email": "usuario1@example.com",
        "full_name": "Usuário 1",
        "is_active": true,
        "roles": [...],
        ...
    },
    {
        "id": "uuid-2",
        "email": "usuario2@example.com",
        "full_name": "Usuário 2",
        "is_active": true,
        "roles": [...],
        ...
    }
]
```

---

### 4. Buscar Usuário por ID

**Endpoint:** `GET /users/{user_id}`

**Permissão:** Apenas usuários com role `gestor`

**Descrição:**
- Busca informações de um usuário específico

**Response:**
```json
{
    "id": "uuid-do-usuario",
    "email": "usuario@example.com",
    "full_name": "Nome do Usuário",
    "is_active": true,
    "roles": [...],
    "created_at": "2026-02-03T10:00:00Z",
    "updated_at": "2026-02-03T10:00:00Z"
}
```

---

## 🔒 Controle de Acesso

### Dependências de Permissão

O sistema usa dependências do FastAPI para controlar acesso:

1. **`get_current_user`**
   - Valida token JWT
   - Retorna usuário autenticado
   - Usado em todas as rotas protegidas

2. **`get_current_active_user`**
   - Alias para `get_current_user`
   - Garante que usuário está ativo

3. **`get_current_manager`**
   - Verifica se usuário tem role `gestor`
   - Usado em rotas administrativas
   - Retorna `403 Forbidden` se não for gestor

### Exemplo de Uso

```python
@router.post("/admin-only")
def admin_endpoint(
    current_manager: User = Depends(get_current_manager),
):
    # Apenas gestores podem acessar
    ...
```

---

## 📝 Fluxo Completo de Uso

### Cenário 1: Primeiro Gestor (Setup Inicial)

1. **Criar primeiro gestor via script:**
   ```bash
   python scripts/create_test_user.py \
     --email gestor@example.com \
     --password senha123456 \
     --name "Gestor Principal"
   ```

2. **Atribuir role gestor:**
   - Conectar ao banco de dados
   - Atribuir role `gestor` manualmente ou via script

3. **Login como gestor:**
   ```bash
   POST /auth/login
   {
       "email": "gestor@example.com",
       "password": "senha123456"
   }
   ```

4. **Criar outros usuários:**
   ```bash
   POST /auth/register
   Authorization: Bearer {token_gestor}
   {
       "email": "atendente@example.com",
       "password": "senha123",
       "full_name": "Atendente",
       "role_names": ["atendente"]
   }
   ```

---

### Cenário 2: Usuário OAuth

1. **Usuário faz login via Google:**
   - Acessa `/auth/google/login`
   - Autoriza no Google
   - Sistema cria usuário automaticamente
   - **Role padrão: `atendente`**

2. **Gestor promove usuário:**
   ```bash
   PUT /users/{user_id}/roles
   Authorization: Bearer {token_gestor}
   ["corretor"]
   ```

---

### Cenário 3: Gestor Cria Usuário com Múltiplas Roles

```bash
POST /auth/register
Authorization: Bearer {token_gestor}
{
    "email": "corretor@example.com",
    "password": "senha123",
    "full_name": "Corretor Experiente",
    "role_names": ["atendente", "corretor"]
}
```

---

## 🛠️ Endpoints Disponíveis

### Autenticação (Públicos)
- `POST /auth/login` - Login com email/senha
- `GET /auth/google/login` - Iniciar OAuth Google
- `GET /auth/google/callback` - Callback OAuth Google

### Autenticação (Protegidos)
- `GET /auth/me` - Informações do usuário atual
- `POST /auth/register` - Criar usuário (apenas gestores)

### Usuários (Apenas Gestores)
- `GET /users` - Listar usuários
- `GET /users/{user_id}` - Buscar usuário
- `PUT /users/{user_id}/roles` - Atualizar roles

### Clientes (Protegidos)
- `POST /clients` - Criar cliente
- `GET /clients` - Listar clientes
- `GET /clients/{client_id}` - Buscar cliente
- `PUT /clients/{client_id}` - Atualizar cliente
- `DELETE /clients/{client_id}` - Deletar cliente

---

## ⚠️ Importante

1. **Primeiro Gestor:**
   - Deve ser criado manualmente ou via script
   - Depois pode criar outros usuários via API

2. **Usuários OAuth:**
   - Recebem role `atendente` automaticamente
   - Gestor pode alterar depois
   - Não podem fazer login com email/senha

3. **Segurança:**
   - Tokens JWT expiram automaticamente
   - Senhas são hasheadas com bcrypt
   - Apenas gestores podem criar/gerenciar usuários

4. **Roles:**
   - Valores válidos: `atendente`, `corretor`, `gestor`
   - Um usuário pode ter múltiplas roles
   - Roles são case-sensitive

---

## 🧪 Como Testar

### 1. Criar Primeiro Gestor

```bash
# Via script
python scripts/create_test_user.py \
  --email gestor@example.com \
  --password senha123456 \
  --name "Gestor"

# Depois, conectar ao banco e atribuir role 'gestor'
```

### 2. Login como Gestor

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "gestor@example.com",
    "password": "senha123456"
  }'
```

### 3. Criar Usuário

```bash
TOKEN="token_do_gestor"

curl -X POST "http://localhost:8000/auth/register" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "atendente@example.com",
    "password": "senha123",
    "full_name": "Atendente",
    "role_names": ["atendente"]
  }'
```

### 4. Atualizar Roles

```bash
USER_ID="uuid-do-usuario"

curl -X PUT "http://localhost:8000/users/$USER_ID/roles" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '["corretor"]'
```

---

## 📚 Referências

- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [JWT Authentication](https://jwt.io/)
- [OAuth 2.0](https://oauth.net/2/)

