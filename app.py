import streamlit as st
import pandas as pd
import os
from datetime import datetime
from pyairtable import Table

# Arquivos locais ainda usados para checklist e troca de óleo
ARQUIVO_EXCEL = "checklist_samu.xlsx"
ARQUIVO_TROCA = "troca_oleo.txt"
INTERVALO_TROCA_OLEO = 10000

# Lista de matrículas de administradores
ADMINS = ["0000", "9999"]

# ---------------- Conexão com Airtable ----------------
API_KEY = st.secrets["connections"]["airtable"]["personal_access_token"]
BASE_ID = st.secrets["connections"]["airtable"]["base_id"]
TABLE_ID = st.secrets["connections"]["airtable"]["table_id"]

table = Table(API_KEY, BASE_ID, TABLE_ID)

def carregar_usuarios():
    registros = table.all()
    return [r["fields"] for r in registros]

def salvar_usuario(usuario, senha, nome, matricula):
    table.create({
        "usuario": usuario.strip(),
        "senha": senha.strip(),
        "nome": nome.strip(),
        "matricula": matricula.strip()
    })

def autenticar(usuario, senha):
    if not usuario or not senha:
        return None
    usuarios = carregar_usuarios()
    for u in usuarios:
        if str(u.get("usuario", "")).strip() == str(usuario).strip() and str(u.get("senha", "")).strip() == str(senha).strip():
            matricula = str(u.get("matricula", "")).strip()
            u["admin"] = matricula in ADMINS
            return u
    return None

def obter_ultima_troca():
    if os.path.exists(ARQUIVO_TROCA):
        try:
            with open(ARQUIVO_TROCA, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except:
            return 0
    return 0

def salvar_ultima_troca(km):
    with open(ARQUIVO_TROCA, "w", encoding="utf-8") as f:
        f.write(str(km))

# ---------------- Interface ----------------
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulância SAMU/SOCIAL")

menu = ["Login", "Cadastro"]
escolha = st.sidebar.selectbox("Menu", menu)

if "usuario" not in st.session_state:
    st.session_state.usuario = None

# ---------------- Cadastro ----------------
if escolha == "Cadastro":
    st.subheader("📋 Cadastro de Usuário")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    nome = st.text_input("Nome completo")
    matricula = st.text_input("Matrícula")
    if st.button("Cadastrar"):
        if not usuario or not senha or not nome or not matricula:
            st.error("Preencha todos os campos!")
        else:
            usuarios = carregar_usuarios()
            if any(str(u.get("usuario", "")).strip() == usuario.strip() for u in usuarios):
                st.error("Usuário já existe!")
            else:
                salvar_usuario(usuario, senha, nome, matricula)
                st.success("Usuário cadastrado com sucesso! Vá para Login.")

# ---------------- Login ----------------
elif escolha == "Login":
    if st.session_state.usuario:
        st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

        # Administração de usuários (somente admins)
        if st.session_state.usuario.get("admin", False):
            st.sidebar.subheader("⚙️ Administração de Usuários")
            usuarios = carregar_usuarios()
            if usuarios:
                df = pd.DataFrame(usuarios)
                csv = df.to_csv(index=False).encode("utf-8")
                st.sidebar.download_button(
                    label="⬇️ Baixar usuários (Airtable)",
                    data=csv,
                    file_name="usuarios.csv",
                    mime="text/csv"
                )

        # Formulário checklist
        st.subheader("🚐 Dados da Viatura")
        placa = st.text_input("Placa da viatura")
        prefixo = st.text_input("Prefixo da viatura")
        km = st.number_input("Quilometragem atual", min_value=0, step=1)
        comb = st.radio("Nível de combustível", ["1/4", "1/2", "3/4", "Cheio"])

        st.subheader("🧯 Oxigênio")
        ox1 = st.number_input("Oxigênio Grande 1 (PSI)", min_value=0, step=1)
        ox2 = st.number_input("Oxigênio Grande 2 (PSI)", min_value=0, step=1)
        oxp = st.number_input("Oxigênio Portátil (PSI)", min_value=0, step=1)

        st.subheader("⚠️ Avarias encontradas")
        avarias = st.text_area("Descreva as avarias (se houver)", "")

        if st.button("💾 Salvar Checklist"):
            if not placa or not prefixo or km == 0:
                st.error("Preencha todos os campos obrigatórios!")
            else:
                data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
                dados = {
                    "Data": data_atual,
                    "Condutor": st.session_state.usuario["nome"],
                    "Matrícula": st.session_state.usuario["matricula"],
                    "Placa": placa,
                    "Prefixo": prefixo,
                    "Quilometragem": km,
                    "Combustível": comb,
                    "Oxigênio Grande 1": ox1,
                    "Oxigênio Grande 2": ox2,
                    "Oxigênio Portátil": oxp,
                    "Avarias": avarias if avarias else "Nenhuma"
                }

                if os.path.exists(ARQUIVO_EXCEL):
                    df_existente = pd.read_excel(ARQUIVO_EXCEL)
                    df_novo = pd.concat([df_existente, pd.DataFrame([dados])], ignore_index=True)
                else:
                    df_novo = pd.DataFrame([dados])

                df_novo.to_excel(ARQUIVO_EXCEL, index=False)
                st.success("Checklist registrado com sucesso!")

                # Aviso de troca de óleo
                ultima_troca = obter_ultima_troca()
                proxima_troca = ultima_troca + INTERVALO_TROCA_OLEO if ultima_troca > 0 else ((km // INTERVALO_TROCA_OLEO) + 1) * INTERVALO_TROCA_OLEO
                if km >= proxima_troca:
                    st.error(f"⚠️ Atenção: a viatura atingiu {km} km. Necessária troca de óleo.")
                else:
                    faltam = proxima_troca - km
                    st.info(f"⏳ Faltam {faltam} km para a próxima troca de óleo.")

        if st.button("🔧 Registrar troca de óleo (Admin)"):
            salvar_ultima_troca(km)
            st.success(f"Troca de óleo registrada em {km} km.")

        if st.button("Sair"):
            st.session_state.usuario = None
            st.rerun()

    else:
        st.subheader("🔑 Login")
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if not usuario or not senha:
                st.error("Preencha usuário e senha!")
            else:
                u = autenticar(usuario, senha)
                if u:
                    st.session_state.usuario = u
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos!")
