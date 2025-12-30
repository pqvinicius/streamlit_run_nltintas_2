import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from src.config import get_paths, get_mes_comercial_config, get_horario_comercial_config

logger = logging.getLogger(__name__)


# ============================================================================
# FUNÇÕES CENTRALIZADAS DE PERÍODO E META PROPORCIONAL
# ============================================================================

def get_periodo_semana(data_atual: date) -> tuple[date, date]:
    """
    Retorna o período semanal: segunda-feira até a data atual.
    
    Args:
        data_atual: Data de referência
        
    Returns:
        Tupla (inicio_semana, fim_semana) onde:
        - inicio_semana: Segunda-feira da semana
        - fim_semana: data_atual (não sábado!)
    """
    dt_segunda = data_atual - timedelta(days=data_atual.weekday())
    return (dt_segunda, data_atual)


def get_periodo_mes_comercial(data_atual: date, mes_config: Dict[str, int]) -> tuple[date, date]:
    """
    Retorna o período do mês comercial: dia_inicio até a data atual.
    Usa cálculo dinâmico baseado em configuração (elimina hardcoded).
    
    Args:
        data_atual: Data de referência
        mes_config: Dict com "dia_inicio" e "dia_fim" (ex: {"dia_inicio": 26, "dia_fim": 25})
        
    Returns:
        Tupla (inicio_ciclo, fim_ciclo) onde:
        - inicio_ciclo: Dia 26 do mês anterior (ou mês atual se já passou do dia 26)
        - fim_ciclo: data_atual (não dia 25!)
    """
    dia_inicio = mes_config["dia_inicio"]
    dia_fim = mes_config["dia_fim"]
    
    if data_atual.day <= dia_fim:
        # Estamos no final do ciclo (ex: dia 25/Jan). Início foi 26/Dez.
        mes_anterior = (data_atual.replace(day=1) - timedelta(days=1))
        inicio_ciclo = mes_anterior.replace(day=dia_inicio)
    else:
        # Estamos após o dia 25, então o ciclo começou no dia 26 do mês atual
        if data_atual.day >= dia_inicio:
            inicio_ciclo = data_atual.replace(day=dia_inicio)
        else:
            # Entre dia 1 e dia 25, ciclo começou no dia 26 do mês anterior
            mes_anterior = (data_atual.replace(day=1) - timedelta(days=1))
            inicio_ciclo = mes_anterior.replace(day=dia_inicio)
    
    fim_ciclo = data_atual
    return (inicio_ciclo, fim_ciclo)


def calcular_meta_proporcional(
    meta_total: float,
    data_inicio: date,
    data_atual: date,
    data_fim_periodo: date,
    feriados_mgr: Any,
    loja: str = ""
) -> float:
    """
    Calcula meta proporcional ao período decorrido.
    
    Fórmula: meta_proporcional = meta_total × (dias_decorridos / dias_totais)
    
    Args:
        meta_total: Meta total do período completo
        data_inicio: Início do período completo
        data_atual: Data atual (fim do período decorrido)
        data_fim_periodo: Fim do período completo (ex: sábado para semana, dia 25 para mês)
        feriados_mgr: Instância de FeriadosManager
        loja: Código da loja (para cálculo de feriados municipais)
        
    Returns:
        Meta proporcional ao período decorrido
    """
    # Calcula dias úteis do período completo
    du_total = feriados_mgr.calcular_dias_uteis_periodo(data_inicio, data_fim_periodo, loja)
    
    # Calcula dias úteis decorridos (até hoje)
    du_decorridos = feriados_mgr.calcular_dias_uteis_periodo(data_inicio, data_atual, loja)
    
    if du_total <= 0:
        return meta_total  # Fallback: retorna meta total se cálculo inválido
    
    # Meta proporcional
    meta_proporcional = meta_total * (du_decorridos / du_total)
    
    return meta_proporcional

