import sqlite3
from datetime import datetime
from pathlib import Path
import sys
import os

# Ajustar path para importar do src
sys.path.append(os.getcwd())

from src.services.notification_policy import NotificationPolicy
from src.config import get_paths
from src.gamificacao_vendedores import get_engine

def debug():
    print("=== DEBUG NOTIFICACOES (SQLite) ===")
    now = datetime.now()
    engine = get_engine() # Força criação das tabelas se não existirem
    policy = NotificationPolicy()
    
    # 1. Verificar Histórico no Banco
    print(f"\n1. Histórico em {policy.db_path}")
    if policy.db_path.exists():
        with sqlite3.connect(policy.db_path) as conn:
            cursor = conn.cursor()
            day_str = now.strftime("%Y-%m-%d")
            
            # Notificados hoje
            cursor.execute("""
                SELECT vendedor_nome, tipo, referencia, hora_envio 
                FROM notificacoes_enviadas 
                WHERE data_envio = ?
            """, (day_str,))
            rows = cursor.fetchall()
            
            print(f"Notificações registradas hoje ({day_str}): {len(rows)}")
            if not rows:
                print("  - Nenhuma")
            for r in rows:
                print(f"  - [{r[3]}] {r[0]} | {r[1]} | {r[2]}")
    else:
        print("Banco de dados não encontrado.")

    # 2. Verificar Conquistas no Banco (Motor)
    print(f"\n2. Banco de Dados (Troféus)")
    try:
        engine = get_engine()
        resumo = engine.db.get_resumo_dia(now.date())
        print(f"Vendedores com atividade hoje: {len(resumo) if resumo else 0}")
        if resumo:
            for r in resumo:
                if r.get('trofeus'):
                    print(f"  - {r['nome']}: {r['trofeus']} (Pontos: {r.get('pontos_mes')})")
        else:
            print("  - Nenhum resumo para hoje.")
    except Exception as e:
        print(f"Erro ao acessar banco de dados: {e}")

    # 3. Teste do deve_enviar
    print("\n3. Simulação de Decisão (Individual)")
    vendedor_teste = "FELIX AUGUSTO DE PAIVA" # Exemplo do banco
    conquistas_teste = ["BRONZE"]
    deve = policy.deve_enviar_mensagem_individual(vendedor_teste, now, conquistas_teste)
    print(f"Decisão para {vendedor_teste} com {conquistas_teste}: {'ENVIAR' if deve else 'PULAR'}")

if __name__ == "__main__":
    debug()
