import streamlit as st
import pandas as pd
from datetime import datetime
from pyairtable import Table

# ====================== Configuracao Airtable ======================
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

# ====================== Mapeamento de campos ======================
# Ajuste ESTES nomes para corresponder 100% às colunas do SEU Airtable.
# Se o Airtable tiver acentos, use acentos aqui. Se não tiver, remova aqui.
VIATURAS_FIELDS = {
    "placa":        "Placa",
    "prefixo":      "Prefixo",
    "status":       "Status",
    "observacoes":  "Observacoes",      # Ex.: troque para "Observações" se for o seu caso
    "tipo_servico": "Tipo de Servico"   # Ex.: troque para "Tipo de Serviço" se sua coluna tiver acento
}

CHECKLIST_FIELDS = {
    "data":               "Data",
    "condutor":           "Condutor",
    "matricula":          "Matricula",
    "placa":              "Placa",
    "prefixo":            "Prefixo",
    "quilometragem":      "Quilometragem",
    "combustivel":        "Combustivel",
    "oxigenio_grande_1":  "OxigenioGrande1",
    "oxigenio_grande_2":  "OxigenioGrande2",
    "oxigenio_portatil":  "OxigenioPortatil",
    "avarias":            "Avarias",
    "tipo_servico":       "Tipo de Servico"  # alinhe com a coluna da sua base
}

TROCAOLEO_FIELDS = {
    "km":   "km",
    "data": "data"
}

USUARIOS_FIELDS = {
    "usuario":   "usuario",
    "senha":     "senha",
    "nome":      "nome",
    "matricula": "matricula",
    "is_admin":  "is_admin"
}

# ====================== Constantes ======================
INTERVALO_TROCA_OLEO = 10000
OPCOES_COMBUSTIVEL   = ["1/4", "1/2", "3/4", "Cheio"]
TIPOS_SERVICO        = ["SAMU", "Remocao", "Van Social"]  # apenas estes; sem "Outro"

# ====================== Utils ======================
def safe_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower().strip() in ["true", "1", "yes", "sim"]

def listar_campos(table: Table, titulo: str):
    try:
        registros = table.all(max_records=1)
        if registros:
            st.caption(f"Campos detectados em {titulo}: {list(registros[0].get('fields', {}).keys())}")
        else:
            st.caption(f"Sem registros em {titulo} para listar campos.")
    except Exception as e:
        st.caption(f"Falha ao listar campos de {titulo}: {e}")

# ====================== Usuarios ======================
def carregar_usuarios():
    registros = usuarios_table.all()
    return [r.get("fields", {}) for r in registros]

def salvar_usuario(usuario, senha, nome, matricula, is_admin=False):
    usuarios_table.create({
        USUARIOS_FIELDS["usuario"]:   usuario.strip(),
        USUARIOS_FIELDS["senha"]:     senha.strip(),
        USUARIOS_FIELDS["nome"]:      nome.strip(),
        USUARIOS_FIELDS["matricula"]: matricula.strip(),
        USUARIOS_FIELDS["is_admin"]:  bool(is_admin),
    })

def autenticar(usuario, senha):
    for u in carregar_usuarios():
        if u.get(USUARIOS_FIELDS["usuario"]) == usuario and u.get(USUARIOS_FIELDS["senha"]) == senha:
            return {
                "nome":      u.get(USUARIOS_FIELDS["nome"]),
                "matricula": u.get(USUARIOS_FIELDS["matricula"]),
                "admin":     safe_bool(u.get(USUARIOS_FIELDS["is_admin"], False)),
            }
    return None

# ====================== Viaturas ======================
def carregar_viaturas():
    registros = viaturas_table.all()
    return [r.get("fields", {}) for r in registros]

def salvar_viatura(placa, prefixo, status="Ativa", obs="", tipo_servico="SAMU"):
    if not placa or not prefixo:
        raise ValueError("Placa e Prefixo sao obrigatorios.")
    if tipo_servico not in TIPOS_SERVICO:
        raise ValueError("Tipo de Servico invalido.")
    viaturas_table.create({
        VIATURAS_FIELDS["placa"]:        placa.strip().upper(),
        VIATURAS_FIELDS["prefixo"]:      prefixo.strip(),
        VIATURAS_FIELDS["status"]:       status,
        VIATURAS_FIELDS["observacoes"]:  (obs.strip() if obs else ""),
        VIATURAS_FIELDS["tipo_servico"]: tipo_servico
    })

