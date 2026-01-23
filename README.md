```markdown
# ✈️ T-FlightOps

**T-FlightOps** é um sistema web robusto de Operações de Voo, desenvolvido para gerenciar e planejar malhas aéreas, escalas, aeroportos e acompanhamento de cargas e voos. O sistema utiliza uma arquitetura modular baseada em Python (Flask), integrando-se com bancos de dados SQL Server e PostgreSQL para garantir integridade e eficiência operacional.

---

## 🛠️ Tecnologias Utilizadas

O projeto foi construído utilizando uma stack moderna e eficiente:

* **Backend:** Python 3.13+, Flask 3.1.2
* **Banco de Dados:** SQL Server (Legado/Corporativo) e PostgreSQL (Novos módulos)
* **ORM & Dados:** SQLAlchemy 2.0, Pandas, OpenPyXL
* **Frontend:** HTML5, CSS3, Jinja2 (Templates)
* **Autenticação:** Flask-Login (Integração com AD/Usuários SQL)
* **Serviços:** NetworkX (Grafos de rotas), Waitress (WSGI Production)

---

## 📂 Estrutura do Projeto

Abaixo segue a árvore de diretórios do projeto, detalhando a organização dos módulos, rotas e serviços.

```text
T-FlightOps/
├── .env                       # Variáveis de ambiente
├── .gitignore                 # Arquivos ignorados pelo Git
├── App.py                     # Ponto de entrada da aplicação (Flask App)
├── Conexoes.py                # Gerenciamento de conexões com Banco de Dados
├── Configuracoes.py           # Configurações globais do sistema
├── LICENSE                    # Licença do projeto
├── README.md                  # Documentação do projeto
├── StatusAWB.sql              # Scripts SQL auxiliares
├── VERSION                    # Arquivo de controle de versão
├── WSGI.py                    # Entry point para servidor de produção
├── requirements.txt           # Dependências do Python
│
├── Data/                      # Arquivos de dados estáticos (Carga inicial/Importação)
│   ├── cidades.xlsx - Plan1.csv
│   ├── iata-icao.csv
│   └── malha-aerea.xlsx - MALHA AÉREA.csv
│
├── Models/                    # Modelos de Dados (ORM)
│   ├── UsuarioModel.py        # Modelo de Usuário do Sistema
│   ├── POSTGRES/              # Modelos mapeados para PostgreSQL
│   │   ├── Aeroporto.py
│   │   ├── Base.py
│   │   ├── Cidade.py
│   │   ├── MalhaAerea.py
│   │   └── VersaoSistema.py
│   └── SQL_SERVER/            # Modelos mapeados para SQL Server
│       ├── Awb.py
│       ├── Cadastros.py
│       ├── Ctc.py
│       ├── Manifesto.py
│       └── Usuario.py
│
├── Routes/                    # Rotas (Blueprints) e Controladores
│   ├── Acompanhamento.py
│   ├── Aeroportos.py
│   ├── Auth.py
│   ├── Cidades.py
│   ├── Escalas.py
│   ├── Malha.py
│   └── Planejamento.py
│
├── Scripts/                   # Scripts de manutenção e automação
│   ├── AtualizarBanco.py
│   ├── DiagnosticoTabelas.py
│   ├── GerarRelatorioCidades.py
│   ├── GestaoVersao.py
│   ├── InicializarBanco.py
│   ├── RecriarAeroportos.py
│   └── Teste.py
│
├── Services/                  # Regras de Negócio e Serviços
│   ├── AcompanhamentoService.py
│   ├── AeroportosService.py
│   ├── AuthService.py
│   ├── CidadesService.py
│   ├── MalhaService.py
│   ├── PlanejamentoService.py
│   ├── VersaoService.py
│   └── Shared/                # Serviços compartilhados
│       └── GeoService.py      # Cálculos geográficos e geometria
│
├── Static/                    # Arquivos Estáticos (Frontend)
│   └── CSS/
│       ├── Global.css
│       └── Temas.css
│
├── Templates/                 # Templates HTML (Jinja2)
│   ├── Base.html              # Layout base
│   ├── Dashboard.html         # Página inicial
│   ├── Acompanhamento/
│   │   └── Index.html
│   ├── Aeroportos/
│   │   └── Manager.html
│   ├── Auth/
│   │   └── Login.html
│   ├── Cidades/
│   │   └── Manager.html
│   ├── Components/            # Modais e componentes reutilizáveis
│   │   ├── _ModalAwb.html
│   │   └── _ModalCtc.html
│   ├── Escalas/
│   │   └── Index.html
│   ├── Malha/
│   │   └── Manager.html
│   └── Planejamento/
│       ├── Editor.html
│       ├── Index.html
│       └── Map.html
│
└── Utils/                     # Utilitários e Helpers
    ├── Formatadores.py
    ├── Geometria.py
    └── Texto.py

```

## 🚀 Instalação e Execução

### Pré-requisitos

Certifique-se de ter o Python instalado.

1. **Clonar o repositório:**
```bash
git clone https://seu-repositorio/T-FlightOps.git
cd T-FlightOps

```


2. **Criar e ativar o ambiente virtual:**
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

```


3. **Instalar as dependências:**
```bash
pip install -r requirements.txt

```


4. **Configurar Variáveis de Ambiente:**
Crie um arquivo `.env` na raiz baseado nas configurações necessárias (Banco de dados, Chaves secretas).
5. **Executar o Projeto:**
```bash
python App.py

```


O sistema estará disponível em `http://127.0.0.1:5000/`.



## 📋 Funcionalidades Principais

* **Planejamento de Malha:** Criação e visualização de rotas aéreas e escalas.
* **Gestão de Aeroportos e Cidades:** CRUD completo com dados geográficos.
* **Acompanhamento:** Monitoramento de status de AWB e Manifestos.
* **Mapas Interativos:** Visualização geográfica das operações (Planejamento).
* **Relatórios e Diagnósticos:** Scripts dedicados para integridade de dados.

---

© 2026 T-FlightOps. Todos os direitos reservados.

```
