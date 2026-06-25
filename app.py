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
    st.header("FASE 2: Motor de Mapeamento Dinâmico (DE-PARA)")

    template_columns = st.session_state['template_df'].columns.tolist()
    client_columns = st.session_state['client_df'].columns.tolist()

    st.subheader("Mapeamento de Colunas")
    st.write("Para cada coluna do Arquivo Modelo, selecione a coluna correspondente no Arquivo do Cliente ou escolha preencher com um valor fixo.")

    mapping_choices = {}
    fixed_values = {}

    for col in template_columns:
        st.markdown(f"**Coluna Modelo: {col}**")
        options = ["-- Selecione --", "[Preencher com Valor Fixo]"] + client_columns
        selected_option = st.selectbox(
            f"Mapear \'{col}\' para:",
            options,
            key=f"map_{col}"
        )

        if selected_option == "[Preencher com Valor Fixo]":
            fixed_value = st.text_input(
                f"Valor fixo para \'{col}':",
                key=f"fixed_{col}"
            )
            fixed_values[col] = fixed_value
            mapping_choices[col] = "[Preencher com Valor Fixo]"
        elif selected_option != "-- Selecione --":
            mapping_choices[col] = selected_option
        else:
            mapping_choices[col] = None

    st.session_state['mapping_choices'] = mapping_choices
    st.session_state['fixed_values'] = fixed_values

    if all(value is not None for value in mapping_choices.values()) and all(value != "-- Selecione --" for value in mapping_choices.values()):
        st.success("Mapeamento de colunas completo! Você pode prosseguir.")
        st.markdown("--- ")
        st.header("Configuração de Região e Processamento")

        region_type_options = ["-- Selecione --", "Capital", "Interior", "Metropolitano"]
        selected_region_type = st.selectbox(
            "Selecione o Tipo de Região para esta tabela:",
            region_type_options,
            key='region_type_selector'
        )

        if selected_region_type != "-- Selecione --":
            st.session_state['selected_region_type'] = selected_region_type
            st.success(f"Tipo de Região selecionado: **{selected_region_type}**")

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
                
                output_df[region_col_name_to_use] = selected_region_type


                st.success("Arquivo unificado processado com sucesso!")
                st.markdown("--- ")
                st.header("Download do Arquivo Final")

                # Gerar o CSV em memória
                csv_buffer = io.StringIO()
                output_df.to_csv(csv_buffer, sep=';', encoding='utf-8-sig', index=False)
                csv_buffer.seek(0)

                st.download_button(
                    label="Baixar Arquivo CSV Unificado",
                    data=csv_buffer.getvalue().encode('utf-8-sig'), # Ensure bytes for download
                    file_name="tabela_frete_unificada.csv",
                    mime="text/csv"
                )
        # Aqui entrará a lógica da FASE 3
