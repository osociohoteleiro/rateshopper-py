import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import re
import sqlite3
import os

# Configuração da página
st.set_page_config(
    page_title="Rate Shopper Profissional",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuração do banco de dados
DB_FILE = "rate_shopper.db"

def init_database():
    """Inicializa o banco de dados SQLite com as tabelas necessárias"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabela de hotéis
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hoteis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            booking_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de relacionamentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS relacionamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_principal TEXT NOT NULL,
            concorrente TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hotel_principal) REFERENCES hoteis (nome),
            FOREIGN KEY (concorrente) REFERENCES hoteis (nome)
        )
    ''')
    
    # Tabela de importações (para títulos únicos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS importacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT UNIQUE NOT NULL,
            hotel TEXT NOT NULL,
            data_importacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_registros INTEGER DEFAULT 0,
            FOREIGN KEY (hotel) REFERENCES hoteis (nome)
        )
    ''')
    
    # Tabela de tarifas (com referência à importação)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tarifas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel TEXT NOT NULL,
            data DATE NOT NULL,
            preco REAL NOT NULL,
            sequencia INTEGER DEFAULT 1,
            importacao_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hotel) REFERENCES hoteis (nome),
            FOREIGN KEY (importacao_id) REFERENCES importacoes (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# CRUD para Hotéis
def criar_hotel(nome, booking_url=""):
    """Cria um novo hotel no banco"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO hoteis (nome, booking_url) VALUES (?, ?)", (nome, booking_url))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def listar_hoteis():
    """Lista todos os hotéis"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM hoteis ORDER BY nome", conn)
    conn.close()
    return df

def atualizar_hotel(nome_antigo, nome_novo, booking_url):
    """Atualiza dados de um hotel"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE hoteis SET nome = ?, booking_url = ? WHERE nome = ?", 
                   (nome_novo, booking_url, nome_antigo))
    conn.commit()
    conn.close()

def excluir_hotel(nome):
    """Exclui um hotel e todos os dados relacionados"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tarifas WHERE hotel = ?", (nome,))
    cursor.execute("DELETE FROM relacionamentos WHERE hotel_principal = ? OR concorrente = ?", (nome, nome))
    cursor.execute("DELETE FROM importacoes WHERE hotel = ?", (nome,))
    cursor.execute("DELETE FROM hoteis WHERE nome = ?", (nome,))
    conn.commit()
    conn.close()

# CRUD para Relacionamentos
def criar_relacionamento(hotel_principal, concorrente):
    """Cria um relacionamento entre hotéis"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO relacionamentos (hotel_principal, concorrente) VALUES (?, ?)", 
                   (hotel_principal, concorrente))
    conn.commit()
    conn.close()

def listar_relacionamentos():
    """Lista todos os relacionamentos"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT hotel_principal, GROUP_CONCAT(concorrente, ', ') as concorrentes
        FROM relacionamentos 
        GROUP BY hotel_principal
        ORDER BY hotel_principal
    """, conn)
    conn.close()
    return df

def excluir_relacionamentos(hotel_principal):
    """Exclui todos os relacionamentos de um hotel"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM relacionamentos WHERE hotel_principal = ?", (hotel_principal,))
    conn.commit()
    conn.close()

def obter_concorrentes(hotel_principal):
    """Obtém lista de concorrentes de um hotel"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT concorrente FROM relacionamentos WHERE hotel_principal = ?", (hotel_principal,))
    concorrentes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return concorrentes

# CRUD para Importações
def criar_importacao(titulo, hotel, total_registros):
    """Cria uma nova importação"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO importacoes (titulo, hotel, total_registros) VALUES (?, ?, ?)", 
                   (titulo, hotel, total_registros))
    importacao_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return importacao_id

def listar_importacoes():
    """Lista todas as importações"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT id, titulo, hotel, data_importacao, total_registros
        FROM importacoes 
        ORDER BY data_importacao DESC
    """, conn)
    conn.close()
    return df

def excluir_importacao(importacao_id):
    """Exclui uma importação e todas as tarifas relacionadas"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Primeiro, obter informações da importação para identificar as tarifas relacionadas
    cursor.execute("SELECT hotel, titulo FROM importacoes WHERE id = ?", (importacao_id,))
    importacao_info = cursor.fetchone()
    
    if importacao_info:
        hotel, titulo = importacao_info
        # Como não temos importacao_id na tabela tarifas, vamos excluir apenas a importação
        # As tarifas ficam no sistema (não há como identificar quais pertencem a esta importação específica)
        cursor.execute("DELETE FROM importacoes WHERE id = ?", (importacao_id,))
    
    conn.commit()
    conn.close()