def atualizar_status_viatura(placa, novo_status):
    registros = viaturas_table.all()
    for r in registros:
        fields = r.get("fields", {})
        if fields.get(VIATURAS_FIELDS["placa"], "").upper() == (placa or "").strip().upper():
            viaturas_table.update(r["id"], {VIATURAS_FIELDS["status"]: novo_status})
            return True
    return False

# ====================== Troca de oleo ======================
def obter_ultima_troca():
    registros = trocaoleo_table.all(sort=[f'-{TROCAOLEO_FIELDS["data"]}'])
    if registros:
        return int(registros[0]["fields"].get(TROCAOLEO_FIELDS["km"], 0))
    return 0

def salvar_troca_oleo(km):
    trocaoleo_table.create({
        TROCAOLEO_FIELDS["km"]:   int(km),
        TROCAOLEO_FIELDS["data"]: datetime.now().isoformat(),
    })

# ====================== Checklist ======================
def salvar_checklist(dados):
    try:
        return checklists_table.create(dados, typecast=True)
    except Exception as e:
        st.error("Erro ao salvar checklist")
        st.write("Dados enviados:", dados)
        st.exception(e)

# ====================== UI ======================
st.set_page_config(page_title="Checklist SAMU", page_icon="🚑")
st.title("🚑 Check List Ambulancia SAMU/SOCIAL")

# Estado
if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "tela" not in st.session_state:
    st.session_state.tela = "login"

# Ajuda rápida para descobrir nomes de campos reais no Airtable
with st.expander("Ver nomes de campos detectados no Airtable (ajuste os mapeamentos acima se necessário)"):
    listar_campos(viaturas_table,   "Viaturas")
    listar_campos(checklists_table, "Checklists")
    listar_campos(trocaoleo_table,  "Troca de Oleo")
    listar_campos(usuarios_table,   "Usuarios")

# ====================== Tela de cadastro ======================
if st.session_state.tela == "cadastro":
    st.subheader("Cadastro de Usuario")
    usuario = st.text_input("Usuario")
    senha = st.text_input("Senha", type="password")
    nome = st.text_input("Nome completo")
    matricula = st.text_input("Matricula")
    is_admin = st.checkbox("Administrador?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cadastrar"):
            if not usuario or not senha or not nome or not matricula:
                st.error("Preencha todos os campos!")
            else:
                usuarios = carregar_usuarios()
                if any(u.get(USUARIOS_FIELDS["usuario"]) == usuario for u in usuarios):
                    st.error("Usuario ja existe!")
                else:
                    salvar_usuario(usuario, senha, nome, matricula, is_admin)
                    st.success("Usuario cadastrado com sucesso!")
    with col2:
        if st.button("Voltar para Login"):
            st.session_state.tela = "login"
            st.rerun()

