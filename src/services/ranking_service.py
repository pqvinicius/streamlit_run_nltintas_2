from __future__ import annotations

import logging
import os
import time
import json
import warnings
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import unicodedata

from src.config import (
    get_base_dir,
    get_horario_comercial_config,
    get_ranking_config,
    get_gamificacao_config,
    get_mes_comercial_config,
    get_whatsapp_config,
    get_execution_mode,
)
from src.html_renderer import TemplateRenderer, html_to_png, image_to_data_uri
from src.logger import get_logger
from src.gamificacao_vendedores import get_engine
from src.services.message_service import get_message_service
from src.services.whatsapp_service import WhatsAppService
from src.services.notification_policy import NotificationPolicy

# Dataclass Definition
BASE_DIR = get_base_dir()
DEFAULT_TEMPLATE_DIR = BASE_DIR / "templates"

@dataclass(frozen=True)
class SellerRankingConfig:
    """Configurações para geração do ranking diário de vendedores."""
    meta_col: tuple[str, ...] = ("meta diaria", "meta diária", "meta")
    fat_col: tuple[str, ...] = ("fat. hoje", "faturado hoje", "venda hoje", "fat hoje")
    alcance_col: tuple[str, ...] = ("% alcance", "alcance", "alcance %")
    nome_col: tuple[str, ...] = ("nome", "vendedor", "funcionario")
    image_name_key: str = "ranking_vendedor_nome"
    template_name: str = "ranking_diario.html"
    templates_dir: Path = field(default_factory=lambda: DEFAULT_TEMPLATE_DIR)
    logo_candidates: tuple[str, ...] = ("logo_empresa.png", "logo_empresa.jpg", "logo_empresa.jpeg")
    viewport: tuple[int, int] = (1080, 1080)
    producer_signature: str = "Produzido por Vinicius Xavier"

