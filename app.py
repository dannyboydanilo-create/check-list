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
        "Tipo de Servico": tipo_servico   # ajuste se no Airtable estiver diferente
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
if "tela" not in st.session_state:
    st.session_state.tela = "login"

# ---------------- Cadastro ----------------
if st.session_state.tela == "cadastro":
    st.subheader("Cadastro de Usuario")
    usuario = st.text_input("Usuario")
    senha = st.text_input("Senha", type="password")
    nome = st.text_input("Nome completo")
    matricula = st.text_input("Matricula")
    is_admin = st.checkbox("Administrador?")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cadastrar"):
            if usuario and senha and nome and matricula:
                salvar_usuario(usuario, senha, nome, matricula, is_admin)
                st.success("Usuario cadastrado com sucesso!")
            else:
                st.error("Preencha todos os campos!")
    with c2:
        if st.button("Voltar para Login"):
            st.session_state.tela = "login"
            st.rerun()

# ---------------- Login ----------------
elif st.session_state.tela == "login":
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
    else:
        st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

        # Escolha de viatura
        viaturas = carregar_viaturas()
        viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]

        if viaturas_ativas:
            tipos_disponiveis = [t for t in TIPOS_SERVICO if any(v.get("Tipo de Servico") == t for v in viaturas_ativas)]
            tipo_escolhido = st.selectbox("Selecione o tipo de servico", tipos_disponiveis)

            viaturas_filtradas = [v for v in viaturas_ativas if v.get("Tipo de Servico") == tipo_escolhido]
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
                        "Tipo de Servico": tipo_escolhido
                    }
                    salvar_checklist(dados)
                    st.success("Checklist registrado com sucesso!")

                    ultima_troca = obter_ultima_troca()
                    proxima_troca = ultima_troca + INTERVALO_TROCA_OLEO if ultima_troca else ((int(km)//INTERVALO_TROCA_OLEO)+1)*INTERVALO_TROCA_OLEO
                    if int(km) >= proxima_troca:
                        st.error(f"Atenção: a viatura atingiu {int(km)} km. Necessaria troca de oleo.")
                    else:
                        st.info(f"Faltam {proxima_troca-int(km)} km para a proxima troca de oleo.")

        if st.button("Sair"):
            st.session_state.usuario = None
            st.rerun()
