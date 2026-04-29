import re
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(layout="wide")

st.title("Dashboard ENADE: Análise de Desempenho")


def extrair_numero_questao(coluna):
    coluna_str = str(coluna).strip()

    try:
        valor = float(coluna_str)
        if valor.is_integer():
            return str(int(valor))
    except ValueError:
        pass

    busca = re.search(r"\d+", coluna_str)
    return busca.group(0) if busca else coluna_str


def eh_dissertativa(coluna):
    coluna_str = str(coluna).strip().upper()
    return bool(re.fullmatch(r"D\d+", coluna_str))


def normalizar_chave_tema(chave):
    chave_str = str(chave).strip().upper()

    busca_dissertativa = re.fullmatch(r"D\s*(\d+)", chave_str)
    if busca_dissertativa:
        return f"D{int(busca_dissertativa.group(1))}"

    busca_objetiva = re.fullmatch(r"Q?\s*(\d+)", chave_str)
    if busca_objetiva:
        return str(int(busca_objetiva.group(1)))

    numero = extrair_numero_questao(chave_str)
    return numero


def obter_tema_objetiva(coluna, temas_questoes):
    numero = extrair_numero_questao(coluna)
    return temas_questoes.get(numero, temas_questoes.get(f"Q{numero}", "Tema não mapeado"))


def obter_tema_dissertativa(coluna, temas_questoes):
    chave = normalizar_chave_tema(coluna)
    return temas_questoes.get(chave, "Tema não mapeado")


def carregar_temas_txt(arquivo_txt):
    if arquivo_txt is None:
        raise ValueError("O arquivo TXT com os temas das questões não foi enviado.")

    try:
        arquivo_txt.seek(0)
    except Exception:
        pass

    conteudo_bytes = arquivo_txt.read()

    try:
        conteudo = conteudo_bytes.decode("utf-8")
    except UnicodeDecodeError:
        conteudo = conteudo_bytes.decode("latin-1")

    try:
        arquivo_txt.seek(0)
    except Exception:
        pass

    temas_questoes = {}

    linhas = conteudo.splitlines()

    for numero_linha, linha in enumerate(linhas, start=1):
        linha = linha.strip()

        if linha == "":
            continue

        if linha.startswith("#"):
            continue

        chave_bruta = None
        tema = None

        for separador in ["=", ";", "\t", ":"]:
            if separador in linha:
                partes = linha.split(separador, 1)
                chave_bruta = partes[0].strip()
                tema = partes[1].strip()
                break

        if chave_bruta is None or tema is None:
            busca = re.match(
                r"^\s*(D\s*\d+|Q\s*\d+|\d+)\s+(.+?)\s*$",
                linha,
                flags=re.IGNORECASE
            )

            if busca:
                chave_bruta = busca.group(1).strip()
                tema = busca.group(2).strip()
            else:
                raise ValueError(
                    f"Linha inválida no TXT de temas: linha {numero_linha}. "
                    "Use um formato como 1=Tema da questão ou D1=Tema da dissertativa."
                )

        chave = normalizar_chave_tema(chave_bruta)

        if chave == "":
            raise ValueError(f"Chave de questão inválida no TXT de temas: linha {numero_linha}.")

        if tema == "":
            raise ValueError(f"Tema vazio no TXT de temas: linha {numero_linha}.")

        temas_questoes[chave] = tema

    if len(temas_questoes) == 0:
        raise ValueError("O TXT de temas não possui nenhum tema válido.")

    return temas_questoes


def descrever_questao(coluna, temas_questoes):
    numero = extrair_numero_questao(coluna)
    tema = obter_tema_objetiva(coluna, temas_questoes)
    return f"Q{numero}: {tema}"


def descrever_dissertativa(coluna, temas_questoes):
    chave = normalizar_chave_tema(coluna)
    tema = obter_tema_dissertativa(coluna, temas_questoes)
    return f"{chave}: {tema}"


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


