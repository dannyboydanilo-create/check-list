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
TIPOS_SERVICO        = ["SAMU", "Remocao", "Van Social", "Van Hemodialise"]

# ---------------- Usuarios ----------------
def carregar_usuarios():
    try:
        return [r.get("fields", {}) for r in usuarios_table.all()]
    except Exception as e:
        st.error(f"Erro ao carregar usuarios: {e}")
        return []

def salvar_usuario(usuario, senha, nome, matricula, is_admin=False):
    try:
        usuarios_table.create({
            "usuario": usuario.strip(),
            "senha": senha.strip(),
            "nome": nome.strip(),
            "matricula": matricula.strip(),
            "is_admin": bool(is_admin),
        })
    except Exception as e:
        st.error(f"Erro ao salvar usuario: {e}")

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
    try:
        return [r.get("fields", {}) for r in viaturas_table.all()]
    except Exception as e:
        st.error(f"Erro ao carregar viaturas: {e}")
        return []

def salvar_viatura(placa, prefixo, status="Ativa", obs="", tipo_servico="SAMU"):
    if not placa or not prefixo:
        st.sidebar.error("Placa e Prefixo sao obrigatorios.")
        return
    if tipo_servico not in TIPOS_SERVICO:
        st.sidebar.error("Tipo de Servico invalido.")
        return
    try:
        viaturas_table.create({
            "Placa": placa.strip().upper(),
            "Prefixo": prefixo.strip(),
            "Status": status,
            "Observacoes": obs.strip() if obs else "",
            "TipoServico": tipo_servico
        })
        st.sidebar.success("Viatura cadastrada!")
    except Exception as e:
        st.sidebar.error(f"Erro ao cadastrar viatura: {e}")

def atualizar_status_viatura(placa, novo_status):
    try:
        registros = viaturas_table.all()
        for r in registros:
            fields = r.get("fields", {})
            if fields.get("Placa", "").upper() == (placa or "").strip().upper():
                viaturas_table.update(r["id"], {"Status": novo_status})
                return True
        return False
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")
        return False

# ---------------- Troca de oleo ----------------
def obter_ultima_troca():
    try:
        registros = trocaoleo_table.all(sort=["-data"])
        if registros:
            return int(registros[0]["fields"].get("km", 0))
        return 0
    except Exception as e:
        st.error(f"Erro ao obter ultima troca de oleo: {e}")
        return 0

def salvar_troca_oleo(km):
    try:
        trocaoleo_table.create({
            "km": int(km),
            "data": datetime.now().isoformat(),
        })
        st.success(f"Troca de oleo registrada em {int(km)} km.")
    except Exception as e:
        st.error(f"Erro ao salvar troca de oleo: {e}")

# ---------------- Checklist ----------------
def salvar_checklist(dados):
    try:
        checklists_table.create(dados, typecast=True)
    except Exception as e:
        st.error(f"Erro ao salvar checklist: {e}")

# ---------------- UI ----------------
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulancia SAMU/SOCIAL")

# Estado
if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "tela" not in st.session_state:
    st.session_state.tela = "login"

