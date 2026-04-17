import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO

st.set_page_config(layout="wide")
st.title("Extrator BB/CAIXA/SICOOB")

def parse(v): 
    try: return float(str(v).replace('.','').replace(',','.'))
    except: return 0

def get(rx,tx): 
    m=re.search(rx,tx,re.I|re.S)
    return m.group(1).strip() if m else ''

def proc(txt):
    out=[]
    for p in re.split(r'(?=COMPROVANTE|2ª Via|Via Gerenciador)', txt):
        if len(p)<20: continue
        d={'Banco':'','Tipo':'','Beneficiário':'','CNPJ/CPF':'','Data Vencimento':'','Data Pagamento':'','Nr Documento':'','Valor Nominal':0,'Valor Pago':0}
        
        if 'PAGAMENTO DE TITULOS' in p:
            d['Banco']='BB'; d['Tipo']='Título'
            d['Beneficiário']=get(r'BENEFICIARIO:\s*\n(.*?)\n',p)
            d['CNPJ/CPF']=get(r'CNPJ:\s*([\d\./-]+)',p)
            d['Data Vencimento']=get(r'DATA DE VENCIMENTO\s+(\d{2}/\d{4})',p)  # CORRETO
            d['Data Pagamento']=get(r'DATA DO PAGAMENTO\s+(\d{2}/\d{4})',p)   # CORRETO
            d['Nr Documento']=get(r'NR\. DOCUMENTO\s+([\d\.]+)',p)
            d['Valor Nominal']=parse(get(r'VALOR DO DOCUMENTO\s+([\d\.,]+)',p))
            d['Valor Pago']=parse(get(r'VALOR COBRADO\s+([\d\.,]+)',p))
        
        elif 'Pagamento de Boleto' in p:
            d['Banco']='CAIXA'
            d['Data Vencimento']=get(r'Data do Vencimento:\s*(\d{2}/\d{4})',p)
            d['Data Pagamento']=get(r'Data de Efetivação.*?(\d{2}/\d{4})',p)
            d['Nr Documento']=get(r'Código da operação:\s*(\d+)',p)
            d['Valor Pago']=parse(get(r'Valor Pago.*?([\d\.,]+)',p))
        
        elif 'Gerenciador CAIXA' in p:
            d['Banco']='CAIXA'; d['Tipo']='Pix'
            d['Data Pagamento']=get(r'Data e Hora:\s*(\d{2}/\d{4})',p)
            d['Nr Documento']=get(r'ID da transação:\s*(\S+)',p)
            d['Valor Pago']=parse(get(r'Valor Original.*?([\d\.,]+)',p))
        
        elif 'SICOOB' in p:
            d['Banco']='SICOOB'
            d['Data Vencimento']=get(r'Vencimento:\s*(\d{2}/\d{4})',p)
            d['Data Pagamento']=get(r'Pagamento:\s*(\d{2}/\d{2}/\d{4})',p)
            d['Nr Documento']=get(r'Número do agendamento:\s*(\d+)',p)
            d['Valor Pago']=parse(get(r'Pago:\s*R\$\s*([\d\.,]+)',p))
        
        out.append(d)
    return out

ups=st.file_uploader("PDFs",type="pdf",accept_multiple_files=True)
if ups:
    all=[]
    for f in ups:
        txt="\n".join([p.get_text("text") for p in fitz.open(stream=f.read(),filetype="pdf")])
        all.extend(proc(txt))
    df=pd.DataFrame(all)
    st.dataframe(df)
    out=BytesIO()
    df.to_excel(out,index=False)
    st.download_button("Excel",out.getvalue(),"saida.xlsx")
