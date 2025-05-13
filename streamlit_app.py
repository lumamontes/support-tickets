import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
from sqlalchemy import create_engine

# Configuração da página
st.set_page_config(
    page_title="Análise de Critérios Avaliativos",
    page_icon="📊",
    layout="wide"
)

# Título do dashboard
st.title("📊 Análise Detalhada de Critérios Avaliativos")

database_url = st.secrets["DB_URL"]
@st.cache_resource
def get_connection():
    # Usar diretamente a URL completa
    return create_engine(database_url)


# Função para executar consultas
def executar_consulta(query):
    try:
        conn = get_connection()
        return pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"Erro ao executar consulta: {e}")
        st.code(query)  # Mostra a consulta com erro para depuração
        return None

# Função para carregar dados detalhados das categorias específicas
def carregar_dados_categorias():
    query = """
    SELECT 
        e.id AS entidade_id,
        e.nome AS nome_entidade,
        
        -- Total de critérios
        COUNT(DISTINCT ca.id) AS total_criterios,
        
        -- Critérios com fórmula personalizada
        SUM(CASE WHEN ca.formula_personalizada IS NOT NULL THEN 1 ELSE 0 END) AS formula_personalizada,
        
        -- Critérios de grupo
        SUM(CASE WHEN ca.criterio_calculo_grupo_id IS NOT NULL AND ca.possui_criterios_grupos = true THEN 1 ELSE 0 END) AS criterio_grupo,
        
        -- Critérios de grupo com recuperação paralela
        SUM(CASE WHEN ca.criterio_calculo_grupo_id IS NOT NULL 
                  AND ca.possui_criterios_grupos = true 
                  AND ca.possui_recuperacao_paralela = true THEN 1 ELSE 0 END) AS grupo_rec_paralela,
        
        -- Critérios de grupo com recuperação semestral
        SUM(CASE WHEN ca.criterio_calculo_grupo_id IS NOT NULL 
                  AND ca.possui_criterios_grupos = true 
                  AND ca.possui_recuperacao_semestral = true THEN 1 ELSE 0 END) AS grupo_rec_semestral,
        
        -- Critérios com fórmula personalizada com recuperação paralela
        SUM(CASE WHEN ca.formula_personalizada IS NOT NULL 
                  AND ca.possui_recuperacao_paralela = true THEN 1 ELSE 0 END) AS formula_rec_paralela,
        
        -- Critérios com fórmula personalizada com recuperação semestral
        SUM(CASE WHEN ca.formula_personalizada IS NOT NULL 
                  AND ca.possui_recuperacao_semestral = true THEN 1 ELSE 0 END) AS formula_rec_semestral
        
    FROM 
        entidades e
    LEFT JOIN 
        criterios_avaliativos ca ON ca.entidade_id = e.id
    GROUP BY 
        e.id, e.nome
    HAVING 
        COUNT(DISTINCT ca.id) > 0
    ORDER BY 
        total_criterios DESC
    """
    return executar_consulta(query)

# Função para carregar dados de matrículas por entidade
def carregar_dados_matriculas():
    query = """
    SELECT 
        e.id AS entidade_id,
        e.nome AS nome_entidade,
        COUNT(DISTINCT m.id) AS total_matriculas,
        COUNT(DISTINCT t.id) AS total_turmas
    FROM 
        entidades e
    LEFT JOIN 
        turmas t ON t.entidade_id = e.id
    LEFT JOIN 
        matriculas m ON m.turma_id = t.id
    GROUP BY 
        e.id, e.nome
    ORDER BY 
        total_matriculas DESC
    """
    return executar_consulta(query)

