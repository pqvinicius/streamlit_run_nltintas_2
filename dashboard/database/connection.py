"""
Gerenciador de conexão SQLite com context manager.
Garante fechamento correto e evita múltiplas conexões simultâneas.
"""
import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from dashboard.config.paths import get_db_path


class DatabaseConnection:
    """
    Gerenciador de conexão SQLite com suporte a context manager.
    
    Usa singleton pattern para evitar múltiplas conexões simultâneas.
    """
    
    _instance: Optional['DatabaseConnection'] = None
    _db_path: Optional[Path] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._db_path = get_db_path()
        return cls._instance
    
    @property
    def db_path(self) -> Optional[Path]:
        """Retorna o caminho do banco de dados."""
        return self._db_path
    
    @property
    def exists(self) -> bool:
        """Verifica se o banco de dados existe."""
        return self._db_path is not None and self._db_path.exists()
    
    @contextmanager
    def get_connection(self, read_only: bool = True):
        """
        Context manager para conexão SQLite.
        
        Args:
            read_only: Se True, abre em modo read-only (padrão).
        
        Yields:
            sqlite3.Connection: Conexão com o banco.
        
        Raises:
            FileNotFoundError: Se o banco não existir.
            sqlite3.Error: Em caso de erro de conexão.
        """
        conn = None
        try:
            if not self.exists or self._db_path.stat().st_size < 10240:
                # MODO HÍBRIDO (In-Memory Fallback)
                conn = sqlite3.connect(":memory:")
                self._load_csv_snapshots(conn)
            else:
                # MODO PADRÃO (Physical DB)
                if read_only:
                    uri = f"file:{self._db_path}?mode=ro"
                    conn = sqlite3.connect(uri, uri=True)
                else:
                    conn = sqlite3.connect(str(self._db_path))
            
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if not conn and not self.exists:
                 raise FileNotFoundError(f"Banco não encontrado e erro ao carregar snapshots: {e}")
            raise e
        finally:
            if conn:
                conn.close()

    def _load_csv_snapshots(self, conn: sqlite3.Connection):
        """Carrega arquivos CSV do diretório data/ para o banco em memória."""
        import pandas as pd
        from dashboard.config.paths import get_data_dir
        
        data_dir = get_data_dir()
        tables = ["vendedores", "resultado_meta", "trofeus", "resultado_semanal", "metas_semanais"]
        
        for table in tables:
            csv_path = data_dir / f"{table}.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                df.to_sql(table, conn, if_exists="replace", index=False)
    
    def test_connection(self) -> bool:
        """
        Testa a conexão com o banco de dados.
        
        Returns:
            True se a conexão foi bem-sucedida, False caso contrário.
        """
        if not self.exists:
            return False
        
        try:
            with self.get_connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

