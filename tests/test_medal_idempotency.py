import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from src.gamificacao_vendedores import GamificacaoDB, MotorPontuacao

# Configure logging to see output during test
logging.basicConfig(level=logging.DEBUG)

def test_medalha_prata_idempotencia(tmp_path):
    """
    Testa se a medalha de PRATA é concedida apenas uma vez na semana,
    mesmo que o script rode múltiplas vezes com a meta batida.
    """
    db_path = tmp_path / "test_gamificacao.db"
    
    # 1. Setup DB
    db = GamificacaoDB(db_path=db_path)
    engine = MotorPontuacao(db=db)
    
    # 2. Setup Data
    vendedor = "Test Vendedor"
    loja = "Loja Teste"
    today = date(2025, 1, 14) # Terça-feira (Exemplo)
    
    # Simula Meta Semanal (Segunda-Feira define a meta)
    # Suponha Meta Total da Semana = 10.000
    engine._assegurar_meta_semanal(vendedor, today, 2000.0, loja) 
    # (Internamente ele calcula dias uteis e salva, mas vamos forçar se precisar ou confiar no mock)
    
    # Vamos injetar manualmente uma meta semanal conhecida para facilitar
    conn = db._get_connection()
    conn.execute("INSERT INTO vendedores (nome, loja, ativo) VALUES (?, ?, 1)", (vendedor, loja))
    conn.execute("""
        INSERT INTO metas_semanais (vendedor_nome, semana_uuid, data_inicio, data_fim, meta_valor)
        VALUES (?, '2025_W03', '2025-01-13', '2025-01-18', 10000)
    """, (vendedor,))
    conn.commit()
    conn.close()
    
    # 3. Simulate Hitting Target (Venda = 12.000 -> 120%)
    # Inserimos venda acumulada no banco (que o script lê)
    conn = db._get_connection()
    conn.execute("""
        INSERT INTO resultado_meta (vendedor_nome, data, meta, venda, alcance)
        VALUES (?, ?, 2000, 12000, 600)
    """, (vendedor, today))
    conn.commit()
    conn.close()
    
    # 4. Run Process 5 Times
    print("\n--- INICIANDO RODADAS DE TEXTE ---")
    for i in range(1, 6):
        print(f"Rodada {i}...")
        engine.processar_semanal(today)
        
    # 5. Assertions
    conn = db._get_connection()
    rows = conn.execute("SELECT * FROM trofeus WHERE vendedor_nome = ? AND tipo_trofeu = 'PRATA'", (vendedor,)).fetchall()
    conn.close()
    
    print(f"\nTotal de Medalhas Prata encontradas: {len(rows)}")
    for r in rows:
        print(f"  > {r}")
        
    assert len(rows) == 1, f"Falha de Idempotência! Esperado 1 medalha, encontradas {len(rows)}"
    print("\n✅ SUCESSO! Idempotência confirmada.")

if __name__ == "__main__":
    # Manually run with a temp dir
    import tempfile
    import shutil
    
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        test_medalha_prata_idempotencia(tmp_dir)
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
