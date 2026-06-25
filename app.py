import streamlit as st
import pandas as pd
import io
import zipfile
import re

st.set_page_config(layout="wide", page_title="Conversor Dinâmico de Tabelas de Frete")

st.title("Conversor Dinâmico de Tabelas de Frete")
st.markdown("Faça o upload dos seus arquivos para iniciar o processo de conversão.")

def read_file(uploaded_file):
    if uploaded_file is not None:
        file_extension = uploaded_file.name.split('.')[-1]
        try:
            if file_extension == 'csv':
                # Tenta ler com diferentes delimitadores e encodings
                try:
                    df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8')
                except UnicodeDecodeError:
                    uploaded_file.seek(0) # Reset file pointer
                    df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
                except Exception:
                    uploaded_file.seek(0) # Reset file pointer
                    df = pd.read_csv(uploaded_file, encoding='latin1')
            elif file_extension in ['xlsx', 'xls']:
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            else:
                st.error(f"Formato de arquivo não suportado: .{file_extension}")
                return None
            return df
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            return None
    return None

def auto_map_columns(template_cols, client_cols):
    suggestions = {}
    for t_col in template_cols:
        best_match = None
        highest_score = 0
        for c_col in client_cols:
            # Simple substring match (case-insensitive)
            if t_col.lower() in c_col.lower() or c_col.lower() in t_col.lower():
                # A simple scoring: exact match is best, then partial
                if t_col.lower() == c_col.lower():
                    score = 100
                else:
                    score = 50 # Could be more sophisticated
                
                if score > highest_score:
                    highest_score = score
                    best_match = c_col
        
        if best_match:
            suggestions[t_col] = best_match
    return suggestions

# Colunas para upload de arquivos
col1, col2 = st.columns(2)

with col1:
    st.header("Arquivo Modelo / Gabarito")
    uploaded_template_file = st.file_uploader(
        "Selecione o arquivo que define a estrutura final (CSV, XLSX, XLS)",
        type=['csv', 'xlsx', 'xls'],
        key='template_file_uploader'
    )
    if uploaded_template_file:
        template_df = read_file(uploaded_template_file)
        if template_df is not None:
            st.subheader("Preview do Arquivo Modelo:")
            st.dataframe(template_df.head())
            st.session_state['template_df'] = template_df

with col2:
    st.header("Arquivo de Origem / Cliente")
    uploaded_client_file = st.file_uploader(
        "Selecione o arquivo com os dados brutos do cliente (CSV, XLSX, XLS)",
        type=['csv', 'xlsx', 'xls'],
        key='client_file_uploader'
    )
    if uploaded_client_file:
        client_df = read_file(uploaded_client_file)
        if client_df is not None:
            st.subheader("Preview do Arquivo do Cliente:")
            st.dataframe(client_df.head())
            st.session_state['client_df'] = client_df

