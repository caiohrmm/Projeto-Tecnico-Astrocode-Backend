# 🏠 Sistema para Corretor de Imóveis com Inteligência Artificial

<div align="center">

**Imagine um caderninho mágico que ajuda corretores a vender casas! 🪄**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org)

</div>

---

## 🎯 O Que Este Sistema Faz? (Explicação Simples)

Imagine que você é um corretor de imóveis. Você tem muitas pessoas querendo comprar ou alugar casas, e muitas casas para vender. É muita coisa para lembrar, né?

**Este sistema é como um assistente super inteligente que:**

1. **Lembra de todos os seus clientes** 📝
   - Quem são eles
   - O que eles querem (casa grande? apartamento? onde?)
   - Quanto dinheiro eles têm
   - Quando você falou com eles pela última vez

2. **Anota tudo que acontece** 📖
   - Quando você liga para um cliente
   - Quando você manda mensagem no WhatsApp
   - O que o cliente disse que quer
   - Se ele gostou de alguma casa

3. **Tem um robô mágico que lê as conversas** 🤖
   - O robô lê tudo que você escreveu sobre o cliente
   - Ele entende o que o cliente quer (casa de 3 quartos? apartamento no centro?)
   - Ele sugere casas que o cliente pode gostar
   - Ele diz: "Este cliente está muito interessado! Priorize ele!"

4. **Ajuda você a não esquecer nada** ✅
   - "Lembre de ligar para a Maria amanhã"
   - "Mostre estas 3 casas para o João"
   - "Este cliente quer comprar logo, é urgente!"

5. **Mostra o que está funcionando** 📊
   - Quantas vendas você fez este mês
   - Quais clientes estão quase fechando negócio
   - O que você pode fazer melhor

**Em resumo:** É como ter um assistente que nunca esquece nada, sempre sabe o que fazer, e ajuda você a vender mais casas! 🎉

---

## 🎨 Como Funciona? (Passo a Passo Simples)

### 1️⃣ Um Cliente Chega

**O que acontece:**
- Você cadastra o cliente no sistema
- O robô mágico (IA) lê as informações e dá uma "nota" para o cliente
- Quanto maior a nota, mais interessado ele está!

### 2️⃣ Você Atende o Cliente

**O que acontece:**
- Você registra a conversa (pode ser por telefone, WhatsApp, presencial)
- Você escreve o que o cliente disse
- O robô mágico lê tudo e entende:
  - "Ah! Ele quer um apartamento de 3 quartos!"
  - "Ele tem R$ 500.000 para gastar"
  - "Ele quer mudar em 2 meses (é urgente!)"

### 3️⃣ O Sistema Sugere Casas

**O que acontece:**
- O robô mágico procura casas que combinam com o que o cliente quer
- Ele mostra: "Olha! Estas 3 casas são perfeitas para ele!"
- Você pode mostrar essas casas para o cliente

### 4️⃣ Você Agenda uma Visita

**O que acontece:**
- Você marca quando vai mostrar a casa
- O sistema lembra você da visita
- Depois da visita, você anota se o cliente gostou

### 5️⃣ Se o Cliente Comprou! 🎉

**O que acontece:**
- Você registra a venda
- O sistema entende que o objetivo foi alcançado
- Ele sugere: "Agora você precisa preparar os documentos!"

### 6️⃣ Se o Cliente Não Comprou 😔

**O que acontece:**
- Você registra o que aconteceu
- O robô mágico aprende: "Ah, este tipo de cliente não comprou porque..."
- Isso ajuda você a melhorar no futuro!

---

## 🧩 As Partes do Sistema (Como um Quebra-Cabeça)

O sistema tem várias "caixinhas" que fazem coisas diferentes:

### 📱 **Clientes** (A Caixinha das Pessoas)
- Guarda informações de todas as pessoas que querem comprar/alugar
- Lembra o que cada uma quer
- Mostra quem está mais perto de comprar

### 💬 **Atendimentos** (A Caixinha das Conversas)
- Guarda todas as vezes que você falou com alguém
- O robô mágico lê essas conversas e entende o que o cliente quer
- Cria um resumo automático de cada conversa

### 🏘️ **Imóveis** (A Caixinha das Casas)
- Guarda informações de todas as casas/apartamentos à venda
- Tem fotos, preço, localização
- O sistema procura casas que combinam com o que o cliente quer

### 🚗 **Visitas** (A Caixinha dos Agendamentos)
- Lembra quando você vai mostrar uma casa
- Ajuda você a não esquecer de nenhuma visita

### 💰 **Vendas** (A Caixinha do Dinheiro)
- Registra quando uma venda aconteceu
- Calcula quanto você ganhou de comissão

### 🤖 **Inteligência Artificial** (O Robô Mágico)
- Lê todas as conversas
- Entende o que o cliente quer
- Sugere o que fazer
- Aprende com o tempo

---

## 🚀 Como Começar a Usar? (Instruções Simples)