class GamificacaoDB:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            paths = get_paths()
            data_dir = Path(paths["data_dir"])
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "gamificacao_vendedores.db"
        else:
            self.db_path = db_path
        
        # Detecta se DB foi excluído e recria (sem backup na recriação)
        db_existia = self.db_path.exists()
        if not db_existia:
            logger.warning(f"DB não encontrado em {self.db_path}. Recriando schema...")
        
        self._init_db()
        
        # Se foi recriado, loga mas não faz backup (conforme solicitado)
        if not db_existia and self.db_path.exists():
            logger.info(f"DB recriado com sucesso em {self.db_path}")

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Inicializa o schema do banco de dados se não existir."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Tabela Vendedores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                codigo TEXT,
                loja TEXT,
                tipo TEXT DEFAULT 'VENDEDOR',
                ativo BOOLEAN DEFAULT 1
            )
        """)
        
        # Migração: Adiciona coluna tipo se não existir
        try:
            cursor.execute("ALTER TABLE vendedores ADD COLUMN tipo TEXT DEFAULT 'VENDEDOR'")
        except sqlite3.OperationalError:
            pass # Coluna já existe
        
        # Migração: Adiciona coluna codigo se não existir
        try:
            cursor.execute("ALTER TABLE vendedores ADD COLUMN codigo TEXT")
        except sqlite3.OperationalError:
            pass # Coluna já existe
        
        # Tabela Resultados Diários (Meta vs Realizado)
        # Unique constraint garante idempotência por Vendedor + Data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resultado_meta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendedor_nome TEXT NOT NULL,
                data DATE NOT NULL,
                meta REAL,
                venda REAL,
                alcance REAL,
                UNIQUE(vendedor_nome, data)
            )
        """)
        
        # Tabela Troféus (Registro de conquistas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trofeus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendedor_nome TEXT NOT NULL,
                data_conquista DATE NOT NULL,
                tipo_trofeu TEXT NOT NULL, -- BRONZE, PRATA, OURO, BONUS_1, BONUS_2
                pontos INTEGER NOT NULL,
                motivo TEXT,
                UNIQUE(vendedor_nome, data_conquista, tipo_trofeu)
            )
        """)

        # Tabela Metas Semanais (Persistência para cálculo de alcance consolidado)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metas_semanais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendedor_nome TEXT NOT NULL,
                semana_uuid TEXT NOT NULL, -- Ex: "2024_W53"
                data_inicio DATE NOT NULL,
                data_fim DATE NOT NULL,
                meta_valor REAL NOT NULL,
                UNIQUE(vendedor_nome, semana_uuid)
            )
        """)
        # Tabela Resultado Semanal (Persistência do resultado final da semana - apenas no sábado)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resultado_semanal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendedor_nome TEXT NOT NULL,
                semana_uuid TEXT NOT NULL, -- Ex: "2024_W53"
                venda_total_semana REAL NOT NULL,
                meta_total_semana REAL NOT NULL,
                alcance_final REAL NOT NULL,
                data_fechamento DATE NOT NULL, -- Data do sábado
                UNIQUE(vendedor_nome, semana_uuid)
            )
        """)
        
        # Tabela Notificações Enviadas (Idempotência WhatsApp)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notificacoes_enviadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendedor_nome TEXT NOT NULL,
                tipo TEXT NOT NULL,          -- 'RANKING_DIARIO', 'RANKING_SEMANAL', 'CONQUISTA_INDIVIDUAL', etc.
                referencia TEXT NOT NULL,    -- '2025-01-29_M', '2025-W05', 'BRONZE+PRATA'
                data_envio DATE NOT NULL,
                hora_envio TEXT NOT NULL,
                UNIQUE(vendedor_nome, tipo, referencia, data_envio)
            )
        """)
        
        # --- TABELAS DE MENSAGENS ESTRATÉGICAS ---
        # 1. Repertório de Frases (Templates)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mensagens_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT NOT NULL, -- DIARIO_MANHA, DIARIO_TARDE, SEMANAL, MENSAL, PONTOS
                texto TEXT NOT NULL,
                ativo INTEGER DEFAULT 1
            )
        """)
        
        # 2. Histórico de Envios (Log de Uso)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mensagens_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT NOT NULL,
                template_id INTEGER NOT NULL,
                data_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (template_id) REFERENCES mensagens_templates(id)
            )
        """)
        
        # 3. Tabela de Feriados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feriados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data DATE NOT NULL UNIQUE,
                descricao TEXT,
                abrangencia TEXT NOT NULL, -- NACIONAL, ESTADUAL, MUNICIPAL
                uf TEXT,
                cidade TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def upsert_vendedor(self, nome: str, loja: str = "", tipo: str = "VENDEDOR"):
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO vendedores (nome, loja, tipo) VALUES (?, ?, ?)
                ON CONFLICT(nome) DO UPDATE SET loja=excluded.loja, tipo=excluded.tipo, ativo=1
            """, (nome, loja, tipo))
            conn.commit()
        finally:
            conn.close()

    def registrar_resultado_diario(self, nome: str, data_ref: date, meta: float, venda: float, alcance: float):
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO resultado_meta (vendedor_nome, data, meta, venda, alcance)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(vendedor_nome, data) DO UPDATE SET
                    meta=excluded.meta,
                    venda=excluded.venda,
                    alcance=excluded.alcance
            """, (nome, data_ref, meta, venda, alcance))
            conn.commit()
        except Exception as e:
            logger.error(f"Erro ao registrar resultado diário para {nome}: {e}")
            raise
        finally:
            conn.close()

    def registrar_trofeu(self, nome: str, data_ref: date, tipo: str, pontos: int, motivo: str):
        """
        Registra ou atualiza troféu. A última execução do dia sobrescreve a anterior.
        Idempotência: UNIQUE(vendedor_nome, data_conquista, tipo_trofeu) garante que não duplica,
        mas ON CONFLICT DO UPDATE garante que a última execução do dia salva os valores corretos.
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO trofeus (vendedor_nome, data_conquista, tipo_trofeu, pontos, motivo)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(vendedor_nome, data_conquista, tipo_trofeu) DO UPDATE SET
                    pontos=excluded.pontos,
                    motivo=excluded.motivo
            """, (nome, data_ref, tipo, pontos, motivo))
            # ON CONFLICT DO UPDATE garante que a última execução do dia sobrescreve a anterior
            conn.commit()
            if conn.total_changes > 0:
                logger.info(f"🏆 Troféu {tipo} concedido a {nome} ({pontos} pts)")
        finally:
            conn.close()

    def registrar_meta_semanal(self, nome: str, semana_uuid: str, data_inicio: date, data_fim: date, valor: float):
        """
        Registra meta semanal TOTAL (Seg-Sab) calculada na primeira execução da semana.
        INSERT OR IGNORE garante que a meta fique FIXA durante toda a semana, nunca sendo atualizada.
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO metas_semanais (vendedor_nome, semana_uuid, data_inicio, data_fim, meta_valor)
                VALUES (?, ?, ?, ?, ?)
            """, (nome, semana_uuid, data_inicio, data_fim, valor))
            conn.commit()
        finally:
            conn.close()

    def get_meta_semanal(self, nome: str, semana_uuid: str) -> Optional[float]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT meta_valor FROM metas_semanais WHERE vendedor_nome = ? AND semana_uuid = ?", (nome, semana_uuid))
            res = cursor.fetchone()
            return res[0] if res else None
        finally:
            conn.close()

    def registrar_resultado_semanal(self, nome: str, semana_uuid: str, venda_total: float, meta_total: float, alcance_final: float, data_fechamento: date):
        """
        Registra/atualiza resultado acumulado da semana (atualizado diariamente).
        ON CONFLICT DO UPDATE garante que seja atualizado todo dia com o acumulado.
        
        A lógica acumulativa funciona assim:
        - Segunda: venda_total = fat_segunda
        - Terça: venda_total = fat_segunda + fat_terca (soma automática via SQL SUM)
        - Quarta: venda_total = fat_segunda + fat_terca + fat_quarta
        - E assim por diante até sábado
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO resultado_semanal 
                (vendedor_nome, semana_uuid, venda_total_semana, meta_total_semana, alcance_final, data_fechamento)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(vendedor_nome, semana_uuid) DO UPDATE SET
                    venda_total_semana = excluded.venda_total_semana,
                    meta_total_semana = excluded.meta_total_semana,
                    alcance_final = excluded.alcance_final,
                    data_fechamento = excluded.data_fechamento
            """, (nome, semana_uuid, venda_total, meta_total, alcance_final, data_fechamento))
            conn.commit()
        finally:
            conn.close()
    
    def get_resultado_semanal(self, nome: str, semana_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Busca resultado final da semana para um vendedor.
        
        Returns:
            Dict com 'venda_total_semana', 'meta_total_semana', 'alcance_final' ou None se não existir.
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT venda_total_semana, meta_total_semana, alcance_final
                FROM resultado_semanal
                WHERE vendedor_nome = ? AND semana_uuid = ?
            """, (nome, semana_uuid))
            row = cursor.fetchone()
            if row:
                return {
                    'venda_total_semana': row['venda_total_semana'],
                    'meta_total_semana': row['meta_total_semana'],
                    'alcance_final': row['alcance_final']
                }
            return None
        finally:
            conn.close()
    
    # ============================================================================
    # MÓDULO DE MENSAGENS RANDÔMICAS (GRUPOS)
    # ============================================================================

    def get_random_template(self, categoria: str, limite_repeticao: int = 5) -> Optional[tuple[int, str]]:
        """
        Busca um template aleatório para a categoria, evitando os últimos X enviados.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Seleciona uma frase ativa da categoria que não esteja no log recente
            cursor.execute("""
                SELECT id, texto
                FROM mensagens_templates
                WHERE categoria = ?
                  AND ativo = 1
                  AND id NOT IN (
                      SELECT template_id
                      FROM mensagens_log
                      WHERE categoria = ?
                      ORDER BY data_envio DESC
                      LIMIT ?
                  )
                ORDER BY RANDOM()
                LIMIT 1
            """, (categoria, categoria, limite_repeticao))
            
            return cursor.fetchone()
        finally:
            conn.close()

    def registrar_envio_template(self, categoria: str, template_id: int):
        """Registra o uso de um template no log."""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO mensagens_log (categoria, template_id)
                VALUES (?, ?)
            """, (categoria, template_id))
            conn.commit()
        finally:
            conn.close()

    def is_feriado(self, data: date, uf: str = None, cidade: str = None) -> bool:
        """Verifica se uma data é feriado (Nacional, Estadual ou Municipal)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM feriados
                WHERE data = ?
                  AND (
                      abrangencia = 'NACIONAL'
                      OR (abrangencia = 'ESTADUAL' AND uf = ?)
                      OR (abrangencia = 'MUNICIPAL' AND cidade = ?)
                  )
                LIMIT 1
            """, (data.isoformat(), uf, cidade))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def seed_templates(self, templates: List[tuple[str, str]]):
        """Popula a tabela de templates (inicialização)."""
        conn = self._get_connection()
        try:
            # Verifica se já está populado para evitar duplicidade
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM mensagens_templates")
            if cursor.fetchone()[0] > 0:
                logger.info("MENSAGENS | Tabela de templates já populada.")
                return

            logger.info(f"MENSAGENS | Semeando {len(templates)} templates iniciais...")
            conn.executemany(
                "INSERT INTO mensagens_templates (categoria, texto) VALUES (?, ?)",
                templates
            )
            conn.commit()
        finally:
            conn.close()

    def seed_feriados(self, feriados_list: List[tuple[str, str, str]]):
        """Popula feriados nacionais (exemplo)."""
        conn = self._get_connection()
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO feriados (data, descricao, abrangencia) VALUES (?, ?, ?)",
                feriados_list
            )
            conn.commit()
        finally:
            conn.close()
            
    # ============================================================================
    # FUNÇÕES AUXILIARES PARA ESTILO DO RANKING
    # ============================================================================
    
    def _gradient_colors(self, valor: float) -> tuple[str, str]:
        """Retorna cores do gradiente baseadas no alcance."""
        if valor >= 120: return ("#5eead4", "#0ea5e9")
        if valor >= 100: return ("#4ade80", "#16a34a")
        if valor >= 80: return ("#facc15", "#f97316")
        return ("#f87171", "#ef4444")
    
    def _badge_config(self, alcance: float, faixa_esperada: float) -> tuple[str, str, str]:
        """Retorna configuração do badge (label, bg_color, text_color)."""
        if alcance > 100: return ("META BATIDA!", "#22c55e", "#052e16")
        if alcance >= faixa_esperada: return ("DE ACORDO", "#0ea5e9", "#02182a")
        if alcance >= faixa_esperada * 0.8: return ("ATENÇÃO", "#facc15", "#341b00")
        return ("ABAIXO", "#f87171", "#2a0704")
    
    def _format_percent(self, valor: float) -> str:
        """Formata valor como percentual."""
        return f"{valor:.1f}%"
    
    def _format_currency(self, valor: float) -> str:
        """Formata valor como moeda brasileira."""
        return ("R$ {:,.0f}".format(valor)).replace(",", "X").replace(".", ",").replace("X", ".")
    
    def _calcular_faixa_esperada(self) -> float:
        """Calcula faixa esperada baseada no horário comercial atual."""
        agora = datetime.now()
        hora_atual = agora.hour
        horario_cfg = get_horario_comercial_config()
        hora_inicio = horario_cfg["hora_inicio"]
        hora_fim = horario_cfg["hora_fim"]
        incremento = horario_cfg["incremento_por_hora"]
        
        if hora_atual < hora_inicio: return 0.0
        if hora_atual >= hora_fim: return 100.0
        
        horas_decorridas = hora_atual - hora_inicio
        faixa_esperada = (horas_decorridas + 1) * incremento
        return min(faixa_esperada, 100.0)
            
    def get_resultados_periodo(self, nome: str, data_inicio: date, data_fim: date) -> List[tuple]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data, meta, venda, alcance 
            FROM resultado_meta 
            WHERE vendedor_nome = ? AND data BETWEEN ? AND ?
            ORDER BY data
        """, (nome, data_inicio, data_fim))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_resumo_dia(self, data: date) -> List[Dict[str, Any]]:
        """
        Retorna um resumo de quem ganhou o que no dia, para notificações.
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Pega resultados do dia
        cursor.execute("""
            SELECT r.vendedor_nome, r.venda, r.alcance
            FROM resultado_meta r
            WHERE r.data = ?
        """, (data,))
        resultados = cursor.fetchall()
        
        resumo = []
        for row in resultados:
            nome = row['vendedor_nome']
            
            # Pega troféus do dia
            cursor.execute("""
                SELECT tipo_trofeu, pontos 
                FROM trofeus 
                WHERE vendedor_nome = ? AND data_conquista = ?
            """, (nome, data))
            trofeus_rows = cursor.fetchall()
            
            trofeus = [t['tipo_trofeu'] for t in trofeus_rows]
            pontos_dia = sum(t['pontos'] for t in trofeus_rows)
            
            # Se ganhou algo, adiciona ao resumo
            if trofeus:
                # Calcula total mensal
                mes_inicio = data.replace(day=1) # Simplificado, ideal usar regra comercial setada no motor
                cursor.execute("""
                    SELECT SUM(pontos) as total
                    FROM trofeus
                    WHERE vendedor_nome = ? AND data_conquista BETWEEN ? AND ?
                """, (nome, mes_inicio, data))
                pontos_mes = cursor.fetchone()['total'] or 0
                
                # Conta medalhas no mês
                cursor.execute("""
                    SELECT tipo_trofeu, COUNT(*) as qtd
                    FROM trofeus
                    WHERE vendedor_nome = ? AND data_conquista BETWEEN ? AND ?
                    GROUP BY tipo_trofeu
                """, (nome, mes_inicio, data))
                medalhas_mes = {r['tipo_trofeu']: r['qtd'] for r in cursor.fetchall()}
                
                resumo.append({
                    "nome": nome,
                    "venda_dia": row['venda'],
                    "alcance_dia": row['alcance'],
                    "trofeus": trofeus,
                    "pontos_ganhos": pontos_dia,
                    "pontos_mes": pontos_mes,
                    "medalhas": medalhas_mes
                })
        
        conn.close()
        return resumo

    def get_ranking_semanal(self, data_ref: date) -> List[Dict[str, Any]]:
        """
        Calcula o ranking da semana usando lógica unificada.
        
        Durante a semana (Seg-Sex): Vendas acumuladas até hoje / Meta Total da Semana
        No sábado: Usa resultado_semanal (resultado final fechado) quando disponível
        
        IMPORTANTE: Alcance sempre calculado sobre Meta Total da Semana (não proporcional).
        
        Retorna campos enriquecidos com estilo para reaproveitar visual do ranking diário.
        """
        from src.feriados import FeriadosManager
        
        # Usa função centralizada para período
        inicio_semana, fim_semana = get_periodo_semana(data_ref)
        dt_sabado = inicio_semana + timedelta(days=5)  # Para cálculo de meta total
        iso_year, iso_week, _ = inicio_semana.isocalendar()
        semana_uuid = f"{iso_year}_W{iso_week}"
        
        # Verifica se é sábado e se deve usar resultado final
        is_saturday = (data_ref.weekday() == 5)
        
        feriados_mgr = FeriadosManager()
        faixa_esperada = self._calcular_faixa_esperada()
        
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 1. Busca Vendas Acumuladas na Semana (segunda até hoje)
        c.execute("""
            SELECT 
                rm.vendedor_nome as nome, 
                SUM(rm.venda) as venda_total,
                v.loja as loja,
                v.tipo as tipo_vendedor,
                v.ativo as ativo
            FROM resultado_meta rm
            LEFT JOIN vendedores v ON rm.vendedor_nome = v.nome
            WHERE rm.data BETWEEN ? AND ?
              AND (v.ativo IS NULL OR v.ativo = 1) 
              AND (v.tipo IS NULL OR v.tipo != 'GERENTE')
            GROUP BY rm.vendedor_nome, v.loja, v.tipo, v.ativo
        """, (inicio_semana, fim_semana))
        rows = c.fetchall()
        conn.close()
        
        res = []
        for r in rows:
            nome = r['nome']
            venda_parcial = r['venda_total']
            loja = r['loja'] or ""
            
            # 2. Verifica se existe resultado final da semana (apenas no sábado)
            resultado_final = None
            if is_saturday:
                resultado_final = self.get_resultado_semanal(nome, semana_uuid)
            
            # 3. Define venda, meta e alcance
            if resultado_final:
                # Usa resultado final (sábado)
                venda = resultado_final['venda_total_semana']
                meta = resultado_final['meta_total_semana']
                alcance = resultado_final['alcance_final']
            else:
                # Usa dados parciais (durante a semana ou sábado sem resultado salvo)
                venda = venda_parcial
                
                # Busca Meta Semanal Total (Seg-Sab) gravada no banco
                meta_semanal_total = self.get_meta_semanal(nome, semana_uuid)
                
                if meta_semanal_total is None:
                    # Fallback: calcula on-the-fly se não existir
                    conn_temp = self._get_connection()
                    c_temp = conn_temp.cursor()
                    c_temp.execute("""
                        SELECT MAX(meta) as meta_diaria_ref
                        FROM resultado_meta
                        WHERE vendedor_nome = ? AND data BETWEEN ? AND ?
                    """, (nome, inicio_semana, fim_semana))
                    row_meta = c_temp.fetchone()
                    meta_diaria_ref = row_meta[0] if row_meta and row_meta[0] else 0
                    conn_temp.close()
                    
                    if meta_diaria_ref > 0:
                        du_semana_total = feriados_mgr.calcular_dias_uteis_periodo(inicio_semana, dt_sabado, loja)
                        meta_semanal_total = meta_diaria_ref * du_semana_total
                    else:
                        meta_semanal_total = 0
                
                # Usa Meta Total da Semana (não proporcional)
                # Alcance sempre calculado sobre meta total, mesmo durante a semana
                meta = meta_semanal_total
                alcance = (venda / meta * 100) if meta > 0 else 0
            
            # 4. Calcula campos de estilo (igual ao ranking diário)
            badge_label, badge_bg, badge_text = self._badge_config(alcance, faixa_esperada)
            grad_start, grad_end = self._gradient_colors(alcance)
            
            res.append({
                "nome": nome,
                "loja": loja,
                "venda": venda,
                "meta": meta,
                "alcance": alcance,
                # Campos de estilo para template
                "rank": 0,  # Será preenchido após ordenação
                "bar_width": min(alcance, 100),
                "grad_start": grad_start,
                "grad_end": grad_end,
                "text_on_bar": "#03131f" if alcance >= 30 else "#0f172a",
                "badge_label": badge_label,
                "badge_bg": badge_bg,
                "badge_text": badge_text,
                "alcance_label": self._format_percent(alcance),
                "meta_val": self._format_currency(meta),
                "fat_val": self._format_currency(venda)
            })
        
        # Ordena por alcance e atribui ranks
        res_sorted = sorted(res, key=lambda x: x['alcance'], reverse=True)
        for idx, item in enumerate(res_sorted, start=1):
            item['rank'] = idx
            
        return res_sorted

    def get_ranking_mensal(self, data_ref: date) -> List[Dict[str, Any]]:
        """
        Calcula o ranking mensal usando lógica unificada (dinâmica, sem hardcoded).
        Vendas: dia 26 até hoje
        Meta: TOTAL do período completo (não proporcional) - alcance calculado sobre meta total
        Filtra gerentes e vendedores inativos.
        """
        from src.feriados import FeriadosManager
        from src.config import get_mes_comercial_config
        
        mes_config = get_mes_comercial_config()
        
        # Usa função centralizada para período (elimina hardcoded)
        inicio_ciclo, fim_ciclo = get_periodo_mes_comercial(data_ref, mes_config)
        
        # Calcula fim do período completo (dia 25 do mês atual ou próximo)
        if data_ref.day <= mes_config["dia_fim"]:
            # Estamos antes do dia 25, então fim é dia 25 do mês atual
            fim_periodo_completo = data_ref.replace(day=mes_config["dia_fim"])
        else:
            # Estamos após dia 25, então fim é dia 25 do próximo mês
            if data_ref.month == 12:
                fim_periodo_completo = date(data_ref.year + 1, 1, mes_config["dia_fim"])
            else:
                fim_periodo_completo = date(data_ref.year, data_ref.month + 1, mes_config["dia_fim"])
        
        feriados_mgr = FeriadosManager()
        
        # 2. Ranking Acumulado no Período (com filtro de gerentes e inativos)
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT 
                rm.vendedor_nome as nome, 
                SUM(rm.venda) as venda_total,
                MAX(rm.meta) as meta_diaria_ref,
                v.loja as loja,
                v.tipo as tipo_vendedor,
                v.ativo as ativo
            FROM resultado_meta rm
            LEFT JOIN vendedores v ON rm.vendedor_nome = v.nome
            WHERE rm.data BETWEEN ? AND ?
              AND (v.ativo IS NULL OR v.ativo = 1) 
              AND (v.tipo IS NULL OR v.tipo != 'GERENTE')
            GROUP BY rm.vendedor_nome, v.loja, v.tipo, v.ativo
        """, (inicio_ciclo, fim_ciclo))
        rows = c.fetchall()
        conn.close()
        
        res = []
        for r in rows:
            nome = r['nome']
            loja = r['loja'] or ""
            meta_diaria = r['meta_diaria_ref'] or 0
            
            # Calcula meta total do período completo
            du_mensal_total = feriados_mgr.calcular_dias_uteis_periodo(inicio_ciclo, fim_periodo_completo, loja)
            meta_total = meta_diaria * du_mensal_total
            
            # Alcance calculado sobre meta TOTAL (não proporcional)
            alcance = (r['venda_total'] / meta_total * 100) if meta_total > 0 else 0
            
            res.append({
                "nome": nome, 
                "venda": r['venda_total'], 
                "meta": meta_total,  # Meta total do período completo
                "alcance": alcance,
                "loja": loja
            })
        return sorted(res, key=lambda x: x['alcance'], reverse=True)

    def get_ranking_pontos(self, data_ref: date) -> List[Dict[str, Any]]:
        """
        Ranking Geral de Pontos (Nível Olimpíadas).
        Acumulado desde o início da campanha (29/12/2024).
        Filtra gerentes e vendedores inativos (mesma lógica do ranking diário).
        """
        inicio = date(2024, 12, 29)
        fim = data_ref
        
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # JOIN com vendedores para filtrar inativos e gerentes
        c.execute("""
            SELECT 
                t.vendedor_nome as nome, 
                SUM(t.pontos) as pontos_total,
                SUM(CASE WHEN t.tipo_trofeu='BRONZE' THEN 1 ELSE 0 END) as qtd_bronze,
                SUM(CASE WHEN t.tipo_trofeu='PRATA' THEN 1 ELSE 0 END) as qtd_prata,
                SUM(CASE WHEN t.tipo_trofeu='OURO' THEN 1 ELSE 0 END) as qtd_ouro,
                SUM(CASE WHEN t.tipo_trofeu LIKE 'BONUS_%' THEN 1 ELSE 0 END) as qtd_bonus,
                v.tipo as tipo_vendedor,
                v.ativo as ativo
            FROM trofeus t
            LEFT JOIN vendedores v ON t.vendedor_nome = v.nome
            WHERE t.data_conquista BETWEEN ? AND ?
              AND (v.ativo IS NULL OR v.ativo = 1) 
              AND (v.tipo IS NULL OR v.tipo != 'GERENTE')
            GROUP BY t.vendedor_nome, v.tipo, v.ativo
            ORDER BY pontos_total DESC
        """, (inicio, fim))
        rows = c.fetchall()
        conn.close()
        
        res = []
        rank = 1
        for r in rows:
            res.append({
                "rank": rank,
                "nome": r['nome'],
                "pontos": r['pontos_total'] or 0,
                "medalhas": {
                    "BRONZE": r['qtd_bronze'] or 0,
                    "PRATA": r['qtd_prata'] or 0,
                    "OURO": r['qtd_ouro'] or 0,
                    "BONUS": r['qtd_bonus'] or 0
                }
            })
            rank += 1
        return res


