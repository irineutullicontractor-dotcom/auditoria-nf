import streamlit as st
import pandas as pd
import io

# Configuração da página
st.set_page_config(page_title="Auditoria Master NF", layout="wide")

st.title("📊 Auditoria Master de Notas Fiscais")
st.markdown("""
Arraste os 4 relatórios abaixo para processar a conferência automática.
A aba de **Oficina** consolidará os pedidos numa única linha e verificará se a NF já foi resolvida no **Painel**.
""")

# --- UPLOAD DOS FICHEIROS ---
col1, col2 = st.columns(2)
with col1:
    file_nf = st.file_uploader("1. Relatório de NFs (Ex: 01.03 a 10.03)", type=['xlsx', 'csv'])
    file_forn = st.file_uploader("2. Cadastro de Fornecedores", type=['xlsx', 'csv'])
with col2:
    file_painel = st.file_uploader("3. Relatório Painel", type=['xlsx', 'csv'])
    file_relacao = st.file_uploader("4. Relatório Relação/Oficina", type=['xlsx', 'csv'])

def carregar(file):
    if file is None: return None
    if file.name.endswith('.csv'):
        return pd.read_csv(file)
    return pd.read_excel(file)

if st.button("🚀 Processar Auditoria"):
    if not all([file_nf, file_forn, file_painel, file_relacao]):
        st.error("Por favor, carregue os 4 ficheiros antes de processar.")
    else:
        # Carregamento
        df_nf = carregar(file_nf)
        df_forn = carregar(file_forn)
        df_painel = carregar(file_painel)
        df_relacao = carregar(file_relacao)

        # Mapeamento
        NF_NUMERO, NF_CNPJ, NF_FORN, NF_DATA, NF_VALOR = 'Número (nNFSe)', 'Prestador (CNPJ / CPF)', 'Prestador (xNome)', 'Data da Emissão (dhEmi)', 'Valor Serviço (vServ)'
        PED_FORN_PAINEL, PED_NUM_PAINEL, PED_NF_REF = 'Fornecedor', 'N° do Pedido', 'N° da Nota fiscal'
        PED_FORN_REL, PED_NUM_REL = 'Cód. fornecedor', 'Nº do pedido'
        FORN_COD, FORN_CNPJ, FORN_CRED = 'Cód. Fornecedor', 'CNPJCPF', 'Credor'

        # Limpezas
        def limpar_cnpj(v):
            num = "".join(filter(str.isdigit, str(v)))
            return num.zfill(14) if len(num) > 11 else num.zfill(11)

        def limpar_cod(v):
            return str(v).split('.')[0].strip().lstrip('0')

        def extrair_nf(v):
            if pd.isna(v) or v == "": return ""
            return "".join(filter(str.isdigit, str(v).split('/')[-1])).strip()

        df_nf[NF_CNPJ] = df_nf[NF_CNPJ].apply(limpar_cnpj)
        df_nf['nf_limpa'] = df_nf[NF_NUMERO].astype(str).str.strip()
        df_forn[FORN_CNPJ] = df_forn[FORN_CNPJ].apply(limpar_cnpj)
        df_forn[FORN_COD] = df_forn[FORN_COD].apply(limpar_cod)
        df_forn[FORN_CRED] = df_forn[FORN_CRED].str.strip().str.upper()

        # --- LÓGICA PAINEL ---
        df_painel[PED_FORN_PAINEL] = df_painel[PED_FORN_PAINEL].str.strip().str.upper()
        df_painel['nf_extraida'] = df_painel[PED_NF_REF].apply(extrair_nf)
        painel_com_cnpj = pd.merge(df_painel, df_forn[[FORN_CRED, FORN_CNPJ]], left_on=PED_FORN_PAINEL, right_on=FORN_CRED, how='left')
        painel_com_cnpj['chave'] = painel_com_cnpj[FORN_CNPJ] + "_" + painel_com_cnpj['nf_extraida']
        df_nf['chave'] = df_nf[NF_CNPJ] + "_" + df_nf['nf_limpa']

        match_exato = pd.merge(df_nf, painel_com_cnpj, on='chave', how='inner')
        match_exato['Status'] = "✅ NF Lançada"
        
        nfs_restantes = df_nf[~df_nf['chave'].isin(match_exato['chave'])]
        peds_disponiveis = painel_com_cnpj[~painel_com_cnpj[PED_NUM_PAINEL].isin(match_exato[PED_NUM_PAINEL].unique())]
        sugestoes_painel = pd.merge(nfs_restantes, peds_disponiveis, left_on=NF_CNPJ, right_on=FORN_CNPJ, how='left')
        sugestoes_painel['Status'] = sugestoes_painel[PED_NUM_PAINEL].apply(lambda x: "⚠️ Pedido Encontrado" if pd.notna(x) else "❌ Sem Pedido")
        
        resumo_painel = pd.concat([match_exato, sugestoes_painel], ignore_index=True)
        resumo_painel = resumo_painel[[NF_NUMERO, NF_CNPJ, NF_FORN, NF_DATA, PED_NUM_PAINEL, PED_NF_REF, NF_VALOR, 'Status']].drop_duplicates()

        # --- LÓGICA OFICINA ---
        df_relacao[PED_FORN_REL] = df_relacao[PED_FORN_REL].apply(limpar_cod)
        rel_com_cnpj = pd.merge(df_relacao, df_forn[[FORN_COD, FORN_CNPJ]], left_on=PED_FORN_REL, right_on=FORN_COD, how='left')
        peds_agrupados = rel_com_cnpj.groupby(FORN_CNPJ)[PED_NUM_REL].apply(lambda x: ", ".join(set(x.astype(str).unique()))).reset_index()
        resumo_relacao = pd.merge(df_nf, peds_agrupados, left_on=NF_CNPJ, right_on=FORN_CNPJ, how='left')
        
        resolvidas = match_exato['nf_limpa'].unique()
        resumo_relacao['Status'] = resumo_relacao.apply(lambda r: "✅ Resolvido no Painel" if r['nf_limpa'] in resolvidas else ("⚠️ Pendente (Oficina)" if pd.notna(r[PED_NUM_REL]) else "❌ Sem Pedido Oficina"), axis=1)
        resumo_relacao = resumo_relacao[[NF_NUMERO, NF_CNPJ, NF_FORN, NF_DATA, PED_NUM_REL, NF_VALOR, 'Status']]

        # --- DOWNLOAD ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            resumo_painel.to_excel(writer, sheet_name='1. PAINEL', index=False)
            resumo_relacao.to_excel(writer, sheet_name='2. OFICINA', index=False)
        
        st.success("Conferência concluída!")
        st.download_button(label="📥 Baixar Relatório Consolidado", data=output.getvalue(), file_name="AUDITORIA_MASTER.xlsx", mime="application/vnd.ms-excel")
