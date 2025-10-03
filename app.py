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
        st.error("Já existe um usuário com esse login."); return
    if any(u.get("matricula", "").strip().lower() == matricula.strip().lower() for u in existentes):
        st.error("Já existe um usuário com essa matrícula."); return
    if len(nome.strip().split()) < 2:
        st.error("O nome deve conter pelo menos um sobrenome."); return
    if not telefone.strip().isdigit() or len(telefone.strip()) != 11:
    st.error("Telefone inválido. Digite apenas os 11 números (DDD + celular)."); return
    
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
    novo_user = st.text_input("Novo usuário (login)")
    nova_senha = st.text_input("Nova senha", type="password")
    nome = st.text_input("Nome completo (com sobrenome)")
    matricula = st.text_input("Matrícula")
    telefone = st.text_input("Telefone (apenas números)", max_chars=11, placeholder="Ex: 11912345678")

    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("Cadastrar"):
            if novo_user and nova_senha and nome and matricula and telefone:
                telefone_formatado = f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
                salvar_usuario(novo_user, nova_senha, nome, matricula, telefone_formatado, False)
            else:
                st.error("Preencha todos os campos, incluindo o telefone!")
    with cc2:
        if st.button("Voltar para login"):
            st.session_state.tela = "login"
            st.rerun()

