import sqlite3
import uuid
import time
import traceback
from datetime import datetime
from pathlib import Path

class ExecutionLogger:
    def __init__(self, db_path: str | Path, environment="DEV", trigger_type="MANUAL"):
        self.db_path = str(db_path)
        self.environment = environment
        self.trigger_type = trigger_type
        self.execution_id = str(uuid.uuid4())
        self.start_time = time.time()

        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS execution_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        execution_id TEXT,
                        execution_date DATE,
                        execution_time DATETIME,
                        environment TEXT,
                        trigger_type TEXT,
                        step TEXT,
                        substep TEXT,
                        status TEXT,
                        message TEXT,
                        error_stack TEXT,
                        duration_ms INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Create indices if not exist
                conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_log_date ON execution_log (execution_date)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_log_execution_id ON execution_log (execution_id)")
        except Exception as e:
            print(f"CRITICAL: Failed to initialize execution log DB: {e}")

    def log(self, step, status, substep=None, message=None, error_stack=None):
        duration_ms = int((time.time() - self.start_time) * 1000)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO execution_log (
                        execution_id,
                        execution_date,
                        execution_time,
                        environment,
                        trigger_type,
                        step,
                        substep,
                        status,
                        message,
                        error_stack,
                        duration_ms
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.execution_id,
                    datetime.now().date(),
                    datetime.now(),
                    self.environment,
                    self.trigger_type,
                    step,
                    substep,
                    status,
                    message,
                    error_stack,
                    duration_ms
                ))
        except Exception as e:
            # Fallback to print if DB fails, don't crash the app for logging
            print(f"CRITICAL: Failed to write to execution log: {e}")
