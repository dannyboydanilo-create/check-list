import streamlit as st
import pandas as pd
from datetime import datetime
from pyairtable import Table

# ====================== Configuracao Airtable ======================
API_KEY = st.secrets["connections"]["airtable"]["personal_access_token"]
BASE_ID = st.secrets["connections"]["airtable"]["base_id"]

USUARIOS_TABLE_ID   = st.secrets["connections"]["airtable"]["usuarios_table_id"]
CHECKLISTS_TABLE_ID = st.secrets["connections"]["airtable"]["checklists_table_id"]
TROCAOLEO_TABLE_ID  = st.secrets["connections"]["airtable"]["trocaoleo_table_id"]
VIATURAS_TABLE_ID   = st.secrets["connections"]["airtable"]["viaturas_table_id"]

usuarios_table   = Table(API_KEY, BASE_ID, USUARIOS_TABLE_ID)
checklists_table = Table(API_KEY, BASE_ID, CHECKLISTS_TABLE_ID)
trocaoleo_table  = Table(API_KEY, BASE_ID, TROCAOLEO_TABLE_ID)
viaturas_table   = Table(API_KEY, BASE_ID, VIATURAS_TABLE_ID)

# ====================== Mapeamento de campos ======================
# Ajuste estes nomes para corresponder exatamente às colunas do seu Airtable
VIATURAS_FIELDS = {
    "placa":        "Placa",
    "prefixo":      "Prefixo",
    "status":       "Status",
    "observacoes":  "Observacoes",      # troque para "Observações" se for o caso
    "tipo_servico": "Tipo de Servico"   # troque para "Tipo de Serviço" se for o caso
}

CHECKLIST_FIELDS = {
    "data":               "Data",
    "condutor":           "Condutor",
    "matricula":          "Matricula",
    "placa":              "Placa",
    "prefixo":            "Prefixo",
    "quilometragem":      "Quilometragem",
    "combustivel":        "Combustivel",
    "oxigenio_grande_1":  "OxigenioGrande1",
    "oxigenio_grande_2":  "OxigenioGrande2",
    "oxigenio_portatil":  "OxigenioPortatil",
    "avarias":            "Avarias",
    "tipo_servico":       "Tipo de Servico"
}

TROCAOLEO_FIELDS = {
    "km":   "km",
    "data": "data"
}

USUARIOS_FIELDS = {
    "usuario":   "usuario",
    "senha":     "senha",
    "nome":      "nome",
    "matricula": "matricula",
    "is_admin":  "is_admin"
}

# ====================== Constantes ======================
INTERVALO_TROCA_OLEO = 10000
OPCOES_COMBUSTIVEL   = ["1/4", "1/2", "3/4", "Cheio"]
TIPOS_SERVICO        = ["SAMU", "Remocao", "Van Social"]

# ====================== Utils ======================
def safe_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower().strip() in ["true", "1", "yes", "sim"]

# ====================== Usuarios ======================
def carregar_usuarios():
    registros = usuarios_table.all()
    return [r.get("fields", {}) for r in registros]

def salvar_usuario(usuario, senha, nome, matricula, is_admin=False):
    usuarios_table.create({
        USUARIOS_FIELDS["usuario"]:   usuario.strip(),
        USUARIOS_FIELDS["senha"]:     senha.strip(),
        USUARIOS_FIELDS["nome"]:      nome.strip(),
        USUARIOS_FIELDS["matricula"]: matricula.strip(),
        USUARIOS_FIELDS["is_admin"]:  bool(is_admin),
    })

def autenticar(usuario, senha):
    for u in carregar_usuarios():
        if u.get(USUARIOS_FIELDS["usuario"]) == usuario and u.get(USUARIOS_FIELDS["senha"]) == senha:
            return {
                "nome":      u.get(USUARIOS_FIELDS["nome"]),
                "matricula": u.get(USUARIOS_FIELDS["matricula"]),
                "admin":     safe_bool(u.get(USUARIOS_FIELDS["is_admin"], False)),
            }
    return None

