import streamlit as st
import pandas as pd
from datetime import datetime, date
from pyairtable import Table
import re

# ---------------- Configuração Airtable ----------------
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
        st.error("Já existe um usuário com esse login.")
        return

    if any(u.get("matricula", "").strip().lower() == matricula.strip().lower() for u in existentes):
        st.error("Já existe um usuário com essa matrícula.")
        return

    if len(nome.strip().split()) < 2:
        st.error("O nome deve conter pelo menos um sobrenome.")
        return

    if not telefone.strip().isdigit() or len(telefone.strip()) != 11:
        st.error("Telefone inválido. Digite apenas os 11 números (DDD + celular).")
        return

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

def atualizar_senha(usuario, senha_antiga, nova_senha):
    registros = usuarios_table.all()
    for r in registros:
        f = r.get("fields", {})
        if f.get("usuario") == usuario and f.get("senha") == senha_antiga:
            usuarios_table.update(r["id"], {"senha": nova_senha})
            return True
    return False

def atualizar_cadastro(matricula, novo_nome, novo_telefone):
    registros = usuarios_table.all()
    for r in registros:
        f = r.get("fields", {})
        if f.get("matricula") == matricula:
            usuarios_table.update(r["id"], {
                "nome": novo_nome,
                "telefone": novo_telefone
            })
            return True
    return False
# ---------------- UI ----------------
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulância SAMU/SOCIAL")

if "usuario" not in st.session_state: st.session_state.usuario = None
if "tela" not in st.session_state: st.session_state.tela = "login"
if "viatura_atual" not in st.session_state: st.session_state.viatura_atual = None  # {"placa": "...", "prefixo": "..."}

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

    novo_user    = st.text_input("Novo usuário (login)")
    nova_senha   = st.text_input("Nova senha", type="password")
    nome         = st.text_input("Nome completo (com sobrenome)")
    matricula    = st.text_input("Matrícula")
    telefone_raw = st.text_input("Telefone (apenas números)", max_chars=11, placeholder="Ex: 11912345678")

    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("Cadastrar"):
            if not (novo_user and nova_senha and nome and matricula and telefone_raw):
                st.error("Preencha todos os campos, incluindo o telefone!")
            elif not telefone_raw.isdigit() or len(telefone_raw) != 11:
                st.error("Telefone inválido. Digite apenas os 11 números (DDD + celular).")
            elif len(nome.strip().split()) < 2:
                st.error("O nome deve conter pelo menos um sobrenome.")
            else:
                salvar_usuario(
                    novo_user.strip(),
                    nova_senha.strip(),
                    nome.strip(),
                    matricula.strip(),
                    telefone_raw.strip(),
                    False
                )
    with cc2:
        if st.button("Voltar para login"):
            st.session_state.tela = "login"
            st.rerun()

# ---------------- Tela de Mudar Senha ----------------
elif st.session_state.tela == "mudar_senha":
    st.subheader("🔄 Alterar senha")

    senha_atual = st.text_input("Senha atual", type="password")
    nova_senha = st.text_input("Nova senha", type="password")
    confirmar = st.text_input("Confirmar nova senha", type="password")

    col1, col2 = st.columns(2)
    with col1:
        atualizar = st.button("Atualizar senha")
    with col2:
        voltar = st.button("Voltar")

    if atualizar:
        if not (senha_atual and nova_senha and confirmar):
            st.error("Preencha todos os campos.")
        elif nova_senha != confirmar:
            st.error("A nova senha e a confirmação não coincidem.")
        elif atualizar_senha(st.session_state.usuario["nome"], senha_atual, nova_senha):
            st.success("Senha atualizada com sucesso!")
            st.session_state.tela = "principal"
            st.rerun()
        else:
            st.error("Senha atual incorreta.")

    if voltar:
        st.session_state.tela = "principal"
        st.rerun()

# ---------------- Tela de Atualizar Cadastro ----------------
elif st.session_state.tela == "atualizar_cadastro":
    st.subheader("✏️ Atualizar cadastro")

    nome_atual = st.session_state.usuario["nome"]
    telefone_atual = st.session_state.usuario["telefone"]

    novo_nome = st.text_input("Nome completo", value=nome_atual)
    novo_telefone = st.text_input("Telefone (apenas números)", value=telefone_atual, max_chars=11)

    col1, col2 = st.columns(2)
    with col1:
        salvar = st.button("Salvar alterações")
    with col2:
        voltar = st.button("Voltar")

    if salvar:
        if not novo_nome or not novo_telefone.isdigit() or len(novo_telefone) != 11:
            st.error("Preencha corretamente os campos.")
        elif atualizar_cadastro(st.session_state.usuario["matricula"], novo_nome, novo_telefone):
            st.success("Cadastro atualizado!")
            st.session_state.usuario["nome"] = novo_nome
            st.session_state.usuario["telefone"] = novo_telefone
            st.session_state.tela = "principal"
            st.rerun()
        else:
            st.error("Erro ao atualizar cadastro.")

    if voltar:
        st.session_state.tela = "principal"
        st.rerun()

# ---------------- Tela Principal ----------------
elif st.session_state.usuario:
    st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Mudar senha"):
            st.session_state.tela = "mudar_senha"
            st.rerun()
    with col2:
        if st.button("✏️ Atualizar cadastro"):
            st.session_state.tela = "atualizar_cadastro"
            st.rerun()

    opcao = st.radio("Escolha o que deseja fazer:", ["Checklist", "Abastecimento"])

    # Checklist
    if opcao == "Checklist":
        # [todo o seu código de checklist aqui — já está completo e funcionando]
        # (Você pode colar o trecho que me enviou anteriormente sem alterações)

    # Abastecimento
    elif opcao == "Abastecimento":
        # [todo o seu código de abastecimento aqui — já está completo e funcionando]
        # (Você pode colar o trecho que me enviou anteriormente sem alterações)

    # Dashboard Manutenção (Admin)
    if st.session_state.usuario.get("admin", False):
        # [todo o seu dashboard de manutenção — já está completo e funcionando]

    # Histórico de Viaturas (Admin)
    if st.session_state.usuario.get("admin", False):
        # [todo o seu histórico de viaturas — já está completo e funcionando]

    st.markdown("---")
    if st.button("Sair"):
        st.session_state.usuario = None
        st.session_state.tela = "login"
        st.session_state.viatura_atual = None
        st.rerun()
