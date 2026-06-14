# 🐄 Gestão de Gado Leiteiro API

![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange?logo=mysql)
![JWT](https://img.shields.io/badge/Auth-JWT-red?logo=jsonwebtokens)
![Cloudinary](https://img.shields.io/badge/Storage-Cloudinary-blue?logo=cloudinary)
![License](https://img.shields.io/badge/License-Private-lightgrey)

API completa para gerenciamento de propriedades leiteiras, desenvolvida com **FastAPI** e **MySQL**. Sistema robusto com regras de negócio reais do agronegócio, segurança severa e relatórios financeiros.

---

## 📋 Índice

- [Funcionalidades](#-funcionalidades)
- [Tecnologias](#-tecnologias)
- [Como rodar](#-como-rodar)
- [Estrutura do projeto](#-estrutura-do-projeto)
- [Segurança](#-segurança)
- [Endpoints](#-endpoints)
- [Regras de negócio](#-regras-de-negócio)

---

## ✨ Funcionalidades

| Módulo | Descrição |
|---|---|
| 🐄 **Animais** | Cadastro completo com genealogia, peso, status reprodutivo e foto |
| 🍼 **Partos** | Controle de partos com carência de colostro automática e alertas |
| 💉 **Vacinas** | Calendário de vacinação com alertas de próxima dose |
| 💊 **Medicamentos** | Estoque com desconto automático e carência do leite |
| 🥛 **Produções** | Registro diário com descarte automático em período de carência |
| 🔬 **Reprodução** | Cio, inseminação artificial, diagnóstico de gestação |
| 🏥 **Ocorrências** | Registro de doenças, exames e acidentes |
| 💰 **Financeiro** | Preço do leite com histórico e relatório financeiro por animal |
| 📊 **Dashboard** | Resumo do rebanho e alertas consolidados em tempo real |
| 📄 **Relatórios** | Exportação em PDF e Excel com dados financeiros |
| 👤 **Usuários** | Autenticação JWT com refresh token e foto de perfil |

---

## 🚀 Tecnologias

- **Python 3.14** + **FastAPI** — framework web moderno e rápido
- **SQLAlchemy** — ORM para MySQL
- **MySQL** — banco de dados relacional
- **JWT** — autenticação segura com refresh token
- **Cloudinary** — armazenamento de imagens na nuvem
- **ReportLab** — geração de relatórios em PDF
- **OpenPyXL** — geração de planilhas Excel
- **SlowAPI** — rate limiting por IP
- **Bcrypt** — hash seguro de senhas

---

## ⚙️ Como rodar

### 1. Clonar o repositório
```bash
git clone https://github.com/seu-usuario/gado_leiteiro_api.git
cd gado_leiteiro_api
```

### 2. Criar e ativar o ambiente virtual
```bash
python -m venv venv
venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate    # Linux/Mac
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente
Crie um arquivo `.env` na raiz do projeto:
```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=gado_leiteiro
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
SECRET_KEY=sua-chave-secreta-aqui
CLOUDINARY_CLOUD_NAME=seu_cloud_name
CLOUDINARY_API_KEY=sua_api_key
CLOUDINARY_API_SECRET=seu_api_secret
```

### 5. Criar o banco de dados
Execute o script SQL no MySQL Workbench:
```
migrations/atualizar_banco_v2.sql
```

### 6. Iniciar a API
```bash
uvicorn app.main:aplicacao --reload
```

### 7. Acessar a documentação
```
http://127.0.0.1:8000/docs
```

---

## 📁 Estrutura do projeto

```
gado_leiteiro_api/
├── app/
│   ├── main.py                 # Aplicação principal, CORS, handlers
│   ├── database.py             # Conexão com MySQL
│   ├── auth.py                 # JWT, refresh token, bloqueio de login
│   ├── security.py             # Hash de senhas
│   ├── erros.py                # Tratamento global de erros
│   ├── logger.py               # Sistema de logs
│   ├── limitador.py            # Rate limiting
│   ├── cloudinary_config.py    # Upload de imagens
│   ├── models/                 # Models SQLAlchemy
│   │   ├── animal.py
│   │   ├── parto.py
│   │   ├── vacina.py
│   │   ├── medicamento.py
│   │   ├── producao.py
│   │   ├── reproducao.py
│   │   └── usuario.py
│   ├── schemas/                # Schemas Pydantic
│   │   ├── animais.py
│   │   ├── partos.py
│   │   ├── vacinas.py
│   │   ├── medicamentos.py
│   │   ├── producoes.py
│   │   ├── reproducao.py
│   │   └── usuarios.py
│   └── routers/                # Endpoints da API
│       ├── animais.py
│       ├── partos.py
│       ├── vacinas.py
│       ├── medicamentos.py
│       ├── producoes.py
│       ├── reproducao.py
│       ├── usuarios.py
│       ├── dashboard.py
│       └── relatorios.py
├── migrations/
│   └── atualizar_banco_v2.sql
├── tests/
│   └── test_api.py
├── logs/                       # Gerado automaticamente
├── requirements.txt
├── .env                        # Não commitado
└── .gitignore
```

---

## 🔒 Segurança

- ✅ Autenticação via **JWT Bearer Token** (expira em 30 minutos)
- ✅ **Refresh Token** com validade de 7 dias
- ✅ Bloqueio automático após **5 tentativas** de login incorretas (15 minutos)
- ✅ **Rate limiting** — 10 logins e 5 cadastros por minuto por IP
- ✅ Isolamento total de dados por usuário
- ✅ Senhas com **hash Bcrypt**
- ✅ Credenciais protegidas via `.env`
- ✅ Tratamento global de erros sem exposição de dados internos

---

## 📡 Endpoints

### Autenticação
| Método | Rota | Descrição |
|---|---|---|
| POST | `/usuarios/cadastrar` | Cadastrar novo usuário |
| POST | `/usuarios/login` | Login e obter tokens |
| POST | `/usuarios/refresh` | Renovar access token |
| GET | `/usuarios/perfil` | Ver perfil |
| PUT | `/usuarios/perfil` | Atualizar perfil |
| POST | `/usuarios/perfil/foto` | Upload foto de perfil |

### Animais
| Método | Rota | Descrição |
|---|---|---|
| GET | `/animais/` | Listar todos os animais |
| GET | `/animais/ativos` | Listar animais ativos |
| GET | `/animais/em-lactacao` | Listar animais em lactação |
| POST | `/animais/` | Cadastrar animal |
| PUT | `/animais/{id}` | Atualizar animal |
| POST | `/animais/{id}/foto` | Upload foto do animal |

### Produções
| Método | Rota | Descrição |
|---|---|---|
| POST | `/producoes/` | Registrar produção diária |
| GET | `/producoes/relatorio/diario` | Relatório do dia |
| GET | `/producoes/relatorio/semanal` | Relatório semanal |
| GET | `/producoes/relatorio/mensal` | Relatório mensal |
| POST | `/producoes/preco-leite/` | Cadastrar preço do leite |

### Dashboard
| Método | Rota | Descrição |
|---|---|---|
| GET | `/dashboard/resumo` | Resumo geral da propriedade |
| GET | `/dashboard/alertas` | Todos os alertas consolidados |

### Relatórios
| Método | Rota | Descrição |
|---|---|---|
| GET | `/relatorios/pdf/producao-mensal` | PDF de produção mensal |
| GET | `/relatorios/excel/producao-mensal` | Excel de produção mensal |
| GET | `/relatorios/excel/rebanho` | Excel com todo o rebanho |

---

## 📋 Regras de negócio

- 🐄 Apenas fêmeas podem ter produção de leite e partos registrados
- 🍼 Intervalo mínimo entre partos: **9 meses**
- 🥛 Leite em período de carência (pós-parto ou medicamento) é automaticamente marcado como **descartado**
- 💊 Estoque de medicamento é descontado automaticamente a cada aplicação
- 💉 Intervalo mínimo entre doses da mesma vacina: **30 dias**
- 📅 Período seco calculado automaticamente: **60 dias antes do parto previsto**
- 🐂 Gestação bovina calculada automaticamente: **283 dias após a cobertura**
- 💰 Relatório financeiro usa o preço vigente na data do período consultado

---

## 🧪 Testes

```bash
pytest tests/ -v
```

---

## 📄 Licença

Este projeto é de uso privado.
