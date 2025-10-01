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

# ---------------- UI Base ----------------
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

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Entrar"):
            u = autenticar(usuario, senha)
            if u:
                st.session_state.usuario = u
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos!")
    with col2:
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
                st.success("Usuário cadastrado com sucesso! Clique em Voltar para Login.")
            else:
                st.error("Preencha todos os campos!")
    with c2:
        if st.button("Voltar para Login"):
            st.session_state.tela = "login"
            st.rerun()
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

# ---------------- Tela Principal (Admin) ----------------
elif st.session_state.usuario:
    st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

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
    """Mostra aviso claro sobre a troca de óleo."""
    ultima_troca_admin = obter_ultima_troca(placa)

    if ultima_troca_admin > 0:
        proxima_troca = ultima_troca_admin + INTERVALO_TROCA_OLEO
    else:
        # Nunca houve troca registrada → calcula próximo múltiplo de 10.000
        proxima_troca = ((km_atual // INTERVALO_TROCA_OLEO) + 1) * INTERVALO_TROCA_OLEO

    if km_atual < proxima_troca - TOLERANCIA_ALERTA:
        faltam = proxima_troca - km_atual
        st.info(f"ℹ️ Faltam {faltam} km para a próxima troca de óleo. "
                f"Próxima prevista: {proxima_troca} km.")

    elif proxima_troca - TOLERANCIA_ALERTA <= km_atual <= proxima_troca + TOLERANCIA_ALERTA:
        st.warning(f"⚠️ Atenção: a viatura {placa} está com {km_atual} km. "
                   f"Está na FAIXA DE TROCA DE ÓLEO! Próxima prevista: {proxima_troca} km.")

    else:  # km_atual > proxima_troca + tolerância
        st.error(f"🚨 URGENTE: a viatura {placa} ultrapassou a quilometragem de troca! "
                 f"Deveria ter sido feita em {proxima_troca} km | Atual: {km_atual} km. "
                 f"O administrador precisa registrar a troca imediatamente.")

# ---------------- Tela de Checklist ----------------
    st.subheader("Checklist da Viatura")

    ultimo_km_check = obter_ultimo_km(placa)
    if ultimo_km_check > 0:
        st.info(f"Último km de checklist para {placa}: {ultimo_km_check} km.")

    km = st.number_input("Quilometragem atual", min_value=0, step=1)
    comb = st.radio("Nível de combustível", OPCOES_COMBUSTIVEL, horizontal=True)

    st.markdown("#### Oxigênio")
    ox1 = st.number_input("Oxigenio Grande 1 (PSI)", min_value=0, step=1)
    ox2 = st.number_input("Oxigenio Grande 2 (PSI)", min_value=0, step=1)
    oxp = st.number_input("Oxigenio Portatil (PSI)", min_value=0, step=1)

    st.markdown("#### Pneus")
    pneu_dd = st.selectbox("Pneu dianteiro direito", ["Ruim", "Bom", "Otimo"])
    pneu_de = st.selectbox("Pneu dianteiro esquerdo", ["Ruim", "Bom", "Otimo"])
    pneu_td = st.selectbox("Pneu traseiro direito", ["Ruim", "Bom", "Otimo"])
    pneu_te = st.selectbox("Pneu traseiro esquerdo", ["Ruim", "Bom", "Otimo"])

    if st.button("Salvar checklist"):
        if km <= 0:
            st.error("Informe uma quilometragem válida!")
        elif ultimo_km_check and km < ultimo_km_check:
            st.error(f"A quilometragem informada ({km}) é menor que a última registrada ({ultimo_km_check}).")
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
            st.success("Checklist registrado com sucesso!")
            mostrar_alerta_troca(placa, int(km))

    # Admin: registrar troca (faz o alerta desaparecer até o próximo ciclo)
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

# ---------------- Botão de Sair ----------------
    if st.button("Sair"):
        st.session_state.usuario = None
        st.session_state.tela = "login"
        st.rerun()