def gerar_chave_segura(valor):
    valor_str = str(valor)
    valor_str = re.sub(r"[^a-zA-Z0-9_]", "_", valor_str)
    return valor_str


def ordenar_colunas_dissertativas(colunas):
    return sorted(
        colunas,
        key=lambda col: int(extrair_numero_questao(col))
        if extrair_numero_questao(col).isdigit()
        else str(col)
    )


def ordenar_chaves_temas(chaves):
    def chave_ordenacao(chave):
        chave_str = str(chave).strip().upper()

        busca_d = re.fullmatch(r"D(\d+)", chave_str)
        if busca_d:
            return (1, int(busca_d.group(1)))

        busca_q = re.fullmatch(r"Q?(\d+)", chave_str)
        if busca_q:
            return (0, int(busca_q.group(1)))

        return (2, chave_str)

    return sorted(chaves, key=chave_ordenacao)


def converter_coluna_nota(serie):
    serie_convertida = serie.astype(str).str.strip()
    serie_convertida = serie_convertida.str.replace(",", ".", regex=False)

    serie_convertida = serie_convertida.replace({
        "": pd.NA,
        "nan": pd.NA,
        "NaN": pd.NA,
        "None": pd.NA,
        "none": pd.NA,
        "NULL": pd.NA,
        "null": pd.NA
    })

    return pd.to_numeric(serie_convertida, errors="coerce")


def formatar_numero(valor):
    if pd.isna(valor):
        return "Sem nota"
    return f"{float(valor):.2f}"


def processar_arquivo(arquivo_excel):
    try:
        arquivo_excel.seek(0)
    except Exception:
        pass

    df = pd.read_excel(arquivo_excel)

    if df.shape[0] < 2:
        raise ValueError("O arquivo precisa ter pelo menos uma linha de aluno e uma linha de gabarito.")

    if df.shape[1] < 2:
        raise ValueError("O arquivo precisa ter uma coluna de RA e pelo menos uma coluna de questão.")

    gabarito = df.iloc[-1, 1:]
    df_alunos = df.iloc[:-1].copy()

    coluna_ra = df_alunos.columns[0]
    df_alunos["_RA"] = df_alunos[coluna_ra].astype(str).str.strip()

    colunas_respostas = list(df.columns[1:])

    dissertativas = [
        col for col in colunas_respostas
        if eh_dissertativa(col)
    ]

    dissertativas = ordenar_colunas_dissertativas(dissertativas)

    questoes = [
        col for col in colunas_respostas
        if not eh_dissertativa(col)
    ]

    if len(questoes) == 0:
        raise ValueError("Nenhuma questão objetiva válida foi encontrada após separar as dissertativas.")

    comp_geral = questoes[:9]
    comp_especifico = questoes[9:]

    for q in questoes:
        resposta_aluno = df_alunos[q].astype(str).str.strip().str.upper()
        resposta_correta = str(gabarito[q]).strip().upper()
        df_alunos[q] = resposta_aluno == resposta_correta

    for d in dissertativas:
        df_alunos[d] = converter_coluna_nota(df_alunos[d])

    df_alunos["Acertos"] = df_alunos[questoes].sum(axis=1)
    df_alunos["Percentual"] = (df_alunos["Acertos"] / len(questoes)) * 100
    df_alunos["Posicao"] = df_alunos["Acertos"].rank(ascending=False, method="min").astype(int)

    if len(dissertativas) > 0:
        df_alunos["Media_dissertativas"] = df_alunos[dissertativas].mean(axis=1, skipna=True)
        media_dissertativas = df_alunos[dissertativas].stack().mean()
        medias_por_dissertativa = {
            str(d): df_alunos[d].mean(skipna=True)
            for d in dissertativas
        }
    else:
        media_dissertativas = pd.NA
        medias_por_dissertativa = {}

    acerto_por_questao = df_alunos[questoes].mean().sort_values(ascending=False)

    top10 = acerto_por_questao.head(10)
    bottom10 = acerto_por_questao.tail(10).sort_values()

    media_geral = df_alunos[comp_geral].mean().mean() if len(comp_geral) > 0 else 0
    media_especifico = df_alunos[comp_especifico].mean().mean() if len(comp_especifico) > 0 else 0

    percentual_ponderado = (media_geral * 0.25 + media_especifico * 0.75) * 100
    conceito = calcular_conceito_enade(percentual_ponderado)

    tabela_resumo = pd.DataFrame()
    tabela_resumo["RA"] = df_alunos["_RA"]
    tabela_resumo["Acertos objetivas"] = df_alunos["Acertos"]
    tabela_resumo["Percentual objetivas"] = df_alunos["Percentual"]

    for d in dissertativas:
        tabela_resumo[str(d)] = df_alunos[d]

    if len(dissertativas) > 0:
        tabela_resumo["Média dissertativas"] = df_alunos["Media_dissertativas"]

    tabela_resumo["Posição"] = df_alunos["Posicao"]

    tabela_resumo = tabela_resumo.sort_values(
        by=["Acertos objetivas", "RA"],
        ascending=[False, True]
    )

    return {
        "df_original": df,
        "df_alunos": df_alunos,
        "questoes": questoes,
        "dissertativas": dissertativas,
        "comp_geral": comp_geral,
        "comp_especifico": comp_especifico,
        "acerto_por_questao": acerto_por_questao,
        "top10": top10,
        "bottom10": bottom10,
        "media_geral": media_geral,
        "media_especifico": media_especifico,
        "percentual_ponderado": percentual_ponderado,
        "conceito": conceito,
        "tabela_resumo": tabela_resumo,
        "quantidade_alunos": len(df_alunos),
        "quantidade_questoes": len(questoes),
        "quantidade_dissertativas": len(dissertativas),
        "media_acertos": df_alunos["Acertos"].mean(),
        "media_dissertativas": media_dissertativas,
        "medias_por_dissertativa": medias_por_dissertativa
    }


