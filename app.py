import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extrator", layout="wide")
st.title("📊 Extrator de Comprovantes")

def parse_valor(v):
    if not v: return 0.0
    try: return float(str(v).replace('.','').replace(',','.'))
    except: return 0.0

def extrair(fb):
    return "\n".join([p.get_text("text") for p in fitz.open(stream=fb, filetype="pdf")])

def get(pat, txt):
    m = re.search(pat, txt, re.I|re.S)
    return m.group(1).strip() if m else ''

def processar(txt):
    res = []
    for p in re.split(r'(?=COMPROVANTE|2ª Via|Via Gerenciador)', txt):
        if len(p)<30: continue
        d = dict.fromkeys(['Banco','Tipo','Beneficiário','CNPJ/CPF','Data Vencimento','Data Pagamento',
                          'Nr Documento','Valor Nominal','Juros','Multa','Desconto','Abatimento','Valor Pago',
                          'Descrição','Observação'], '')
        d.update({k:0 for k in ['Valor Nominal','Juros','Multa','Desconto','Abatimento','Valor Pago']})

        # BB - CORREÇÃO AQUI
        if 'PAGAMENTO DE TITULOS' in p:
            d['Banco']='BB'; d['Tipo']='Título'
            d['Beneficiário']=get(r'BENEFICIARIO:\s*\n(.*?)\n',p)
            d['CNPJ/CPF']=get(r'CNPJ:\s*([\d\./-]+)',p)
            d['Data Vencimento']=get(r'DATA DE VENCIMENTO\s+(\d{2}/\d{4})',p) # <-- AGORA PEGA 02/02/2026
            d['Data Pagamento']=get(r'DATA DO PAGAMENTO\s+(\d{2}/\d{4})',p) # <-- AGORA PEGA 02/02/2026
            d['Nr Documento']=get(r'NR\. DOCUMENTO\s+([\d\.]+)',p)
            d['Valor Nominal']=parse_valor(get(r'VALOR DO DOCUMENTO\s+([\d\.,]+)',p))
            d['Valor Pago']=parse_valor(get(r'VALOR COBRADO\s+([\d\.,]+)',p))
            d['Juros']=d['Valor Pago']-d['Valor Nominal']

        # CAIXA BOLETO
        elif 'Comprovante de Pagamento de Boleto' in p:
            d['Banco']='CAIXA'; d['Tipo']='Boleto'
            d['Beneficiário']=get(r'Nome/Razão Social:\s*(.*)',p)
            d['CNPJ/CPF']=get(r'CPF/CNPJ:\s*([\d\./-]+)',p)
            d['Data Vencimento']=get(r'Data do Vencimento:\s*(\d{2}/\d{4})',p)
            d['Data Pagamento']=get(r'Data de Efetivação.*?(\d{2}/\d{4})',p)
            d['Nr Documento']=get(r'Código da operação:\s*(\d+)',p)
            d['Valor Nominal']=parse_valor(get(r'Valor Nominal.*?([\d\.,]+)',p))
            d['Valor Pago']=parse_valor(get(r'Valor Pago.*?([\d\.,]+)',p))

        # CAIXA PIX
        elif 'Gerenciador CAIXA' in p:
            d['Banco']='CAIXA'; d['Tipo']='Pix'
            d['Beneficiário']=get(r'Destino\s+Nome:\s*(.*)',p)
            d['Data Pagamento']=get(r'Data e Hora:\s*(\d{2}/\d{4})',p)
            d['Nr Documento']=get(r'ID da transação:\s*(\S+)',p)
            d['Valor Pago']=parse_valor(get(r'Valor Original.*?([\d\.,]+)',p))
            d['Valor Nominal']=d['Valor Pago']
            d['Descrição']=get(r'Detalhes:\s*(.*)',p)

        # SICOOB
        elif 'SICOOB' in p and 'PAGAMENTO DE BOLETO' in p:
            d['Banco']='SICOOB'; d['Tipo']='Boleto'
            d['Beneficiário']=get(r'Nome/Razão Social:\s*(.*)',p)
            d['Data Vencimento']=get(r'Vencimento:\s*(\d{2}/\d{4})',p)
            d['Data Pagamento']=get(r'Pagamento:\s*(\d{2}/\d{4})',p)
            d['Nr Documento']=get(r'Número do agendamento:\s*(\d+)',p)
            d['Valor Nominal']=parse_valor(get(r'Documento:\s*R\$\s*([\d\.,]+)',p))
            d['Valor Pago']=parse_valor(get(r'Pago:\s*R\$\s*([\d\.,]+)',p))

        res.append(d)
    return res

ups = st.file_uploader("Envie PDFs", type="pdf", accept_multiple_files=True)
if ups:
    dados=[]
    for f in ups: dados.extend(processar(extrair(f.read())))
    df = pd.DataFrame(dados)
    for c in ['Valor Nominal','Juros','Multa','Desconto','Abatimento','Valor Pago']:
        df[c]=pd.to_numeric(df[c], errors='coerce').fillna(0)

    st.dataframe(df, use_container_width=True)

    out=BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as w:
        df.to_excel(w,index=False)
        ws=w.sheets['Sheet1']
        for col in ['H','I','J','K','L','M']:
            for cell in ws[col][1:]: cell.number_format='#.##0,00'
    st.download_button("Baixar Excel", out.getvalue(), "comprovantes.xlsx")
