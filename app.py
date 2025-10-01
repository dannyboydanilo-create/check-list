import streamlit as st
import pandas as pd
from datetime import datetime
from pyairtable import Table

# ---------------- Configuração Airtable ----------------
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
TOLERANCIA_ALERTA    = 500
OPCOES_COMBUSTIVEL   = ["1/4", "1/2", "3/4", "Cheio"]
TIPOS_SERVICO        = ["SAMU", "Remocao", "Van Social", "Van Hemodialise"]

# ---------------- Usuários ----------------
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
    if not placa or not prefixo:
        st.sidebar.error("Placa e Prefixo são obrigatórios.")
        return
    viaturas_table.create({
        "Placa": placa.strip().upper(),
        "Prefixo": prefixo.strip(),
        "Status": status,
        "Observacoes": obs.strip() if obs else "",
        "TipoServico": tipo_servico
    })
    st.sidebar.success("Viatura cadastrada!")

# ---------------- Troca de óleo ----------------
def obter_ultima_troca(placa):
    registros = trocaoleo_table.all(sort=["-data"])
    for r in registros:
        f = r.get("fields", {})
        if f.get("Placa") == placa:
            try:
                return int(f.get("km", 0))
            except Exception:
                return 0
    return 0

def salvar_troca_oleo(placa, prefixo, km):
    trocaoleo_table.create({
        "Placa": placa,
        "Prefixo": prefixo,
        "km": int(km),
        "data": datetime.now().isoformat(),
    })
    st.success(f"Troca de óleo registrada para {placa} em {int(km)} km.")

def carregar_trocas():
    registros = trocaoleo_table.all(sort=["-data"])
    return [r.get("fields", {}) for r in registros]

# ---------------- Checklist helpers ----------------
def salvar_checklist(dados):
    checklists_table.create(dados, typecast=True)

def obter_ultimo_km(placa):
    registros = checklists_table.all(sort=["-Data"])
    for r in registros:
        f = r.get("fields", {})
        if f.get("Placa") == placa:
            try:
                return int(f.get("Quilometragem", 0))
            except Exception:
                return 0
    return 0