# Carregar dados
with st.spinner("Carregando dados detalhados..."):
    # Carregar categorias de critérios
    df_categorias = carregar_dados_categorias()
    
    # Carregar matrículas
    df_matriculas = carregar_dados_matriculas()
    
    if df_categorias is not None and df_matriculas is not None:
        # Mesclar os dados
        df_completo = pd.merge(
            df_categorias,
            df_matriculas[['entidade_id', 'total_matriculas', 'total_turmas']],
            on='entidade_id',
            how='left'
        )
        
        # Preencher valores nulos com zeros
        df_completo.fillna(0, inplace=True)
        
        # Calcular alguns campos derivados
        df_completo['percentual_formula'] = (df_completo['formula_personalizada'] / df_completo['total_criterios'] * 100).round(1)
        df_completo['percentual_grupo'] = (df_completo['criterio_grupo'] / df_completo['total_criterios'] * 100).round(1)
        
        st.success(f"✅ Dados carregados com sucesso! Analisando {len(df_completo)} entidades.")
        
        # Filtros na barra lateral
        st.sidebar.header("Filtros")
        
        # Filtro por nome de entidade
        todas_entidades = df_completo['nome_entidade'].unique()
        entidades_selecionadas = st.sidebar.multiselect(
            "Filtrar por entidades específicas",
            options=todas_entidades,
            default=[]
        )
        
        # Filtro por quantidade mínima de matrículas
        min_matriculas = st.sidebar.slider(
            "Quantidade mínima de matrículas",
            min_value=0,
            max_value=int(df_completo['total_matriculas'].max()),
            value=0
        )
        
        # Filtro por quantidade mínima de critérios
        min_criterios = st.sidebar.slider(
            "Quantidade mínima de critérios",
            min_value=1,
            max_value=int(df_completo['total_criterios'].max()),
            value=1
        )
        
        # Número de entidades a exibir nos gráficos
        num_entidades = st.sidebar.slider(
            "Entidades a exibir nos gráficos",
            min_value=5,
            max_value=100,
            value=30
        )
        
        # Aplicar filtros
        df_filtrado = df_completo.copy()
        
        if entidades_selecionadas:
            df_filtrado = df_filtrado[df_filtrado['nome_entidade'].isin(entidades_selecionadas)]
        
        df_filtrado = df_filtrado[df_filtrado['total_matriculas'] >= min_matriculas]
        df_filtrado = df_filtrado[df_filtrado['total_criterios'] >= min_criterios]
        
        # Informar número de entidades após filtros
        st.sidebar.info(f"Exibindo {len(df_filtrado)} entidades após filtros")
        
        # Resumo das categorias específicas
        st.header("Resumo por Categoria")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_criterios = df_filtrado['total_criterios'].sum()
            st.metric("Total de Critérios", int(total_criterios))
            
            total_formula = df_filtrado['formula_personalizada'].sum()
            perc_formula = (total_formula / total_criterios * 100).round(1) if total_criterios > 0 else 0
            st.metric("Com Fórmula Personalizada", f"{int(total_formula)} ({perc_formula}%)")
            
            total_grupo = df_filtrado['criterio_grupo'].sum()
            perc_grupo = (total_grupo / total_criterios * 100).round(1) if total_criterios > 0 else 0
            st.metric("Critérios de Grupo", f"{int(total_grupo)} ({perc_grupo}%)")
        
        with col2:
            total_grupo_paralela = df_filtrado['grupo_rec_paralela'].sum()
            perc_grupo_paralela = (total_grupo_paralela / total_grupo * 100).round(1) if total_grupo > 0 else 0
            st.metric("Grupo com Rec. Paralela", f"{int(total_grupo_paralela)} ({perc_grupo_paralela}%)")
            
            total_grupo_semestral = df_filtrado['grupo_rec_semestral'].sum()
            perc_grupo_semestral = (total_grupo_semestral / total_grupo * 100).round(1) if total_grupo > 0 else 0
            st.metric("Grupo com Rec. Semestral", f"{int(total_grupo_semestral)} ({perc_grupo_semestral}%)")
        
        with col3:
            total_formula_paralela = df_filtrado['formula_rec_paralela'].sum()
            perc_formula_paralela = (total_formula_paralela / total_formula * 100).round(1) if total_formula > 0 else 0
            st.metric("Fórmula com Rec. Paralela", f"{int(total_formula_paralela)} ({perc_formula_paralela}%)")
            
            total_formula_semestral = df_filtrado['formula_rec_semestral'].sum()
            perc_formula_semestral = (total_formula_semestral / total_formula * 100).round(1) if total_formula > 0 else 0
            st.metric("Fórmula com Rec. Semestral", f"{int(total_formula_semestral)} ({perc_formula_semestral}%)")
        
        # Resumo de matrículas
        col1, col2 = st.columns(2)
        
        with col1:
            total_matriculas = df_filtrado['total_matriculas'].sum()
            st.metric("Total de Matrículas", f"{int(total_matriculas):,}".replace(",", "."))
        
        with col2:
            total_turmas = df_filtrado['total_turmas'].sum()
            st.metric("Total de Turmas", int(total_turmas))
        
        # Abas para diferentes análises
        tab1, tab2, tab3 = st.tabs(["Visão Geral", "Análise por Categoria", "Análise por Entidade"])
        
        with tab1:
            st.header("Visão Geral dos Critérios")
            
            # Criar dados para o gráfico de pizza das categorias
            dados_pizza = {
                'Categoria': [
                    'Fórmula Personalizada com Rec. Paralela',
                    'Fórmula Personalizada com Rec. Semestral',
                    'Fórmula Personalizada (outros)',
                    'Critério de Grupo com Rec. Paralela',
                    'Critério de Grupo com Rec. Semestral',
                    'Critério de Grupo (outros)',
                    'Outros Critérios'
                ],
                'Quantidade': [
                    total_formula_paralela,
                    total_formula_semestral,
                    total_formula - total_formula_paralela - total_formula_semestral,
                    total_grupo_paralela,
                    total_grupo_semestral,
                    total_grupo - total_grupo_paralela - total_grupo_semestral,
                    total_criterios - total_formula - total_grupo
                ]
            }
            
            df_pizza = pd.DataFrame(dados_pizza)
            
            # Remover categorias com zero
            df_pizza = df_pizza[df_pizza['Quantidade'] > 0]
            
            # Gráfico de pizza das categorias
            fig_pizza = px.pie(
                df_pizza,
                values='Quantidade',
                names='Categoria',
                title='Distribuição dos Critérios por Categoria',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig_pizza, use_container_width=True)
            
            # Top entidades por matrículas
            st.subheader(f"Top {num_entidades} Entidades por Matrículas")
            
            df_top_matriculas = df_filtrado.sort_values('total_matriculas', ascending=False).head(num_entidades)
            
            fig_matriculas = px.bar(
                df_top_matriculas,
                x='nome_entidade',
                y='total_matriculas',
                title=f'Top {num_entidades} Entidades por Número de Matrículas',
                labels={'nome_entidade': 'Entidade', 'total_matriculas': 'Total de Matrículas'}
            )
            fig_matriculas.update_layout(xaxis={'categoryorder':'total descending'})
            st.plotly_chart(fig_matriculas, use_container_width=True)
        
        with tab2:
            st.header("Análise por Categoria")
            
            # Seletor de categoria para análise
            categoria_selecionada = st.selectbox(
                "Selecione a categoria para análise detalhada",
                [
                    "Fórmula Personalizada",
                    "Critérios de Grupo",
                    "Grupo com Recuperação Paralela",
                    "Grupo com Recuperação Semestral",
                    "Fórmula com Recuperação Paralela",
                    "Fórmula com Recuperação Semestral"
                ]
            )
            
            # Mapeamento de categoria para coluna
            mapa_categorias = {
                "Fórmula Personalizada": "formula_personalizada",
                "Critérios de Grupo": "criterio_grupo",
                "Grupo com Recuperação Paralela": "grupo_rec_paralela",
                "Grupo com Recuperação Semestral": "grupo_rec_semestral",
                "Fórmula com Recuperação Paralela": "formula_rec_paralela",
                "Fórmula com Recuperação Semestral": "formula_rec_semestral"
            }
            
            coluna_categoria = mapa_categorias[categoria_selecionada]
            
            # Top entidades para a categoria selecionada
            df_top_categoria = df_filtrado.sort_values(coluna_categoria, ascending=False).head(num_entidades)
            
            # Gráfico de barras para a categoria selecionada
            fig_categoria = px.bar(
                df_top_categoria,
                x='nome_entidade',
                y=coluna_categoria,
                title=f'Top {num_entidades} Entidades com Mais {categoria_selecionada}',
                labels={'nome_entidade': 'Entidade', coluna_categoria: f'Quantidade de {categoria_selecionada}'}
            )
            fig_categoria.update_layout(xaxis={'categoryorder':'total descending'})
            st.plotly_chart(fig_categoria, use_container_width=True)
            
            # Relação entre a categoria selecionada e matrículas
            fig_relacao = px.scatter(
                df_filtrado[df_filtrado[coluna_categoria] > 0],
                x=coluna_categoria,
                y='total_matriculas',
                size='total_matriculas',
                color='total_criterios',
                hover_name='nome_entidade',
                title=f'Relação entre {categoria_selecionada} e Matrículas',
                labels={
                    coluna_categoria: f'Quantidade de {categoria_selecionada}',
                    'total_matriculas': 'Total de Matrículas',
                    'total_criterios': 'Total de Critérios'
                }
            )
            st.plotly_chart(fig_relacao, use_container_width=True)
            
            # Tabela das entidades com essa categoria
            st.subheader(f"Entidades com {categoria_selecionada}")
            
            df_categoria = df_filtrado[df_filtrado[coluna_categoria] > 0].sort_values(coluna_categoria, ascending=False)
            
            # Preparar para exibição
            df_display_cat = df_categoria[['nome_entidade', 'total_criterios', coluna_categoria, 'total_matriculas', 'total_turmas']]
            df_display_cat['percentual'] = (df_display_cat[coluna_categoria] / df_display_cat['total_criterios'] * 100).round(1)
            
            # Renomear colunas
            df_display_cat = df_display_cat.rename(columns={
                'nome_entidade': 'Entidade',
                'total_criterios': 'Total de Critérios',
                coluna_categoria: categoria_selecionada,
                'total_matriculas': 'Total de Matrículas',
                'total_turmas': 'Total de Turmas',
                'percentual': f'% {categoria_selecionada}'
            })
            
            st.dataframe(df_display_cat, use_container_width=True)
        
        with tab3:
            st.header("Análise por Entidade")
            
            # Filtrar ainda mais para entidades específicas
            if len(df_filtrado) > 1:
                entidade_analise = st.selectbox(
                    "Selecione uma entidade para análise detalhada",
                    options=df_filtrado['nome_entidade'].tolist(),
                    index=0
                )
            
                # Filtrar para a entidade selecionada
                df_entidade = df_filtrado[df_filtrado['nome_entidade'] == entidade_analise].iloc[0]
                
                # Exibir métricas da entidade
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total de Critérios", int(df_entidade['total_criterios']))
                    st.metric("Total de Matrículas", int(df_entidade['total_matriculas']))
                    st.metric("Total de Turmas", int(df_entidade['total_turmas']))
                
                with col2:
                    st.metric("Fórmulas Personalizadas", int(df_entidade['formula_personalizada']))
                    st.metric("Fórmula com Rec. Paralela", int(df_entidade['formula_rec_paralela']))
                    st.metric("Fórmula com Rec. Semestral", int(df_entidade['formula_rec_semestral']))
                
                with col3:
                    st.metric("Critérios de Grupo", int(df_entidade['criterio_grupo']))
                    st.metric("Grupo com Rec. Paralela", int(df_entidade['grupo_rec_paralela']))
                    st.metric("Grupo com Rec. Semestral", int(df_entidade['grupo_rec_semestral']))
                
                # Gráfico de radar para visualizar todas as categorias
                categorias = [
                    'Fórmula Personalizada',
                    'Fórmula c/ Rec. Paralela',
                    'Fórmula c/ Rec. Semestral',
                    'Critérios de Grupo',
                    'Grupo c/ Rec. Paralela',
                    'Grupo c/ Rec. Semestral'
                ]
                
                valores = [
                    df_entidade['formula_personalizada'],
                    df_entidade['formula_rec_paralela'],
                    df_entidade['formula_rec_semestral'],
                    df_entidade['criterio_grupo'],
                    df_entidade['grupo_rec_paralela'],
                    df_entidade['grupo_rec_semestral']
                ]
                
                # Criar gráfico de radar
                fig_radar = go.Figure()
                
                fig_radar.add_trace(go.Scatterpolar(
                    r=valores,
                    theta=categorias,
                    fill='toself',
                    name=entidade_analise
                ))
                
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, max(valores) * 1.1]
                        )
                    ),
                    title=f"Perfil de Critérios Avaliativos de {entidade_analise}"
                )
                
                st.plotly_chart(fig_radar, use_container_width=True)
                
                # Gráfico de barras comparando as categorias
                df_barras = pd.DataFrame({
                    'Categoria': categorias,
                    'Quantidade': valores
                })
                
                fig_barras = px.bar(
                    df_barras,
                    x='Categoria',
                    y='Quantidade',
                    title=f"Distribuição de Critérios em {entidade_analise}",
                    labels={'Quantidade': 'Número de Critérios'}
                )
                
                st.plotly_chart(fig_barras, use_container_width=True)
            else:
                st.info("Selecione pelo menos uma entidade nos filtros para ver a análise detalhada.")
        
        # Tabela completa com todas as categorias
        st.header("Tabela Completa de Critérios Avaliativos")
        
        # Preparar para exibição
        df_display = df_filtrado.copy()
        df_display = df_display.rename(columns={
            'nome_entidade': 'Entidade',
            'total_criterios': 'Total de Critérios',
            'formula_personalizada': 'Fórmula Personalizada',
            'criterio_grupo': 'Critérios de Grupo',
            'grupo_rec_paralela': 'Grupo com Rec. Paralela',
            'grupo_rec_semestral': 'Grupo com Rec. Semestral',
            'formula_rec_paralela': 'Fórmula com Rec. Paralela',
            'formula_rec_semestral': 'Fórmula com Rec. Semestral',
            'total_matriculas': 'Total de Matrículas',
            'total_turmas': 'Total de Turmas'
        })
        
        # Remover coluna de ID para exibição
        df_display = df_display.drop(columns=['entidade_id'])
        
        # Opções de ordenação
        opcoes_ordenacao = {
            "Total de Critérios": "Total de Critérios",
            "Total de Matrículas": "Total de Matrículas",
            "Fórmulas Personalizadas": "Fórmula Personalizada",
            "Critérios de Grupo": "Critérios de Grupo"
        }
        
        coluna_ordenacao = st.selectbox(
            "Ordenar tabela por",
            options=list(opcoes_ordenacao.keys()),
            index=0
        )
        
        # Aplicar ordenação
        df_display = df_display.sort_values(opcoes_ordenacao[coluna_ordenacao], ascending=False)
        
        # Exibir tabela
        st.dataframe(df_display, use_container_width=True)
        
        # Botão para download dos dados
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download dos dados como CSV",
            data=csv,
            file_name="criterios_avaliativos_detalhados.csv",
            mime="text/csv",
        )
    else:
        st.error("Não foi possível carregar os dados necessários para a análise.")