# CRUD para Tarifas
def criar_tarifa(hotel, data, preco, sequencia):
    """Cria uma nova tarifa"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tarifas (hotel, data, preco, sequencia) VALUES (?, ?, ?, ?)",
                   (hotel, data, preco, sequencia))
    conn.commit()
    conn.close()

def listar_tarifas():
    """Lista todas as tarifas"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT id, hotel, data, preco, sequencia, created_at
        FROM tarifas 
        ORDER BY hotel, data, sequencia
    """, conn)
    conn.close()
    return df

def listar_tarifas_por_hotel(hotel):
    """Lista tarifas de um hotel específico"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT id, hotel, data, preco, sequencia, created_at
        FROM tarifas 
        WHERE hotel = ? 
        ORDER BY data, sequencia
    """, conn, params=(hotel,))
    conn.close()
    return df

def excluir_tarifa(tarifa_id):
    """Exclui uma tarifa específica"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tarifas WHERE id = ?", (tarifa_id,))
    conn.commit()
    conn.close()

def importar_tarifas_excel(hotel, df_excel, titulo_importacao):
    """Importa tarifas de um DataFrame do Excel"""
    # Inserir tarifas diretamente (sem sistema de importações por enquanto)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    for _, row in df_excel.iterrows():
        data = row['data']
        preco = row['preco']
        sequencia = row.get('sequencia', 1)
        
        cursor.execute("INSERT INTO tarifas (hotel, data, preco, sequencia) VALUES (?, ?, ?, ?)", 
                       (hotel, data, preco, sequencia))
    
    conn.commit()
    conn.close()
    return len(df_excel)  # Retorna quantidade de tarifas importadas

