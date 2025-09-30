import streamlit as st
import pandas as pd
from datetime import datetime
from pyairtable import Table

# ---------------- Configuração Airtable ----------------
API_KEY = st.secrets["connections"]["airtable"]["personal_access_token"]
BASE_ID = st.secrets["connections"]["airtable"]["base_id"]

# IDs de tabelas no secrets.toml
USUARIOS_TABLE_ID = st.secrets["connections"]["airtable"]["usuarios_table_id"]
CHECKLISTS_TABLE_ID = st.secrets["connections"]["airtable"]["checklists_table_id"]
TROCAOLEO_TABLE_ID = st.secrets["connections"]["airtable"]["trocaoleo_table_id"]
VIATURAS_TABLE_ID = st.secrets["connections"]["airtable"]["viaturas_table_id"]

usuarios_table = Table(API_KEY, BASE_ID, USUARIOS_TABLE_ID)
checklists_table = Table(API_KEY, BASE_ID, CHECKLISTS_TABLE_ID)
trocaoleo_table = Table(API_KEY, BASE_ID, TROCAOLEO_TABLE_ID)
viaturas_table = Table(API_KEY, BASE_ID, VIATURAS_TABLE_ID)

# ---------------- Constantes ----------------
INTERVALO_TROCA_OLEO = 10000
OPCOES_COMBUSTIVEL = ["1/4", "1/2", "3/4", "Cheio"]
TIPOS_SERVICO = ["SAMU", "Remoção", "Van Social"]

# ---------------- Utils ----------------
def safe_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower().strip() in ["true", "1", "yes", "sim"]

# ---------------- Usuários ----------------
def carregar_usuarios():
    registros = usuarios_table.all()
    return [r.get("fields", {}) for r in registros]

def salvar_usuario(usuario, senha, nome, matricula, is_admin=False):
    usuarios_table.create({
        "usuario": usuario.strip(),
        "senha": senha.strip(),
        "nome": nome.strip(),
        "matricula": matricula.strip(),
        "is_admin": bool(is_admin),
    })

def autenticar(usuario, senha):
    usuarios = carregar_usuarios()
    for u in usuarios:
        if u.get("usuario") == usuario and u.get("senha") == senha:
            u["admin"] = safe_bool(u.get("is_admin", False))
            return u
    return None

# ---------------- Viaturas ----------------
def carregar_viaturas():
    registros = viaturas_table.all()
    return [r.get("fields", {}) for r in registros]

def salvar_viatura(placa, prefixo, status="Ativa", obs="", tipo_servico="SAMU"):
    if not placa or not prefixo:
        raise ValueError("Placa e Prefixo são obrigatórios.")
    if tipo_servico not in TIPOS_SERVICO:
        raise ValueError("Tipo de Serviço inválido.")
    viaturas_table.create({
        "Placa": placa.strip().upper(),
        "Prefixo": prefixo.strip(),
        "Status": status,
        "Observações": obs.strip() if obs else "",
        "Tipo de Serviço": tipo_servico
    })

def atualizar_status_viatura(placa, novo_status):
    registros = viaturas_table.all()
    for r in registros:
        fields = r.get("fields", {})
        if fields.get("Placa", "").upper() == placa.strip().upper():
            viaturas_table.update(r["id"], {"Status": novo_status})
            return True
    return False

# ---------------- Troca de óleo ----------------
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
    try:
        return checklists_table.create(dados, typecast=True)
    except Exception as e:
        st.error("❌ Erro ao salvar checklist")
        st.write("Dados enviados:", dados)
        st.exception(e)