def mostrar_alerta_troca(placa, km_atual):
    ultima_troca_admin = obter_ultima_troca(placa)
    if ultima_troca_admin > 0:
        proxima_troca = ultima_troca_admin + INTERVALO_TROCA_OLEO
        contexto = f"Última troca: {ultima_troca_admin} km | Próxima: {proxima_troca} km."
    else:
        proxima_troca = ((km_atual // INTERVALO_TROCA_OLEO) + 1) * INTERVALO_TROCA_OLEO
        contexto = f"Primeira troca prevista: {proxima_troca} km."

    if km_atual < proxima_troca - TOLERANCIA_ALERTA:
        faltam = proxima_troca - km_atual
        st.info(f"ℹ️ Faltam {faltam} km para a troca de óleo. {contexto}")
    elif proxima_troca - TOLERANCIA_ALERTA <= km_atual <= proxima_troca + TOLERANCIA_ALERTA:
        st.warning(f"⚠️ {placa} está na FAIXA DE TROCA! Atual: {km_atual} km | {contexto}")
    else:
        st.error(f"🚨 URGENTE: {placa} já passou da troca! Prevista: {proxima_troca} km | Atual: {km_atual} km.")

# ---------------- UI ----------------
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulância SAMU/SOCIAL")

if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "tela" not in st.session_state:
    st.session_state.tela = "login"

# ---------------- Tela de Login ----------------
if st.session_state.tela == "login" and not st.session_state.usuario:
    st.subheader("Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Entrar"):
            u = autenticar(usuario, senha)
            if u:
                st.session_state.usuario = u
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos!")
    with c2:
        if st.button("Cadastro"):
            st.session_state.tela = "cadastro"
            st.rerun()

# ---------------- Tela de Cadastro ----------------
elif st.session_state.tela == "cadastro" and not st.session_state.usuario:
    st.subheader("Cadastro de Usuário")
    novo_user = st.text_input("Novo usuário")
    nova_senha = st.text_input("Nova senha", type="password")
    nome = st.text_input("Nome completo")
    matricula = st.text_input("Matrícula")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cadastrar"):
            if novo_user and nova_senha and nome and matricula:
                salvar_usuario(novo_user, nova_senha, nome, matricula, False)
                st.success("Usuário cadastrado! Clique em Voltar para Login.")
            else:
                st.error("Preencha todos os campos!")
    with c2:
        if st.button("Voltar para Login"):
            st.session_state.tela = "login"
            st.rerun()

# ---------------- Tela Principal ----------------
elif st.session_state.usuario:
    st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

    # Admin: gestão de viaturas e histórico de trocas
    if st.session_state.usuario.get("admin", False):
        st.sidebar.subheader("Gestão de Viaturas")
        placa_admin = st.sidebar.text_input("Placa")
        prefixo_admin = st.sidebar.text_input("Prefixo")
        status_admin = st.sidebar.selectbox("Status", ["Ativa", "Inativa"])
        tipo_servico_admin = st.sidebar.selectbox("Tipo de Serviço", TIPOS_SERVICO)
        obs_admin = st.sidebar.text_area("Observações")
        if st.sidebar.button("Adicionar Viatura"):
            salvar_viatura(placa_admin, prefixo_admin, status_admin, obs_admin, tipo_servico_admin)

        st.sidebar.markdown("---")
        st.sidebar.subheader("Histórico de Trocas de Óleo")
        trocas = carregar_trocas()
        if trocas:
            st.sidebar.dataframe(pd.DataFrame(trocas), use_container_width=True)
        else:
            st.sidebar.info("Nenhuma troca registrada ainda.")

    # Escolha de viatura
    st.subheader("Escolha a viatura")
    viaturas = carregar_viaturas()
    viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]

    placa, prefixo, tipo_escolhido = None, None, None
    if viaturas_ativas:
        tipos_disponiveis = [t for t in TIPOS_SERVICO if any(v.get("TipoServico") == t for v in viaturas_ativas)]
        tipo_escolhido = st.selectbox("Tipo de serviço", ["-- Selecione --"] + tipos_disponiveis)
        if tipo_escolhido and tipo_escolhido != "-- Selecione --":
            viaturas_filtradas = [v for v in viaturas_ativas if v.get("TipoServico") == tipo_escolhido]
            if viaturas_filtradas:
                opcoes = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_filtradas]
                escolha = st.selectbox("Viatura", opcoes)
                viatura = next((v for v in viaturas_filtradas if f"{v.get('Prefixo','')} - {v.get('Placa','')}" == escolha), None)
                if viatura:
                    placa = viatura.get("Placa")
                    prefixo = viatura.get("Prefixo")
            else:
                st.warning("Nenhuma viatura ativa para esse tipo de serviço.")
    else:
        st.info("Cadastre viaturas ativas para continuar.")

    # Checklist com layout mobile-friendly
    if placa and prefixo and tipo_escolhido and tipo_escolhido != "-- Selecione --":
        st.subheader("Checklist da Viatura")

        ultimo_km_check = obter_ultimo_km(placa)
        if ultimo_km_check > 0:
            st.info(f"Último km de checklist para {placa}: {ultimo_km_check} km.")
        ultima_troca_admin = obter_ultima_troca(placa)
        if ultima_troca_admin > 0:
            st.info(f"Última troca de óleo: {ultima_troca_admin} km.")

        # Combustível e Km lado a lado
        col1, col2 = st.columns(2)
        with col1:
            km = st.number_input("Quilometragem atual", min_value=0, step=1)
        with col2:
            comb = st.radio("Combustível", OPCOES_COMBUSTIVEL, horizontal=True)

        # Oxigênio em 3 colunas
        st.markdown("#### Oxigênio")
        cox1, cox2, cox3 = st.columns(3)
        with cox1:
            ox1 = st.number_input("Grande 1 (PSI)", min_value=0, step=1)
        with cox2:
            ox2 = st.number_input("Grande 2 (PSI)", min_value=0, step=1)
        with cox3:
            oxp = st.number_input("Portátil (PSI)", min_value=0, step=1)

        # Pneus em 2 colunas
        st.markdown("#### Pneus")
        cp1, cp2 = st.columns(2)
        with cp1:
            pneu_dd = st.selectbox("Dianteiro direito", ["Ruim", "Bom", "Ótimo"])
            pneu_td = st.selectbox("Traseiro direito", ["Ruim", "Bom", "Ótimo"])
        with cp2:
            pneu_de = st.selectbox("Dianteiro esquerdo", ["Ruim", "Bom", "Ótimo"])
            pneu_te = st.selectbox("Traseiro esquerdo", ["Ruim", "Bom", "Ótimo"])

        # Botões de ação
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            salvar = st.button("Salvar")
        with bcol2:
            sair = st.button("Sair")

        # Salvar checklist
        if salvar:
            if km <= 0:
                st.error("Informe uma quilometragem válida!")
            elif ultimo_km_check and km < ultimo_km_check:
                st.error(f"A quilometragem informada ({km}) é menor que a última ({ultimo_km_check}).")
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
                    "Pneu dianteiro direito": pneu_dd,
                    "Pneu dianteiro esquerdo": pneu_de,
                    "Pneu traseiro direito": pneu_td,
                    "Pneu traseiro esquerdo": pneu_te,
                    "TipoServico": tipo_escolhido
                }
                salvar_checklist(dados)
                st.success("Checklist registrado!")
                mostrar_alerta_troca(placa, int(km))

        # Admin: registrar troca (após salvar km válido)
        if st.session_state.usuario.get("admin", False):
            st.markdown("---")
            st.subheader("Troca de óleo")
            if st.button("Registrar troca de óleo"):
                if km <= 0:
                    st.error("Informe uma quilometragem válida para registrar a troca!")
                elif ultimo_km_check and km < ultimo_km_check:
                    st.error(f"Não é possível registrar troca com km menor que o último checklist ({ultimo_km_check}).")
                else:
                    salvar_troca_oleo(placa, prefixo, km)
                    st.rerun()

        # Sair
        if sair:
            st.session_state.usuario = None
            st.session_state.tela = "login"
            st.rerun()
    else:
        # Botão de sair sempre disponível
        if st.button("Sair"):
            st.session_state.usuario = None
            st.session_state.tela = "login"
            st.rerun()