### Passo 1: Preparar o Computador

Você precisa ter instalado:
- **Python** (versão 3.11 ou mais nova) - É a linguagem que o sistema usa
- **PostgreSQL** (versão 13 ou mais nova) - É onde guardamos todas as informações
- **Chave da API Google Gemini** - É o que faz o robô mágico funcionar

### Passo 2: Baixar o Sistema

```bash
# Baixar o sistema do computador
git clone <url-do-repositorio>
cd Projeto-Tecnico-Astrocode-Backend

# Criar um "ambiente virtual" (é como uma caixinha separada para o sistema)
python -m venv .venv

# Entrar na caixinha
# No Windows:
.venv\Scripts\activate
# No Linux/Mac:
source .venv/bin/activate

# Instalar todas as "peças" que o sistema precisa
pip install -e .
```

### Passo 3: Configurar o Sistema

Crie um arquivo chamado `.env` na pasta do projeto e coloque estas informações:

```env
# Onde guardar as informações (banco de dados)
DATABASE_URL=postgresql://usuario:senha@localhost:5432/real_estate_crm

# Uma senha secreta para proteger o sistema
JWT_SECRET_KEY=sua-chave-secreta-mude-em-producao
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# A chave do robô mágico (Google Gemini)
GEMINI_API_KEY=sua-chave-gemini

# Configurações do Google (opcional - para fazer login com Google)
GOOGLE_CLIENT_ID=seu-google-client-id
GOOGLE_CLIENT_SECRET=seu-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Onde o sistema vai rodar
FRONTEND_URL=http://localhost:5173
```

### Passo 4: Preparar o Banco de Dados

```bash
# Criar o "armário" onde vamos guardar tudo
psql -U postgres -c "CREATE DATABASE real_estate_crm;"

# Organizar o armário (criar as gavetas e prateleiras)
alembic upgrade head
```

### Passo 5: Ligar o Sistema

```bash
# Ligar o sistema (ele vai "acordar" e ficar pronto para usar)
uvicorn app.main:app --reload --port 8000
```

Agora o sistema está funcionando! 🎉

Você pode acessar:
- **A tela principal:** http://localhost:8000
- **A documentação (para ver como usar):** http://localhost:8000/docs
- **Outra documentação:** http://localhost:8000/redoc

### Passo 6: Criar o Primeiro Usuário

```bash
# Criar um usuário "chefe" (que pode fazer tudo)
python scripts/create_manager.py --email admin@exemplo.com --password senha123 --name "Admin"

# Ou criar um usuário de teste
python scripts/create_test_user.py
```

---

## 📚 Como Usar o Sistema? (Guia Rápido)

### 🔐 Entrar no Sistema

1. Abra o sistema no navegador
2. Digite seu email e senha
3. Clique em "Entrar"
4. Pronto! Você está dentro! 🎉

### 👥 Cadastrar um Cliente

1. Vá em "Clientes"
2. Clique em "Novo Cliente"
3. Preencha:
   - Nome da pessoa
   - Telefone
   - Email (se tiver)
   - O que ela quer (comprar? alugar?)
4. Clique em "Salvar"
5. O robô mágico já vai analisar e dar uma nota para o cliente!

### 💬 Registrar um Atendimento

1. Vá no cliente que você quer registrar
2. Clique em "Novo Atendimento"
3. Escolha como foi (telefone? WhatsApp? presencial?)
4. Escreva o que o cliente disse
5. Clique em "Salvar"
6. O robô mágico vai ler tudo e:
   - Criar um resumo
   - Entender o que o cliente quer
   - Sugerir casas que combinam
   - Dizer o que fazer depois

### 🏠 Cadastrar um Imóvel

1. Vá em "Imóveis"
2. Clique em "Novo Imóvel"
3. Preencha:
   - Tipo (casa? apartamento?)
   - Endereço
   - Preço
   - Fotos
   - Descrição
4. Clique em "Salvar"

### 🚗 Agendar uma Visita

1. Vá no cliente
2. Clique em "Agendar Visita"
3. Escolha qual casa você vai mostrar
4. Escolha data e hora
5. Clique em "Salvar"
6. O sistema vai lembrar você da visita!

### 💰 Registrar uma Venda

1. Vá no cliente que comprou
2. Clique em "Registrar Venda"
3. Escolha qual imóvel foi vendido
4. Coloque o valor da venda
5. Clique em "Salvar"
6. O sistema vai entender que o objetivo foi alcançado! 🎉

---

## 🤖 Como o Robô Mágico (IA) Funciona?

O robô mágico usa o **Google Gemini** (uma inteligência artificial muito esperta).

### O Que Ele Faz:

1. **Lê Conversas** 📖
   - Quando você escreve sobre um atendimento, ele lê tudo
   - Ele entende português muito bem!

