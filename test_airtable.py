from pyairtable import Table
import streamlit as st

API_KEY = st.secrets["connections"]["airtable"]["personal_access_token"]
BASE_ID = st.secrets["connections"]["airtable"]["base_id"]
USUARIOS_TABLE_ID = st.secrets["connections"]["airtable"]["usuarios_table_id"]

table = Table(API_KEY, BASE_ID, USUARIOS_TABLE_ID)

try:
    registros = table.all(max_records=1)
    st.write("✅ Conexão OK:", registros)
except Exception as e:

    st.error(f"❌ Erro: {e}")
