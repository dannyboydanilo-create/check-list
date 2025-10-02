import streamlit as st
import pandas as pd
from datetime import datetime, date
from pyairtable import Table

# ---------------- Configuração Airtable ----------------
API_KEY = st.secrets["connections"]["airtable"]["personal_access_token"]
BASE_ID = st.secrets["connections"]["airtable"]["base_id"]

USUARIOS_TABLE_ID   = st.secrets["connections"]["airtable"]["usuarios_table_id"]
CHECKLISTS_TABLE_ID = st.secrets["connections"]["airtable"]["checklists_table_id"]
TROCAOLEO_TABLE_ID  = st.secrets["connections"]["airtable"]["trocaoleo_table_id"]
VIATURAS_TABLE_ID   = st.secrets["connections"]["airtable"]["viaturas_table_id"]

# Abastecimentos é opcional: só ativa se a chave existir nos secrets para evitar KeyError
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
INTERVALO_TROCA_OLEO = 10000
TOLERANCIA_ALERTA    = 500
OPCOES_COMBUSTIVEL   = ["1/4", "1/2", "3/4", "Cheio"]
TIPOS_SERVICO        = ["SAMU", "Remocao", "Van Social", "Van Hemodialise"]
OXIGENIO_MIN_PSI     = 50

# ---------------- Usuários ----------------
def carregar_usuarios():
    return [r.get("fields", {}) for r in usuarios_table.all()]

def salvar_usuario(usuario, senha, nome, matricula, is_admin=False):
    existentes = carregar_usuarios()

    # Login único
    if any(u.get("usuario", "").strip().lower() == usuario.strip().lower() for u in existentes):
        st.error("Já existe um usuário com esse login. Escolha outro.")
        return
    # Matrícula única
    if any(u.get("matricula", "").strip().lower() == matricula.strip().lower() for u in existentes):
        st.error("Já existe um usuário com essa matrícula.")
        return
    # Nome com sobrenome
    if len(nome.strip().split()) < 2:
        st.error("O nome deve conter pelo menos um sobrenome.")
        return

    usuarios_table.create({
        "usuario": usuario.strip(),
        "senha": senha.strip(),
        "nome": nome.strip(),
        "matricula": matricula.strip(),
        "is_admin": bool(is_admin),
    })
    st.success("Usuário cadastrado com sucesso!")

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

# ---------------- Checklists ----------------
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

def obter_ultimo_checklist_motorista(matricula):
    registros = checklists_table.all(sort=["-Data"])
    for r in registros:
        f = r.get("fields", {})
        if f.get("Matricula") == matricula:
            return f
    return None

# ---------------- Abastecimentos (opcional) ----------------
def salvar_abastecimento(dados):
    if not has_abastecimentos:
        st.error("Tabela de Abastecimentos não configurada nos secrets.")
        return
    abastecimentos_table.create(dados, typecast=True)

def carregar_abastecimentos():
    if not has_abastecimentos:
        return []
    return [r.get("fields", {}) for r in abastecimentos_table.all(sort=["-Data"])]

# ---------------- Alertas ----------------
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
if "viatura_atual" not in st.session_state:
    st.session_state.viatura_atual = None  # {"placa": "...", "prefixo": "..."}

