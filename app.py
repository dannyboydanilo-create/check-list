import streamlit as st
import pandas as pd
from datetime import datetime
from pyairtable import Table

# ---------------- Configuracao Airtable ----------------
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

# ---------------- Constantes ----------------
INTERVALO_TROCA_OLEO = 10000
OPCOES_COMBUSTIVEL   = ["1/4", "1/2", "3/4", "Cheio"]
TIPOS_SERVICO        = ["SAMU", "Remocao", "Van Social"]

# ---------------- Usuarios ----------------
def carregar_usuarios():
    return [r.get("fields", {}) for r in usuarios_table.all()]

def salvar_usuario(usuario, senha, nome, matricula, is_admin=False):
    usuarios_table.create({
        "usuario": usuario.strip(),
        "senha": senha.strip(),
        "nome": nome.strip(),
        "matricula": matricula.strip(),
        "is_admin": bool(is_admin),
    })

def autenticar(usuario, senha):
    for u in carregar_usuarios():
        if u.get("usuario") == usuario and u.get("senha") == senha:
            return {
                "nome": u.get("nome"),
                "matricula": u.get("matricula"),
                "admin": bool(u.get("is_admin", False))
            }
    return None

# ---------------- Viaturas ----------------
def carregar_viaturas():
    return [r.get("fields", {}) for r in viaturas_table.all()]

def salvar_viatura(placa, prefixo, status="Ativa", obs="", tipo_servico="SAMU"):
    viaturas_table.create({
        "Placa": placa.strip().upper(),
        "Prefixo": prefixo.strip(),
        "Status": status,
        "Observacoes": obs.strip() if obs else "",
        "TipoServico": tipo_servico   # sem acento
    })

# ---------------- Troca de oleo ----------------
def obter_ultima_troca():
    registros = trocaoleo_table.all(sort=["-data"])
    if registros:
        return int(registros[0]["fields"].get("km", 0))
    return 0

def salvar_troca_oleo(km):
    trocaoleo_table.create({
        "km": int(km),
        "data": datetime.now().isoformat(),
    })

# ---------------- Checklist ----------------
def salvar_checklist(dados):
    checklists_table.create(dados, typecast=True)

# ---------------- UI ----------------
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulancia SAMU/SOCIAL")

if "usuario" not in st.session_state:
    st.session_state.usuario = None

# ---------------- Login + Cadastro na mesma tela ----------------
if not st.session_state.usuario:
    st.subheader("Acesso ao Sistema")

    col1, col2 = st.columns(2)

    # ---- Login ----
    with col1:
        st.markdown("### Login")
        usuario = st.text_input("Usuario", key="login_user")
        senha = st.text_input("Senha", type="password", key="login_pass")
        if st.button("Entrar"):
            u = autenticar(usuario, senha)
            if u:
                st.session_state.usuario = u
                st.rerun()
            else:
                st.error("Usuario ou senha incorretos!")

    # ---- Cadastro ----
    with col2:
        st.markdown("### Cadastro")
        novo_user = st.text_input("Novo usuario", key="cad_user")
        nova_senha = st.text_input("Nova senha", type="password", key="cad_pass")
        nome = st.text_input("Nome completo", key="cad_nome")
        matricula = st.text_input("Matricula", key="cad_mat")
        is_admin = st.checkbox("Administrador?", key="cad_admin")
        if st.button("Cadastrar"):
            if novo_user and nova_senha and nome and matricula:
                salvar_usuario(novo_user, nova_senha, nome, matricula, is_admin)
                st.success("Usuario cadastrado com sucesso! Faça login ao lado.")
            else:
                st.error("Preencha todos os campos!")
else:
    # ---------------- Tela principal ----------------
    st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

    # Administração (somente admins)
    if st.session_state.usuario.get("admin", False):
        st.sidebar.subheader("Administracao")
        st.sidebar.subheader("Gestao de Viaturas")
        placa = st.sidebar.text_input("Placa")
        prefixo = st.sidebar.text_input("Prefixo")
        status = st.sidebar.selectbox("Status", ["Ativa", "Inativa"])
        tipo_servico = st.sidebar.selectbox("Tipo de Servico", TIPOS_SERVICO)
        obs = st.sidebar.text_area("Observacoes")

        if st.sidebar.button("Adicionar Viatura"):
            salvar_viatura(placa, prefixo, status, obs, tipo_servico)
            st.sidebar.success("Viatura cadastrada!")

    # Escolha de viatura
    viaturas = carregar_viaturas()
    viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]

    if viaturas_ativas:
        tipos_disponiveis = [t for t in TIPOS_SERVICO if any(v.get("TipoServico") == t for v in viaturas_ativas)]
        tipo_escolhido = st.selectbox("Selecione o tipo de servico", tipos_disponiveis)

        viaturas_filtradas = [v for v in viaturas_ativas if v.get("TipoServico") == tipo_escolhido]
        if viaturas_filtradas:
            opcoes = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_filtradas]
            escolha = st.selectbox("Selecione a viatura", opcoes)
            viatura = next(v for v in viaturas_filtradas if f"{v.get('Prefixo','')} - {v.get('Placa','')}" == escolha)
            placa = viatura.get("Placa")
            prefixo = viatura.get("Prefixo")

            # Checklist
            st.subheader("Checklist da Viatura")
            km = st.number_input("Quilometragem atual", min_value=0, step=1)
            comb = st.radio("Nivel de combustivel", OPCOES_COMBUSTIVEL, horizontal=True)
            ox1 = st.number_input("Oxigenio Grande 1 (PSI)", min_value=0, step=1)
            ox2 = st.number_input("Oxigenio Grande 2 (PSI)", min_value=0, step=1)
            oxp = st.number_input("Oxigenio Portatil (PSI)", min_value=0, step=1)
            avarias = st.text_area("Avarias encontradas", "")

            if st.button("Salvar Checklist"):
                dados = {
                    "Data": datetime.now().isoformat(),
                    "Condutor": st.session_state.usuario["nome"],
                    "Matricula": st.session_state.usuario["matricula"],
                    "Placa": placa,
                    "Prefixo": prefixo,
                    "Quilometragem": int(km),
                    "Combustivel": comb,
                    "OxigenioGrande1": int(ox1),
                    "OxigenioGrande2": int(ox2),
                    "OxigenioPortatil": int(oxp),
                    "Avarias": avarias if avarias else "Nenhuma",
                    "TipoServico": tipo_escolhido
                }
                salvar_checklist(dados)
                st.success("Checklist registrado com sucesso!")

                ultima_troca = obter_ultima_troca()
                proxima_troca = ultima_troca + INTERVALO_TROCA_OLEO if ultima_troca else ((int(km)//INTERVALO_TROCA_OLEO)+1)*INTERVALO_TROCA_OLEO
                if int(km) >= proxima_troca:
                    st.error(f"Atenção: a viatura atingiu {int(km)} km. Necessaria troca de oleo.")
                else:
                   
