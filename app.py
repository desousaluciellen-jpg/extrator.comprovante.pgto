import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extrator", layout="wide")
st.title("📊 Extrator Detalhado")

def parse_valor(v):
    if not v: return 0.0
    return float(str(v).replace('.','').replace(',','.'))

def extrair(fb):
    doc = fitz.open(stream=fb, filetype="pdf")
    return "\n".join([p.get_text("text") for p in doc])

def get(pattern, txt):
    m = re.search(pattern, txt, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ''

def processar(txt):
    res = []
    # divide pelos comprovantes
    partes = re.split(r'(?=COMPROVANTE|SISBB|2ª Via)', txt)

    for p in partes:
        if len(p) < 50: continue
        d = {k:'' for k in ['Banco','Tipo','Beneficiário','CNPJ/CPF','Data Vencimento','Data Pagamento',
                           'Nr Documento','Valor Nominal','Juros','Multa','Desconto','Abatimento','Valor Pago',
                           'Descrição','Observação']}

        # CAIXA BOLETO
        if 'Comprovante de Pagamento de Boleto' in p:
            d['Banco'] = 'CAIXA'; d['Tipo']='Boleto'
            d['Beneficiário'] = get(r'Nome/Razão Social:\s*(.*)', p)
            d['CNPJ/CPF'] = get(r'CPF/CNPJ:\s*([\d\./-]+)', p)
            d['Data Vencimento'] = get(r'Data do Vencimento:\s*(\d{2}/\d{4})', p)
            d['Data Pagamento'] = get(r'Data de Efetivação.*?(\d{2}/\d{4})', p)
            d['Nr Documento'] = get(r'Código da operação:\s*(\d+)', p)
            d['Valor Nominal'] = parse_valor(get(r'Valor Nominal.*?([\d\.,]+)', p))
            d['Juros'] = parse_valor(get(r'Juros.*?([\d\.,]+)', p))
            d['Multa'] = parse_valor(get(r'Multa.*?([\d\.,]+)', p))
            d['Desconto'] = parse_valor(get(r'Desconto.*?([\d\.,]+)', p))
            d['Abatimento'] = parse_valor(get(r'Abatimento.*?([\d\.,]+)', p))
            d['Valor Pago'] = parse_valor(get(r'Valor Pago.*?([\d\.,]+)', p))
            res.append(d)

        # CAIXA PIX
        elif 'Via Gerenciador CAIXA' in p:
            d['Banco'] = 'CAIXA'; d['Tipo']='Pix'
            d['Beneficiário'] = get(r'Destino\s+Nome:\s*(.*)', p)
            d['CNPJ/CPF'] = get(r'CPF:\s*([X\d\.\-]+)|CNPJ:\s*([\d\./-]+)', p)
            d['Data Pagamento'] = get(r'Data e Hora:\s*(\d{2}/\d{4})', p)
            d['Data Vencimento'] = ''
            d['Nr Documento'] = get(r'ID da transação:\s*(\S+)', p)
            d['Valor Nominal'] = parse_valor(get(r'Valor Original.*?([\d\.,]+)', p))
            d['Valor Pago'] = d['Valor Nominal']
            d['Descrição'] = get(r'Detalhes:\s*(.*)', p)
            res.append(d)

        # SICOOB
        elif 'SICOOB' in p and 'PAGAMENTO DE BOLETO' in p:
            d['Banco'] = 'SICOOB'; d['Tipo']='Boleto'
            d['Beneficiário'] = get(r'Nome/Razão Social:\s*(.*)', p)
            d['CNPJ/CPF'] = get(r'CPF/CNPJ:\s*([\d\./-]+)', p)
            d['Data Vencimento'] = get(r'Vencimento:\s*(\d{2}/\d{4})', p)
            d['Data Pagamento'] = get(r'Pagamento:\s*(\d{2}/\d{2}/\d{4})', p)
            d['Nr Documento'] = get(r'Número do agendamento:\s*(\d+)', p)
            d['Valor Nominal'] = parse_valor(get(r'Documento:\s*R\$\s*([\d\.,]+)', p))
            d['Juros'] = parse_valor(get(r'Juros/Multa:\s*R\$\s*([\d\.,]+)', p))
            d['Desconto'] = parse_valor(get(r'Desconto/Abatimento:\s*R\$\s*([\d\.,]+)', p))
            d['Valor Pago'] = parse_valor(get(r'Pago:\s*R\$\s*([\d\.,]+)', p))
            res.append(d)

        # BB TITULOS
        elif 'PAGAMENTO DE TITULOS' in p:
            d['Banco']='BB'; d['Tipo']='Título'
            d['Beneficiário'] = get(r'BENEFICIARIO:\s*\n(.*?)\n', p)
            d['CNPJ/CPF'] = get(r'CNPJ:\s*([\d\./-]+)', p)
            d['Data Vencimento'] = get(r'DATA DE VENCIMENTO\s+(\d{2}/\d{2}/\d{4})', p)
            d['Data Pagamento'] = get(r'DATA DO PAGAMENTO\s+(\d{2}/\d{4})', p)
            d['Nr Documento'] = get(r'NR\. DOCUMENTO\s+([\d\.]+)', p)
            d['Valor Nominal'] = parse_valor(get(r'VALOR DO DOCUMENTO\s+([\d\.,]+)', p))
            d['Valor Pago'] = parse_valor(get(r'VALOR COBRADO\s+([\d\.,]+)', p))
            res.append(d)

    return res

ups = st.file_uploader("PDFs", type="pdf", accept_multiple_files=True)
if ups:
    all_data = []
    for f in ups:
        all_data.extend(processar(extrair(f.read())))

    df = pd.DataFrame(all_data)
    st.dataframe(df, use_container_width=True)

    # Excel formatado
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as w:
        df.to_excel(w, index=False)
        ws = w.sheets['Sheet1']
        for col in 'HIJKLM': # colunas de valores
            for c in ws[col][1:]:
                c.number_format = '#.##0,00'
    st.download_button("Baixar Excel", out.getvalue(), "relatorio.xlsx")