def montar_tabela_dissertativas(resultado, temas_questoes):
    df_alunos = resultado["df_alunos"]
    dissertativas = resultado["dissertativas"]

    linhas = []

    for d in dissertativas:
        linhas.append({
            "Questão dissertativa": normalizar_chave_tema(d),
            "Tema": obter_tema_dissertativa(d, temas_questoes),
            "Média": df_alunos[d].mean(skipna=True),
            "Mínima": df_alunos[d].min(skipna=True),
            "Máxima": df_alunos[d].max(skipna=True),
            "Desvio padrão": df_alunos[d].std(skipna=True),
            "Notas válidas": df_alunos[d].count()
        })

    return pd.DataFrame(linhas)


def montar_tabela_temas(temas_questoes):
    chaves_ordenadas = ordenar_chaves_temas(temas_questoes.keys())

    tabela_temas = pd.DataFrame({
        "Questão": [
            f"Q{chave}" if str(chave).isdigit() else str(chave)
            for chave in chaves_ordenadas
        ],
        "Tipo": [
            "Objetiva" if str(chave).isdigit() else "Dissertativa"
            for chave in chaves_ordenadas
        ],
        "Tema": [
            temas_questoes[chave]
            for chave in chaves_ordenadas
        ]
    })

    return tabela_temas


def montar_tabela_dissertativas_aluno(df_aluno, dissertativas, temas_questoes):
    linha_aluno = df_aluno.iloc[0]

    tabela = pd.DataFrame({
        "Questão dissertativa": [
            normalizar_chave_tema(d)
            for d in dissertativas
        ],
        "Tema": [
            obter_tema_dissertativa(d, temas_questoes)
            for d in dissertativas
        ],
        "Nota": [
            linha_aluno[d]
            for d in dissertativas
        ]
    })

    return tabela