# Placeholder para as próximas fases
if 'template_df' in st.session_state and 'client_df' in st.session_state:
    st.success("Ambos os arquivos foram carregados com sucesso! Prossiga para a próxima fase.")
    st.markdown("--- ")

    with st.expander("Configuração de Mapeamento e Região", expanded=True):
        st.header("FASE 2: Motor de Mapeamento Dinâmico (DE-PARA)")

        template_columns = st.session_state['template_df'].columns.tolist()
        client_columns = st.session_state['client_df'].columns.tolist()

        st.subheader("Mapeamento de Colunas")
        st.write("Para cada coluna do Arquivo Modelo, selecione a coluna correspondente no Arquivo do Cliente ou escolha preencher com um valor fixo.")

        # Inicializa mapping_choices e fixed_values se não existirem na session_state
        if 'mapping_choices' not in st.session_state:
            st.session_state['mapping_choices'] = {col: "-- Selecione --" for col in template_columns}
        if 'fixed_values' not in st.session_state:
            st.session_state['fixed_values'] = {col: "" for col in template_columns}

        # Botões de Ação Rápida
        col_btn1, col_btn2, _ = st.columns([1, 1, 4])
        with col_btn1:
            if st.button("Auto-Mapear"):
                suggestions = auto_map_columns(template_columns, client_columns)
                for t_col, c_col in suggestions.items():
                    st.session_state['mapping_choices'][t_col] = c_col
                st.experimental_rerun() # Rerun para atualizar os selectboxes
        with col_btn2:
            if st.button("Limpar Seleções"):
                st.session_state['mapping_choices'] = {col: "-- Selecione --" for col in template_columns}
                st.session_state['fixed_values'] = {col: "" for col in template_columns}
                st.experimental_rerun() # Rerun para atualizar os selectboxes

        # Layout em grade para os seletores de mapeamento
        cols_per_row = 3
        for i in range(0, len(template_columns), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(template_columns):
                    template_col = template_columns[i + j]
                    with cols[j]:
                        st.markdown(f"**Coluna Modelo: {template_col}**")
                        options = ["-- Selecione --", "[Preencher com Valor Fixo]"] + client_columns
                        
                        # Encontra o índice da opção pré-selecionada
                        current_selection = st.session_state['mapping_choices'].get(template_col, "-- Selecione --")
                        try:
                            default_index = options.index(current_selection)
                        except ValueError:
                            default_index = 0 # Default to "-- Selecione --" if not found

                        selected_option = st.selectbox(
                            f"Mapear \'{template_col}\' para:",
                            options,
                            index=default_index,
                            key=f"map_{template_col}"
                        )

                        st.session_state['mapping_choices'][template_col] = selected_option

                        if selected_option == "[Preencher com Valor Fixo]":
                            fixed_value = st.text_input(
                                f"Valor fixo para \'{template_col}':",
                                value=st.session_state['fixed_values'].get(template_col, ""),
                                key=f"fixed_{template_col}"
                            )
                            st.session_state['fixed_values'][template_col] = fixed_value
                        else:
                            st.session_state['fixed_values'][template_col] = "" # Limpa valor fixo se a opção mudar

        # Seção de Configuração de Região
        st.markdown("--- ")
        st.header("Configuração de Região")

        region_type_options = ["-- Selecione --", "Capital", "Interior", "Metropolitano"]
        selected_region_type = st.selectbox(
            "Selecione o Tipo de Região para esta tabela:",
            region_type_options,
            key='region_type_selector'
        )
        st.session_state['selected_region_type'] = selected_region_type

    # Lógica de processamento e download fora do expander, mas dependente das seleções
    if all(value is not None and value != "-- Selecione --" for value in st.session_state['mapping_choices'].values()) and \
       st.session_state['selected_region_type'] != "-- Selecione --":
        st.success("Mapeamento de colunas e Tipo de Região completos! Você pode prosseguir.")

        if st.button("Processar e Gerar Arquivo Final"):
            st.write("Iniciando processamento para gerar arquivo unificado...")

            # 1. Monta um novo DataFrame estruturado estritamente com as colunas do Arquivo Modelo.
            output_df = pd.DataFrame(columns=template_columns)

            # 2. Preenche esse DataFrame mapeando os dados do cliente e os valores fixos informados.
            for template_col in template_columns:
                mapped_source = st.session_state['mapping_choices'].get(template_col)
                if mapped_source == "[Preencher com Valor Fixo]":
                    output_df[template_col] = st.session_state['fixed_values'].get(template_col)
                elif mapped_source:
                    output_df[template_col] = st.session_state['client_df'][mapped_source]
                else:
                    output_df[template_col] = None # Caso não haja mapeamento

            # 3. Adiciona a nova coluna "Região" e preenche com o valor fixo selecionado.
            region_col_name_to_use = "Região" # Default name if not found in template
            if "Região" in template_columns:
                region_col_name_to_use = "Região"
            elif "Tipo Região" in template_columns:
                region_col_name_to_use = "Tipo Região"
            
            # Ensure the column exists in output_df before filling
            if region_col_name_to_use not in output_df.columns:
                output_df[region_col_name_to_use] = "" # Initialize if new
            
            output_df[region_col_name_to_use] = st.session_state['selected_region_type']


            st.success("Arquivo unificado processado com sucesso!")
            st.markdown("--- ")
            st.header("Download do Arquivo Final")

            # Gerar o CSV em memória
            csv_buffer = io.StringIO()
            output_df.to_csv(csv_buffer, sep=';', encoding='utf-8-sig', index=False)
            csv_buffer.seek(0)

            # Nome do arquivo dinâmico
            file_name = f"tabela_frete_{st.session_state['selected_region_type'].lower()}.csv"

            st.download_button(
                label="Baixar Arquivo CSV Unificado",
                data=csv_buffer.getvalue().encode('utf-8-sig'), # Ensure bytes for download
                file_name=file_name,
                mime="text/csv"
            )