# ---------------- UI ----------------
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
    # Usuário já autenticado
    if st.session_state.usuario:
        st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

        # Administração (somente admins)
        if st.session_state.usuario.get("admin", False):
            st.sidebar.subheader("⚙️ Administração")

            # Gestão de viaturas
            st.sidebar.subheader("🚐 Gestão de Viaturas")
            placa = st.sidebar.text_input("Placa")
            prefixo = st.sidebar.text_input("Prefixo")
            status = st.sidebar.selectbox("Status", ["Ativa", "Inativa"])
            tipo_servico = st.sidebar.selectbox("Tipo de Serviço", TIPOS_SERVICO)
            obs = st.sidebar.text_area("Observações")

            if st.sidebar.button("Adicionar Viatura"):
                try:
                    salvar_viatura(placa, prefixo, status, obs, tipo_servico)
                    st.sidebar.success("Viatura cadastrada!")
                except Exception as e:
                    st.sidebar.error("Erro ao cadastrar viatura")
                    st.sidebar.exception(e)

            # Lista rápida de viaturas e alteração de status
            viaturas_admin = carregar_viaturas()
            if viaturas_admin:
                df_v = pd.DataFrame(viaturas_admin)
                st.sidebar.dataframe(df_v, use_container_width=True)
                placa_status = st.sidebar.text_input("Placa para alterar status")
                novo_status = st.sidebar.selectbox("Novo status", ["Ativa", "Inativa"])
                if st.sidebar.button("Atualizar status"):
                    ok = atualizar_status_viatura(placa_status, novo_status)
                    if ok:
                        st.sidebar.success("Status atualizado!")
                    else:
                        st.sidebar.error("Viatura não encontrada pela placa.")

        # Seleção de viatura para motorista
        st.subheader("🚐 Escolha a Viatura")
        viaturas = carregar_viaturas()
        viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]

        if viaturas_ativas:
            tipos_disponiveis = sorted(set(v.get("Tipo de Serviço", "Outro") for v in viaturas_ativas))
            tipo_escolhido = st.selectbox("Selecione o tipo de serviço", tipos_disponiveis)

            viaturas_filtradas = [v for v in viaturas_ativas if v.get("Tipo de Serviço") == tipo_escolhido]

            if viaturas_filtradas:
                opcoes_viaturas = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_filtradas]
                escolha_viatura = st.selectbox("Selecione a viatura", opcoes_viaturas)
                viatura_selecionada = next(v for v in viaturas_filtradas if f"{v.get('Prefixo','')} - {v.get('Placa','')}" == escolha_viatura)
                placa = viatura_selecionada.get("Placa", "")
                prefixo = viatura_selecionada.get("Prefixo", "")
            else:
                st.warning("Nenhuma viatura ativa para esse tipo de serviço.")
                placa, prefixo = None, None
        else:
            st.error("Nenhuma viatura ativa cadastrada!")
            placa, prefixo = None, None

        # Formulário de checklist
        if placa and prefixo:
            st.subheader("🧾 Checklist da Viatura")
            km = st.number_input("Quilometragem atual", min_value=0, step=1)
            comb = st.radio("Nível de combustível", OPCOES_COMBUSTIVEL, horizontal=True)

            st.subheader("🧯 Oxigênio")
            ox1 = st.number_input("Oxigênio Grande 1 (PSI)", min_value=0, step=1)
            ox2 = st.number_input("Oxigênio Grande 2 (PSI)", min_value=0, step=1)
            oxp = st.number_input("Oxigênio Portátil (PSI)", min_value=0, step=1)

            st.subheader("⚠️ Avarias encontradas")
            avarias = st.text_area("Descreva as avarias (se houver)", "")

            if st.button("💾 Salvar Checklist"):
                if km <= 0:
                    st.error("Informe uma quilometragem válida!")
                else:
                    dados = {
                        "Data": datetime.now().isoformat(),
                        "Condutor": st.session_state.usuario["nome"],
                        "Matricula": st.session_state.usuario["matricula"],
                        "Placa": placa,
                        "Prefixo": prefixo,
                        "Quilometragem": int(km),
                        "Combustível": comb,
                        "Oxigênio Grande 1": int(ox1),
                        "Oxigênio Grande 2": int(ox2),
                        "Oxigênio Portátil": int(oxp),
                        "Avarias": avarias.strip() if avarias else "Nenhuma",
                        "Tipo de Serviço": tipo_escolhido
                    }
                    salvar_checklist(dados)
                    st.success("Checklist registrado com sucesso!")

                    # Aviso de troca de óleo
                    ultima_troca = obter_ultima_troca()
                    if ultima_troca > 0:
                        proxima_troca = ultima_troca + INTERVALO_TROCA_OLEO
                    else:
                        proxima_troca = ((int(km) // INTERVALO_TROCA_OLEO) + 1) * INTERVALO_TROCA_OLEO

                    if int(km) >= proxima_troca:
                        st.error(f"⚠️ Atenção: a viatura atingiu {int(km)} km. Necessária troca de óleo.")
                    else:
                        faltam = proxima_troca - int(km)
                        st.info(f"⏳ Faltam {faltam} km para a próxima troca de óleo.")

            # Registrar troca de óleo (somente admin)
            if st.session_state.usuario.get("admin", False):
                if st.button("🔧 Registrar troca de óleo"):
                    if km <= 0:
                        st.error("Informe uma quilometragem válida para registrar a troca!")
                    else:
                        salvar_troca_oleo(km)
                        st.success(f"Troca de óleo registrada em {int(km)} km.")

        # Sair
        if st.button("Sair"):
            st.session_state.usuario = None
            st.rerun()

    # Tela de login (quando não autenticado)
    else:
        st.subheader("🔑 Login")
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            u = autenticar(usuario, senha)
            if u:
                st.session_state.usuario = u
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos!")