# ---------------- Tela de Login ----------------
if st.session_state.tela == "login" and not st.session_state.usuario:
    st.subheader("Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        u = autenticar(usuario, senha)
        if u:
            st.session_state.usuario = u
            st.session_state.tela = "principal"
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos!")
    if st.button("Cadastro"):
        st.session_state.tela = "cadastro"
        st.rerun()

# ---------------- Tela de Cadastro ----------------
elif st.session_state.tela == "cadastro" and not st.session_state.usuario:
    st.subheader("Cadastro de Usuário")
    novo_user = st.text_input("Novo usuário (login)")
    nova_senha = st.text_input("Nova senha", type="password")
    nome = st.text_input("Nome completo (com sobrenome)")
    matricula = st.text_input("Matrícula")

    if st.button("Cadastrar"):
        if novo_user and nova_senha and nome and matricula:
            salvar_usuario(novo_user, nova_senha, nome, matricula, False)
        else:
            st.error("Preencha todos os campos!")
    if st.button("Voltar para Login"):
        st.session_state.tela = "login"
        st.rerun()

# ---------------- Tela Principal ----------------
elif st.session_state.usuario:
    st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")

    # ---------------- Sidebar Admin ----------------
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

    # ---------------- Escolha de viatura ----------------
    st.subheader("Escolha a viatura")
    viaturas = carregar_viaturas()
    viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]

    placa, prefixo, tipo_escolhido = None, None, None

    # Se já temos viatura atual em sessão, usa como padrão
    if st.session_state.viatura_atual:
        placa = st.session_state.viatura_atual.get("placa")
        prefixo = st.session_state.viatura_atual.get("prefixo")

    if viaturas_ativas:
        tipos_disponiveis = [t for t in TIPOS_SERVICO if any(v.get("TipoServico") == t for v in viaturas_ativas)]
        tipo_escolhido = st.selectbox("Tipo de serviço", ["-- Selecione --"] + tipos_disponiveis)
        if tipo_escolhido and tipo_escolhido != "-- Selecione --":
            viaturas_filtradas = [v for v in viaturas_ativas if v.get("TipoServico") == tipo_escolhido]
            if viaturas_filtradas:
                opcoes = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_filtradas]
                escolha = st.selectbox("Viatura", ["-- Selecione --"] + opcoes)
                if escolha and escolha != "-- Selecione --":
                    viatura = next((v for v in viaturas_filtradas if f"{v.get('Prefixo','')} - {v.get('Placa','')}" == escolha), None)
                    if viatura:
                        placa = viatura.get("Placa")
                        prefixo = viatura.get("Prefixo")
                        st.session_state.viatura_atual = {"placa": placa, "prefixo": prefixo}
            else:
                st.warning("Nenhuma viatura ativa para esse tipo de serviço.")
    else:
        st.info("Cadastre viaturas ativas para continuar.")

    # ---------------- Checklist (sem pneus) ----------------
    if placa and prefixo and tipo_escolhido and tipo_escolhido != "-- Selecione --":
        st.subheader("Checklist da Viatura")

        ultimo_km_check = obter_ultimo_km(placa)
        if ultimo_km_check > 0:
            st.info(f"Último km de checklist para {placa}: {ultimo_km_check} km.")
        ultima_troca_admin = obter_ultima_troca(placa)
        if ultima_troca_admin > 0:
            st.info(f"Última troca de óleo: {ultima_troca_admin} km.")

        km = st.number_input("Quilometragem atual", min_value=0, step=1)
        comb = st.radio("Nível de combustível", OPCOES_COMBUSTIVEL, horizontal=True)

        st.markdown("#### Oxigênio")
        ox1 = st.number_input("Oxigênio Grande 1 (PSI)", min_value=0, step=1)
        ox2 = st.number_input("Oxigênio Grande 2 (PSI)", min_value=0, step=1)
        oxp = st.number_input("Oxigênio Portátil (PSI)", min_value=0, step=1)

        if st.button("Salvar checklist"):
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
                    "TipoServico": tipo_escolhido
                }
                salvar_checklist(dados)
                st.success("Checklist registrado!")
                st.session_state.viatura_atual = {"placa": placa, "prefixo": prefixo}

                # Alertas do motorista: óleo e oxigênio
                mostrar_alerta_troca(placa, int(km))
                if ox1 < OXIGENIO_MIN_PSI:
                    st.error(f"🚨 Oxigênio Grande 1 muito baixo ({ox1} PSI) – reabastecer imediatamente!")
                if ox2 < OXIGENIO_MIN_PSI:
                    st.error(f"🚨 Oxigênio Grande 2 muito baixo ({ox2} PSI) – reabastecer imediatamente!")
                if oxp < OXIGENIO_MIN_PSI:
                    st.error(f"🚨 Oxigênio Portátil muito baixo ({oxp} PSI) – reabastecer imediatamente!")

        # Admin: registrar troca de óleo
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

        # ---------------- Registro de Abastecimento (motorista) ----------------
        st.markdown("---")
        st.subheader("⛽ Registro de Abastecimento")

        # Sugere a última viatura do motorista (fallback se sessão não tiver)
        if not st.session_state.viatura_atual:
            ultimo_do_motorista = obter_ultimo_checklist_motorista(st.session_state.usuario["matricula"])
            if ultimo_do_motorista:
                placa = ultimo_do_motorista.get("Placa")
                prefixo = ultimo_do_motorista.get("Prefixo")
                st.session_state.viatura_atual = {"placa": placa, "prefixo": prefixo}

        if has_abastecimentos:
            km_abast = st.number_input("Quilometragem no abastecimento", min_value=0, step=1)
            litros = st.number_input("Litros abastecidos", min_value=0.0, step=0.1, format="%.1f")
            valor = st.number_input("Valor total (R$)", min_value=0.0, step=0.01, format="%.2f")
            if st.button("Salvar abastecimento"):
                if km_abast <= 0 or litros <= 0 or valor <= 0:
                    st.error("Informe valores válidos para km, litros e valor.")
                else:
                    dados_abast = {
                        "Data": datetime.now().isoformat(),
                        "Placa": placa,
                        "Prefixo": prefixo,
                        "Condutor": st.session_state.usuario["nome"],
                        "Matricula": st.session_state.usuario["matricula"],
                        "Km": int(km_abast),
                        "Litros": float(litros),
                        "Valor": float(valor)
                    }
                    salvar_abastecimento(dados_abast)
                    st.success("Abastecimento registrado com sucesso!")
        else:
            st.info("Funcionalidade de abastecimento está desativada: configure 'abastecimentos_table_id' nos secrets para habilitar.")

    # ---------------- Dashboard de Manutenção (Admin) ----------------
    if st.session_state.usuario.get("admin", False):
        st.markdown("---")
        st.subheader("📊 Dashboard de Manutenção")

        viaturas_dash = carregar_viaturas()
        dados_dashboard = []

        for v in viaturas_dash:
            placa_v = v.get("Placa")
            prefixo_v = v.get("Prefixo")
            if not placa_v:
                continue

            ultimo_km_v = obter_ultimo_km(placa_v)
            ultima_troca_v = obter_ultima_troca(placa_v)

            if ultima_troca_v > 0:
                proxima_troca_v = ultima_troca_v + INTERVALO_TROCA_OLEO
            else:
                proxima_troca_v = ((max(ultimo_km_v, 0) // INTERVALO_TROCA_OLEO) + 1) * INTERVALO_TROCA_OLEO

            faltam_v = proxima_troca_v - ultimo_km_v

            if ultimo_km_v < proxima_troca_v - TOLERANCIA_ALERTA:
                status_oleo = "✅ OK"
            elif proxima_troca_v - TOLERANCIA_ALERTA <= ultimo_km_v <= proxima_troca_v + TOLERANCIA_ALERTA:
                status_oleo = "⚠️ Atenção"
            else:
                status_oleo = "🚨 Urgente"

            dados_dashboard.append({
                "Prefixo": prefixo_v,
                "Placa": placa_v,
                "Último KM": ultimo_km_v,
                "Última troca": ultima_troca_v if ultima_troca_v > 0 else "—",
                "Próxima troca": proxima_troca_v,
                "Faltam (km)": faltam_v,
                "Status óleo": status_oleo
            })

        if dados_dashboard:
            df_dash = pd.DataFrame(dados_dashboard)
            st.dataframe(df_dash, use_container_width=True)
        else:
            st.info("Nenhuma viatura cadastrada ainda.")

    # ---------------- Histórico de Viaturas (Admin) ----------------
    if st.session_state.usuario.get("admin", False):
        st.markdown("---")
        st.subheader("📜 Histórico de Viaturas")

        viaturas_hist = carregar_viaturas()
        opcoes_hist = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_hist]
        escolha_hist = st.selectbox("Selecione a viatura", ["-- Selecione --"] + opcoes_hist)

        if escolha_hist and escolha_hist != "-- Selecione --":
            viatura_sel = next(
                (v for v in viaturas_hist if f"{v.get('Prefixo','')} - {v.get('Placa','')}" == escolha_hist),
                None
            )
            if viatura_sel:
                placa_sel = viatura_sel.get("Placa")

                # Histórico de checklists
                st.markdown("### ✅ Checklists")
                registros_check_raw = checklists_table.all(sort=["-Data"])
                registros_check = [
                    r.get("fields", {}) for r in registros_check_raw
                    if r.get("fields", {}).get("Placa") == placa_sel
                ]
                if registros_check:
                    df_check = pd.DataFrame(registros_check)
                    st.dataframe(df_check, use_container_width=True)
                else:
                    st.info("Nenhum checklist registrado para esta viatura.")

                # Histórico de trocas de óleo
                st.markdown("### 🛢️ Trocas de Óleo")
                registros_troca_raw = trocaoleo_table.all(sort=["-data"])
                registros_troca = [
                    r.get("fields", {}) for r in registros_troca_raw
                    if r.get("fields", {}).get("Placa") == placa_sel
                ]
                if registros_troca:
                    df_troca = pd.DataFrame(registros_troca)
                    st.dataframe(df_troca, use_container_width=True)
                else:
                    st.info("Nenhuma troca de óleo registrada para esta viatura.")

                # Histórico de abastecimentos (se ativado)
                if has_abastecimentos:
                    st.markdown("### ⛽ Abastecimentos")
                    registros_abast_raw = abastecimentos_table.all(sort=["-Data"])
                    registros_abast = [
                        r.get("fields", {}) for r in registros_abast_raw
                        if r.get("fields", {}).get("Placa") == placa_sel
                    ]
                    if registros_abast:
                        df_abast = pd.DataFrame(registros_abast)
                        try:
                            df_abast_sorted = df_abast.sort_values(by="Km")
                            df_abast_sorted["Km anterior"] = df_abast_sorted["Km"].shift(1)
                            df_abast_sorted["Km rodados"] = df_abast_sorted["Km"] - df_abast_sorted["Km anterior"]
                            df_abast_sorted["Consumo (km/l)"] = df_abast_sorted["Km rodados"] / df_abast_sorted["Litros"]
                            df_abast_sorted["R$/litro"] = df_abast_sorted["Valor"] / df_abast_sorted["Litros"]
                            df_abast_sorted["R$/km"] = df_abast_sorted["Valor"] / df_abast_sorted["Km rodados"]
                            st.dataframe(df_abast_sorted, use_container_width=True)
                        except Exception:
                            st.dataframe(df_abast, use_container_width=True)
                    else:
                        st.info("Nenhum abastecimento registrado para esta viatura.")
                else:
                    st.info("Histórico de abastecimentos desativado (configure 'abastecimentos_table_id' nos secrets).")

    # ---------------- Sair ----------------
    if st.button("Sair"):
        st.session_state.usuario = None
        st.session_state.tela = "login"
        st.session_state.viatura_atual = None
        st.rerun()
