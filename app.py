import streamlit as st
import pandas as pd
from datetime import datetime, date
from pyairtable import Table
import re

# ---------------- Airtable ----------------
API_KEY = st.secrets["connections"]["airtable"]["personal_access_token"]
BASE_ID = st.secrets["connections"]["airtable"]["base_id"]

USUARIOS_TABLE_ID   = st.secrets["connections"]["airtable"]["usuarios_table_id"]
CHECKLISTS_TABLE_ID = st.secrets["connections"]["airtable"]["checklists_table_id"]
TROCAOLEO_TABLE_ID  = st.secrets["connections"]["airtable"]["trocaoleo_table_id"]
VIATURAS_TABLE_ID   = st.secrets["connections"]["airtable"]["viaturas_table_id"]

has_abastecimentos = (
    "connections" in st.secrets and
    "airtable" in st.secrets["connections"] and
    "abastecimentos_table_id" in st.secrets["connections"]["airtable"]
)
ABASTECIMENTOS_TABLE_ID = (
    st.secrets["connections"]["airtable"]["abastecimentos_table_id"]
    if has_abastecimentos else None
)

usuarios_table   = Table(API_KEY, BASE_ID, USUARIOS_TABLE_ID)
checklists_table = Table(API_KEY, BASE_ID, CHECKLISTS_TABLE_ID)
trocaoleo_table  = Table(API_KEY, BASE_ID, TROCAOLEO_TABLE_ID)
viaturas_table   = Table(API_KEY, BASE_ID, VIATURAS_TABLE_ID)
abastecimentos_table = Table(API_KEY, BASE_ID, ABASTECIMENTOS_TABLE_ID) if has_abastecimentos else None

# ---------------- Constantes ----------------
TOLERANCIA_ALERTA  = 500
OPCOES_COMBUSTIVEL = ["1/4", "1/2", "3/4", "Cheio"]
TIPOS_SERVICO      = ["SAMU", "Remocao", "Van Social", "Van Hemodialise", "Moto"]
OXIGENIO_MIN_PSI   = 50

INTERVALOS_TROCA = {
    "SAMU": 10000,
    "Remocao": 10000,
    "Van Social": 10000,
    "Van Hemodialise": 10000,
    "Moto": 2000
}

# ---------------- Utilidades ----------------
def parse_iso_datetime(dt_str: str):
    try:
        return datetime.fromisoformat(dt_str.replace("Z", ""))
    except Exception:
        return None

def tocar_alerta():
    sound = """
    <audio autoplay>
        <source src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg" type="audio/ogg">
    </audio>
    """
    st.markdown(sound, unsafe_allow_html=True)

# ---------------- Usuários ----------------
def carregar_usuarios():
    return [r.get("fields", {}) for r in usuarios_table.all()]

def salvar_usuario(usuario, senha, nome, matricula, telefone, is_admin=False):
    existentes = carregar_usuarios()
    if any(u.get("usuario", "").strip().lower() == usuario.strip().lower() for u in existentes):
        st.error("Já existe um usuário com esse login."); return
    if any(u.get("matricula", "").strip().lower() == matricula.strip().lower() for u in existentes):
        st.error("Já existe um usuário com essa matrícula."); return
    if len(nome.strip().split()) < 2:
        st.error("O nome deve conter pelo menos um sobrenome."); return

    usuarios_table.create({
        "usuario": usuario.strip(),
        "senha": senha.strip(),
        "nome": nome.strip(),
        "matricula": matricula.strip(),
        "telefone": telefone.strip(),
        "is_admin": bool(is_admin),
    })
    st.success("Usuário cadastrado com sucesso!")

def autenticar(usuario, senha):
    for u in carregar_usuarios():
        if u.get("usuario") == usuario and u.get("senha") == senha:
            return {
                "nome": u.get("nome"),
                "matricula": u.get("matricula"),
                "telefone": u.get("telefone", ""),
                "admin": bool(u.get("is_admin", False))
            }
    return None

# ---------------- Viaturas ----------------
def carregar_viaturas():
    return [r.get("fields", {}) for r in viaturas_table.all()]

def salvar_viatura(placa, prefixo, status="Ativa", obs="", tipo_servico="SAMU"):
    if not placa or not prefixo:
        st.sidebar.error("Placa e Prefixo são obrigatórios."); return
    viaturas_table.create({
        "Placa": placa.strip().upper(),
        "Prefixo": prefixo.strip(),
        "Status": status,
        "Observacoes": (obs or "").strip(),
        "TipoServico": tipo_servico
    })
    st.sidebar.success("Viatura cadastrada!")

# ---------------- Troca de óleo ----------------
def obter_ultima_troca(placa):
    registros = trocaoleo_table.all(sort=["-data"])
    for r in registros:
        f = r.get("fields", {})
        if f.get("Placa") == placa:
            try: return int(f.get("km", 0))
            except Exception: return 0
    return 0

