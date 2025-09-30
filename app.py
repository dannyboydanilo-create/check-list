import streamlit as st
import pandas as pd
from datetime import datetime
from pyairtable import Table

# ---------------- Conexões com Airtable ----------------
API_KEY = st.secrets["connections"]["airtable"]["personal_access_token"]
BASE_ID = st.secrets["connections"]["airtable"]["base_id"]

usuarios_table = Table(API_KEY, BASE_ID, st.secrets["connections"]["airtable"]["usuarios_table_id"])
checklists_table = Table(API_KEY, BASE_ID, st.secrets["connections"]["airtable"]["checklists_table_id"])
trocaoleo_table = Table(API_KEY, BASE_ID, st.secrets["connections"]["airtable"]["trocaoleo_table_id"])
viaturas_table = Table(API_KEY, BASE_ID, st.secrets["connections"]["airtable"]["viaturas_table_id"])

INTERVALO_TROCA_OLEO = 10000

# ---------------- Funções Usuários ----------------
def carregar_usuarios():
    registros = usuarios_table.all()
    return [r["fields"] for r in registros]

def salvar_usuario(usuario, senha, nome, matricula, is_admin=False):
    usuarios_table.create({
        "usuario": usuario.strip(),
        "senha": senha.strip(),
        "nome": nome.strip(),
        "matricula": matricula.strip(),
        "is_admin": is_admin
    })

def autenticar(usuario, senha):
    usuarios = carregar_usuarios()
    for u in usuarios:
        if u.get("usuario") == usuario and u.get("senha") == senha:
            valor_admin = str(u.get("is_admin", "")).lower()
            u["admin"] = valor_admin in ["true", "1", "yes", "sim"]
            return u
    return None

# ---------------- Funções Viaturas ----------------
def carregar_viaturas():
    registros = viaturas_table.all()
    return [r["fields"] for r in registros]

def salvar_viatura(placa, prefixo, status="Ativa", obs=""):
    viaturas_table.create({
        "Placa": placa.strip(),
        "Prefixo": prefixo.strip(),
        "Status": status,
        "Observações": obs
    })

# ---------------- Funções Checklist ----------------
def salvar_checklist(dados):
    try:
        return checklists_table.create(dados, typecast=True)
    except Exception as e:
        st.error("❌ Erro ao salvar checklist")
        st.write("Dados enviados:", dados)
        st.exception(e)

def obter_ultima_troca():
    registros = trocaoleo_table.all(sort=["-data"])
    if registros:
        return int(registros[0]["fields"].get("km", 0))
    return 0

def salvar_troca_oleo(km):
    trocaoleo_table.create({
        "km": km,
        "data": datetime.now().isoformat()
    })

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
    is_admin = st.checkbox("Administrador?")
    if st.button("Cadastrar"):
        if not usuario or not senha or not nome or not matricula:
            st.error("Preencha todos os campos!")
        else:
            usuarios = carregar_usuarios()
            if any(u.get("usuario") == usuario for u in usuarios):
                st.error("Usuário já existe!")
            else:
                salvar_usuario(usuario, senha, nome, matricula, is_admin)
                st.success("Usuário cadastrado com sucesso! Vá para Login.")

# ---------------- Login ----------------
elif escolha == "Login":
    if st.session_state.usuario:
        st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

        # Administração de usuários e viaturas (somente admins)
        if st.session_state.usuario.get("admin", False):
            st.sidebar.subheader("⚙️ Administração")
            
            # Usuários
            usuarios = carregar_usuarios()
            if usuarios:
                df = pd.DataFrame(usuarios)
                csv = df.to_csv(index=False).encode("utf-8")
                st.sidebar.download_button(
                    label="⬇️ Baixar usuários",
                    data=csv,
                    file_name="usuarios.csv",
                    mime="text/csv"
                )

            # Viaturas
            st.sidebar.subheader("🚐 Gestão de Viaturas")
            placa = st.sidebar.text_input("Placa")
            prefixo = st.sidebar.text_input("Prefixo")
            status = st.sidebar.selectbox("Status", ["Ativa", "Inativa"])
            obs = st.sidebar.text_area("Observações")
            if st.sidebar.button("Adicionar Viatura"):
                salvar_viatura(placa, prefixo, status, obs)
                st.sidebar.success("Viatura cadastrada!")

        # Formulário checklist
        st.subheader("🚐 Escolha a Viatura")
        viaturas = carregar_viaturas()
        viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]

        if viaturas_ativas:
            escolha = st.selectbox("Selecione a viatura", [f"{v['Prefixo']} - {v['Placa']}" for v in viaturas_ativas])
            viatura_selecionada = next(v for v in viaturas_ativas if f"{v['Prefixo']} - {v['Placa']}" == escolha)
            placa = viatura_selecionada["Placa"]
            prefixo = viatura_selecionada["Prefixo"]
        else:
            st.error("Nenhuma viatura ativa cadastrada!")
            placa, prefixo = None, None

        if placa and prefixo:
            st.subheader("🚐 Dados da Viatura")
            km = st.number_input("Quilometragem atual", min_value=0, step=1)
            comb = st.radio("Nível de combustível", ["1/4", "1/2", "3/4", "Cheio"])

            st.subheader("🧯 Oxigênio")
            ox1 = st.number_input("Oxigênio Grande 1 (PSI)", min_value=0, step=1)
            ox2 = st.number_input("Oxigênio Grande 2 (PSI)", min_value=0, step=1)
            oxp = st.number_input("Oxigênio Portátil (PSI)", min_value=0, step=1)

            st.subheader("⚠️ Avarias encontradas")
            avarias = st.text_area("Descreva as avarias (se houver)", "")

            if st.button("💾 Salvar Checklist"):
                if km == 0:
                    st.error("Preencha a quilometragem!")
                else:
                    dados = {
                        "Data": datetime.now().isoformat(),
                        "Condutor": st.session_state.usuario["nome"],
                        "Matricula": st.session_state.usuario["matricula"],
                        "Placa": placa,
                        "Prefixo": prefixo,
                        "Quilometragem": km,
                        "Combustível": comb,
                        "Oxigênio Grande 1": ox1,
                        "Oxigênio Grande 2": ox2,
                        "Oxigênio Portátil": oxp,
                        "Avarias": avarias if avarias else "Nenhuma"
                    }
                    salvar_checklist(dados)
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
                salvar_troca_oleo(km)
                st.success(f"Troca de óleo registrada em {km} km.")

        if st.button("Sair"):
            st.session_state.usuario = None
            st.rerun