def renderizar_boletim(resultado, temas_questoes, titulo_boletim, chave):
    df_alunos = resultado["df_alunos"]
    questoes = resultado["questoes"]
    dissertativas = resultado["dissertativas"]
    possui_dissertativas = len(dissertativas) > 0

    st.header(titulo_boletim)

    st.subheader("Visão geral da turma")

    top10 = resultado["top10"]
    bottom10 = resultado["bottom10"]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 10 questões objetivas com mais acertos")
        for i, (q, val) in enumerate(top10.items(), start=1):
            st.write(f"{i}º: {descrever_questao(q, temas_questoes)}: {val * 100:.2f}% de acerto")

    with col2:
        st.subheader("Top 10 questões objetivas com mais erros")
        for i, (q, val) in enumerate(bottom10.items(), start=1):
            erro = (1 - val) * 100
            st.write(f"{i}º: {descrever_questao(q, temas_questoes)}: {erro:.2f}% de erro")

    st.subheader("Distribuição de acertos nas questões objetivas")

    fig_hist = px.histogram(
        df_alunos,
        x="Acertos",
        nbins=20,
        title=f"Distribuição de acertos objetivos: {titulo_boletim}"
    )

    st.plotly_chart(
        fig_hist,
        use_container_width=True,
        key=f"grafico_histograma_{chave}"
    )

    if possui_dissertativas:
        st.subheader("Desempenho nas questões dissertativas")

        tabela_dissertativas = montar_tabela_dissertativas(resultado, temas_questoes)

        st.dataframe(
            tabela_dissertativas,
            use_container_width=True,
            key=f"tabela_dissertativas_{chave}"
        )

        fig_dissertativas = px.bar(
            tabela_dissertativas,
            x="Questão dissertativa",
            y="Média",
            hover_data=["Tema"],
            title=f"Média por questão dissertativa: {titulo_boletim}"
        )

        st.plotly_chart(
            fig_dissertativas,
            use_container_width=True,
            key=f"grafico_media_dissertativas_{chave}"
        )

        fig_media_dissertativas = px.histogram(
            df_alunos,
            x="Media_dissertativas",
            nbins=20,
            title=f"Distribuição da média das dissertativas: {titulo_boletim}"
        )

        st.plotly_chart(
            fig_media_dissertativas,
            use_container_width=True,
            key=f"grafico_histograma_media_dissertativas_{chave}"
        )

    st.subheader("Resumo por aluno")

    st.dataframe(
        resultado["tabela_resumo"],
        use_container_width=True,
        key=f"tabela_resumo_{chave}"
    )

    st.subheader("Conceito ENADE aproximado da turma")

    if possui_dissertativas:
        col_metric1, col_metric2, col_metric3, col_metric4, col_metric5, col_metric6, col_metric7 = st.columns(7)

        col_metric1.metric("Alunos", resultado["quantidade_alunos"])
        col_metric2.metric("Questões objetivas", resultado["quantidade_questoes"])
        col_metric3.metric("Dissertativas", resultado["quantidade_dissertativas"])
        col_metric4.metric("Média acertos objetivos", f"{resultado['media_acertos']:.2f}")
        col_metric5.metric("Média comp. geral (%)", f"{resultado['media_geral'] * 100:.2f}")
        col_metric6.metric("Média comp. específico (%)", f"{resultado['media_especifico'] * 100:.2f}")
        col_metric7.metric("Conceito", resultado["conceito"])

        col_extra1, col_extra2 = st.columns(2)
        col_extra1.metric("Percentual ponderado das objetivas (%)", f"{resultado['percentual_ponderado']:.2f}")
        col_extra2.metric("Média geral das dissertativas", formatar_numero(resultado["media_dissertativas"]))

    else:
        col_metric1, col_metric2, col_metric3, col_metric4, col_metric5, col_metric6 = st.columns(6)

        col_metric1.metric("Alunos", resultado["quantidade_alunos"])
        col_metric2.metric("Questões objetivas", resultado["quantidade_questoes"])
        col_metric3.metric("Média acertos objetivos", f"{resultado['media_acertos']:.2f}")
        col_metric4.metric("Média comp. geral (%)", f"{resultado['media_geral'] * 100:.2f}")
        col_metric5.metric("Média comp. específico (%)", f"{resultado['media_especifico'] * 100:.2f}")
        col_metric6.metric("Conceito", resultado["conceito"])

        st.metric("Percentual ponderado das objetivas (%)", f"{resultado['percentual_ponderado']:.2f}")

    st.header("Filtro por aluno")

    lista_alunos = resultado["tabela_resumo"]["RA"].tolist()

    aluno = st.selectbox(
        "Selecione o RA",
        lista_alunos,
        key=f"select_aluno_{chave}"
    )

    aluno_chave = gerar_chave_segura(aluno)

    df_aluno = df_alunos[df_alunos["_RA"] == aluno]

    st.subheader(f"Desempenho do aluno {aluno}")

    acertos_aluno = pd.DataFrame({
        "Questão": [f"Q{extrair_numero_questao(q)}" for q in questoes],
        "Tema": [
            obter_tema_objetiva(q, temas_questoes)
            for q in questoes
        ],
        "Acerto": df_aluno[questoes].iloc[0].astype(int).values
    })

    fig_aluno = px.bar(
        acertos_aluno,
        x="Questão",
        y="Acerto",
        hover_data=["Tema"],
        title=f"Desempenho objetivo por questão: Aluno {aluno}"
    )

    st.plotly_chart(
        fig_aluno,
        use_container_width=True,
        key=f"grafico_aluno_{chave}_{aluno_chave}"
    )

    if possui_dissertativas:
        col_a, col_b, col_c, col_d = st.columns(4)

        col_a.metric("Total de acertos objetivos", int(df_aluno["Acertos"].values[0]))
        col_b.metric("Percentual objetivo (%)", f"{float(df_aluno['Percentual'].values[0]):.2f}")
        col_c.metric("Posição no ranking", int(df_aluno["Posicao"].values[0]))
        col_d.metric("Média dissertativas", formatar_numero(df_aluno["Media_dissertativas"].values[0]))

    else:
        col_a, col_b, col_c = st.columns(3)

        col_a.metric("Total de acertos objetivos", int(df_aluno["Acertos"].values[0]))
        col_b.metric("Percentual objetivo (%)", f"{float(df_aluno['Percentual'].values[0]):.2f}")
        col_c.metric("Posição no ranking", int(df_aluno["Posicao"].values[0]))

    st.subheader("Detalhamento das questões objetivas do aluno")

    st.dataframe(
        acertos_aluno,
        use_container_width=True,
        key=f"tabela_detalhamento_aluno_{chave}_{aluno_chave}"
    )

    if possui_dissertativas:
        st.subheader("Detalhamento das questões dissertativas do aluno")

        dissertativas_aluno = montar_tabela_dissertativas_aluno(
            df_aluno,
            dissertativas,
            temas_questoes
        )

        st.dataframe(
            dissertativas_aluno,
            use_container_width=True,
            key=f"tabela_dissertativas_aluno_{chave}_{aluno_chave}"
        )

    st.subheader("Temas carregados para este boletim")

    tabela_temas = montar_tabela_temas(temas_questoes)

    st.dataframe(
        tabela_temas,
        use_container_width=True,
        key=f"tabela_temas_{chave}"
    )


