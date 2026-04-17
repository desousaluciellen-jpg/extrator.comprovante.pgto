import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extrator Completo", layout="wide")
st.title("📊 Extrator de Comprovantes Detalhado")

def parse_valor(v):
    if not v: return 0.0
    try:
        return float(str(v).replace('.','').replace(',','.'))
    except:
        return 0.0

def extrair(file_bytes):
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        return "\n".join([p.get_text("text") for p in doc])
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return ""

def safe_search(pattern, text, group=1, default=''):
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(group).strip() if m else default

def processar(texto):
    comps = []
    blocos = texto.split('COMPROVANTE') if 'COMPROVANTE' in texto else [texto]

    for b in blocos:
        d = {
            'Banco':'', 'Tipo':'', 'Beneficiário':'', 'CNPJ/CPF':'',
            'Data Vencimento':'', 'Data Pagamento':'',
            'Valor Nominal':0, 'Juros':0, 'Multa':0, 'Desconto':0, 'Abatimento':0, 'Valor Pago':0,
            'Descrição':'', 'Observação':''
        }

        # CAIXA BOLETO
        if 'Pagamento de Boleto' in b and 'CAIXA' in b:
            d['Banco'] = 'CAIXA'
            d['Tipo'] = 'Boleto'
            d['Beneficiário'] = safe_search(r'Nome/Razão Social:\s*(.*?)\n', b)
            d['CNPJ/CPF'] = safe_search(r'CPF/CNPJ:\s*([\d\./-]+)', b)
            d['Data Vencimento'] = safe_search(r'Data do Vencimento:\s*(\d{2}/\d{4})', b)
            d['Data Pagamento'] = safe_search(r'Data de Efetivação.*?:\s*(\d{2}/\d{2}/\d{4})', b)
            d['Valor Nominal'] = parse_valor(safe_search(r'Valor Nominal.*?:\s*([\d\.,]+)', b))
            d['Juros'] = parse_valor(safe_search(r'Juros.*?:\s*([\d\.,]+)', b))
            d['Multa'] = parse_valor(safe_search(r'Multa.*?:\s*([\d\.,]+)', b))
            d['Desconto'] = parse_valor(safe_search(r'Desconto.*?:\s*([\d\.,]+)', b))
            d['Abatimento'] = parse_valor(safe_search(r'Abatimento.*?:\s*([\d\.,]+)', b))
            d['Valor Pago'] = parse_valor(safe_search(r'Valor Pago.*?:\s*([\d\.,]+)', b))
            d['Observação'] = safe_search(r'Código da operação:\s*(\d+)', b)
            comps.append(d)

        # CAIXA PIX - CORRIGIDO
        elif 'Gerenciador CAIXA' in b and 'Pix' in b:
            d['Banco'] = 'CAIXA'
            d['Tipo'] = 'Pix'
            d['Beneficiário'] = safe_search(r'Destino\s+Nome:\s*(.*?)\n', b)
            d['CNPJ/CPF'] = safe_search(r'(?:CPF|CNPJ):\s*([X\d\.\/-]+)', b)
            # CORREÇÃO AQUI - data completa
            d['Data Pagamento'] = safe_search(r'Data e Hora:\s*(\d{2}/\d{4})', b)
            d['Valor Nominal'] = parse_valor(safe_search(r'Valor Original:\s*R\$\s*([\d\.,]+)', b))
            d['Valor Pago'] = d['Valor Nominal']
            d['Descrição'] = safe_search(r'Detalhes:\s*(.*?)\n', b)
            d['Observação'] = safe_search(r'ID da transação:\s*(\S+)', b)
            comps.append(d)

        # SICOOB
        elif 'SICOOB' in b and 'PAGAMENTO DE BOLETO' in b:
            d['Banco'] = 'SICOOB'
            d['Tipo'] = 'Boleto'
            d['Beneficiário'] = safe_search(r'Nome/Razão Social:\s*(.*?)\n', b)
            d['CNPJ/CPF'] = safe_search(r'CPF/CNPJ:\s*([\d\./-]+)', b)
            d['Data Vencimento'] = safe_search(r'Vencimento:\s*(\d{2}/\d{4})', b)
            d['Data Pagamento'] = safe_search(r'Pagamento:\s*(\d{2}/\d{4})', b)
            d['Valor Nominal'] = parse_valor(safe_search(r'Documento:\s*R\$\s*([\d\.,]+)', b))
            d['Juros'] = parse_valor(safe_search(r'Juros/Multa:\s*R\$\s*([\d\.,]+)', b))
            d['Desconto'] = parse_valor(safe_search(r'Desconto/Abatimento:\s*R\$\s*([\d\.,]+)', b))
            d['Valor Pago'] = parse_valor(safe_search(r'Pago:\s*R\$\s*([\d\.,]+)', b))
            comps.append(d)

        # BB
        elif 'PAGAMENTO DE TITULOS' in b:
            d['Banco'] = 'BB'
            d['Tipo'] = 'Título'
            d['Beneficiário'] = safe_search(r'BENEFICIARIO:\s*\n(.*?)\n', b)
            d['CNPJ/CPF'] = safe_search(r'CNPJ:\s*([\d\./-]+)', b)
            d['Data Vencimento'] = safe_search(r'DATA DE VENCIMENTO\s+(\d{2}/\d{4})', b)
            d['Data Pagamento'] = safe_search(r'DATA DO PAGAMENTO\s+(\d{2}/\d{4})', b)
            d['Valor Nominal'] = parse_valor(safe_search(r'VALOR DO DOCUMENTO\s+([\d\.,]+)', b))
            d['Valor Pago'] = parse_valor(safe_search(r'VALOR COBRADO\s+([\d\.,]+)', b))
            d['Juros'] = d['Valor Pago'] - d['Valor Nominal']
            comps.append(d)

    return comps

uploaded = st.file_uploader("Envie seus PDFs", type="pdf", accept_multiple_files=True)

if uploaded:
    todos = []
    for f in uploaded:
        texto = extrair(f.read())
        todos.extend(processar(texto))

    if todos:
        df = pd.DataFrame(todos)

        # Formatar valores para padrão brasileiro na exibição
        df_display = df.copy()
        for col in ['Valor Nominal','Juros','Multa','Desconto','Abatimento','Valor Pago']:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}".replace(',','X').replace('.',',').replace('X','.'))

        st.success(f"{len(df)} comprovantes processados")
        st.dataframe(df_display, use_container_width=True)

        # Excel com formatação brasileira
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Detalhado')
            ws = writer.sheets['Detalhado']
            for col in ['G','H','I','J','K','L']: # colunas de valores
                for cell in ws[col][1:]:
                    cell.number_format = '#.##0,00'

        st.download_button("📥 Baixar Excel", output.getvalue(),
                          file_name="relatorio_completo.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("Nenhum dado encontrado nos PDFs")
