"""
Script simples para consultar o banco de dados.
Uso: python ver_db.py [opcao]
  Opcoes: metas, resultados, trofeus, vendedores
  Ou sem opcao para ver todas as metas semanais
"""
import sqlite3
from pathlib import Path
import sys

DB_PATH = Path(__file__).parent / "data" / "gamificacao_vendedores.db"

if not DB_PATH.exists():
    print(f"ERRO: Banco nao encontrado em {DB_PATH}")
    sys.exit(1)

def consultar_metas_semanais():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT vendedor_nome, semana_uuid, data_inicio, data_fim, meta_valor
        FROM metas_semanais
        ORDER BY semana_uuid DESC, vendedor_nome
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Nenhuma meta semanal encontrada.")
        return
    
    print(f"\nMETAS SEMANAIS ({len(rows)} registros):\n")
    print(f"{'Vendedor':<30} {'Semana':<12} {'Inicio':<12} {'Fim':<12} {'Meta':>12}")
    print("-" * 90)
    
    for row in rows:
        print(f"{row['vendedor_nome']:<30} {row['semana_uuid']:<12} {row['data_inicio']:<12} {row['data_fim']:<12} {row['meta_valor']:>12,.2f}")

def consultar_resultados():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT vendedor_nome, data, meta, venda, alcance
        FROM resultado_meta
        ORDER BY data DESC, alcance DESC
        LIMIT 30
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Nenhum resultado encontrado.")
        return
    
    print(f"\nRESULTADOS DIARIOS (ultimos 30):\n")
    print(f"{'Vendedor':<30} {'Data':<12} {'Meta':>12} {'Venda':>12} {'Alcance':>10}")
    print("-" * 90)
    
    for row in rows:
        print(f"{row['vendedor_nome']:<30} {row['data']:<12} {row['meta']:>12,.2f} {row['venda']:>12,.2f} {row['alcance']:>10.1f}%")

def consultar_trofeus():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT vendedor_nome, data_conquista, tipo_trofeu, pontos, motivo
        FROM trofeus
        ORDER BY data_conquista DESC, pontos DESC
        LIMIT 30
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Nenhum trofeu encontrado.")
        return
    
    print(f"\nTROFEUS (ultimos 30):\n")
    print(f"{'Vendedor':<30} {'Data':<12} {'Tipo':<10} {'Pontos':>8} {'Motivo':<30}")
    print("-" * 100)
    
    for row in rows:
        print(f"{row['vendedor_nome']:<30} {row['data_conquista']:<12} {row['tipo_trofeu']:<10} {row['pontos']:>8} {row['motivo']:<30}")

def consultar_vendedores():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT nome, loja, tipo, ativo FROM vendedores ORDER BY nome")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Nenhum vendedor encontrado.")
        return
    
    print(f"\nVENDEDORES ({len(rows)} registros):\n")
    print(f"{'Nome':<40} {'Loja':<10} {'Tipo':<15} {'Ativo':<8}")
    print("-" * 80)
    
    for row in rows:
        ativo = "Sim" if row['ativo'] else "Nao"
        print(f"{row['nome']:<40} {str(row['loja']):<10} {row['tipo']:<15} {ativo:<8}")

if __name__ == "__main__":
    opcao = sys.argv[1] if len(sys.argv) > 1 else "metas"
    
    if opcao == "metas":
        consultar_metas_semanais()
    elif opcao == "resultados":
        consultar_resultados()
    elif opcao == "trofeus":
        consultar_trofeus()
    elif opcao == "vendedores":
        consultar_vendedores()
    else:
        print("Opcoes: metas, resultados, trofeus, vendedores")
        print("Exemplo: python ver_db.py metas")