class MotorPontuacao:
    SCORING_RULES = {
        "BRONZE": {"pontos": 1, "meta_pct": 100},  # Diário
        "PRATA": {"pontos": 3, "meta_pct": 100},   # Semanal (Acumulado)
        "OURO": {"pontos": 10, "meta_pct": 100},   # Mensal (Acumulado)
        "BONUS_1": {"pontos": 3, "meta_pct": 105}, # Mensal Extra
        "BONUS_2": {"pontos": 5, "meta_pct": 110}, # Mensal Extra
    }

    def __init__(self, db: Optional[GamificacaoDB] = None):
        self.db = db or GamificacaoDB()
        self.mes_config = get_mes_comercial_config()
        
    def processar_diario(self, df: pd.DataFrame, data_ref: date):
        """
        Processa o DataFrame diário (Vendedor, Meta, Venda, Alcance (%))
        """
        logger.info(f"🏆 Processando Gamificação Diária para {data_ref}")
        
        for _, row in df.iterrows():
            nome = str(row["Vendedor"]).strip().title()
            meta = float(row.get("Meta", 0))
            venda = float(row.get("Venda", 0))
            # Recalcula alcance para garantir precisão
            alcance = (venda / meta * 100) if meta > 0 else 0
            
            # 1. Atualiza Cadastros / Resultados
            loja = str(row.get("Loja", "")).strip()
            tipo = str(row.get("Tipo", "VENDEDOR")).strip().upper()
            self.db.upsert_vendedor(nome, loja=loja, tipo=tipo)
            self.db.registrar_resultado_diario(nome, data_ref, meta, venda, alcance)
            
            # 2. Persistência de Meta Semanal (Calculada no primeiro dia que aparece na semana)
            self._assegurar_meta_semanal(nome, data_ref, meta, loja)
            
            # 3. Avalia Bronze (Meta Diária Batida)
            if alcance >= self.SCORING_RULES["BRONZE"]["meta_pct"]:
                self.db.registrar_trofeu(
                    nome, 
                    data_ref, 
                    "BRONZE", 
                    self.SCORING_RULES["BRONZE"]["pontos"], 
                    f"Meta Diária Batida: {alcance:.1f}%"
                )

    def _assegurar_meta_semanal(self, nome: str, data_ref: date, meta_diaria_ref: float, loja: str):
        """
        Garante que a meta semanal TOTAL (Seg-Sab) está registrada no banco.
        Esta meta total será usada para calcular a proporcional depois.
        Se for o início da semana (ou primeira vez que vê o vendedor na semana), calcula e salva.
        """
        # Usa função centralizada para período
        dt_segunda, _ = get_periodo_semana(data_ref)
        dt_sabado = dt_segunda + timedelta(days=5)
        
        # Semana ISO (ano, semana, dia) - usamos (ano, semana) como ID
        iso_year, iso_week, _ = dt_segunda.isocalendar()
        semana_uuid = f"{iso_year}_W{iso_week}"
        
        # Verifica se já existe
        meta_existente = self.db.get_meta_semanal(nome, semana_uuid)
        if meta_existente is None:
            # Calcula Meta Semanal TOTAL (Seg-Sab) - será usada para proporcional depois
            from src.feriados import FeriadosManager
            feriados_mgr = FeriadosManager()
            
            # Dias Úteis da Semana TOTAL (Seg-Sab)
            du_semana_total = feriados_mgr.calcular_dias_uteis_periodo(dt_segunda, dt_sabado, loja)
            
            # Meta Semanal TOTAL = Meta Diária de Referência * Dias Úteis Total
            meta_semanal_total = meta_diaria_ref * du_semana_total
            
            self.db.registrar_meta_semanal(nome, semana_uuid, dt_segunda, dt_sabado, meta_semanal_total)
            logger.info(f"METAS | Registrada meta semanal TOTAL para {nome}: {meta_semanal_total:.2f} (DU: {du_semana_total})")

    def processar_semanal(self, data_ref: date):
        self._processar_semanal(data_ref)

    def processar_mensal(self, data_ref: date):
        self._processar_mensal(data_ref)

    def _processar_semanal(self, data_ref: date):
        """
        Processa medalha PRATA (semanal) e atualiza resultado acumulado da semana.
        
        - Todo dia: Atualiza resultado_semanal com vendas acumuladas até hoje (Seg até hoje)
        - Sexta-feira: Processa medalhas PRATA (vendas Seg-Sex vs meta TOTAL da semana)
        
        IMPORTANTE: 
        - resultado_semanal é atualizado DIARIAMENTE com o acumulado
        - Medalha PRATA só é concedida se bater a meta TOTAL da semana (não proporcional)
        """
        from src.feriados import FeriadosManager
        
        is_friday = (data_ref.weekday() == 4)
        
        feriados_mgr = FeriadosManager()
        
        # Usa função centralizada para período
        inicio_semana, fim_semana = get_periodo_semana(data_ref)
        dt_sabado = inicio_semana + timedelta(days=5)  # Fim do período completo
        
        # Busca meta semanal total do banco
        iso_year, iso_week, _ = inicio_semana.isocalendar()
        semana_uuid = f"{iso_year}_W{iso_week}"
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Pega lista de vendedores ativos com LOJA
        cursor.execute("SELECT nome, loja FROM vendedores WHERE ativo=1")
        vendedores_info = {r[0]: r[1] for r in cursor.fetchall()}
        
        for nome, loja in vendedores_info.items():
            loja = loja or ""
            
            # 1. Pega vendas acumuladas (segunda até hoje)
            cursor.execute("""
                SELECT SUM(venda) as venda_total
                FROM resultado_meta
                WHERE vendedor_nome = ? AND data BETWEEN ? AND ?
            """, (nome, inicio_semana, fim_semana))
            row = cursor.fetchone()
            
            if not row or row[0] is None:
                continue
                
            venda_acumulada = row[0]
            
            # 2. Busca meta semanal TOTAL (Seg-Sab) do banco
            meta_semanal_total = self.db.get_meta_semanal(nome, semana_uuid)
            
            if meta_semanal_total is None or meta_semanal_total <= 0:
                logger.warning(f"⚠️ Meta semanal não encontrada para {nome} na semana {semana_uuid}")
                continue
            
            # 3. Processa medalhas PRATA (apenas na sexta-feira)
            if is_friday:
                # IMPORTANTE: Alcance calculado sobre meta TOTAL da semana (não proporcional)
                # Medalha PRATA só é concedida se bater a meta total da semana inteira
                if meta_semanal_total > 0:
                    alcance_acumulado = (venda_acumulada / meta_semanal_total) * 100
                    
                    logger.info(f"PRATA | {nome}: Vendas={venda_acumulada:.2f}, Meta Total={meta_semanal_total:.2f}, Alcance={alcance_acumulado:.1f}%")
                    
                    if alcance_acumulado >= self.SCORING_RULES["PRATA"]["meta_pct"]:
                        self.db.registrar_trofeu(
                            nome, 
                            data_ref, 
                            "PRATA", 
                            self.SCORING_RULES["PRATA"]["pontos"], 
                            f"Meta Semanal Batida: {alcance_acumulado:.1f}%"
                        )
            
            # 4. Atualiza resultado acumulado da semana (TODO DIA)
            # Calcula alcance sobre meta TOTAL (não proporcional)
            alcance_atual = (venda_acumulada / meta_semanal_total * 100) if meta_semanal_total > 0 else 0
            
            # data_fechamento sempre será o sábado (fim da semana)
            self.db.registrar_resultado_semanal(
                nome,
                semana_uuid,
                venda_acumulada,      # Soma de todas as vendas até hoje (Seg até hoje)
                meta_semanal_total,   # Meta total da semana (Seg-Sab)
                alcance_atual,        # Alcance calculado sobre meta total
                dt_sabado             # data_fechamento = sábado (fim da semana)
            )
            
            logger.info(f"RESULTADO SEMANAL | {nome}: Vendas Acumuladas={venda_acumulada:.2f}, Meta Total={meta_semanal_total:.2f}, Alcance={alcance_atual:.1f}%")
        
        conn.close()

    def _processar_mensal(self, data_ref: date):
        """
        Processa medalhas OURO e BONUS (mensal) usando lógica unificada.
        Compara vendas até hoje com meta proporcional até hoje.
        
        IMPORTANTE: Esta função só deve ser chamada no FIM DO MÊS COMERCIAL (dia 25)
        ou no último dia do mês civil.
        """
        from src.feriados import FeriadosManager
        
        # VALIDAÇÃO: Só processa no fim do mês comercial (dia 25) ou último dia civil
        dia_fim_comercial = self.mes_config["dia_fim"]
        is_end_commercial = (data_ref.day == dia_fim_comercial)
        
        proximo_dia = data_ref + timedelta(days=1)
        is_end_civil = (proximo_dia.month != data_ref.month)
        
        if not (is_end_commercial or is_end_civil):
            logger.warning(f"⚠️ _processar_mensal() chamado em {data_ref.strftime('%d/%m/%Y')} (dia {data_ref.day}). Deveria ser apenas no dia {dia_fim_comercial} (fim comercial) ou último dia do mês. Ignorando...")
            return
        
        feriados_mgr = FeriadosManager()
        
        # Usa função centralizada para período (elimina duplicação)
        inicio_ciclo, fim_ciclo = get_periodo_mes_comercial(data_ref, self.mes_config)
        
        # Calcula fim do período completo (dia 25)
        if data_ref.day <= self.mes_config["dia_fim"]:
            fim_periodo_completo = data_ref.replace(day=self.mes_config["dia_fim"])
        else:
            if data_ref.month == 12:
                fim_periodo_completo = date(data_ref.year + 1, 1, self.mes_config["dia_fim"])
            else:
                fim_periodo_completo = date(data_ref.year, data_ref.month + 1, self.mes_config["dia_fim"])
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Pega lista de vendedores ativos com LOJA
        cursor.execute("SELECT nome, loja FROM vendedores WHERE ativo=1")
        vendedores_info = {r[0]: r[1] for r in cursor.fetchall()}
        
        for nome, loja in vendedores_info.items():
            loja = loja or ""
            
            # 1. Pega vendas acumuladas (dia 26 até hoje)
            cursor.execute("""
                SELECT SUM(venda) as venda_total, MAX(meta) as meta_diaria_ref
                FROM resultado_meta
                WHERE vendedor_nome = ? AND data BETWEEN ? AND ?
            """, (nome, inicio_ciclo, fim_ciclo))
            row = cursor.fetchone()
            
            if not row or row[0] is None:
                continue
            
            total_venda = row[0]
            meta_diaria_ref = row[1] or 0
            
            if meta_diaria_ref <= 0:
                continue
            
            # 2. Calcula meta total do período completo
            du_mensal_total = feriados_mgr.calcular_dias_uteis_periodo(inicio_ciclo, fim_periodo_completo, loja)
            meta_total = meta_diaria_ref * du_mensal_total
            
            # 3. Calcula meta proporcional (até hoje, não até dia 25)
            meta_proporcional = calcular_meta_proporcional(
                meta_total,
                inicio_ciclo,
                fim_ciclo,  # data_atual
                fim_periodo_completo,  # data_fim_periodo (dia 25)
                feriados_mgr,
                loja
            )
            
            if meta_proporcional > 0:
                alcance_acumulado = (total_venda / meta_proporcional) * 100
                
                # Ouro
                if alcance_acumulado >= self.SCORING_RULES["OURO"]["meta_pct"]:
                    self.db.registrar_trofeu(
                        nome, data_ref, "OURO", 
                        self.SCORING_RULES["OURO"]["pontos"], 
                        f"Meta Mensal Batida: {alcance_acumulado:.1f}%"
                    )
                
                # Bonus 1 (105%)
                if alcance_acumulado >= self.SCORING_RULES["BONUS_1"]["meta_pct"]:
                     self.db.registrar_trofeu(
                        nome, data_ref, "BONUS_1", 
                        self.SCORING_RULES["BONUS_1"]["pontos"], 
                        f"Superação Mensal 105%: {alcance_acumulado:.1f}%"
                    )

                # Bonus 2 (110%)
                if alcance_acumulado >= self.SCORING_RULES["BONUS_2"]["meta_pct"]:
                     self.db.registrar_trofeu(
                        nome, data_ref, "BONUS_2", 
                        self.SCORING_RULES["BONUS_2"]["pontos"], 
                        f"Superação Mensal 110%: {alcance_acumulado:.1f}%"
                    )
        conn.close()

def get_engine():
    return MotorPontuacao()
