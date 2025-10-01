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
TOLERANCIA_ALERTA    = 500
OPCOES_COMBUSTIVEL   = ["1/4", "1/2", "3/4", "Cheio"]
TIPOS_SERVICO        = ["SAMU", "Remocao", "Van Hemodialise"]

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
        "TipoServico": tipo_servico
    })

def atualizar_status_viatura(placa, novo_status):
    registros = viaturas_table.all()
    for r in registros:
        fields = r.get("fields", {})
        if fields.get("Placa", "").upper() == (placa or "").strip().upper():
            viaturas_table.update(r["id"], {"Status": novo_status})
            return True
    return False

# ---------------- Troca de oleo ----------------
def obter_ultima_troca(placa):
    """Retorna o km da ultima troca registrada pelo admin para a placa."""
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
    """Registra troca de oleo vinculada a placa/prefixo e km atual."""
    trocaoleo_table.create({
        "Placa": placa,
        "Prefixo": prefixo,
        "km": int(km),
        "data": datetime.now().isoformat(),
    })
    st.success(f"Troca de óleo registrada para {placa} em {int(km)} km.")

def carregar_trocas():
    """Carrega todas as trocas para exibir em histórico (somente admin)."""
    registros = trocaoleo_table.all(sort=["-data"])
    return [r.get("fields", {}) for r in registros]

# ---------------- Checklist helpers ----------------
def salvar_checklist(dados):
    checklists_table.create(dados, typecast=True)

def obter_ultimo_km(placa):
    """Ultimo km de checklist para a placa (para garantir km crescente)."""
    registros = checklists_table.all(sort=["-Data"])
    for r in registros:
        f = r.get("fields", {})
        if f.get("Placa") == placa:
            try:
                return int(f.get("Quilometragem", 0))
            except Exception:
                return 0
    return 0

# ---------------- UI ----------------
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulancia SAMU/SOCIAL")

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
        placa_admin = st.sidebar.text_input("Placa")
        prefixo_admin = st.sidebar.text_input("Prefixo")
        status_admin = st.sidebar.selectbox("Status", ["Ativa", "Inativa"])
        tipo_servico_admin = st.sidebar.selectbox("Tipo de Servico", TIPOS_SERVICO)
        obs_admin = st.sidebar.text_area("Observacoes")

        if st.sidebar.button("Adicionar Viatura"):
            salvar_viatura(placa_admin, prefixo_admin, status_admin, obs_admin, tipo_servico_admin)

        st.sidebar.markdown("---")
        st.sidebar.subheader("Historico de Trocas de Oleo")
        trocas = carregar_trocas()
        if trocas:
            st.sidebar.dataframe(pd.DataFrame(trocas), use_container_width=True)
        else:
            st.sidebar.info("Nenhuma troca registrada ainda.")

    # Escolha de viatura
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

        # Dicas de contexto
        ultimo_km_check = obter_ultimo_km(placa)
        if ultimo_km_check > 0:
            st.info(f"Ultimo km de checklist para {placa}: {ultimo_km_check} km.")

        ultima_troca_admin = obter_ultima_troca(placa)
        if ultima_troca_admin > 0:
            st.info(f"Ultima troca de oleo registrada para {placa}: {ultima_troca_admin} km.")

        # Entradas
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

        # Botao salvar checklist
        if st.button("Salvar Checklist"):
            # Validacoes de km crescente
            if km <= 0:
                st.error("Informe uma quilometragem valida!")
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

                # Alerta de troca baseado SOMENTE na ultima troca registrada pelo admin
                # (o alerta só some quando o admin registrar nova troca)
                if ultima_troca_admin > 0:
                    proxima_troca = ultima_troca_admin + INTERVALO_TROCA_OLEO
                    if int(km) >= proxima_troca - TOLERANCIA_ALERTA:
                        if int(km) <= proxima_troca + TOLERANCIA_ALERTA:
                            st.warning(
                                f"Atenção: {placa} está com {int(km)} km. "
                                f"Faixa de troca de óleo (próxima em {proxima_troca} km; última troca em {ultima_troca_admin} km)."
                            )
                        else:
                            st.error(
                                f"Atenção: {placa} ultrapassou a quilometragem de troca "
                                f"({int(km)} km). Necessária troca de óleo! (última troca em {ultima_troca_admin} km)"
                            )
                    else:
                        faltam = proxima_troca - int(km)
                        st.info(f"Faltam {faltam} km para a próxima troca de óleo (em {proxima_troca} km).")
                else:
                    # Nunca houve troca registrada: exibe informação para admin iniciar o ciclo
                    st.info("Ainda não há troca de óleo registrada pelo administrador para esta viatura.")

        # Registrar troca de oleo (somente admin)
        if st.session_state.usuario.get("admin", False):
            st.markdown("---")
            st.subheader("Troca de óleo")
            if st.button("Registrar troca de oleo"):
                # Validar km (sempre crescente)
                if km <= 0:
                    st.error("Informe uma quilometragem valida para registrar a troca!")
                elif ultimo_km_check and km < ultimo_km_check:
                    st.error(f"Não é possível registrar troca com km menor que o último checklist ({ultimo_km_check}).")
                else:
                    salvar_troca_oleo(placa, prefixo, km)
                    # Após registrar, reexecuta para atualizar alertas
                    st.rerun()

    # Sair
    if st.button("Sair"):
        st.session_state.usuario = None
        st.session_state.tela = "login"
        st.rerun()