# ====================== Tela de login / app ======================
elif st.session_state.tela == "login":
    # Se NAO autenticado: mostra login
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

    # Se autenticado: mostra app
    else:
        st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

        # ---------------- Admin ----------------
        if st.session_state.usuario.get("admin", False):
            st.sidebar.subheader("Administracao")
            st.sidebar.subheader("Gestao de Viaturas")
            placa = st.sidebar.text_input("Placa")
            prefixo = st.sidebar.text_input("Prefixo")
            status = st.sidebar.selectbox("Status", ["Ativa", "Inativa"])
            tipo_servico = st.sidebar.selectbox("Tipo de Servico", TIPOS_SERVICO)
            obs = st.sidebar.text_area("Observacoes")

            if st.sidebar.button("Adicionar Viatura"):
                try:
                    salvar_viatura(placa, prefixo, status, obs, tipo_servico)
                    st.sidebar.success("Viatura cadastrada!")
                except Exception as e:
                    st.sidebar.error("Erro ao cadastrar viatura")
                    st.sidebar.exception(e)

            # Lista e alteracao de status
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
                        st.sidebar.error("Viatura nao encontrada pela placa.")

        # ---------------- Escolha de viatura ----------------
        st.subheader("Escolha a Viatura")
        viaturas = carregar_viaturas()
        viaturas_ativas = [v for v in viaturas if v.get(VIATURAS_FIELDS["status"]) == "Ativa"]

        if viaturas_ativas:
            # Apenas tipos válidos cadastrados (sem "Outro")
            tipos_disponiveis = [
                t for t in TIPOS_SERVICO
                if any(v.get(VIATURAS_FIELDS["tipo_servico"]) == t for v in viaturas_ativas)
            ]
            if not tipos_disponiveis:
                st.warning("Nenhum tipo de servico disponivel nas viaturas ativas.")
                placa, prefixo = None, None
            else:
                tipo_escolhido = st.selectbox("Selecione o tipo de servico", tipos_disponiveis)
                viaturas_filtradas = [
                    v for v in viaturas_ativas if v.get(VIATURAS_FIELDS["tipo_servico"]) == tipo_escolhido
                ]

                if viaturas_filtradas:
                    opcoes_viaturas = [
                        f"{v.get(VIATURAS_FIELDS['prefixo'],'')} - {v.get(VIATURAS_FIELDS['placa'],'')}"
                        for v in viaturas_filtradas
                    ]
                    escolha_viatura = st.selectbox("Selecione a viatura", opcoes_viaturas)
                    viatura_selecionada = next(
                        v for v in viaturas_filtradas
                        if f"{v.get(VIATURAS_FIELDS['prefixo'],'')} - {v.get(VIATURAS_FIELDS['placa'],'')}" == escolha_viatura
                    )
                    placa = viatura_selecionada.get(VIATURAS_FIELDS["placa"], "")
                    prefixo = viatura_selecionada.get(VIATURAS_FIELDS["prefixo"], "")
                else:
                    st.warning("Nenhuma viatura ativa para esse tipo de servico.")
                    placa, prefixo = None, None
        else:
            st.error("Nenhuma viatura ativa cadastrada!")
            placa, prefixo = None, None

        # ---------------- Checklist ----------------
        if placa and prefixo:
            st.subheader("Checklist da Viatura")
            km = st.number_input("Quilometragem atual", min_value=0, step=1)
            comb = st.radio("Nivel de combustivel", OPCOES_COMBUSTIVEL, horizontal=True)

            st.subheader("Oxigenio")
            ox1 = st.number_input("Oxigenio Grande 1 (PSI)", min_value=0, step=1)
            ox2 = st.number_input("Oxigenio Grande 2 (PSI)", min_value=0, step=1)
            oxp = st.number_input("Oxigenio Portatil (PSI)", min_value=0, step=1)

            st.subheader("Avarias encontradas")
            avarias = st.text_area("Descreva as avarias (se houver)", "")

            if st.button("Salvar Checklist"):
                if km <= 0:
                    st.error("Informe uma quilometragem valida!")
                else:
                    dados = {
                        CHECKLIST_FIELDS["data"]:              datetime.now().isoformat(),
                        CHECKLIST_FIELDS["condutor"]:          st.session_state.usuario["nome"],
                        CHECKLIST_FIELDS["matricula"]:         st.session_state.usuario["matricula"],
                        CHECKLIST_FIELDS["placa"]:             placa,
                        CHECKLIST_FIELDS["prefixo"]:           prefixo,
                        CHECKLIST_FIELDS["quilometragem"]:     int(km),
                        CHECKLIST_FIELDS["combustivel"]:       comb,
                        CHECKLIST_FIELDS["oxigenio_grande_1"]: int(ox1),
                        CHECKLIST_FIELDS["oxigenio_grande_2"]: int(ox2),
                        CHECKLIST_FIELDS["oxigenio_portatil"]: int(oxp),
                        CHECKLIST_FIELDS["avarias"]:           (avarias.strip() if avarias else "Nenhuma"),
                        CHECKLIST_FIELDS["tipo_servico"]:      tipo_escolhido
                    }
                    salvar_checklist(dados)
                    st.success("Checklist registrado com sucesso!")

                    # Aviso troca de oleo
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
                        st.success(f"Troca de oleo registrada em {int(km)} km.")

        # ---------------- Sair ----------------
        if st.button("Sair"):
            st.session_state.usuario = None
            st.session_state.tela = "login"
            st.rerun()