class RankingService:
    """
    Service responsible for the end-to-end Seller Ranking logic (Ingestion -> Processing -> Rendering -> Notification).
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.cfg = SellerRankingConfig()
        self.policy = NotificationPolicy()

    # --- Utils ---
    def _normalizar_nome(self, nome: str) -> str:
        return str(nome).strip().lower()

    def _format_currency(self, valor: float) -> str:
        return ("R$ {:,.0f}".format(valor)).replace(",", "X").replace(".", ",").replace("X", ".")

    def _format_percent(self, valor: float) -> str:
        return f"{valor:.1f}%"

    def _badge_config(self, alcance: float, faixa_esperada: float) -> tuple[str, str, str]:
        if alcance > 100: return "META BATIDA!", "#22c55e", "#052e16"
        if alcance >= faixa_esperada: return "DE ACORDO", "#0ea5e9", "#02182a"
        if alcance >= faixa_esperada * 0.8: return "ATENÇÃO", "#facc15", "#341b00"
        return "ABAIXO", "#f87171", "#2a0704"

    def _gradient_colors(self, valor: float) -> tuple[str, str]:
        if valor >= 120: return ("#5eead4", "#0ea5e9")
        if valor >= 100: return ("#4ade80", "#16a34a")
        if valor >= 80: return ("#facc15", "#f97316")
        return ("#f87171", "#ef4444")

    def _calcular_faixa_esperada(self) -> float:
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

    def _parse_ptbr_number(self, valor: object) -> Optional[float]:
        if pd.isna(valor): return None
        texto = str(valor).strip()
        if not texto or texto.lower() in {"none", "nan"}: return None
        texto = texto.replace("R$", "").replace("%", "").replace("\xa0", "").replace(".", "").replace(",", ".")
        try: return float(texto)
        except ValueError: return None

    def _norm_header(self, txt: Any) -> str:
        if not isinstance(txt, str): return ""
        txt = unicodedata.normalize("NFKD", txt)
        txt = "".join(c for c in txt if not unicodedata.combining(c))
        return txt.upper().strip()

    def _encontrar_coluna(self, df: pd.DataFrame, candidatos: tuple[str, ...]) -> Optional[str]:
        colunas_normalizadas = {self._normalizar_nome(c): c for c in df.columns}
        for candidato in candidatos:
            cand_norm = self._normalizar_nome(candidato)
            if cand_norm in colunas_normalizadas:
                return colunas_normalizadas[cand_norm]
        return None

    def _limpar_colunas_numericas(self, df: pd.DataFrame, colunas: tuple[str, ...]) -> pd.DataFrame:
        for coluna in colunas:
            if coluna in df.columns:
                df[coluna] = df[coluna].apply(self._parse_ptbr_number)
        return df

    def _validar_excel_meta_vendedor(self, df_raw: pd.DataFrame) -> bool:
        self.logger.info("INGESTAO | Validando integridade do Excel (pré-header)")
        linhas_avaliadas = min(6, len(df_raw))
        for idx in range(linhas_avaliadas):
            linha = df_raw.iloc[idx].astype(str).values.tolist()
            for cell in linha:
                if "ERRO AO RECUPERAR RESULTADOS" in cell.upper():
                    self.logger.error(f"INGESTAO | Excel inválido detectado (Linha {idx}): 'Erro ao recuperar resultados'")
                    return True
        self.logger.info("INGESTAO | Excel passou na validação de integridade")
        return False

    # --- Ingestion ---
    def carregar_excel_meta_vendedor_com_retry(self, path_excel: str | Path, tentativas_max: int = 3) -> pd.DataFrame:
        espera_segundos = 40
        for tentativa in range(1, tentativas_max + 1):
            self.logger.info(f"INGESTAO | Tentativa {tentativa}/{tentativas_max} de leitura do Meta Vendedor")
            if not os.path.exists(path_excel):
                self.logger.warning(f"INGESTAO | Arquivo não existe. Aguardando {espera_segundos}s...")
                time.sleep(espera_segundos)
                continue
            try:
                df_raw = pd.read_excel(path_excel, header=None)
            except Exception as e:
                self.logger.warning(f"INGESTAO | Erro de leitura: {e}. Retry...")
                time.sleep(espera_segundos)
                continue

            if self._validar_excel_meta_vendedor(df_raw):
                self.logger.info("INGESTAO | Arquivo inválido removido.")
                try: os.remove(path_excel)
                except Exception as e: self.logger.error(f"Falha ao remover arquivo: {e}")
                time.sleep(espera_segundos)
                continue
            
            self.logger.info("INGESTAO | Arquivo válido detectado.")
            return df_raw
        
        raise RuntimeError("INGESTAO | Falha crítica: Não foi possível obter Excel válido.")

    def _carregar_planilha(self, path: Path) -> pd.DataFrame:
        path_str = str(path)
        df_raw = self.carregar_excel_meta_vendedor_com_retry(path_str)
        
        self.logger.info(f"INGESTAO | Iniciando analise de header: {path.name}")
        header_idx = None
        max_linhas = 50
        
        for idx in range(min(max_linhas, len(df_raw))):
            linha = df_raw.iloc[idx]
            valores = [self._norm_header(v) for v in linha.values]
            colunas_validas = sum(1 for v in valores if v)
            possui_nome = any(v in ("NOME", "VENDEDOR", "FUNCIONARIO") for v in valores)
            possui_meta = any("META DIARIA" in v for v in valores)
            possui_fat = any("FAT. HOJE" in v or "FAT HOJE" in v for v in valores)

            self.logger.info(f"INGESTAO | Header Linha {idx}: Valid={colunas_validas} Cols={valores}")

            if possui_nome and possui_meta and possui_fat and colunas_validas >= 5:
                header_idx = idx
                self.logger.info(f"INGESTAO | Cabeçalho detectado na linha {header_idx}")
                break
        
        if header_idx is None:
            raise ValueError("Cabecalho Meta Vendedor nao encontrado.")

        df = pd.read_excel(path, header=header_idx)
        df = df.loc[:, ~df.columns.duplicated()]
        return df

    def _preparar_dataframe(self, path: Path) -> pd.DataFrame:
        if not path.exists(): raise FileNotFoundError(f"Arquivo nao encontrado: {path}")
        df = self._carregar_planilha(path)
        
        cfg = self.cfg
        col_meta = self._encontrar_coluna(df, cfg.meta_col)
        col_fat = self._encontrar_coluna(df, cfg.fat_col)
        col_nome = self._encontrar_coluna(df, cfg.nome_col)
        col_alcance = self._encontrar_coluna(df, cfg.alcance_col)

        if not col_nome: raise ValueError("Coluna de Nome nao encontrada.")
        
        # Select and Rename
        cols_map = {col_nome: "Vendedor"}
        if col_meta: cols_map[col_meta] = "Meta"
        if col_fat: cols_map[col_fat] = "Venda"
        if col_alcance: cols_map[col_alcance] = "Alcance (%)"
        
        to_keep = [c for c in [col_nome, col_meta, col_fat, col_alcance] if c]
        df = df[to_keep].rename(columns=cols_map).copy()
        
        # Clean
        df = df.dropna(subset=["Vendedor"])
        df["Vendedor"] = df["Vendedor"].astype(str).str.strip().str.replace(r"(?i)^loja\s*[:.\-]?\s*", "", regex=True).str.title()
        df = df[~df["Vendedor"].str.lower().isin(["total", "total geral"])]
        
        # Clean Numbers
        df = self._limpar_colunas_numericas(df, ("Meta", "Venda"))
        df = df.dropna(subset=["Meta", "Venda"])
        df = df[df["Meta"] > 0]
        
        # Calc Alcance Diario
        df["Alcance (%)"] = (df["Venda"] / df["Meta"]).clip(lower=0) * 100
        
        return df.sort_values("Alcance (%)", ascending=False).fillna(0)

    # --- Rendering ---
    def _resolver_logo_path(self, data_dir: Path) -> Optional[Path]:
        for candidate in self.cfg.logo_candidates:
            for p in [data_dir / candidate, BASE_DIR / candidate]:
                if p.exists(): return p
        return None

    def _montar_contexto(self, df_pagina: pd.DataFrame, df_completo: pd.DataFrame, logo_path: Optional[Path], page_info: Dict) -> Dict:
        faixa_esperada = self._calcular_faixa_esperada()
        ranking = []
        
        for idx, linha in enumerate(df_pagina.to_dict(orient="records"), start=page_info['start_rank']):
            alcance = float(linha["Alcance (%)"])
            badge_lbl, badge_col, badge_txt = self._badge_config(alcance, faixa_esperada)
            grad_s, grad_e = self._gradient_colors(alcance)
            
            ranking.append({
                "rank": idx,
                "loja": linha["Vendedor"],
                "alcance": self._format_percent(alcance),
                "badge_label": badge_lbl,
                "badge_bg": badge_col,
                "badge_text": badge_txt,
                "meta_val": self._format_currency(linha["Meta"]),
                "fat_val": self._format_currency(linha["Venda"]),
                "bar_width": min(alcance, 100),
                "grad_start": grad_s, "grad_end": grad_e,
                "text_on_bar": "#03131f" if alcance >= 30 else "#0f172a"
            })

        total_fat = df_completo["Venda"].sum()
        total_meta = df_completo["Meta"].sum()
        alcance_med = (total_fat / total_meta * 100) if total_meta > 0 else 0
        
        hero_cards = [
            {"label": "Qtd. Vendedores", "value": str(len(df_completo))},
            {"label": "Venda Total", "value": self._format_currency(total_fat)},
            {"label": "Alcance Médio", "value": self._format_percent(alcance_med)},
        ]

        return {
            "title": "Ranking Vendedores • Diário",
            "subtitle": f"Performance Individual | {datetime.now():%d/%m/%Y} às {datetime.now():%H:%M}h",
            "hero_cards": hero_cards,
            "ranking": ranking,
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "company_name": get_gamificacao_config()["company_name"],
            "producer_signature": self.cfg.producer_signature,
            "logo_data_uri": image_to_data_uri(logo_path) if logo_path else None,
            "faixa_esperada": self._format_percent(faixa_esperada),
            "pagina_atual": page_info['current'],
            "total_paginas": page_info['total'],
            "mostrar_paginacao": page_info['total'] > 1
        }

    def _render_image(self, template: str, ctx: Dict, dest: Path) -> Path:
        renderer = TemplateRenderer(self.cfg.templates_dir)
        html = renderer.render(template, ctx)
        return html_to_png(html, dest, viewport=self.cfg.viewport)

    # --- Persistence & Gamification ---
    def _execute_gamification_pipeline(self, df_completo: pd.DataFrame, today: datetime.date) -> Any:
        try:
            engine = get_engine()
            # Enriquecer DF com Loja e Tipo
            mapa = self._carregar_contatos()
            if mapa:
                 def get_info(nome):
                     return mapa.get(self._normalizar_nome(nome), {})
                 
                 df_completo["Loja"] = df_completo["Vendedor"].apply(lambda x: get_info(x).get("loja", ""))
                 df_completo["Tipo"] = df_completo["Vendedor"].apply(lambda x: get_info(x).get("tipo", "VENDEDOR"))

            engine.processar_diario(df_completo, today)
            return engine
        except Exception as e:
            self.logger.error(f"GAMIFICACAO | Falha: {e}")
            return None

    def _carregar_contatos(self) -> Dict:
        csv_path = BASE_DIR / "vendedores_contato.csv"
        if not csv_path.exists(): return {}
        try:
            try:
                df = pd.read_csv(csv_path, sep=";", dtype=str, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(csv_path, sep=";", dtype=str, encoding="latin1")
            
            df.columns = [c.strip().lower() for c in df.columns]
            # Simple Logic
            mapa = {}
            col_nome = next((c for c in df.columns if "nome" in c or "vendedor" in c), None)
            col_tel = next((c for c in df.columns if "telefone" in c or "whatsapp" in c), None)
            col_loja = next((c for c in df.columns if "loja" in c), None)
            col_tipo = next((c for c in df.columns if "tipo" in c or "cargo" in c), None)
            
            if col_nome and col_tel:
                for _, row in df.iterrows():
                    nome = self._normalizar_nome(row[col_nome])
                    
                    def get_val(col, default=""):
                        val = str(row[col]).strip() if col in row and pd.notna(row[col]) else ""
                        return val if val.lower() != "nan" else default

                    tipo = get_val(col_tipo, "VENDEDOR").upper()
                    if not tipo: tipo = "VENDEDOR"
                    
                    mapa[nome] = {
                        "telefone": get_val(col_tel), 
                        "loja": get_val(col_loja),
                        "tipo": tipo
                    }
            return mapa
        except Exception as e:
            self.logger.error(f"CONTATOS | Erro: {e}")
            return {}

    # --- Execution ---
    def execute(self, meta_path: Path, destino_dir: Path, send_whatsapp: bool = True) -> Path:
        cfg = self.cfg
        ranking_cfg = get_ranking_config()
        image_name = ranking_cfg.get(cfg.image_name_key, "ranking_vendedor.png")
        
        # 1. Prepare Data
        df_completo = self._preparar_dataframe(meta_path)
        
        # 2. Filter Roles (Ignorar GERENTE)
        mapa = self._carregar_contatos()
        if mapa:
            vendedores_gerentes = [nome for nome, info in mapa.items() if info.get("tipo") == "GERENTE"]
            if vendedores_gerentes:
                total_antes = len(df_completo)
                df_completo = df_completo[~df_completo["Vendedor"].apply(self._normalizar_nome).isin(vendedores_gerentes)].copy()
                purgados = total_antes - len(df_completo)
                if purgados > 0:
                    self.logger.info(f"FILTER | {purgados} Gerentes removidos do ranking.")

        # 3. Pagination & Rendering
        page_size = ranking_cfg.get("lojas_por_pagina_diario", 14)
        total = len(df_completo)
        pages = (total + page_size - 1) // page_size
        
        self.logger.info(f"PROCESSAMENTO | Vendedores: {total}. Páginas: {pages}")
        
        # 3. Gamification & Points Generation (Priority Order)
        today = datetime.now().date()
        engine = self._execute_gamification_pipeline(df_completo, today)
        self.logger.info(f"🎮 GAMIFICACAO | Engine: {'OK' if engine else 'FALHA'}")
        
        paths_pontos = []
        paths_semanal = []
        paths_mensal = []
        paths_gerados = [] # Daily

        if engine:
             # 3.1. Points (First as requested)
             paths_pontos = self._gerar_ranking_pontos(engine, destino_dir, logo)
             
             # 3.2. Weekly/Monthly Preparation (Just prep, render later if strict order needed? 
             # User said: Points before Daily, Weekly, Monthly. 
             # So Points is done. Now Daily. Then Weekly/Monthly.)
             
             # But first let's generate Daily (paths_gerados) using the Excel data
             pass

        # 4. Daily Ranking Generation (Moved after Points)
        name_base = image_name.replace(".png", "")
        logo = self._resolver_logo_path(destino_dir)
        
        for p in range(pages):
            start = p * page_size
            end = min(start + page_size, total)
            df_page = df_completo.iloc[start:end].copy()
            
            fname = f"{name_base}_p{p+1}.png" if pages > 1 else image_name
            dest = destino_dir / fname
            
            ctx = self._montar_contexto(df_page, df_completo, logo, {'current': p+1, 'total': pages, 'start_rank': start+1})
            
            renderer = TemplateRenderer(self.cfg.templates_dir)
            html = renderer.render(self.cfg.template_name, ctx)
            paths_gerados.append(html_to_png(html, dest, viewport=(1080, 1080)))

        # 5. Periodic Rankings (Weekly/Monthly) - After Daily
        if engine:
             paths_semanal = self._gerar_ranking_periodico(engine, destino_dir, logo, "semanal")
             
             engine.processar_semanal(today)
             paths_mensal = self._gerar_ranking_periodico(engine, destino_dir, logo, "mensal")
             
             from src.config import get_mes_comercial_config
             mes_config = get_mes_comercial_config()
             dia_fim_comercial = mes_config["dia_fim"]
             
             # Processamento Semanal (Diário)
             engine.processar_semanal(today)
             
             # Processamento Mensal (Diário - Concessão Contínua)
             engine.processar_mensal(today)

        # 4. Notifications
        self._notify_all(paths_gerados, paths_pontos, paths_semanal, paths_mensal, engine, send_whatsapp=send_whatsapp)
        
        # 5. Snapshots
        if engine:
            self._export_snapshots(engine)
        
        return paths_gerados[0] if paths_gerados else None

    def _gerar_ranking_pontos(self, engine: Any, destino_dir: Path, logo: Path | None) -> list[Path]:
        try:
            today = date.today()
            ranking_data = engine.db.get_ranking_pontos(today)
            
            self.logger.info(f"PONTOS | Gerando imagens... Qtd Vendedores no Ranking: {len(ranking_data)}")
            
            if not ranking_data: 
                self.logger.warning("PONTOS | Ranking de pontos vazio! Gerando imagem de placeholder.")
                ranking_data = []

            page_size = 12
            total = len(ranking_data)
            # Se total for 0 (vazio), força 1 página para gerar o template vazio
            pages = (total + page_size - 1) // page_size
            if pages == 0: pages = 1
            paths = []

            for p in range(pages):
                chunk = ranking_data[p*page_size : (p+1)*page_size]
                ctx = {
                    "titulo": "🏆 QUADRO DE MEDALHAS",
                    "pagina": p + 1, "total_paginas": pages,
                    "ranking": chunk,
                    "logo": str(logo.absolute()) if logo else None,
                    "subtitle": f"Sincronizado em {datetime.now():%d/%m/%Y} às {datetime.now():%H:%Mh}"
                }
                renderer = TemplateRenderer(self.cfg.templates_dir)
                html = renderer.render("ranking_pontos.html", ctx)
                
                fname = f"ranking_pontos_p{p+1}.png" if pages > 1 else "ranking_pontos.png"
                dest = destino_dir / fname
                paths.append(html_to_png(html, dest, viewport=(1080, 1920)))
            return paths
        except Exception as e:
            self.logger.error(f"PONTOS | Erro: {e}")
            return []

    def _gerar_ranking_periodico(self, engine: Any, destino_dir: Path, logo: Path | None, tipo: str) -> list[Path]:
        try:
            today = date.today()
            if tipo == "semanal":
                ranking_data = engine.db.get_ranking_semanal(today)
                title, template, fname_base = "🏆 RANKING SEMANAL", "ranking_semanal.html", "ranking_semanal"
                ranking_data, dias_uteis_semana = self._enriquecer_status_semanal(ranking_data, engine, today)
            else:
                ranking_data = engine.db.get_ranking_mensal(today)
                title, template, fname_base = "📅 RANKING MENSAL", "ranking_mensal.html", "ranking_mensal"
                dias_uteis_semana = 5.0 # Fallback/Not used for monthly

            if not ranking_data: return []

            page_size = 12
            total = len(ranking_data)
            pages = (total + page_size - 1) // page_size
            paths = []

            for p in range(pages):
                start_rank = p * page_size + 1
                chunk = ranking_data[p*page_size : (p+1)*page_size]
                chunk_com_rank = [{**item, 'rank': start_rank + i} for i, item in enumerate(chunk)]
                
                ctx = {
                    "titulo": title, "pagina": p + 1, "total_paginas": pages,
                    "ranking": chunk_com_rank,
                    "logo": str(logo.absolute()) if logo else None,
                    "subtitle": f"Sincronizado em {datetime.now():%d/%m/%Y} às {datetime.now():%H:%Mh}",
                    "dias_uteis_semana": dias_uteis_semana if tipo == "semanal" else None
                }
                renderer = TemplateRenderer(self.cfg.templates_dir)
                html = renderer.render(template, ctx)
                dest = destino_dir / f"{fname_base}_p{p+1}.png"
                viewport = (1080, 1080) if tipo == "semanal" else (1080, 1920)
                paths.append(html_to_png(html, dest, viewport=viewport))
            return paths
        except Exception as e:
            self.logger.error(f"PERIODICO | Erro '{tipo}': {e}")
            return []

    def _enriquecer_status_semanal(self, ranking_data: list[dict], engine: Any, today: date) -> tuple[list[dict], float]:
        dt_segunda = today - timedelta(days=today.weekday())
        # Agora range(6) para pegar de Segunda(0) a Sábado(5)
        dias_semana = [dt_segunda + timedelta(days=i) for i in range(6)]
        
        from src.feriados import FeriadosManager
        feriados_mgr = FeriadosManager()
        dt_sabado = dt_segunda + timedelta(days=5)
        
        # Calcula dias úteis da semana (Seg-Sab) para exibição correta (ex: 4.0 ou 5.5)
        dias_uteis_semana = feriados_mgr.calcular_dias_uteis_periodo(dt_segunda, dt_sabado, "TODAS")
        
        for item in ranking_data:
            nome = item['nome']
            status_list = []
            metas_batidas = 0.0
            for d in dias_semana:
                is_sabado_check = (d.weekday() == 5)
                
                if d > today: 
                    status_list.append(None)
                    continue
                
                res = engine.db.get_resultados_periodo(nome, d, d)
                if res:
                    bateu = res[0][3] >= 100
                    status_list.append(bateu)
                    
                    if bateu:
                        if is_sabado_check:
                            # Sábado vale 0.5 ponto na contagem
                            metas_batidas += 0.5
                        else:
                            # Dias normais valem o peso calculado (normalmente 1.0)
                            peso_dia = feriados_mgr.calcular_dias_uteis_periodo(d, d, "TODAS")
                            metas_batidas += peso_dia
                else: 
                    status_list.append(False)
            
            # (Removido verificação manual de Sábado pois agora está dentro do loop)
            
            item['status_semana'] = status_list
            item['metas_batidas'] = metas_batidas
            item['contador_metas'] = f"{metas_batidas:.1f}"
            
        # ORDENAÇÃO CORRETA: 1. Metas Batidas (DESC), 2. Alcance (DESC)
        ranking_data.sort(key=lambda x: (x.get('metas_batidas', 0), x.get('alcance', 0)), reverse=True)
        
        return ranking_data, dias_uteis_semana

    # --- Notifications ---
    def _notify_all(self, paths_diario, paths_pontos, paths_semanal, paths_mensal, engine, send_whatsapp: bool):
        if not send_whatsapp: return
        
        now = datetime.now()
        wa_cfg = get_whatsapp_config()
        if not wa_cfg.get("enviar_whatsapp", False): return

        msg_service = get_message_service(engine.db)
        msg_service.seed_initial_data()

        if get_execution_mode() == "BATCH":
            self.logger.info("🔕 MODO BATCH | Notificações desativadas (Horário Noturno).")
            return

        if msg_service.is_holiday(now.date()):
            self.logger.info(f"🚩 FERIADO | {now.date()} feriado. Suspenso.")
            return

        shift = self.policy.deve_enviar_ranking_diario(now)
        especial_key = self.policy.hoje_tem_ranking_especial(now)
        
        # 1. Diário & Individual
        self._notify(paths_diario, engine, send_whatsapp=True)

        # 2. Especial
        if shift == "T" and especial_key:
            paths, categoria = [], None
            if especial_key == "points" and paths_pontos and wa_cfg.get("enviar_ranking_vendedores", True):
                paths, categoria = paths_pontos, "PONTOS"
            elif especial_key == "monthly" and paths_mensal:
                paths, categoria = paths_mensal, "MENSAL"
            elif especial_key == "weekly" and paths_semanal:
                paths, categoria = paths_semanal, "SEMANAL"

            if paths and self.policy._check_weekly_idempotency(especial_key, now):
                caption = msg_service.get_randomized_message(categoria) if categoria else ""
                sender = WhatsAppService()
                self.logger.info(f"🔥 ESPECIAL | Enviando {especial_key.upper()}...")
                groups = wa_cfg.get("nome_grupos", [wa_cfg.get("nome_grupo", "Informações Comercial NL")])
                if sender.send_ranking(groups, [str(p) for p in paths], caption=caption):
                    self.policy.registrar_envio_semanal(especial_key, now)
                try: sender.driver.quit()
                except: pass

    def _notify(self, paths: list[Path], engine: Any, send_whatsapp: bool = True):
        wa_cfg = get_whatsapp_config()
        if not wa_cfg.get("enviar_whatsapp", False) or not send_whatsapp: return

        now = datetime.now()
        sender = WhatsAppService()
        
        # Grupo
        if wa_cfg.get("enviar_ranking_diario", True) and paths:
            shift = self.policy.deve_enviar_ranking_diario(now)
            especial_key = self.policy.hoje_tem_ranking_especial(now)
            
            if shift == "T" and especial_key:
                self.logger.info("⏳ DIÁRIO | Pulando (Tarde Especial).")
            elif shift:
                msg_service = get_message_service(engine.db)
                categoria = "DIARIO_MANHA" if now.hour < 13 else "DIARIO_TARDE"
                caption = msg_service.get_randomized_message(categoria)
                groups = wa_cfg.get("nome_grupos", [wa_cfg.get("nome_grupo", "Informações Comercial NL")])
                if sender.send_ranking(groups, [str(p) for p in paths], caption=caption):
                    self.policy.registrar_envio_diario(now, shift)
            else:
                self.logger.info("⏳ DIÁRIO | Fora da janela ou já enviado.")
        
        # Individual
        if wa_cfg.get("enviar_individual", False) and engine:
            resumo = engine.db.get_resumo_dia(now.date())
            contatos = self._carregar_contatos()
            if resumo and contatos:
                for info in resumo:
                    vendedor = info['nome']
                    conquistas = info.get('trofeus', [])
                    if conquistas and self.policy.deve_enviar_mensagem_individual(vendedor, now, conquistas):
                        nome_norm = self._normalizar_nome(vendedor)
                        fone_data = contatos.get(nome_norm)
                        if fone_data:
                            msg = self.policy.gerar_mensagem_conquista(vendedor, conquistas, info.get('pontos_mes', 0))
                            if sender.send_individual_message(fone_data['telefone'], msg):
                                self.policy.registrar_envio_individual(vendedor, now, conquistas)
                                time.sleep(1)

        try: sender.driver.quit() 
        except: pass

    # --- Snapshots ---
    def _export_snapshots(self, engine: Any):
        try:
            from src.config import get_paths
            data_dir = Path(get_paths()["data_dir"])
            tables = ["vendedores", "resultado_meta", "trofeus", "resultado_semanal", "metas_semanais"]
            import sqlite3
            with sqlite3.connect(engine.db.db_path) as conn:
                for table in tables:
                    try:
                        df = pd.read_sql(f"SELECT * FROM {table}", conn)
                        df.to_csv(data_dir / f"{table}.csv", index=False, encoding="utf-8")
                    except: continue
        except Exception as e:
            self.logger.error(f"SNAPSHOT | Erro: {e}")

def get_ranking_service():
    return RankingService()
