"""
Script para cadastrar gerentes na tabela vendedores.
Executa: python cadastrar_gerentes.py
"""

import sqlite3
from pathlib import Path
from src.config import get_paths

# Lista de gerentes (Codigo, Nome, Loja)
GERENTES = [
    ("C01", "NATALIA FERNANDES SOARES", "1"),
    ("V51", "CLAUDIO JOSE DE RESENDE", "3"),
    ("C40", "JOYCE MOREIRA VAZ", "4"),
    ("VB0", "CLAUDINEI DE CASTRO MAGALHAES", "7"),
    ("VK0", "DEOCLECIANO ALVES DE ALMEIDA", "8"),
    ("G40", "MARCUS VINICIUS RAMALHO", "9"),
    ("V18", "ROSIMARA DAS MERCES SILVA", "10"),
    ("G23", "EDSON ALVES DE AZEVEDO", "11"),
    ("VN3", "HEBERT MOTA CEZARIO", "13"),
    ("V68", "AMANDA PINTO PEIXOTO", "14"),
    ("E01", "LEANDRO GONCALVES GOMES", "15"),
    ("VS6", "LUIS FERNANDO MARTINS OLIVEIRA", "16"),
    ("VC5", "DAYANE APARECIDA LUCINO SILVA", "17"),
    ("VF8", "FELIPE JOSE RODRIGUES", "25"),
    ("Z25", "FILIPE MACIEL GOMES OLIVEIRA", "26"),
    ("VL4", "KELI APARECIDA DA SILVA", "28"),
    ("VN9", "BIANCA ARAUJO DOS SANTOS", "30"),
    ("V52", "WENDEL DOS REIS RIBEIRO", "32"),
    ("G53", "LAUDICEIA ANDRADE DE SOUZA SANTOS", "33"),
    ("G54", "CRISTIANO OLIVEIRA DA SILVA", "34"),
    ("VF6", "LORRAYNE FERNANDA FERREIRA", "35"),
    ("G64", "JORGE MARCELINO FILHO", "36"),
    ("VV6", "ROBERTO MARCONI DA SILVA JUNIO", "31"),
]

def cadastrar_gerentes():
    """Cadastra todos os gerentes na tabela vendedores."""
    paths = get_paths()
    db_path = Path(paths.get("db_gamificacao", "data/gamificacao_vendedores.db"))
    
    if not db_path.exists():
        print(f"❌ Banco de dados não encontrado: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Garante que a coluna codigo existe (migração)
    try:
        cursor.execute("ALTER TABLE vendedores ADD COLUMN codigo TEXT")
        conn.commit()
        print("✅ Coluna 'codigo' adicionada à tabela vendedores\n")
    except sqlite3.OperationalError:
        pass  # Coluna já existe
    
    cadastrados = 0
    atualizados = 0
    erros = 0
    
    print(f"\n📋 Cadastrando {len(GERENTES)} gerentes...\n")
    
    for codigo, nome, loja in GERENTES:
        try:
            # Normaliza o nome (Title Case)
            nome_normalizado = nome.strip().title()
            codigo_limpo = codigo.strip()
            loja_limpa = loja.strip()
            
            # Verifica se já existe
            cursor.execute("SELECT nome, tipo, codigo, loja FROM vendedores WHERE nome = ?", (nome_normalizado,))
            existente = cursor.fetchone()
            
            if existente:
                # Atualiza para garantir que seja GERENTE com código e loja corretos
                cursor.execute("""
                    UPDATE vendedores 
                    SET tipo = 'GERENTE', codigo = ?, loja = ?, ativo = 1
                    WHERE nome = ?
                """, (codigo_limpo, loja_limpa, nome_normalizado))
                atualizados += 1
                print(f"  ✅ Atualizado: {nome_normalizado} (Código: {codigo_limpo}, Loja: {loja_limpa})")
            else:
                # Insere novo com código e loja
                cursor.execute("""
                    INSERT INTO vendedores (nome, codigo, loja, tipo, ativo)
                    VALUES (?, ?, ?, 'GERENTE', 1)
                """, (nome_normalizado, codigo_limpo, loja_limpa))
                cadastrados += 1
                print(f"  ➕ Cadastrado: {nome_normalizado} (Código: {codigo_limpo}, Loja: {loja_limpa})")
                
        except Exception as e:
            erros += 1
            print(f"  ❌ Erro ao processar {nome} ({codigo}): {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n📊 Resumo:")
    print(f"  ➕ Novos cadastros: {cadastrados}")
    print(f"  ✅ Atualizações: {atualizados}")
    print(f"  ❌ Erros: {erros}")
    print(f"  📝 Total processado: {len(GERENTES)}")
    print(f"\n✅ Concluído! Gerentes cadastrados com tipo='GERENTE'")
    print(f"   Eles serão automaticamente filtrados dos rankings.\n")

if __name__ == "__main__":
    cadastrar_gerentes()