# CSS customizado para aparência profissional (MANTENDO LAYOUT ATUAL)
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #2F5597 0%, #4472C4 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #4472C4;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        color: #333333;
    }
    .metric-card strong {
        color: #1976D2;
    }
    .metric-card small {
        color: #666666;
    }
    .hotel-principal {
        background-color: #FFF2CC !important;
        font-weight: bold;
        border: 2px solid #F1C40F;
        color: #B7950B;
    }
    .ameaca {
        background-color: #FFCDD2 !important;
        color: #B71C1C !important;
        font-weight: bold;
    }
    .seguro {
        background-color: #C8E6C9 !important;
        color: #1B5E20 !important;
        font-weight: bold;
    }
    .neutro {
        background-color: #F5F5F5 !important;
        color: #424242 !important;
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    .stSelectbox > div > div {
        background-color: white;
    }
    .stSelectbox > div > div > div {
        color: #333333 !important;
    }
    .stSelectbox label {
        color: #333333 !important;
    }
    .upload-area {
        border: 2px dashed #4472C4;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        background-color: #f8f9fa;
        margin: 1rem 0;
    }
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .warning-message {
        background-color: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #dc3545;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar banco de dados
init_database()

# Função para inserir dados iniciais se não existirem
def inserir_dados_iniciais():
    """Insere dados iniciais se o banco estiver vazio"""
    hoteis_df = listar_hoteis()
    if len(hoteis_df) == 0:
        # Inserir hotéis iniciais
        hoteis_iniciais = [
            ("ECOENCANTO", "https://booking.com/ecoencanto"),
            ("VENICE HOTEL", "https://booking.com/venice"),
            ("VILA DA LAGOA", "https://booking.com/vilalagoa"),
            ("ILHA VITÓRIA", "https://booking.com/ilhavitoria"),
            ("MANUS HOTEL", "https://booking.com/manus"),
            ("POUSADA XPTO", "https://booking.com/xpto"),
            ("HOTEL SABARÁ", "https://booking.com/sabara"),
            ("LAGOA RESORT", "https://booking.com/lagoaresort")
        ]
        
        for nome, url in hoteis_iniciais:
            criar_hotel(nome, url)
        
        # Inserir relacionamentos iniciais
        relacionamentos_iniciais = [
            ("ECOENCANTO", "VENICE HOTEL"),
            ("ECOENCANTO", "VILA DA LAGOA"),
            ("ECOENCANTO", "HOTEL SABARÁ"),
            ("VENICE HOTEL", "ECOENCANTO"),
            ("VENICE HOTEL", "MANUS HOTEL"),
            ("VENICE HOTEL", "POUSADA XPTO")
        ]
        
        for principal, concorrente in relacionamentos_iniciais:
            criar_relacionamento(principal, concorrente)

# Inserir dados iniciais
inserir_dados_iniciais()

# Header principal (MANTENDO LAYOUT ATUAL)
st.markdown("""
<div class="main-header">
    <h1>🏨 RATE SHOPPER PROFISSIONAL</h1>
    <p>Sistema completo de análise competitiva hoteleira com períodos longos</p>
</div>
""", unsafe_allow_html=True)

# Sidebar para navegação com logotipo e links diretos
# Logotipo
try:
    st.sidebar.image("logo_osh.png", width=200)
except:
    st.sidebar.markdown("**OSH - O Sócio Hoteleiro**")

st.sidebar.markdown("---")

# Links diretos ao invés de dropdown
if st.sidebar.button("🏨 Cadastro de Hotéis", use_container_width=True):
    st.session_state.pagina = "🏨 Cadastro de Hotéis"

if st.sidebar.button("👥 Relacionamentos", use_container_width=True):
    st.session_state.pagina = "👥 Relacionamentos"

if st.sidebar.button("💰 Gestão de Tarifas", use_container_width=True):
    st.session_state.pagina = "💰 Gestão de Tarifas"

if st.sidebar.button("📊 Matriz Comparativa", use_container_width=True):
    st.session_state.pagina = "📊 Matriz Comparativa"

# Inicializar página padrão se não existir
if 'pagina' not in st.session_state:
    st.session_state.pagina = "🏨 Cadastro de Hotéis"

pagina = st.session_state.pagina

# Página: Cadastro de Hotéis (MANTENDO LAYOUT ATUAL)
if pagina == "🏨 Cadastro de Hotéis":
    st.header("🏨 Cadastro de Hotéis")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Adicionar Novo Hotel")
        
        with st.form("form_hotel"):
            nome_hotel = st.text_input("Nome do Hotel:", placeholder="Ex: HOTEL EXEMPLO")
            booking_url = st.text_input("Link do Booking:", placeholder="https://booking.com/hotel-exemplo")
            
            if st.form_submit_button("➕ Adicionar Hotel", type="primary"):
                if nome_hotel:
                    if criar_hotel(nome_hotel, booking_url):
                        st.success(f"✅ Hotel '{nome_hotel}' adicionado com sucesso!")
                        st.rerun()
                    else:
                        st.error(f"❌ Hotel '{nome_hotel}' já existe!")
                else:
                    st.error("❌ Nome do hotel é obrigatório!")
    
    with col2:
        st.subheader("Remover Hotel")
        hoteis_df = listar_hoteis()
        if len(hoteis_df) > 0:
            hotel_remover = st.selectbox("Selecione:", hoteis_df['nome'].tolist(), key="remover")
            if st.button("🗑️ Remover", type="secondary"):
                excluir_hotel(hotel_remover)
                st.success(f"✅ Hotel '{hotel_remover}' removido!")
                st.rerun()
    
    # Lista de hotéis cadastrados (MANTENDO LAYOUT ATUAL)
    st.subheader("Hotéis Cadastrados")
    hoteis_df = listar_hoteis()
    
    if len(hoteis_df) > 0:
        # Criar tabela HTML (mantendo formato atual)
        html_table = "<table style='width:100%; border-collapse: collapse;'>"
        html_table += "<tr style='background-color: #f2f2f2;'><th style='border: 1px solid #ddd; padding: 8px;'>🏨 Hotel</th><th style='border: 1px solid #ddd; padding: 8px;'>🔗 Link Booking</th></tr>"
        
        for _, row in hoteis_df.iterrows():
            link_html = f'<a href="{row["booking_url"]}" target="_blank">{row["booking_url"]}</a>' if row["booking_url"] else "Não informado"
            html_table += f"<tr><td style='border: 1px solid #ddd; padding: 8px;'>{row['nome']}</td><td style='border: 1px solid #ddd; padding: 8px;'>{link_html}</td></tr>"
        
        html_table += "</table>"
        st.markdown(html_table, unsafe_allow_html=True)
    else:
        st.info("📝 Nenhum hotel cadastrado ainda.")

# Página: Relacionamentos (MANTENDO LAYOUT ATUAL)
elif pagina == "👥 Relacionamentos":
    st.header("👥 Relacionamento de Concorrentes")
    
    hoteis_df = listar_hoteis()
    if len(hoteis_df) == 0:
        st.warning("⚠️ Cadastre hotéis primeiro!")
    else:
        hoteis_lista = hoteis_df['nome'].tolist()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Configurar Relacionamentos")
            
            hotel_principal = st.selectbox("Selecione o hotel principal:", hoteis_lista)
            
            # Obter concorrentes atuais
            concorrentes_atuais = obter_concorrentes(hotel_principal)
            
            # Filtrar hotéis disponíveis (excluir o hotel principal)
            hoteis_disponiveis = [h for h in hoteis_lista if h != hotel_principal]
            
            if hoteis_disponiveis:
                concorrentes_selecionados = st.multiselect(
                    f"Concorrentes de {hotel_principal}:",
                    hoteis_disponiveis,
                    default=concorrentes_atuais
                )
                
                if st.button("💾 Salvar Relacionamentos", type="primary"):
                    # Excluir relacionamentos antigos
                    excluir_relacionamentos(hotel_principal)
                    
                    # Criar novos relacionamentos
                    for concorrente in concorrentes_selecionados:
                        criar_relacionamento(hotel_principal, concorrente)
                    
                    st.success(f"✅ Relacionamentos salvos para {hotel_principal}!")
                    st.rerun()
        
        with col2:
            st.subheader("Limpar")
            hotel_limpar = st.selectbox("Hotel:", hoteis_lista, key="limpar")
            if st.button("🗑️ Limpar Relacionamentos", type="secondary"):
                excluir_relacionamentos(hotel_limpar)
                st.success(f"✅ Relacionamentos de '{hotel_limpar}' removidos!")
                st.rerun()
        
        # Exibir relacionamentos atuais (MANTENDO LAYOUT ATUAL)
        st.subheader("Relacionamentos Atuais")
        relacionamentos_df = listar_relacionamentos()
        
        if len(relacionamentos_df) > 0:
            for _, row in relacionamentos_df.iterrows():
                st.markdown(f"""
                <div class="metric-card">
                    <strong>🏨 {row['hotel_principal']}</strong><br>
                    <small>Concorrentes: {row['concorrentes']}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("📝 Nenhum relacionamento configurado ainda.")

# Página: Gestão de Tarifas (MANTENDO LAYOUT ATUAL)
elif pagina == "💰 Gestão de Tarifas":
    st.header("💰 Gestão de Tarifas")
    
    hoteis_df = listar_hoteis()
    if len(hoteis_df) == 0:
        st.warning("⚠️ Cadastre hotéis primeiro!")
    else:
        hoteis_lista = hoteis_df['nome'].tolist()
        
        # Tabs para diferentes funcionalidades (MANTENDO LAYOUT ATUAL)
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Adicionar Tarifa", "📤 Importar Excel", "📋 Visualizar Tarifas", "📦 Importações", "🗑️ Excluir"])
        
        with tab1:
            st.subheader("➕ Adicionar Tarifa Manual")
            
            with st.form("form_tarifa"):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    hotel_tarifa = st.selectbox("Hotel:", hoteis_lista)
                
                with col2:
                    data_tarifa = st.date_input("Data:", value=datetime.now().date())
                
                with col3:
                    preco_tarifa = st.number_input("Preço (R$):", min_value=0.0, step=0.01)
                
                with col4:
                    sequencia_tarifa = st.number_input("Sequência:", min_value=1, value=1, step=1)
                
                if st.form_submit_button("💾 Salvar Tarifa", type="primary"):
                    if preco_tarifa > 0:
                        criar_tarifa(hotel_tarifa, data_tarifa, preco_tarifa, sequencia_tarifa)
                        st.success(f"✅ Tarifa salva: {hotel_tarifa} - {data_tarifa} - R$ {preco_tarifa:.2f}")
                        st.rerun()
                    else:
                        st.error("❌ Preço deve ser maior que zero!")
        
        with tab2:
            st.subheader("📤 Importar Tarifas do Excel")
            
            hotel_importar = st.selectbox("Selecione o Hotel:", hoteis_lista, key="import")
            
            # Campo para título da importação
            titulo_importacao = st.text_input(
                "Título da Importação:",
                value=f"{hotel_importar}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                help="Título único para identificar esta importação"
            )
            
            uploaded_file = st.file_uploader(
                "Escolha o arquivo Excel:",
                type=['xlsx', 'xls'],
                help="Arquivo no formato: data_inicio | data_fim | preco"
            )
            
            if uploaded_file is not None:
                try:
                    df_excel = pd.read_excel(uploaded_file)
                    
                    st.write("📋 Prévia dos dados:")
                    st.dataframe(df_excel.head())
                    
                    # Processar formato específico da planilha do usuário
                    if len(df_excel.columns) == 3:
                        # Renomear colunas para formato padrão
                        df_processado = df_excel.copy()
                        df_processado.columns = ['data_inicio', 'data_fim', 'preco']
                        
                        # Converter preços (formato brasileiro com vírgula)
                        df_processado['preco'] = df_processado['preco'].astype(str).str.replace(',', '.').astype(float)
                        
                        # Usar data_inicio como data principal
                        df_processado['data'] = pd.to_datetime(df_processado['data_inicio'], format='%d/%m/%Y').dt.date
                        df_processado['sequencia'] = 1
                        
                        # Preparar DataFrame final para importação
                        df_final = df_processado[['data', 'preco', 'sequencia']].copy()
                        
                        st.write("📊 Dados processados:")
                        st.dataframe(df_final.head())
                        
                        if titulo_importacao and st.button("🚀 Importar Tarifas", type="primary"):
                            try:
                                qtd_importadas = importar_tarifas_excel(hotel_importar, df_final, titulo_importacao)
                                st.success(f"✅ {qtd_importadas} tarifas importadas para {hotel_importar}!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao importar: {str(e)}")
                    else:
                        st.error(f"❌ Formato incorreto! Esperado 3 colunas, encontrado {len(df_excel.columns)}")
                
                except Exception as e:
                    st.error(f"❌ Erro ao processar arquivo: {str(e)}")
        
        with tab3:
            st.subheader("📋 Tarifas Cadastradas")
            
            hotel_visualizar = st.selectbox("Filtrar por Hotel:", ["Todos"] + hoteis_lista, key="visualizar")
            
            if hotel_visualizar == "Todos":
                tarifas_df = listar_tarifas()
            else:
                tarifas_df = listar_tarifas_por_hotel(hotel_visualizar)
            
            if len(tarifas_df) > 0:
                # Preparar dados para exibição
                df_display = tarifas_df.copy()
                df_display['data'] = pd.to_datetime(df_display['data']).dt.strftime('%d/%m/%Y')
                df_display['preco'] = df_display['preco'].apply(lambda x: f"R$ {x:.2f}")
                df_display = df_display[['hotel', 'data', 'preco', 'sequencia']].rename(columns={
                    'hotel': 'Hotel',
                    'data': 'Data',
                    'preco': 'Preço',
                    'sequencia': 'Seq'
                })
                
                st.dataframe(df_display, use_container_width=True)
                
                # Estatísticas
                st.subheader("📊 Estatísticas")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total de Registros", len(tarifas_df))
                
                with col2:
                    preco_medio = tarifas_df['preco'].mean()
                    st.metric("Preço Médio", f"R$ {preco_medio:.2f}")
                
                with col3:
                    preco_min = tarifas_df['preco'].min()
                    st.metric("Menor Preço", f"R$ {preco_min:.2f}")
                
                with col4:
                    preco_max = tarifas_df['preco'].max()
                    st.metric("Maior Preço", f"R$ {preco_max:.2f}")
            else:
                st.info("📝 Nenhuma tarifa cadastrada ainda.")
        
        with tab4:
            st.subheader("📦 Gerenciar Importações")
            
            importacoes_df = listar_importacoes()
            
            if len(importacoes_df) > 0:
                # Filtro por hotel
                hoteis_importacao = ["Todos"] + sorted(importacoes_df['hotel'].unique().tolist())
                filtro_hotel = st.selectbox(
                    "🏨 Filtrar por Hotel:",
                    hoteis_importacao,
                    key="filtro_importacoes"
                )
                
                # Aplicar filtro
                if filtro_hotel != "Todos":
                    importacoes_filtradas = importacoes_df[importacoes_df['hotel'] == filtro_hotel]
                else:
                    importacoes_filtradas = importacoes_df
                
                st.write(f"**Importações Realizadas ({len(importacoes_filtradas)} de {len(importacoes_df)}):**")
                
                for _, row in importacoes_filtradas.iterrows():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        data_formatada = pd.to_datetime(row['data_importacao']).strftime('%d/%m/%Y %H:%M')
                        st.markdown(f"""
                        **📦 {row['titulo']}**  
                        Hotel: {row['hotel']} | Data: {data_formatada} | Registros: {row['total_registros']}
                        """)
                    
                    with col2:
                        if st.button(f"🗑️ Excluir", key=f"del_imp_{row['id']}", type="secondary"):
                            excluir_importacao(row['id'])
                            st.success(f"✅ Importação '{row['titulo']}' excluída!")
                            st.rerun()
                    
                    st.divider()
            else:
                st.info("📝 Nenhuma importação realizada ainda.")
        
        with tab5:
            st.subheader("🗑️ Excluir Tarifas")
            
            # Seção para limpar todas as tarifas
            st.markdown("### 🧹 Limpeza em Massa")
            st.warning("⚠️ Esta ação irá excluir TODAS as tarifas do sistema!")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("🧹 LIMPAR TODAS AS TARIFAS", type="primary"):
                    try:
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM tarifas")
                        conn.commit()
                        conn.close()
                        st.success("✅ Todas as tarifas foram excluídas com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao limpar tarifas: {str(e)}")
            
            with col2:
                tarifas_count = len(listar_tarifas())
                st.metric("Total de Tarifas", tarifas_count)
            
            st.divider()
            
            # Seção para excluir tarifas individuais
            st.markdown("### 🎯 Exclusão Individual")
            
            tarifas_df = listar_tarifas()
            if len(tarifas_df) > 0:
                # Criar lista de opções para o dropdown
                opcoes_tarifas = []
                for _, row in tarifas_df.iterrows():
                    data_formatada = pd.to_datetime(row['data']).strftime('%d/%m/%Y')
                    opcao = f"{row['hotel']} - {data_formatada} - R$ {row['preco']:.2f} (Seq: {row['sequencia']})"
                    opcoes_tarifas.append((opcao, row['id']))
                
                tarifa_selecionada = st.selectbox(
                    "Selecione a tarifa para excluir:",
                    options=[opcao[0] for opcao in opcoes_tarifas]
                )
                
                if st.button("🗑️ Excluir Tarifa Selecionada", type="secondary"):
                    # Encontrar o ID da tarifa selecionada
                    tarifa_id = next(opcao[1] for opcao in opcoes_tarifas if opcao[0] == tarifa_selecionada)
                    excluir_tarifa(tarifa_id)
                    st.success("✅ Tarifa excluída com sucesso!")
                    st.rerun()
            else:
                st.info("📝 Nenhuma tarifa cadastrada para excluir.")

# Página: Matriz Comparativa (MANTENDO LAYOUT ATUAL)
elif pagina == "📊 Matriz Comparativa":
    st.header("📊 Matriz Comparativa de Preços")
    
    hoteis_df = listar_hoteis()
    tarifas_df = listar_tarifas()
    
    if len(hoteis_df) == 0:
        st.warning("⚠️ Cadastre hotéis primeiro!")
    elif len(tarifas_df) == 0:
        st.warning("⚠️ Cadastre tarifas primeiro!")
    else:
        # Controles da matriz (MANTENDO LAYOUT ATUAL)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hotel_principal = st.selectbox("🏨 Hotel Principal:", hoteis_df['nome'].tolist())
        
        with col2:
            data_inicio = st.date_input("📅 Data Início:", value=datetime.now().date())
        
        with col3:
            data_fim = st.date_input("📅 Data Fim:", value=datetime.now().date() + timedelta(days=30))
        
        # Validação do período
        if data_inicio and data_fim and data_inicio > data_fim:
            st.error("❌ Data de início deve ser anterior à data de fim!")
        elif data_inicio and data_fim:
            # Filtrar tarifas do período
            tarifas_periodo = tarifas_df[
                (pd.to_datetime(tarifas_df['data']).dt.date >= data_inicio) &
                (pd.to_datetime(tarifas_df['data']).dt.date <= data_fim)
            ].copy()
            
            if len(tarifas_periodo) == 0:
                st.warning("⚠️ Nenhuma tarifa encontrada no período selecionado!")
            else:
                # Obter concorrentes do hotel principal
                concorrentes = obter_concorrentes(hotel_principal)
                
                # Incluir o hotel principal na lista
                hoteis_matriz = [hotel_principal] + concorrentes
                
                # Filtrar tarifas apenas dos hotéis relevantes
                tarifas_matriz = tarifas_periodo[tarifas_periodo['hotel'].isin(hoteis_matriz)].copy()
                
                if len(tarifas_matriz) == 0:
                    st.warning("⚠️ Nenhuma tarifa encontrada para os hotéis selecionados no período!")
                else:
                    # Processar dados para a matriz (MANTENDO LÓGICA ATUAL)
                    tarifas_matriz['data'] = pd.to_datetime(tarifas_matriz['data']).dt.date
                    
                    # Agrupar por hotel e data, considerando múltiplas tarifas
                    matriz_dados = {}
                    
                    for hotel in hoteis_matriz:
                        matriz_dados[hotel] = {}
                        tarifas_hotel = tarifas_matriz[tarifas_matriz['hotel'] == hotel]
                        
                        for data in pd.date_range(data_inicio, data_fim).date:
                            tarifas_data = tarifas_hotel[tarifas_hotel['data'] == data]
                            
                            if len(tarifas_data) == 0:
                                matriz_dados[hotel][data] = None
                            elif len(tarifas_data) == 1:
                                matriz_dados[hotel][data] = tarifas_data.iloc[0]['preco']
                            else:
                                # Múltiplas tarifas - mostrar variação
                                precos = tarifas_data['preco'].tolist()
                                preco_min = min(precos)
                                preco_max = max(precos)
                                variacao_pct = ((preco_max - preco_min) / preco_min) * 100
                                
                                if variacao_pct > 0:
                                    matriz_dados[hotel][data] = f"{preco_min:.0f}→{preco_max:.0f}"
                                else:
                                    matriz_dados[hotel][data] = preco_min
                    
                    # Criar DataFrame da matriz
                    datas_periodo = pd.date_range(data_inicio, data_fim).date
                    df_matriz = pd.DataFrame(index=hoteis_matriz, columns=datas_periodo)
                    
                    for hotel in hoteis_matriz:
                        for data in datas_periodo:
                            df_matriz.loc[hotel, data] = matriz_dados[hotel][data]
                    
                    # Exibir matriz (MANTENDO LAYOUT ATUAL)
                    st.subheader(f"🎯 Análise Competitiva - {hotel_principal}")
                    
                    # Criar HTML da matriz com cores (MANTENDO LÓGICA ATUAL)
                    html_matriz = "<table style='width:100%; border-collapse: collapse;'>"
                    
                    # Cabeçalho
                    html_matriz += "<tr><th style='border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2;'>Hotel</th>"
                    for data in datas_periodo:
                        data_str = data.strftime('%d/%m')
                        html_matriz += f"<th style='border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2; text-align: center;'>{data_str}</th>"
                    html_matriz += "</tr>"
                    
                    # Linhas dos hotéis
                    for hotel in hoteis_matriz:
                        html_matriz += "<tr>"
                        
                        # Nome do hotel
                        if hotel == hotel_principal:
                            html_matriz += f"<td style='border: 1px solid #ddd; padding: 8px; background-color: #FFF2CC; font-weight: bold; color: #B7950B;'>{hotel}</td>"
                        else:
                            html_matriz += f"<td style='border: 1px solid #ddd; padding: 8px; font-weight: bold;'>{hotel}</td>"
                        
                        # Preços por data
                        for data in datas_periodo:
                            valor = df_matriz.loc[hotel, data]
                            
                            if valor is None or pd.isna(valor):
                                html_matriz += "<td style='border: 1px solid #ddd; padding: 8px; text-align: center; color: #999;'>-</td>"
                            else:
                                if hotel == hotel_principal:
                                    # Hotel principal sempre em amarelo
                                    if isinstance(valor, str) and '→' in valor:
                                        html_matriz += f"<td style='border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #FFF2CC; font-weight: bold; color: #B7950B;'>{valor}</td>"
                                    else:
                                        html_matriz += f"<td style='border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #FFF2CC; font-weight: bold; color: #B7950B;'>R$ {valor:.0f}</td>"
                                else:
                                    # Concorrentes - comparar com hotel principal
                                    valor_principal = df_matriz.loc[hotel_principal, data]
                                    
                                    if valor_principal is not None and not pd.isna(valor_principal):
                                        # Extrair valor numérico do hotel principal
                                        if isinstance(valor_principal, str) and '→' in valor_principal:
                                            valor_principal_num = float(valor_principal.split('→')[0])
                                        else:
                                            valor_principal_num = float(valor_principal)
                                        
                                        # Extrair valor numérico do concorrente
                                        if isinstance(valor, str) and '→' in valor:
                                            valor_concorrente_num = float(valor.split('→')[0])
                                        else:
                                            valor_concorrente_num = float(valor)
                                        
                                        # Determinar cor baseada na comparação
                                        if valor_concorrente_num < valor_principal_num * 0.95:  # 5% mais barato
                                            cor_fundo = "#FFCDD2"  # Vermelho - AMEAÇA
                                            cor_texto = "#B71C1C"
                                        elif valor_concorrente_num > valor_principal_num * 1.05:  # 5% mais caro
                                            cor_fundo = "#C8E6C9"  # Verde - SEGURO
                                            cor_texto = "#1B5E20"
                                        else:
                                            cor_fundo = "#F5F5F5"  # Cinza - NEUTRO
                                            cor_texto = "#424242"
                                        
                                        if isinstance(valor, str) and '→' in valor:
                                            html_matriz += f"<td style='border: 1px solid #ddd; padding: 8px; text-align: center; background-color: {cor_fundo}; color: {cor_texto}; font-weight: bold;'>{valor}</td>"
                                        else:
                                            html_matriz += f"<td style='border: 1px solid #ddd; padding: 8px; text-align: center; background-color: {cor_fundo}; color: {cor_texto}; font-weight: bold;'>R$ {valor:.0f}</td>"
                                    else:
                                        if isinstance(valor, str) and '→' in valor:
                                            html_matriz += f"<td style='border: 1px solid #ddd; padding: 8px; text-align: center;'>{valor}</td>"
                                        else:
                                            html_matriz += f"<td style='border: 1px solid #ddd; padding: 8px; text-align: center;'>R$ {valor:.0f}</td>"
                        
                        html_matriz += "</tr>"
                    
                    html_matriz += "</table>"
                    
                    # Adicionar scroll horizontal APENAS na tabela
                    st.markdown(f"""
                    <div style="overflow-x: auto; max-width: 100%;">
                        {html_matriz}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Legenda (MANTENDO LAYOUT ATUAL)
                    st.markdown("""
                    **📋 Legenda:**
                    - 🟡 **Amarelo:** Seu hotel (sempre destacado)
                    - 🔴 **Vermelho:** Concorrente mais barato (AMEAÇA - monitorar!)
                    - 🟢 **Verde:** Concorrente mais caro (SEGURO - sem preocupação)
                    - ⚪ **Branco:** Preços similares (NEUTRO - acompanhar)
                    - **Formato "X→Y":** Múltiplas tarifas na mesma data
                    """)
                    
                    # Gráfico de linhas (ADICIONANDO VISUALIZAÇÃO)
                    st.subheader("📈 Evolução dos Preços")
                    
                    # Preparar dados para o gráfico
                    import plotly.graph_objects as go
                    from plotly.subplots import make_subplots
                    
                    fig = go.Figure()
                    
                    # Cores para cada hotel
                    cores_hoteis = {
                        hotel_principal: '#FFA500',  # Laranja para hotel principal
                        'VENICE HOTEL': '#FF6B6B',   # Vermelho
                        'GRAND PLAZA': '#4ECDC4',    # Azul claro
                        'Mirante da Lagoinha': '#45B7D1',  # Azul
                        'Hotel Teste Persistência': '#96CEB4',  # Verde claro
                        'Hotel Teste SQLite': '#FFEAA7'  # Amarelo claro
                    }
                    
                    for hotel in hoteis_matriz:
                        precos_hotel = []
                        datas_hotel = []
                        
                        # Incluir TODOS os dias do período (dia a dia)
                        for data in datas_periodo:
                            valor = df_matriz.loc[hotel, data]
                            datas_hotel.append(data)
                            
                            if valor is not None and not pd.isna(valor):
                                # Extrair valor numérico
                                if isinstance(valor, str) and '→' in valor:
                                    valor_num = float(valor.split('→')[0])
                                else:
                                    valor_num = float(valor)
                                precos_hotel.append(valor_num)
                            else:
                                # Para dias sem dados, usar None (cria lacuna na linha)
                                precos_hotel.append(None)
                        
                        # Sempre adiciona a linha (mesmo com lacunas)
                        cor = cores_hoteis.get(hotel, '#95A5A6')
                        largura = 4 if hotel == hotel_principal else 2
                        
                        fig.add_trace(go.Scatter(
                            x=datas_hotel,
                            y=precos_hotel,
                            mode='lines+markers',
                            name=hotel,
                            line=dict(color=cor, width=largura),
                            marker=dict(size=6 if hotel == hotel_principal else 4),
                            connectgaps=False  # Não conecta lacunas (dias sem dados)
                        ))
                    
                    # Configurar layout do gráfico
                    fig.update_layout(
                        title=f"Evolução de Preços - {hotel_principal} vs Concorrentes",
                        xaxis_title="Data",
                        yaxis_title="Preço (R$)",
                        height=400,
                        hovermode='x unified',
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        ),
                        xaxis=dict(
                            type='date',
                            dtick='D1',  # Força tick diário
                            tickformat='%d/%m',  # Formato dia/mês
                            tickangle=45,  # Rotaciona labels para melhor legibilidade
                            showgrid=True
                        )
                    )
                    
                    # Exibir gráfico
                    st.plotly_chart(fig, use_container_width=True)