st.subheader("Envio dos arquivos Excel e TXT de temas")

col_upload1, col_upload2, col_upload3, col_upload4 = st.columns(4)

with col_upload1:
    st.markdown("### Boletim 1")
    arquivo1 = st.file_uploader(
        "Excel do boletim 1",
        type=["xlsx"],
        key="arquivo_excel_1"
    )
    temas1 = st.file_uploader(
        "TXT de temas do boletim 1",
        type=["txt"],
        key="arquivo_temas_1"
    )

with col_upload2:
    st.markdown("### Boletim 2")
    arquivo2 = st.file_uploader(
        "Excel do boletim 2",
        type=["xlsx"],
        key="arquivo_excel_2"
    )
    temas2 = st.file_uploader(
        "TXT de temas do boletim 2",
        type=["txt"],
        key="arquivo_temas_2"
    )

with col_upload3:
    st.markdown("### Boletim 3")
    arquivo3 = st.file_uploader(
        "Excel do boletim 3",
        type=["xlsx"],
        key="arquivo_excel_3"
    )
    temas3 = st.file_uploader(
        "TXT de temas do boletim 3",
        type=["txt"],
        key="arquivo_temas_3"
    )

with col_upload4:
    st.markdown("### Boletim 4")
    arquivo4 = st.file_uploader(
        "Excel do boletim 4",
        type=["xlsx"],
        key="arquivo_excel_4"
    )
    temas4 = st.file_uploader(
        "TXT de temas do boletim 4",
        type=["txt"],
        key="arquivo_temas_4"
    )