2. **Entende o Que o Cliente Quer** 🎯
   - "Quero um apartamento de 3 quartos" → Ele entende: tipo=apartamento, quartos=3
   - "Tenho 500 mil" → Ele entende: orçamento=R$ 500.000
   - "Preciso mudar em 2 meses" → Ele entende: urgência=ALTA

3. **Sugere Casas** 🏠
   - Ele procura casas que combinam com o que o cliente quer
   - Mostra as melhores opções

4. **Dá Notas aos Clientes** ⭐
   - Cliente muito interessado = nota alta (80-100)
   - Cliente só olhando = nota baixa (0-30)
   - Isso ajuda você a saber em quem focar!

5. **Sugere o Que Fazer** 💡
   - "Agende uma visita"
   - "Envie mais informações"
   - "Este cliente está quase fechando, priorize!"

6. **Aprende com o Tempo** 📈
   - Quanto mais você usa, mais ele aprende
   - Ele fica melhor em entender o que os clientes querem

---

## 🏗️ Como o Sistema é Feito? (Para Quem Quer Entender Mais)

O sistema tem duas partes principais:

### 🔧 Backend (O "Motor" do Sistema)
- **Linguagem:** Python
- **Framework:** FastAPI (faz o sistema funcionar rápido)
- **Banco de Dados:** PostgreSQL (guarda todas as informações)
- **IA:** Google Gemini (o robô mágico)

### 🎨 Frontend (A "Cara" do Sistema)
- **Linguagem:** JavaScript
- **Framework:** Vue.js (faz a tela bonita e interativa)
- **Biblioteca de Design:** Vuetify (deixa tudo bonito)

### Como Eles Se Comunicam:

```
Você (no navegador)
    ↓
Frontend (Vue.js) - A tela que você vê
    ↓
Backend (FastAPI) - O cérebro que pensa
    ↓
Banco de Dados (PostgreSQL) - A memória que guarda tudo
    ↓
IA (Google Gemini) - O robô mágico que ajuda
```

---

## 🔒 Segurança (Como Proteger o Sistema)

O sistema tem várias "trancas" para proteger suas informações:

1. **Senha Forte** 🔐
   - Você precisa de email e senha para entrar
   - A senha é criptografada (ninguém consegue ver)

2. **Tokens** 🎫
   - Quando você entra, o sistema te dá um "ticket"
   - Você precisa mostrar esse ticket para fazer coisas
   - O ticket expira depois de um tempo

3. **Permissões** 👮
   - Diferentes pessoas podem fazer coisas diferentes:
     - **Chefe:** Pode fazer tudo
     - **Corretor:** Pode gerenciar clientes e vendas
     - **Atendente:** Pode só criar atendimentos

4. **Login com Google** 🌐
   - Você pode entrar usando sua conta do Google
   - Mais fácil e seguro!

---

## 🧪 Testar o Sistema

Se você quer testar se tudo está funcionando:

```bash
# Instalar ferramentas de teste
pip install -e ".[dev]"

# Rodar os testes
pytest

# Ver se o código está bom
pytest --cov=app
```

---

## ❓ Problemas Comuns (E Como Resolver)

### ❌ "Erro de conexão com banco de dados"

**O que fazer:**
- Verifique se o PostgreSQL está rodando
- Verifique se a `DATABASE_URL` no arquivo `.env` está correta
- Teste: `psql -U seu_usuario -d real_estate_crm -c "SELECT 1;"`

### ❌ "ModuleNotFoundError"

**O que fazer:**
- Certifique-se de que o ambiente virtual está ativado
- Reinstale as dependências: `pip install -e . --force-reinstall`

### ❌ "Robô mágico não funciona"

**O que fazer:**
- Verifique se `GEMINI_API_KEY` está no arquivo `.env`
- Verifique se a chave é válida
- O sistema funciona sem IA, mas com menos recursos

### ❌ "Porta já está sendo usada"

**O que fazer:**
- Use outra porta: `uvicorn app.main:app --reload --port 8001`

---

## 📖 Documentação Extra

Se você quiser entender mais profundamente:

- [Como Funciona a Autenticação](docs/AUTHENTICATION.md) - Como o login funciona
- [Como Funciona o Sistema](docs/DOCUMENTACAO_SISTEMA.md) - Explicação completa
- [Fluxo de Cliente e Imóvel](docs/FLUXO_CLIENTE_IMOVEL_ATENDIMENTO.md) - Como tudo se conecta

---

## 🎉 Resumo Final

**Este sistema é como ter um assistente super inteligente que:**

✅ Lembra de todos os seus clientes  
✅ Anota todas as conversas  
✅ Entende o que cada cliente quer  
✅ Sugere casas que combinam  
✅ Diz o que fazer em cada situação  
✅ Ajuda você a vender mais!  

**É como ter um superpoder para vender imóveis!** 🦸‍♂️

---

<div align="center">

**Desenvolvido como Desafio Técnico para a vaga na Astrocode** 🚀

[⬆ Voltar ao topo](#-sistema-para-corretor-de-imóveis-com-inteligência-artificial)

</div>
