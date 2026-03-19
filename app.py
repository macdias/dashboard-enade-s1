import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(layout="wide")

st.title("Dashboard ENADE - Análise de Desempenho")

arquivo = st.file_uploader("Envie o arquivo Excel", type=["xlsx"])

# Mapeamento temático das questões da prova ENADE 2023
temas_questoes = {
    "1": "Fome e segurança alimentar",
    "2": "Saneamento básico e desigualdade urbana",
    "3": "Vacinação infantil e políticas públicas de saúde",
    "4": "IA generativa e impactos socioeconômicos",
    "5": "Mobilidade urbana e segurança das mulheres",
    "6": "Identidade cultural, negritude e representação artística",
    "7": "Etarismo, previdência e trabalho do idoso",
    "8": "Encarceramento feminino e gênero",
    "9": "Sociedade do desempenho, tecnologia e saúde mental",
    "10": "Circuitos elétricos, resistores e associação série/paralelo",
    "11": "Redes de computadores, OSPF e algoritmo de Dijkstra",
    "12": "Matemática discreta, relações de equivalência e partições",
    "13": "Circuitos elétricos, grafos e lei de Kirchhoff",
    "14": "Programação funcional e manipulação de listas",
    "15": "Programação em C, memória dinâmica e memory leak",
    "16": "Sistemas embarcados, operações binárias e bitwise em C",
    "17": "Algoritmos, programação dinâmica e LCS",
    "18": "Estruturas de dados, vetores dinâmicos e análise amortizada",
    "19": "Compiladores, gramáticas e análise sintática/semântica",
    "20": "Computação em nuvem pública",
    "21": "IHC e acessibilidade",
    "22": "Banco de dados relacional e SQL",
    "23": "Eletrônica analógica e filtros ativos",
    "24": "Sistemas embarcados, portas paralelas e registradores de I/O",
    "25": "Sistemas digitais, HDL, Verilog e VHDL",
    "26": "Sistemas operacionais, multiprocessadores e threads",
    "27": "Virtualização de hardware",
    "28": "Sistemas operacionais, memória virtual, paginação e TLB",
    "29": "IA, visão computacional e SVM",
    "30": "Computação paralela e conflito de dados",
    "31": "Sinais e sistemas, teorema da amostragem",
    "32": "Inteligência artificial, busca gulosa e grafos",
    "33": "Controle automático e controlador PID",
    "34": "Redes de computadores e algoritmos de enfileiramento",
    "35": "Sistemas distribuídos, TCP e UDP",
    "36": "Desempenho computacional, threads e núcleos",
    "37": "Segurança da computação",
    "38": "Sistemas distribuídos e microsserviços"
}

def extrair_numero_questao(coluna):
    coluna_str = str(coluna).strip()
    digitos = "".join(ch for ch in coluna_str if ch.isdigit())
    return digitos if digitos else coluna_str

def descrever_questao(coluna):
    numero = extrair_numero_questao(coluna)
    tema = temas_questoes.get(numero, "Tema não mapeado")
    return f"Q{numero} - {tema}"

def calcular_conceito_enade(percentual):
    if percentual <= 10:
        return 1
    elif percentual <= 19:
        return 2
    elif percentual <= 29:
        return 3
    elif percentual <= 45:
        return 4
    return 5

if arquivo is not None:
    df = pd.read_excel(arquivo)

    # Separar gabarito
    gabarito = df.iloc[-1, 1:]
    df_alunos = df.iloc[:-1].copy()

    # Remover D1 e D2
    questoes = [col for col in df.columns[1:] if str(col).strip() not in ["D1", "D2"]]

    # Separar componentes
    comp_geral = questoes[:9]
    comp_especifico = questoes[9:]

    # Comparação com gabarito
    for q in questoes:
        df_alunos[q] = df_alunos[q].astype(str).str.strip().str.upper() == str(gabarito[q]).strip().upper()

    # Acertos por aluno
    df_alunos["Acertos"] = df_alunos[questoes].sum(axis=1)

    # Ranking
    df_alunos["Posicao"] = df_alunos["Acertos"].rank(ascending=False, method="min").astype(int)

    st.header("Visão Geral da Turma")

    # Acerto por questão
    acerto_por_questao = df_alunos[questoes].mean().sort_values(ascending=False)

    top10 = acerto_por_questao.head(10)
    bottom10 = acerto_por_questao.tail(10).sort_values()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 10 questões com mais acertos")
        for i, (q, val) in enumerate(top10.items(), start=1):
            st.write(f"{i}º - {descrever_questao(q)}: {val * 100:.2f}% de acerto")

    with col2:
        st.subheader("Top 10 questões com mais erros")
        for i, (q, val) in enumerate(bottom10.items(), start=1):
            erro = (1 - val) * 100
            st.write(f"{i}º - {descrever_questao(q)}: {erro:.2f}% de erro")

    # Distribuição de acertos
    st.subheader("Distribuição de acertos dos alunos")
    fig_hist = px.histogram(df_alunos, x="Acertos", nbins=20)
    st.plotly_chart(fig_hist, use_container_width=True)

    # Tabela com acertos por aluno
    st.subheader("Acertos por aluno")
    tabela_resumo = df_alunos.iloc[:, [0]].copy()
    tabela_resumo.columns = ["RA"]
    tabela_resumo["Acertos"] = df_alunos["Acertos"]
    tabela_resumo["Posição"] = df_alunos["Posicao"]
    tabela_resumo = tabela_resumo.sort_values(by=["Acertos", "RA"], ascending=[False, True])
    st.dataframe(tabela_resumo, use_container_width=True)

    # Cálculo ponderado ENADE
    media_geral = df_alunos[comp_geral].mean().mean()
    media_especifico = df_alunos[comp_especifico].mean().mean()
    percentual_ponderado = (media_geral * 0.25 + media_especifico * 0.75) * 100
    conceito = calcular_conceito_enade(percentual_ponderado)

    st.subheader("Conceito ENADE aproximado da turma")
    col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
    col_metric1.metric("Média comp. geral (%)", f"{media_geral * 100:.2f}")
    col_metric2.metric("Média comp. específico (%)", f"{media_especifico * 100:.2f}")
    col_metric3.metric("Percentual ponderado (%)", f"{percentual_ponderado:.2f}")
    col_metric4.metric("Conceito", conceito)

    st.header("Filtro por Aluno")

    aluno = st.selectbox("Selecione o RA", df_alunos.iloc[:, 0].tolist())

    df_aluno = df_alunos[df_alunos.iloc[:, 0] == aluno]

    st.subheader(f"Desempenho do aluno {aluno}")

    acertos_aluno = pd.DataFrame({
        "Questão": [f"Q{extrair_numero_questao(q)}" for q in questoes],
        "Tema": [temas_questoes.get(extrair_numero_questao(q), "Tema não mapeado") for q in questoes],
        "Acerto": df_aluno[questoes].iloc[0].astype(int).values
    })

    fig_aluno = px.bar(acertos_aluno, x="Questão", y="Acerto", hover_data=["Tema"])
    st.plotly_chart(fig_aluno, use_container_width=True)

    col_a, col_b = st.columns(2)
    col_a.metric("Total de acertos", int(df_aluno["Acertos"].values[0]))
    col_b.metric("Posição no ranking", int(df_aluno["Posicao"].values[0]))

    st.subheader("Detalhamento por questão do aluno")
    st.dataframe(acertos_aluno, use_container_width=True)