# ---------------- Tela Principal ----------------
elif st.session_state.usuario:
    st.success(f"Bem-vindo, {st.session_state.usuario['nome']} ({st.session_state.usuario['matricula']})")
    opcao = st.radio("Escolha o que deseja fazer:", ["Checklist", "Abastecimento"])

    # Sidebar Admin
    if st.session_state.usuario.get("admin", False):
        st.sidebar.subheader("Gestão de viaturas")
        placa_admin = st.sidebar.text_input("Placa")
        prefixo_admin = st.sidebar.text_input("Prefixo")
        status_admin = st.sidebar.selectbox("Status", ["Ativa", "Inativa"])
        tipo_servico_admin = st.sidebar.selectbox("Tipo de serviço", TIPOS_SERVICO)
        obs_admin = st.sidebar.text_area("Observações")
        if st.sidebar.button("Adicionar viatura"):
            salvar_viatura(placa_admin, prefixo_admin, status_admin, obs_admin, tipo_servico_admin)

        st.sidebar.markdown("---")
        st.sidebar.subheader("Histórico de trocas de óleo")
        trocas = [r.get("fields", {}) for r in trocaoleo_table.all(sort=["-data"])]
        if trocas: st.sidebar.dataframe(pd.DataFrame(trocas), use_container_width=True)
        else: st.sidebar.info("Nenhuma troca registrada ainda.")

    # Checklist
    if opcao == "Checklist":
        st.subheader("✅ Checklist da viatura")
        viaturas = carregar_viaturas()
        viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]

        if not viaturas_ativas:
            st.info("Cadastre viaturas ativas para continuar.")
        else:
            tipos_disponiveis = [t for t in TIPOS_SERVICO if any(v.get("TipoServico") == t for v in viaturas_ativas)]
            tipo_escolhido = st.selectbox("Tipo de serviço", ["-- Selecione --"] + tipos_disponiveis)

            placa, prefixo = None, None
            if tipo_escolhido and tipo_escolhido != "-- Selecione --":
                viaturas_filtradas = [v for v in viaturas_ativas if v.get("TipoServico") == tipo_escolhido]
                opcoes = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_filtradas]
                escolha = st.selectbox("Viatura", ["-- Selecione --"] + opcoes)
                if escolha and escolha != "-- Selecione --":
                    viatura = next((v for v in viaturas_filtradas if f"{v.get('Prefixo','')} - {v.get('Placa','')}" == escolha), None)
                    if viatura:
                        placa = viatura.get("Placa")
                        prefixo = viatura.get("Prefixo")

            if placa and prefixo and tipo_escolhido and tipo_escolhido != "-- Selecione --":
                ultimo_km_check = obter_ultimo_km_checklist(placa)
                if ultimo_km_check > 0: st.info(f"Último km de checklist: {ultimo_km_check} km.")
                ultima_troca_admin = obter_ultima_troca(placa)
                if ultima_troca_admin > 0: st.info(f"Última troca de óleo: {ultima_troca_admin} km.")

                km = st.number_input("Quilometragem atual (checklist)", min_value=0, step=1)
                comb = st.radio("Nível de combustível", OPCOES_COMBUSTIVEL, horizontal=True)

                st.markdown("#### Oxigênio")
                ox1_str = st.text_input("Oxigênio Grande 1 (PSI)")
                ox2_str = st.text_input("Oxigênio Grande 2 (PSI)")
                oxp_str = st.text_input("Oxigênio Portátil (PSI)")
                ox1 = int(ox1_str) if ox1_str.strip().isdigit() else 0
                ox2 = int(ox2_str) if ox2_str.strip().isdigit() else 0
                oxp = int(oxp_str) if oxp_str.strip().isdigit() else 0

                if st.button("Salvar checklist"):
                    if km <= 0:
                        st.error("Informe uma quilometragem válida!"); tocar_alerta()
                    elif ultimo_km_check and km < ultimo_km_check:
                        st.error(f"A quilometragem informada ({km}) é menor que a última ({ultimo_km_check})."); tocar_alerta()
                    else:
                        dados = {
                            "Data": datetime.now().isoformat(),
                            "Condutor": st.session_state.usuario["nome"],
                            "Matricula": st.session_state.usuario["matricula"],
                            "Placa": placa,
                            "Prefixo": prefixo,
                            "Quilometragem": int(km),
                            "Combustivel": comb,
                            "Oxigenio Grande 1": ox1,
                            "Oxigenio Grande 2": ox2,
                            "Oxigenio Portatil": oxp,
                            "TipoServico": tipo_escolhido
                        }
                        salvar_checklist(dados)
                        st.success("Checklist registrado!")
                        st.session_state.viatura_atual = {"placa": placa, "prefixo": prefixo}

                        mostrar_alerta_troca(placa, int(km), tipo_escolhido)
                        if ox1 < OXIGENIO_MIN_PSI:
                            st.error(f"🚨 Oxigênio Grande 1 muito baixo ({ox1} PSI)."); tocar_alerta()
                        if ox2 < OXIGENIO_MIN_PSI:
                            st.error(f"🚨 Oxigênio Grande 2 muito baixo ({ox2} PSI)."); tocar_alerta()
                        if oxp < OXIGENIO_MIN_PSI:
                            st.error(f"🚨 Oxigênio Portátil muito baixo ({oxp} PSI)."); tocar_alerta()

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

    # Abastecimento
    elif opcao == "Abastecimento":
        st.subheader("⛽ Registro de abastecimento")
        if not has_abastecimentos:
            st.info("Funcionalidade de abastecimento desativada: configure 'abastecimentos_table_id' nos secrets.")
        else:
            placa, prefixo = None, None
            if st.session_state.viatura_atual:
                placa = st.session_state.viatura_atual.get("placa")
                prefixo = st.session_state.viatura_atual.get("prefixo")
                st.info(f"Usando viatura da sessão: {prefixo} - {placa}")
            else:
                ultimo = obter_ultimo_checklist_do_motorista_hoje(st.session_state.usuario["matricula"])
                if ultimo:
                    placa = ultimo.get("Placa")
                    prefixo = ultimo.get("Prefixo")
                    st.session_state.viatura_atual = {"placa": placa, "prefixo": prefixo}
                    st.info(f"Detectada última viatura do checklist de hoje: {prefixo} - {placa}")

            if not placa or not prefixo:
                st.warning("Nenhuma viatura detectada para hoje. Selecione abaixo:")
                viaturas = carregar_viaturas()
                viaturas_ativas = [v for v in viaturas if v.get("Status") == "Ativa"]
                if not viaturas_ativas:
                    st.info("Cadastre viaturas ativas para continuar.")
                else:
                    tipos_disponiveis = [t for t in TIPOS_SERVICO if any(v.get("TipoServico") == t for v in viaturas_ativas)]
                    tipo_escolhido_abast = st.selectbox("Tipo de serviço", ["-- Selecione --"] + tipos_disponiveis)
                    if tipo_escolhido_abast and tipo_escolhido_abast != "-- Selecione --":
                        viaturas_filtradas = [v for v in viaturas_ativas if v.get("TipoServico") == tipo_escolhido_abast]
                        opcoes = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_filtradas]
                        escolha = st.selectbox("Viatura", ["-- Selecione --"] + opcoes)
                        if escolha and escolha != "-- Selecione --":
                            v = next((x for x in viaturas_filtradas if f"{x.get('Prefixo','')} - {x.get('Placa','')}" == escolha), None)
                            if v:
                                placa = v.get("Placa"); prefixo = v.get("Prefixo")
                                st.session_state.viatura_atual = {"placa": placa, "prefixo": prefixo}
            else:
                viaturas = carregar_viaturas()
                v_match = next((v for v in viaturas if v.get("Placa") == placa), None)
                tipo_escolhido_abast = v_match.get("TipoServico") if v_match else "SAMU"

            if placa and prefixo:
                st.success(f"Registrando abastecimento para: {prefixo} - {placa}")
                ultimo_km_check = obter_ultimo_km_checklist(placa)
                ultimo_km_abast = obter_ultimo_km_abastecimento(placa)
                if ultimo_km_check > 0: st.info(f"Último km de checklist: {ultimo_km_check} km.")
                if ultimo_km_abast > 0: st.info(f"Último km de abastecimento: {ultimo_km_abast} km.")

                km_abast = st.number_input("Quilometragem no abastecimento", min_value=0, step=1)
                litros   = st.number_input("Litros abastecidos", min_value=0.0, step=0.1, format="%.1f")
                valor    = st.number_input("Valor total (R$)", min_value=0.0, step=0.01, format="%.2f")

                if st.button("Salvar abastecimento"):
                    if km_abast <= 0 or litros <= 0 or valor <= 0:
                        st.error("Informe valores válidos para km, litros e valor."); tocar_alerta()
                    elif ultimo_km_check and km_abast < ultimo_km_check:
                        st.error(f"O km do abastecimento ({km_abast}) não pode ser menor que o último checklist ({ultimo_km_check})."); tocar_alerta()
                    elif ultimo_km_abast and km_abast < ultimo_km_abast:
                        st.error(f"O km do abastecimento ({km_abast}) não pode ser menor que o último abastecimento ({ultimo_km_abast})."); tocar_alerta()
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

    # Dashboard Manutenção (Admin)
    if st.session_state.usuario.get("admin", False):
        st.markdown("---")
        st.subheader("📊 Dashboard de manutenção")
        viaturas_dash = carregar_viaturas()
        dados_dashboard = []
        for v in viaturas_dash:
            placa_v = v.get("Placa"); prefixo_v = v.get("Prefixo"); tipo_v = v.get("TipoServico", "SAMU")
            if not placa_v: continue
            ultimo_km_v = obter_ultimo_km_checklist(placa_v)
            ultima_troca_v = obter_ultima_troca(placa_v)
            intervalo_v = INTERVALOS_TROCA.get(tipo_v, 10000)
            proxima_troca_v = (ultima_troca_v + intervalo_v) if ultima_troca_v > 0 else ((max(ultimo_km_v, 0) // intervalo_v) + 1) * intervalo_v
            faltam_v = proxima_troca_v - ultimo_km_v
            if ultimo_km_v < proxima_troca_v - TOLERANCIA_ALERTA: status_oleo = "✅ OK"
            elif proxima_troca_v - TOLERANCIA_ALERTA <= ultimo_km_v <= proxima_troca_v + TOLERANCIA_ALERTA: status_oleo = "⚠️ Atenção"
            else: status_oleo = "🚨 Urgente"
            dados_dashboard.append({
                "Prefixo": prefixo_v, "Placa": placa_v, "Tipo": tipo_v,
                "Último KM": ultimo_km_v,
                "Última troca": ultima_troca_v if ultima_troca_v > 0 else "—",
                "Próxima troca": proxima_troca_v,
                "Faltam (km)": faltam_v,
                "Status óleo": status_oleo
            })
        if dados_dashboard: st.dataframe(pd.DataFrame(dados_dashboard), use_container_width=True)
        else: st.info("Nenhuma viatura cadastrada ainda.")

    # Histórico de Viaturas (Admin)
    if st.session_state.usuario.get("admin", False):
        st.markdown("---")
        st.subheader("📜 Histórico de viaturas")
        viaturas_hist = carregar_viaturas()
        opcoes_hist = [f"{v.get('Prefixo','')} - {v.get('Placa','')}" for v in viaturas_hist]
        escolha_hist = st.selectbox("Selecione a viatura", ["-- Selecione --"] + opcoes_hist)
        if escolha_hist and escolha_hist != "-- Selecione --":
            viatura_sel = next((v for v in viaturas_hist if f"{v.get('Prefixo','')} - {v.get('Placa','')}" == escolha_hist), None)
            if viatura_sel:
                placa_sel = viatura_sel.get("Placa")
                st.markdown("### ✅ Checklists")
                registros_check = [r.get("fields", {}) for r in checklists_table.all(sort=["-Data"]) if r.get("fields", {}).get("Placa") == placa_sel]
                st.dataframe(pd.DataFrame(registros_check), use_container_width=True) if registros_check else st.info("Nenhum checklist registrado para esta viatura.")

                st.markdown("### 🛢️ Trocas de óleo")
                registros_troca = [r.get("fields", {}) for r in trocaoleo_table.all(sort=["-data"]) if r.get("fields", {}).get("Placa") == placa_sel]
                st.dataframe(pd.DataFrame(registros_troca), use_container_width=True) if registros_troca else st.info("Nenhuma troca de óleo registrada para esta viatura.")

                if has_abastecimentos:
                    st.markdown("### ⛽ Abastecimentos")
                    registros_abast = [r.get("fields", {}) for r in abastecimentos_table.all(sort=["-Data"]) if r.get("fields", {}).get("Placa") == placa_sel]
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

    st.markdown("---")
    if st.button("Sair"):
        st.session_state.usuario = None
        st.session_state.tela = "login"
        st.session_state.viatura_atual = None
        st.rerun()



