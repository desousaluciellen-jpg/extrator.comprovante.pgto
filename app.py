import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO
from openpyxl.styles import numbers

st.set_page_config(page_title="Extrator Completo", layout="wide")
st.title("📊 Extrator de Comprovantes Detalhado")

def parse_valor(v):
    if not v: return 0.0
    return float(str(v).replace('.','').replace(',','.'))

def extrair(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    txt = "\n".join([p.get_text("text") for p in doc])
    return txt

def processar(texto):
    comps = []
    for b in texto.split('---PAGINA---') + [texto]:
        d = {}

        # === CAIXA BOLETO (mais completo) ===
        if 'Comprovante de Pagamento de Boleto' in b and 'CAIXA' in b:
            d['Banco'] = 'CAIXA'
            d['Tipo'] = 'Boleto'
            d['Beneficiário'] = re.search(r'Nome/Razão Social:\s*(.*?)\n', b).group(1).strip() if re.search(r'Nome/Razão Social:\s*(.*?)\n', b) else ''
            d['CNPJ/CPF'] = re.search(r'CPF/CNPJ:\s*([\d\./-]+)', b).group(1) if re.search(r'CPF/CNPJ:\s*([\d\./-]+)', b) else ''
            d['Data Vencimento'] = re.search(r'Data do Vencimento:\s*(\d{2}/\d{4})', b).group(1) if re.search(r'Data do Vencimento', b) else ''
            d['Data Pagamento'] = re.search(r'Data de Efetivação.*?:\s*(\d{2}/\d{4})', b).group(1) if re.search(r'Data de Efetivação', b) else ''
            d['Valor Nominal'] = parse_valor(re.search(r'Valor Nominal.*?:\s*([\d\.,]+)', b).group(1)) if re.search(r'Valor Nominal', b) else 0
            d['Juros'] = parse_valor(re.search(r'Juros.*?:\s*([\d\.,]+)', b).group(1)) if re.search(r'Juros', b) else 0
            d['Multa'] = parse_valor(re.search(r'Multa.*?:\s*([\d\.,]+)', b).group(1)) if re.search(r'Multa', b) else 0
            d['Desconto'] = parse_valor(re.search(r'Desconto.*?:\s*([\d\.,]+)', b).group(1)) if re.search(r'Desconto', b) else 0
            d['Abatimento'] = parse_valor(re.search(r'Abatimento.*?:\s*([\d\.,]+)', b).group(1)) if re.search(r'Abatimento', b) else 0
            d['Valor Pago'] = parse_valor(re.search(r'Valor Pago.*?:\s*([\d\.,]+)', b).group(1)) if re.search(r'Valor Pago', b) else 0
            d['Descrição'] = ''
            d['Observação'] = f"Cód. barras: {re.search(r'Representação numérica.*?:\s*([\d\s]+)', b).group(1).strip()[:30]}..." if re.search(r'Representação', b) else ''
            comps.append(d)

        # === CAIXA PIX ===
        elif 'Via Gerenciador CAIXA' in b and 'Pix' in b:
            d['Banco'] = 'CAIXA'
            d['Tipo'] = 'Pix'
            d['Beneficiário'] = re.search(r'Destino\s+Nome:\s*(.*?)\n', b).group(1).strip() if re.search(r'Destino', b) else ''
            d['CNPJ/CPF'] = re.search(r'CPF:\s*([X\d\.\-]+)|CNPJ:\s*([\d\./-]+)', b).group(0) if re.search(r'CPF|CNPJ', b) else ''
            d['Data Pagamento'] = re.search(r'Data e Hora:\s*(\d{2}/\d{4})', b).group(1) if re.search(r'Data e Hora', b) else ''
            d['Data Vencimento'] = ''
            d['Valor Nominal'] = parse_valor(re.search(r'Valor Original:\s*R\$\s*([\d\.,]+)', b).group(1)) if re.search(r'Valor Original', b) else 0
            d['Valor Pago'] = d['Valor Nominal']
            d['Juros'] = d['Multa'] = d['Desconto'] = d['Abatimento'] = 0
            d['Descrição'] = re.search(r'Detalhes:\s*(.*?)\n', b).group(1).strip() if re.search(r'Detalhes:', b) else ''
            d['Observação'] = f"ID: {re.search(r'ID da transação:\s*(\S+)', b).group(1)}" if re.search(r'ID da', b) else ''
            comps.append(d)

        # === SICOOB BOLETO ===
        elif 'SICOOB' in b and 'PAGAMENTO DE BOLETO' in b:
            d['Banco'] = 'SICOOB'
            d['Tipo'] = 'Boleto'
            d['Beneficiário'] = re.search(r'Nome/Razão Social:\s*(.*?)\n', b).group(1).strip() if re.search(r'Nome/Razão', b) else ''
            d['CNPJ/CPF'] = re.search(r'CPF/CNPJ:\s*([\d\./-]+)', b).group(1) if re.search(r'CPF/CNPJ', b) else ''
            d['Data Vencimento'] = re.search(r'Vencimento:\s*(\d{2}/\d{2}/\d{4})', b).group(1) if re.search(r'Vencimento', b) else ''
            d['Data Pagamento'] = re.search(r'Pagamento:\s*(\d{2}/\d{4})', b).group(1) if re.search(r'Pagamento', b) else ''
            d['Valor Nominal'] = parse_valor(re.search(r'Documento:\s*R\$\s*([\d\.,]+)', b).group(1)) if re.search(r'Documento:', b) else 0
            d['Juros'] = parse_valor(re.search(r'Juros/Multa:\s*R\$\s*([\d\.,]+)', b).group(1)) if re.search(r'Juros/Multa', b) else 0
            d['Multa'] = 0
            d['Desconto'] = parse_valor(re.search(r'Desconto/Abatimento:\s*R\$\s*([\d\.,]+)', b).group(1)) if re.search(r'Desconto', b) else 0
            d['Abatimento'] = 0
            d['Valor Pago'] = parse_valor(re.search(r'Pago:\s*R\$\s*([\d\.,]+)', b).group(1)) if re.search(r'Pago:', b) else 0
            d['Descrição'] = ''
            d['Observação'] = f"Linha: {re.search(r'Linha digitável:\s*([\d\s\.]+)', b).group(1).strip()[:20]}..." if re.search(r'Linha', b) else ''
            comps.append(d)

        # === BB TITULOS ===
        elif 'COMPROVANTE DE PAGAMENTO DE TITULOS' in b:
            d['Banco'] = 'BB'
            d['Tipo'] = 'Título'
            d['Beneficiário'] = re.search(r'BENEFICIARIO:\s*\n(.*?)\n', b).group(1).strip() if re.search(r'BENEFICIARIO', b) else ''
            d['CNPJ/CPF'] = re.search(r'CNPJ:\s*([\d\./-]+)', b).group(1) if re.search(r'CNPJ', b) else ''
            d['Data Vencimento'] = re.search(r'DATA DE VENCIMENTO\s+(\d{2}/\d{2}/\d{4})', b).group(1) if re.search(r'VENCIMENTO', b) else ''
            d['Data Pagamento'] = re.search(r'DATA DO PAGAMENTO\s+(\d{2}/\d{4})', b).group(1) if re.search(r'PAGAMENTO', b) else ''
            d['Valor Nominal'] = parse_valor(re.search(r'VALOR DO DOCUMENTO\s+([\d\.,]+)', b).group(1)) if re.search(r'VALOR DO DOCUMENTO', b) else 0
            d['Valor Pago'] = parse_valor(re.search(r'VALOR COBRADO\s+([\d\.,]+)', b).group(1)) if re.search(r'VALOR COBRADO', b) else 0
            d['Juros'] = d['Valor Pago'] - d['Valor Nominal']
            d['Multa'] = d['Desconto'] = d['Abatimento'] = 0
            d['Descrição'] = ''
            d['Observação'] = ''
            comps.append(d)
    return comps

uploaded = st.file_uploader("Envie PDFs", type="pdf", accept_multiple_files=True)

if uploaded:
    dados = []
    for f in uploaded:
        dados.extend(processar(extrair(f.read())))

    df = pd.DataFrame(dados)
    st.dataframe(df, use_container_width=True)

    # Gerar Excel com formatação brasileira
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Detalhado')
        ws = writer.sheets['Detalhado']
        # Formatar colunas de valor
        for col in ['E','F','G','H','I','J']: # ajuste conforme posição
            for cell in ws[col]:
                cell.number_format = '#.##0,00'

    st.download_button("📥 Baixar Excel (formato brasileiro)", output.getvalue(), "relatorio_detalhado.xlsx")
