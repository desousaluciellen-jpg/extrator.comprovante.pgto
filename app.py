import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extrator Comprovantes", layout="wide")
st.title("📊 Extrator de Comprovantes - BB | CAIXA | SICOOB")

def parse_valor(v):
    if not v: return 0.0
    try:
        return float(str(v).replace('.','').replace(',','.'))
    except:
        return 0.0

def extrair(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join([p.get_text("text") for p in doc])

def get(pattern, txt):
    m = re.search(pattern, txt, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ''

def processar(txt):
    res = []
    partes = re.split(r'(?=COMPROVANTE|SISBB|2ª Via|Via Gerenciador)', txt)

    for p in partes:
        if len(p.strip()) < 30: continue

        d = {k:'' for k in ['Banco','Tipo','Beneficiário','CNPJ/CPF','Data Vencimento','Data Pagamento',
                           'Nr Documento','Valor Nominal','Juros','Multa','Desconto','Abatimento','Valor Pago',
                           'Descrição','Observação']}

        # ===== CAIXA BOLETO =====
        if 'Comprovante de Pagamento de Boleto' in p:
            d['Banco'] = 'CAIXA'
            d['Tipo'] = 'Boleto'
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
            d['Observação'] = get(r'Representação numérica.*?:\s*([\d ]+)', p)[:30]
            res.append(d)

        # ===== CAIXA PIX =====
        elif 'Gerenciador CAIXA' in p and 'Pix' in p:
            d['Banco'] = 'CAIXA'
            d['Tipo'] = 'Pix Enviado' if 'CONTTEC' in p.upper() else 'Pix Recebido'
            d['Beneficiário'] = get(r'Destino\s+Nome:\s*(.*)', p) or get(r'Origem\s+Nome:\s*(.*)', p)
            d['CNPJ/CPF'] = get(r'(?:CPF|CNPJ):\s*([X\d\.\/-]+)', p)
            d['Data Pagamento'] = get(r'Data e Hora:\s*(\d{2}/\d{4})', p)
            d['Data Vencimento'] = ''
            d['Nr Documento'] = get(r'ID da transação:\s*(\S+)', p)
            d['Valor Nominal'] = parse_valor(get(r'Valor Original.*?([\d\.,]+)', p))
            d['Valor Pago'] = d['Valor Nominal']
            d['Descrição'] = get(r'Detalhes:\s*(.*)', p)
            res.append(d)

        # ===== SICOOB BOLETO =====
        elif 'SICOOB' in p and 'PAGAMENTO DE BOLETO' in p:
            d['Banco'] = 'SICOOB'
            d['Tipo'] = 'Boleto'
            d['Beneficiário'] = get(r'Nome/Razão Social:\s*(.*)', p)
            d['CNPJ/CPF'] = get(r'CPF/CNPJ:\s*([\d\./-]+)', p)
            d['Data Vencimento'] = get(r'Vencimento:\s*(\d{2}/\d{4})', p)
            d['Data Pagamento'] = get(r'Pagamento:\s*(\d{2}/\d{4})', p)
            d['Nr Documento'] = get(r'Número do agendamento:\s*(\d+)', p)
            d['Valor Nominal'] = parse_valor(get(r'Documento:\s*R\$\s*([\d\.,]+)', p))
            d['Juros'] = parse_valor(get(r'Juros/Multa:\s*R\$\s*([\d\.,]+)', p))
            d['Desconto'] = parse_valor(get(r'Desconto/Abatimento:\s*R\$\s*([\d\.,]+)', p))
            d['Valor Pago'] = parse_valor(get(r'Pago:\s*R\$\s*([\d\.,]+)', p))
            res.append(d)

        # ===== SICOOB IMPOSTOS =====
        elif 'SICOOB' in p and ('PAGAMENTO DARF' in p or 'SIMPLES NACIONAL' in p):
            d['Banco'] = 'SICOOB'
            d['Tipo'] = 'Imposto'
            d['Beneficiário'] = 'SIMPLES NACIONAL' if 'SIMPLES' in p else 'DARF'
            d['Data Pagamento'] = get(r'Data do pagamento:\s*(\d{2}/\d{4})', p)
            d['Nr Documento'] = get(r'NÚMERO DO AGENDAMENTO:\s*(\d+)', p)
            d['Valor Pago'] = parse_valor(get(r'VALOR TOTAL.*?([\d\.,]+)', p))
            d['Valor Nominal'] = d['Valor Pago']
            res.append(d)

        # ===== BB TITULOS - CORRIGIDO =====
        elif 'PAGAMENTO DE TITULOS' in p:
            d['Banco'] = 'BB'
            d['Tipo'] = 'Título'
            d['Beneficiário'] = get(r'BENEFICIARIO:\s*\n(.*?)\n', p)
            d['CNPJ/CPF'] = get(r'CNPJ:\s*([\d\./-]+)', p)
            d['Data Vencimento'] = get(r'DATA DE VENCIMENTO\s+(\d{2}/\d{4})', p)
            d['Data Pagamento'] = get(r'DATA DO PAGAMENTO\s+(\d{2}/\d{4})', p)
            d['Nr Documento'] = get(r'NR\. DOCUMENTO\s+([\d\.]+)', p)
            d['Valor Nominal'] = parse_valor(get(r'VALOR DO DOCUMENTO\s+([\d\.,]+)', p))
            d['Valor Pago'] = parse_valor(get(r'VALOR COBRADO\s+([\d\.,]+)', p))
            d['Juros'] = round(d['Valor Pago'] - d['Valor Nominal'], 2)
            res.append(d)

        # ===== BB PIX =====
        elif 'Comprovante Pix' in p and 'SISBB' in p:
            d['Banco'] = 'BB'
            d['Tipo'] = 'Pix'
            d['Beneficiário'] = get(r'PAGO PARA:\s+(.*)', p)
            d['CNPJ/CPF'] = get(r'(?:CPF|CNPJ):\s+([\*\d\.\/-]+)', p)
            d['Data Pagamento'] = get(r'DATA:\s+(\d{2}/\d{4})', p)
            d['Nr Documento'] = get(r'DOCUMENTO:\s+(\d+)', p)
            d['Valor Pago'] = parse_valor(get(r'VALOR:\s+R\$([\d\.,]+)', p))
            d['Valor Nominal'] = d['Valor Pago']
            res.append(d)

    return res

uploaded = st.file_uploader("Arraste seus PDFs", type="pdf", accept_multiple_files=True)

if uploaded:
    todos = []
    for f in uploaded:
        todos.extend(processar(extrair(f.read())))

    if todos:
        df = pd.DataFrame(todos)

        # Mostrar com formato brasileiro
        df_show = df.copy()
        for col in ['Valor Nominal','Juros','Multa','Desconto','Abatimento','Valor Pago']:
            df_show[col] = df_show[col].apply(lambda x: f"{x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

        st.success(f"✅ {len(df)} comprovantes encontrados")
        st.dataframe(df_show, use_container_width=True, height=500)

        # Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Comprovantes')
            ws = writer.sheets['Comprovantes']
            # Formatar valores como 1.034,97
            for col_letter in ['H','I','J','K','L','M']:
                for cell in ws[col_letter][1:]:
                    cell.number_format = '#.##0,00'
            # Ajustar largura
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 15

        st.download_button(
            "📥 Baixar Excel Completo",
            data=output.getvalue(),
            file_name=f"comprovantes_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Nenhum comprovante reconhecido")