def salvar_troca_oleo(placa, prefixo, km):
    trocaoleo_table.create({
        "Placa": placa,
        "Prefixo": prefixo,
        "km": int(km),
        "data": datetime.now().isoformat(),
    })
    st.success(f"Troca de óleo registrada para {placa} em {int(km)} km.")

# ---------------- Checklists ----------------
def salvar_checklist(dados):
    checklists_table.create(dados, typecast=True)

def obter_ultimo_km_checklist(placa):
    registros = checklists_table.all(sort=["-Data"])
    for r in registros:
        f = r.get("fields", {})
        if f.get("Placa") == placa:
            try: return int(f.get("Quilometragem", 0))
            except Exception: return 0
    return 0

def obter_ultimo_checklist_do_motorista_hoje(matricula: str):
    hoje = date.today()
    registros = checklists_table.all(sort=["-Data"])
    for r in registros:
        f = r.get("fields", {})
        if f.get("Matricula") != matricula: continue
        dt = parse_iso_datetime(f.get("Data", ""))
        if dt and dt.date() == hoje: return f
    return None

# ---------------- Abastecimentos ----------------
def salvar_abastecimento(dados):
    if not has_abastecimentos:
        st.error("Tabela de Abastecimentos não configurada."); return
    abastecimentos_table.create(dados, typecast=True)

def obter_ultimo_km_abastecimento(placa):
    if not has_abastecimentos: return 0
    registros = abastecimentos_table.all(sort=["-Data"])
    for r in registros:
        f = r.get("fields", {})
        if f.get("Placa") == placa:
            try: return int(f.get("Km", 0))
            except Exception: return 0
    return 0

# ---------------- Alertas ----------------
def mostrar_alerta_troca(placa, km_atual, tipo_servico):
    intervalo = INTERVALOS_TROCA.get(tipo_servico, 10000)
    ultima_troca_admin = obter_ultima_troca(placa)

    if ultima_troca_admin > 0:
        proxima_troca = ultima_troca_admin + intervalo
        contexto = f"Última troca: {ultima_troca_admin} km | Próxima: {proxima_troca} km."
    else:
        proxima_troca = ((km_atual // intervalo) + 1) * intervalo
        contexto = f"Primeira troca prevista: {proxima_troca} km."

    if km_atual < proxima_troca - TOLERANCIA_ALERTA:
        st.info(f"ℹ️ Faltam {proxima_troca - km_atual} km para a troca de óleo. {contexto}")
    elif proxima_troca - TOLERANCIA_ALERTA <= km_atual <= proxima_troca + TOLERANCIA_ALERTA:
        st.warning(f"⚠️ {placa} está na FAIXA DE TROCA! Atual: {km_atual} km | {contexto}")
        tocar_alerta()
    else:
        st.error(f"🚨 URGENTE: {placa} já passou da troca! Prevista: {proxima_troca} km | Atual: {km_atual} km.")
        tocar_alerta()
        # ---------------- Interface ----------------
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulância SAMU/SOCIAL")

if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "tela" not in st.session_state:
    st.session_state.tela = "login"
if "viatura_atual" not in st.session_state:
    st.session_state.viatura_atual = None

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
                st.session_state.tela = "principal"
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos!")
    with c2:
        if st.button("Cadastro"):
            st.session_state.tela = "cadastro"
            st.rerun()

# ---------------- Tela de Cadastro ----------------
elif st.session_state.tela == "cadastro" and not st.session_state.usuario:
    st.subheader("Cadastro de usuário")

    novo_user   = st.text_input("Novo usuário (login)")
    nova_senha  = st.text_input("Nova senha", type="password")
    nome        = st.text_input("Nome completo (com sobrenome)")
    matricula   = st.text_input("Matrícula")
    telefone_raw = st.text_input("Telefone (apenas números)", max_chars=11)

    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("Cadastrar"):
            if not (novo_user and nova_senha and nome and matricula and telefone_raw):
                st.error("Preencha todos os campos, incluindo o telefone!")
            elif not telefone_raw.isdigit() or len(telefone_raw) != 11:
                st.error("Digite um número válido com 11 dígitos (DDD + celular)")
            elif len(nome.strip().split()) < 2:
                st.error("O nome deve conter pelo menos um sobrenome.")
            else:
                telefone_formatado = f"({telefone_raw[:2]}) {telefone_raw[2:7]}-{telefone_raw[7:]}"
                salvar_usuario(novo_user, nova_senha, nome, matricula, telefone_formatado, False)
    with cc2:
        if st.button("Voltar para login"):
            st.session_state.tela = "login"
            st.rerun()

# ---------------- Tela Principal ----------------
elif st.session_state.usuario:
    st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")
    opcao = st.radio("Escolha o que deseja fazer:", ["Checklist", "Abastecimento"])

    # Aqui você pode colar os blocos de Checklist, Abastecimento, Dashboard e Histórico
    # que já montamos anteriormente. Eles funcionam perfeitamente com essa estrutura.

    st.markdown("---")
    if st.button("Sair"):
        st.session_state.usuario = None
        st.session_state.tela = "login"
        st.session_state.viatura_atual = None
        st.rerun()