# ---------------- Tela de Login ----------------
if st.session_state.tela == "login" and not st.session_state.usuario:
    st.subheader("Login")

    usuario = st.text_input("Usuario")
    senha = st.text_input("Senha", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Entrar"):
            u = autenticar(usuario, senha)
            if u:
                st.session_state.usuario = u
                st.rerun()
            else:
                st.error("Usuario ou senha incorretos!")
    with col2:
        if st.button("Cadastro"):
            st.session_state.tela = "cadastro"
            st.rerun()

# ---------------- Tela de Cadastro ----------------
elif st.session_state.tela == "cadastro" and not st.session_state.usuario:
    st.subheader("Cadastro de Usuario")
    novo_user = st.text_input("Novo usuario")
    nova_senha = st.text_input("Nova senha", type="password")
    nome = st.text_input("Nome completo")
    matricula = st.text_input("Matricula")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cadastrar"):
            if novo_user and nova_senha and nome and matricula:
                # cadastra sempre como usuario comum
                salvar_usuario(novo_user, nova_senha, nome, matricula, False)
                st.success("Usuario cadastrado com sucesso! Clique em Voltar para Login.")
            else:
                st.error("Preencha todos os campos!")
    with c2:
        if st.button("Voltar para Login"):
            st.session_state.tela = "login"
            st.rerun()

# ---------------- Tela Principal ----------------
elif st.session_state.usuario:
    st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

    # Administracao (somente admin)
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

        st.sidebar.markdown("---")
        viaturas_admin = carregar_viaturas()
        if viaturas_admin:
            st.sidebar.markdown("### Viaturas cadastradas")
            st.sidebar.dataframe(pd.DataFrame(viaturas_admin), use_container_width=True)
        placa_status = st.sidebar.text_input("Placa para alterar status")
        novo_status = st.sidebar.selectbox("Novo status", ["Ativa", "Inativa"])
        if st.sidebar.button("Atualizar status"):
            ok = atualizar_status_viatura(placa_status, novo_status)
            if ok:
                st.sidebar.success("Status atualizado!")
            else:
                st.sidebar.error("Viatura nao encontrada pela placa.")

    # Escolha de viatura (tipo primeiro, depois viatura)
    st.subheader("Escolha a Viatura")
    viaturas = carregar_viaturas()
    viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]

    placa, prefixo, tipo_escolhido = None, None, None
    if viaturas_ativas:
        tipos_disponiveis = [
            t for t in TIPOS_SERVICO
            if any(v.get("TipoServico") == t for v in viaturas_ativas)
        ]
        tipo_escolhido = st.selectbox("Selecione o tipo de servico", ["-- Selecione --"] + tipos_disponiveis)

        if tipo_escolhido and tipo_escolhido != "-- Selecione --":
            viaturas_filtradas = [v for v in viaturas_ativas if v.get("TipoServico") == tipo_escolhido]
            if viaturas_filtradas:
                opcoes = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_filtradas]
                escolha = st.selectbox("Selecione a viatura", opcoes)
                viatura = next(
                    v for v in viaturas_filtradas
                    if f"{v.get('Prefixo','')} - {v.get('Placa','')}" == escolha
                )
                placa = viatura.get("Placa")
                prefixo = viatura.get("Prefixo")
            else:
                st.warning("Nenhuma viatura ativa para esse tipo de servico.")
    else:
        st.info("Cadastre viaturas ativas para continuar.")

    # Checklist
    if placa and prefixo and tipo_escolhido and tipo_escolhido != "-- Selecione --":
        st.subheader("Checklist da Viatura")
        km = st.number_input("Quilometragem atual", min_value=0, step=1)
        comb = st.radio("Nivel de combustivel", OPCOES_COMBUSTIVEL, horizontal=True)

        st.markdown("#### Oxigenio")
        ox1 = st.number_input("Oxigenio Grande 1 (PSI)", min_value=0, step=1)
        ox2 = st.number_input("Oxigenio Grande 2 (PSI)", min_value=0, step=1)
        oxp = st.number_input("Oxigenio Portatil (PSI)", min_value=0, step=1)

        st.markdown("#### Pneus")
        pneu_dd = st.selectbox("Pneu dianteiro direito", ["Ruim", "Bom", "Otimo"])
        pneu_de = st.selectbox("Pneu dianteiro esquerdo", ["Ruim", "Bom", "Otimo"])
        pneu_td = st.selectbox("Pneu traseiro direito", ["Ruim", "Bom", "Otimo"])
        pneu_te = st.selectbox("Pneu traseiro esquerdo", ["Ruim", "Bom", "Otimo"])

        if st.button("Salvar Checklist"):
            if km <= 0:
                st.error("Informe uma quilometragem valida!")
            else:
                dados = {
                    "Data": datetime.now().isoformat(),
                    "Condutor": st.session_state.usuario["nome"],
                    "Matricula": st.session_state.usuario["matricula"],
                    "Placa": placa,
                    "Prefixo": prefixo,
                    "Quilometragem": int(km),
                    "Combustivel": comb,
                    "Oxigenio Grande 1": int(ox1),
                    "Oxigenio Grande 2": int(ox2),
                    "Oxigenio Portatil": int(oxp),
                    "pneu_dianteiro_direito": pneu_dd,
                    "pneu_dianteiro_esquerdo": pneu_de,
                    "pneu_traseiro_direito": pneu_td,
                    "pneu_traseiro_esquerdo": pneu_te,
                    "TipoServico": tipo_escolhido
                }
                salvar_checklist(dados)
                st.success("Checklist registrado com sucesso!")

                # Aviso de troca de oleo
                ultima_troca = obter_ultima_troca()
                proxima_troca = (ultima_troca + INTERVALO_TROCA_OLEO) if ultima_troca > 0 else (
                    ((int(km) // INTERVALO_TROCA_OLEO) + 1) * INTERVALO_TROCA_OLEO
                )
                if int(km) >= proxima_troca:
                    st.error(f"Atenção: a viatura atingiu {int(km)} km. Necessaria troca de oleo.")
                else:
                    faltam = proxima_troca - int(km)
                    st.info(f"Faltam {faltam} km para a proxima troca de oleo.")

        # Registrar troca de oleo (somente admin)
        if st.session_state.usuario.get("admin", False):
            if st.button("Registrar troca de oleo"):
                if km <= 0:
                    st.error("Informe uma quilometragem valida para registrar a troca!")
                else:
                    salvar_troca_oleo(km)

    # Sair
    if st.button("Sair"):
        st.session_state.usuario = None
        st.session_state.tela = "login"
        st.rerun()