# ====================== Viaturas ======================
def carregar_viaturas():
    registros = viaturas_table.all()
    return [r.get("fields", {}) for r in registros]

def salvar_viatura(placa, prefixo, status="Ativa", obs="", tipo_servico="SAMU"):
    viaturas_table.create({
        VIATURAS_FIELDS["placa"]:        placa.strip().upper(),
        VIATURAS_FIELDS["prefixo"]:      prefixo.strip(),
        VIATURAS_FIELDS["status"]:       status,
        VIATURAS_FIELDS["observacoes"]:  (obs.strip() if obs else ""),
        VIATURAS_FIELDS["tipo_servico"]: tipo_servico
    })

def atualizar_status_viatura(placa, novo_status):
    registros = viaturas_table.all()
    for r in registros:
        fields = r.get("fields", {})
        if fields.get(VIATURAS_FIELDS["placa"], "").upper() == (placa or "").strip().upper():
            viaturas_table.update(r["id"], {VIATURAS_FIELDS["status"]: novo_status})
            return True
    return False

# ====================== Troca de oleo ======================
def obter_ultima_troca():
    registros = trocaoleo_table.all(sort=[f'-{TROCAOLEO_FIELDS["data"]}'])
    if registros:
        return int(registros[0]["fields"].get(TROCAOLEO_FIELDS["km"], 0))
    return 0

def salvar_troca_oleo(km):
    trocaoleo_table.create({
        TROCAOLEO_FIELDS["km"]:   int(km),
        TROCAOLEO_FIELDS["data"]: datetime.now().isoformat(),
    })

# ====================== Checklist ======================
def salvar_checklist(dados):
    try:
        return checklists_table.create(dados, typecast=True)
    except Exception as e:
        st.error("Erro ao salvar checklist")
        st.write("Dados enviados:", dados)
        st.exception(e)

# ====================== UI ======================
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulancia SAMU/SOCIAL")

if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "tela" not in st.session_state:
    st.session_state.tela = "login"

# ====================== Tela de cadastro ======================
if st.session_state.tela == "cadastro":
    st.subheader("Cadastro de Usuario")
    usuario = st.text_input("Usuario")
    senha = st.text_input("Senha", type="password")
    nome = st.text_input("Nome completo")
    matricula = st.text_input("Matricula")
    is_admin = st.checkbox("Administrador?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cadastrar"):
            if not usuario or not senha or not nome or not matricula:
                st.error("Preencha todos os campos!")
            else:
                usuarios = carregar_usuarios()
                if any(u.get(USUARIOS_FIELDS["usuario"]) == usuario for u in usuarios):
                    st.error("Usuario ja existe!")
                else:
                    salvar_usuario(usuario, senha, nome, matricula, is_admin)
                    st.success("Usuario cadastrado com sucesso!")
    with col2:
        if st.button("Voltar para Login"):
            st.session_state.tela = "login"
            st.rerun()

# ====================== Tela de login / app ======================
elif st.session_state.tela == "login":
    # Se NAO autenticado: mostra login
    if not st.session_state.usuario:
        st.subheader("Login")
        usuario = st.text_input("Usuario")
        senha = st.text_input("Senha", type="password")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Entrar"):
                u = autenticar(usuario, senha)
                if u:
                    st.session_state.usuario = u
                    st.rerun()
                else:
                    st.error("Usuario ou senha incorretos!")
        with c2:
            if st.button("Cadastrar"):
                st.session_state.tela = "cadastro"
                st.rerun()

    # Se autenticado: mostra app
    else:
        st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

        # Administração (somente admins)
        if st.session_state.usuario.get("admin", False):
            st.sidebar.subheader("Administracao")
            st.sidebar.subheader("Gestao de Viaturas")
            placa = st.sidebar.text_input("Placa")
            prefixo = st.sidebar.text_input("Prefixo")
