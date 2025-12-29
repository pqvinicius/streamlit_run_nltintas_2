"""
Script para consultar o banco de dados de gamificação.
Uso: python consultar_db.py
"""
import sqlite3
from pathlib import Path
from datetime import date
import sys
import os

# Configura encoding para Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

# Caminho do banco
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "gamificacao_vendedores.db"

if not DB_PATH.exists():
    print(f"❌ Banco de dados não encontrado em: {DB_PATH}")
    sys.exit(1)

def consultar_metas_semanais():
    """Consulta todas as metas semanais salvas."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            vendedor_nome,
            semana_uuid,
            data_inicio,
            data_fim,
            meta_valor
        FROM metas_semanais
        ORDER BY semana_uuid DESC, vendedor_nome
        LIMIT 50
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Nenhuma meta semanal encontrada no banco.")
        return
    
    print(f"\nMETAS SEMANAIS SALVAS ({len(rows)} registros):\n")
    print(f"{'Vendedor':<30} {'Semana':<12} {'Início':<12} {'Fim':<12} {'Meta Total':>12}")
    print("-" * 90)
    
    for row in rows:
        print(f"{row['vendedor_nome']:<30} {row['semana_uuid']:<12} {row['data_inicio']:<12} {row['data_fim']:<12} {row['meta_valor']:>12,.2f}")

def consultar_resultados_diarios(data_ref: str = None):
    """Consulta resultados diários."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if data_ref:
        cursor.execute("""
            SELECT 
                vendedor_nome,
                data,
                meta,
                venda,
                alcance
            FROM resultado_meta
            WHERE data = ?
            ORDER BY alcance DESC
        """, (data_ref,))
    else:
        cursor.execute("""
            SELECT 
                vendedor_nome,
                data,
                meta,
                venda,
                alcance
            FROM resultado_meta
            ORDER BY data DESC, alcance DESC
            LIMIT 50
        """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Nenhum resultado diario encontrado.")
        return
    
    print(f"\nRESULTADOS DIARIOS ({len(rows)} registros):\n")
    print(f"{'Vendedor':<30} {'Data':<12} {'Meta':>12} {'Venda':>12} {'Alcance':>10}")
    print("-" * 90)
    
    for row in rows:
        print(f"{row['vendedor_nome']:<30} {row['data']:<12} {row['meta']:>12,.2f} {row['venda']:>12,.2f} {row['alcance']:>10.1f}%")

def consultar_trofeus():
    """Consulta troféus conquistados."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            vendedor_nome,
            data_conquista,
            tipo_trofeu,
            pontos,
            motivo
        FROM trofeus
        ORDER BY data_conquista DESC, pontos DESC
        LIMIT 50
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Nenhum trofeu encontrado.")
        return
    
    print(f"\nTROFEUS CONQUISTADOS ({len(rows)} registros):\n")
    print(f"{'Vendedor':<30} {'Data':<12} {'Tipo':<10} {'Pontos':>8} {'Motivo':<30}")
    print("-" * 100)
    
    for row in rows:
        print(f"{row['vendedor_nome']:<30} {row['data_conquista']:<12} {row['tipo_trofeu']:<10} {row['pontos']:>8} {row['motivo']:<30}")

def consultar_vendedores():
    """Consulta cadastro de vendedores."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            nome,
            loja,
            tipo,
            ativo
        FROM vendedores
        ORDER BY nome
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Nenhum vendedor cadastrado.")
        return
    
    print(f"\nVENDEDORES CADASTRADOS ({len(rows)} registros):\n")
    print(f"{'Nome':<40} {'Loja':<10} {'Tipo':<15} {'Ativo':<8}")
    print("-" * 80)
    
    for row in rows:
        ativo = "Sim" if row['ativo'] else "Não"
        print(f"{row['nome']:<40} {str(row['loja']):<10} {row['tipo']:<15} {ativo:<8}")

def consulta_customizada(query: str):
    """Executa uma consulta SQL customizada."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("Nenhum resultado encontrado.")
            return
        
        # Pega nomes das colunas
        colunas = [desc[0] for desc in cursor.description]
        
        # Calcula largura das colunas
        larguras = {}
        for col in colunas:
            larguras[col] = max(len(col), max(len(str(row[col])) for row in rows[:10])) + 2
        
        # Imprime cabeçalho
        header = " | ".join(f"{col:<{larguras[col]}}" for col in colunas)
        print(f"\nRESULTADO DA CONSULTA ({len(rows)} registros):\n")
        print(header)
        print("-" * len(header))
        
        # Imprime dados
        for row in rows[:50]:  # Limita a 50 linhas
            linha = " | ".join(f"{str(row[col]):<{larguras[col]}}" for col in colunas)
            print(linha)
        
        if len(rows) > 50:
            print(f"\n... e mais {len(rows) - 50} registros.")
            
    except Exception as e:
        print(f"❌ Erro na consulta: {e}")
    finally:
        conn.close()

def main():
    print("=" * 90)
    print("CONSULTOR DE BANCO DE DADOS - GAMIFICACAO DE VENDEDORES")
    print("=" * 90)
    print(f"\nBanco: {DB_PATH}")
    print(f"Banco encontrado: {DB_PATH.exists()}\n")
    
    while True:
        print("\n" + "=" * 90)
        print("MENU DE CONSULTAS:")
        print("=" * 90)
        print("1. Ver Metas Semanais")
        print("2. Ver Resultados Diários")
        print("3. Ver Troféus Conquistados")
        print("4. Ver Vendedores Cadastrados")
        print("5. Consulta SQL Customizada")
        print("0. Sair")
        print("=" * 90)
        
        opcao = input("\nEscolha uma opção: ").strip()
        
        if opcao == "1":
            consultar_metas_semanais()
        elif opcao == "2":
            data = input("Digite a data (YYYY-MM-DD) ou Enter para ver últimas: ").strip()
            consultar_resultados_diarios(data if data else None)
        elif opcao == "3":
            consultar_trofeus()
        elif opcao == "4":
            consultar_vendedores()
        elif opcao == "5":
            print("\nExemplo: SELECT * FROM metas_semanais WHERE semana_uuid = '2024_W53'")
            query = input("\nDigite sua consulta SQL: ").strip()
            if query:
                consulta_customizada(query)
        elif opcao == "0":
            print("\nAte logo!")
            break
        else:
            print("Opcao invalida!")

if __name__ == "__main__":
    main()

