import streamlit as st
import pandas as pd
import io

# Configuração da página
st.set_page_config(page_title="Auditoria Master: Painel & Contratos", layout="wide")

st.title("📊 Auditoria Master: Painel & Contratos")
st.markdown("""
### Instruções de uso:
1. Carregue o relatório de **NFs**.
2. Carregue o **Cadastro de Fornecedores**.
3. Carregue o relatório do **Painel**.
4. Carregue o relatório **Bruto de Contratos** (O sistema fará a limpeza automática).
""")

# --- UPLOAD DOS FICHEIROS ---
col1, col2 = st.columns(2)
with col1:
    file_nf = st.file_uploader("1. Relatório de NFs", type=['xlsx', 'csv'])
    file_forn = st.file_uploader("2. Cadastro de Fornecedores", type=['xlsx', 'csv'])
with col2:
    file_painel = st.file_uploader("3. Relatório Painel", type=['xlsx', 'csv'])
    file_contrato = st.file_uploader("4. Relatório Contrato (BRUTO)", type=['xlsx', 'csv'])

def carregar(file, header=0):
    if file is None: return None
    if file.name.endswith('.csv'):
        return pd.read_csv(file)
    return pd.read_excel(file, header=header)

if st.button("🚀 Processar Auditoria"):
    if not all([file_nf, file_forn, file_painel, file_contrato]):
        st.error("Por favor, carregue os 4 arquivos.")
    else:
        # Carregamento
        df_nf = carregar(file_nf)
        df_forn = carregar(file_forn)
        df_painel = carregar(file_painel)
        # O contrato é lido sem header para processar o bruto linha a linha
        df_bruto_contrato = carregar(file_contrato, header=None)

        # --- MAPEAMENTO INTELIGENTE E FLEXÍVEL ---
        
        # 1. Função auxiliar para achar a coluna certa em uma lista de opções
        def encontrar_coluna(df, opcoes):
            for opt in opcoes:
                if opt in df.columns:
                    return opt
            return None

        # 2. Definir as opções para cada campo das NFs (baseado no seu erro atual)
        NF_CNPJ = encontrar_coluna(df_nf, ['CNPJ Prestador (CNPJ)', 'Prestador (CNPJ)', 'Prestador (CNPJ / CPF)', 'CNPJ'])
        NF_NUMERO = encontrar_coluna(df_nf, ['Número NFS-e (nNFSe)', 'Número (nNFSe)', 'nNFSe'])
        NF_FORN = encontrar_coluna(df_nf, ['Nome Prestador (xNome)', 'Prestador (xNome)', 'Razão Social Prestador'])
        NF_DATA = encontrar_coluna(df_nf, ['Data/Hora Emissão DPS (dhEmi)', 'Data da Emissão (dhEmi)', 'dhEmi'])
        NF_VALOR = encontrar_coluna(df_nf, ['Valor do Serviço (vServ) (vServ)', 'Valor Serviço (vServ)', 'vServ'])

        # 3. Verificação de segurança para o campo crítico (CNPJ)
        if not NF_CNPJ:
            st.error(f"❌ Não encontrei a coluna de CNPJ. Colunas lidas: {list(df_nf.columns)}")
            st.stop()
        
        # Se as outras colunas essenciais não forem achadas, usamos o nome que você já tinha como padrão
        NF_NUMERO = NF_NUMERO or 'Número (nNFSe)'
        NF_FORN = NF_FORN or 'Prestador (xNome)'
        NF_DATA = NF_DATA or 'Data da Emissão (dhEmi)'
        NF_VALOR = NF_VALOR or 'Valor Serviço (vServ)'

        # Mapeamento dos outros arquivos (Painel e Fornecedores permanecem igual)
        PED_FORN_PAINEL, PED_NUM_PAINEL, PED_NF_REF = 'Fornecedor', 'N° do Pedido', 'N° da Nota fiscal'
        FORN_COD, FORN_CNPJ, FORN_CRED = 'Cód. Fornecedor', 'CNPJCPF', 'Credor'

        # --- PROCESSAMENTO DO CONTRATO BRUTO ---
        registros = []
        item_atual = {}
        for i, row in df_bruto_contrato.iterrows():
            col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            col_c = str(row[2]).strip() if pd.notna(row[2]) else ""
            col_d = row[3] if pd.notna(row[3]) else ""

            if col_c == "Contrato":
                if item_atual: registros.append(item_atual)
                item_atual = {'Contrato': None, 'CNPJ': None}

            if item_atual:
                if col_a == "Contrato": item_atual['Contrato'] = col_d
                elif col_a == "CNPJ": item_atual['CNPJ'] = col_d

        if item_atual: registros.append(item_atual)
        df_contrato_limpo = pd.DataFrame(registros).dropna(how='all')

        # --- PADRONIZAÇÕES ---
        def limpar_cnpj(v):
            num = "".join(filter(str.isdigit, str(v)))
            return num.zfill(14) if len(num) > 11 else num.zfill(11)

        def extrair_nf(v):
            if pd.isna(v) or v == "": return ""
            return "".join(filter(str.isdigit, str(v).split('/')[-1])).strip()

        df_nf[NF_CNPJ] = df_nf[NF_CNPJ].apply(limpar_cnpj)
        df_nf['nf_limpa'] = df_nf[NF_NUMERO].astype(str).str.strip()
        df_forn[FORN_CNPJ] = df_forn[FORN_CNPJ].apply(limpar_cnpj)
        df_forn[FORN_CRED] = df_forn[FORN_CRED].str.strip().str.upper()
        df_contrato_limpo['CNPJ'] = df_contrato_limpo['CNPJ'].apply(limpar_cnpj)

        # --- BLOCO 1: PAINEL ---
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

        # --- BLOCO 2: CONTRATOS ---
        cts_agrupados = df_contrato_limpo.groupby('CNPJ')['Contrato'].apply(lambda x: ", ".join(set(x.astype(str).unique()))).reset_index()
        resumo_contrato = pd.merge(df_nf, cts_agrupados, left_on=NF_CNPJ, right_on='CNPJ', how='left')
        resolvidas = match_exato['nf_limpa'].unique()
        resumo_contrato['Status'] = resumo_contrato.apply(lambda r: "✅ Resolvido no Painel" if r['nf_limpa'] in resolvidas else ("⚠️ Contrato Encontrado" if pd.notna(r['Contrato']) else "❌ Sem Contrato"), axis=1)
        resumo_contrato = resumo_contrato[[NF_NUMERO, NF_CNPJ, NF_FORN, NF_DATA, 'Contrato', NF_VALOR, 'Status']]

        # --- DOWNLOAD ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            resumo_painel.to_excel(writer, sheet_name='1. PAINEL', index=False)
            resumo_contrato.to_excel(writer, sheet_name='2. CONTRATOS', index=False)
        
        st.success("Auditoria concluída!")
        st.download_button(label="📥 Baixar Relatório Master", data=output.getvalue(), file_name="AUDITORIA_GERAL.xlsx", mime="application/vnd.ms-excel")
