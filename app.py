import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extrator de Comprovantes", layout="wide")
st.title("📄 Extrator de Comprovantes - BB | CAIXA | SICOOB")

def parse_valor(v):
    if not v: return 0.0
    v = str(v).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
    try: return float(v)
    except: return 0.0

def extrair_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    txt = ""
    for p in doc:
        txt += p.get_text("text") + "\n---PAGINA---\n"
    return txt

def extrair_tudo(texto):
    comps = []
    for b in texto.split('---PAGINA---'):
        # BB TITULOS
        if 'COMPROVANTE DE PAGAMENTO DE TITULOS' in b:
            d = {'Banco':'BB','Tipo':'Título'}
            d['Beneficiario'] = re.search(r'BENEFICIARIO:\s*\n(.*?)\n', b).group(1).strip() if re.search(r'BENEFICIARIO:\s*\n(.*?)\n', b) else ''
            d['CNPJ'] = re.search(r'CNPJ:\s*([\d\./-]+)', b).group(1) if re.search(r'CNPJ:\s*([\d\./-]+)', b) else ''
            d['Data'] = re.search(r'DATA DO PAGAMENTO\s+(\d{2}/\d{2}/\d{4})', b).group(1) if re.search(r'DATA DO PAGAMENTO\s+(\d{2}/\d{2}/\d{4})', b) else ''
            d['Valor'] = parse_valor(re.search(r'VALOR COBRADO\s+([\d\.,]+)', b).group(1)) if re.search(r'VALOR COBRADO\s+([\d\.,]+)', b) else 0
            comps.append(d)
        # CAIXA PIX
        elif 'Via Gerenciador CAIXA' in b and 'Pix' in b:
            d = {'Banco':'CAIXA','Tipo':'Pix'}
            d['Data'] = re.search(r'Data e Hora:\s*(\d{2}/\d{4})', b).group(1) if re.search(r'Data e Hora:\s*(\d{2}/\d{4})', b) else ''
            d['Valor'] = parse_valor(re.search(r'Valor Original:\s*R\$\s*([\d\.,]+)', b).group(1)) if re.search(r'Valor Original:\s*R\$\s*([\d\.,]+)', b) else 0
            d['Beneficiario'] = re.search(r'Destino\s+Nome:\s*(.*?)\n', b).group(1).strip() if re.search(r'Destino\s+Nome:\s*(.*?)\n', b) else ''
            d['CNPJ'] = ''
            comps.append(d)
        # CAIXA BOLETO
        elif 'Comprovante de Pagamento de Boleto' in b:
            d = {'Banco':'CAIXA','Tipo':'Boleto'}
            d['Beneficiario'] = re.search(r'Nome/Razão Social:\s*(.*?)\n', b).group(1).strip() if re.search(r'Nome/Razão Social:\s*(.*?)\n', b) else ''
            d['CNPJ'] = re.search(r'CPF/CNPJ:\s*([\d\./-]+)', b).group(1) if re.search(r'CPF/CNPJ:\s*([\d\./-]+)', b) else ''
            d['Data'] = re.search(r'Data de Efetivação.*?:\s*(\d{2}/\d{2}/\d{4})', b).group(1) if re.search(r'Data de Efetivação.*?:\s*(\d{2}/\d{2}/\d{4})', b) else ''
            d['Valor'] = parse_valor(re.search(r'Valor Pago \(R\$\):\s*([\d\.,]+)', b).group(1)) if re.search(r'Valor Pago \(R\$\):\s*([\d\.,]+)', b) else 0
            comps.append(d)
        # SICOOB
        elif 'SICOOB' in b and 'PAGAMENTO DE BOLETO' in b:
            d = {'Banco':'SICOOB','Tipo':'Boleto'}
            d['Beneficiario'] = re.search(r'Nome/Razão Social:\s*(.*?)\n', b).group(1).strip() if re.search(r'Nome/Razão Social:\s*(.*?)\n', b) else ''
            d['CNPJ'] = re.search(r'CPF/CNPJ:\s*([\d\./-]+)', b).group(1) if re.search(r'CPF/CNPJ:\s*([\d\./-]+)', b) else ''
            d['Data'] = re.search(r'Pagamento:\s*(\d{2}/\d{4})', b).group(1) if re.search(r'Pagamento:\s*(\d{2}/\d{4})', b) else ''
            d['Valor'] = parse_valor(re.search(r'Pago:\s*R\$\s*([\d\.,]+)', b).group(1)) if re.search(r'Pago:\s*R\$\s*([\d\.,]+)', b) else 0
            comps.append(d)
    return comps

uploaded = st.file_uploader("Arraste seus PDFs aqui", type="pdf", accept_multiple_files=True)

if uploaded:
    todos = []
    for f in uploaded:
        txt = extrair_pdf(f.read())
        todos.extend(extrair_tudo(txt))
    
    df = pd.DataFrame(todos)
    if not df.empty:
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Pago", f"R$ {df['Valor'].sum():,.2f}")
        col2.metric("Transações", len(df))
        col3.metric("Fornecedores", df['Beneficiario'].nunique())
        
        st.dataframe(df, use_container_width=True)
        
        # Download Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Detalhado')
            df.groupby('Beneficiario')['Valor'].sum().sort_values(ascending=False).to_excel(writer, sheet_name='Por Fornecedor')
        st.download_button("📥 Baixar Excel Completo", output.getvalue(), "relatorio_comprovantes.xlsx")
    else:
        st.warning("Nenhum comprovante reconhecido.")