arquivos = [
    {
        "arquivo_excel": arquivo1,
        "arquivo_temas": temas1,
        "nome_aba": "Boletim 1",
        "titulo": "Boletim do primeiro arquivo",
        "chave": "boletim1",
        "descricao_erro": "primeiro boletim"
    },
    {
        "arquivo_excel": arquivo2,
        "arquivo_temas": temas2,
        "nome_aba": "Boletim 2",
        "titulo": "Boletim do segundo arquivo",
        "chave": "boletim2",
        "descricao_erro": "segundo boletim"
    },
    {
        "arquivo_excel": arquivo3,
        "arquivo_temas": temas3,
        "nome_aba": "Boletim 3",
        "titulo": "Boletim do terceiro arquivo",
        "chave": "boletim3",
        "descricao_erro": "terceiro boletim"
    },
    {
        "arquivo_excel": arquivo4,
        "arquivo_temas": temas4,
        "nome_aba": "Boletim 4",
        "titulo": "Boletim do quarto arquivo",
        "chave": "boletim4",
        "descricao_erro": "quarto boletim"
    }
]

boletins_processados = []

for item in arquivos:
    arquivo_excel = item["arquivo_excel"]
    arquivo_temas = item["arquivo_temas"]

    if arquivo_excel is None and arquivo_temas is None:
        continue

    if arquivo_excel is not None and arquivo_temas is None:
        st.warning(
            f"O {item['descricao_erro']} possui Excel enviado, mas não possui TXT de temas. "
            "Envie os dois arquivos para gerar o boletim."
        )
        continue

    if arquivo_excel is None and arquivo_temas is not None:
        st.warning(
            f"O {item['descricao_erro']} possui TXT de temas enviado, mas não possui Excel. "
            "Envie os dois arquivos para gerar o boletim."
        )
        continue

    try:
        temas_questoes = carregar_temas_txt(arquivo_temas)
        resultado = processar_arquivo(arquivo_excel)

        boletins_processados.append({
            "resultado": resultado,
            "temas_questoes": temas_questoes,
            "nome_aba": item["nome_aba"],
            "titulo": item["titulo"],
            "chave": item["chave"]
        })

    except Exception as erro:
        st.error(f"Erro ao processar o {item['descricao_erro']}: {erro}")

if len(boletins_processados) == 0:
    st.info("Envie pelo menos um conjunto com Excel e TXT de temas para gerar o boletim.")
else:
    nomes_abas = [
        item["nome_aba"]
        for item in boletins_processados
    ]

    abas = st.tabs(nomes_abas)

    for indice, item in enumerate(boletins_processados):
        with abas[indice]:
            renderizar_boletim(
                item["resultado"],
                item["temas_questoes"],
                item["titulo"],
                item["chave"]
            )