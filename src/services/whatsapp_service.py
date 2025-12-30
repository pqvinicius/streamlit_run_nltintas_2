from __future__ import annotations

import os
import time
import io
import random
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

# Dependencies
try:
    from selenium import webdriver
    # Edge Imports
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from PIL import Image
    import win32clipboard
    import pywhatkit
except ImportError:
    webdriver = None
    win32clipboard = None

from src.logger import get_logger
from src.config import get_whatsapp_config


class WhatsAppService:
    """
    Serviço centralizado para envio de mensagens via WhatsApp Web (Selenium).
    MIGRADO PARA MICROSOFT EDGE (Chromium) para maior estabilidade.
    """

    def __init__(self, session_dir: str = "edge_whatsapp_session", headless: bool = False):
        self.logger = get_logger(__name__)
        self.session_dir = session_dir
        self.headless = headless
        self.driver: Optional[webdriver.Edge] = None

    def _init_driver(self) -> bool:
        """Inicializa o driver do Microsoft Edge."""
        if webdriver is None:
            self.logger.error("❌ Selenium/Drivers não instalados.")
            return False

        if self.driver:
            return True

        wa_cfg = get_whatsapp_config()
        
        # --- Caminho do Perfil (Fixo para Estabilidade) ---
        # Usa diretório local "edge_whatsapp_session" para garantir persistência do login/QR
        base_dir = Path.cwd()
        profile_path = base_dir / self.session_dir
        profile_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"🌐 Inicializando WhatsApp EDGE (Perfil: {self.session_dir})...")

        def create_driver() -> Optional[webdriver.Edge]:
            # --- Forçar fechamento do Edge para liberar LOCK ---
            try:
                self.logger.info("🧹 Limpando instâncias residuais do Edge...")
                subprocess.call("taskkill /F /IM msedge.exe /T", shell=True)
                time.sleep(2)
            except: pass

            edge_options = EdgeOptions()
            
            # --- Perfil Persistente ---
            edge_options.add_argument(f"--user-data-dir={str(profile_path)}")
            edge_options.add_argument("--profile-directory=Default")

            # --- Anti-Bot Flags Essenciais ---
            edge_options.add_argument("--disable-blink-features=AutomationControlled")
            edge_options.add_argument("--start-maximized")
            edge_options.add_argument("--no-sandbox")
            edge_options.add_argument("--disable-dev-shm-usage")
            edge_options.add_argument("--disable-gpu")
            
            # User-Agent Real (Edge 131)
            edge_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
            )
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            edge_options.add_experimental_option('useAutomationExtension', False)

            # --- Instalação Automática do Driver ---
            service = EdgeService(EdgeChromiumDriverManager().install())
            
            driver = webdriver.Edge(service=service, options=edge_options)
            
            # Navegação IMEDIATA
            driver.get("https://web.whatsapp.com")
            
            # Bypass adicional via JS
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return driver

        try:
            self.driver = create_driver()
            return True
        except Exception as e:
            self.logger.error(f"❌ Falha crítica ao iniciar Edge driver: {e}")
            if self.driver:
                try: self.driver.quit()
                except: pass
                self.driver = None
            return False

    def _wait_for_login(self, timeout: int = 60) -> bool:
        """Aguardar login no WhatsApp Web."""
        if not self.driver:
            return False
            
        try:
            self.driver.get("https://web.whatsapp.com")
            # data-tab="3" -> Barra de pesquisa
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="3"]'))
            )
            self.logger.info("✅ WhatsApp Web carregado e logado.")
            return True
        except Exception:
            self.logger.warning("⏳ Login não detectado no tempo limite.")
            return False

    def _find_group(self, group_name: str) -> bool:
        """Busca e entra no grupo."""
        try:
            self.logger.info(f"🔍 Buscando grupo: {group_name}")
            search_box = self.driver.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="3"]')
            search_box.click()
            search_box.clear()
            search_box.send_keys(group_name)
            time.sleep(2)
            search_box.send_keys(Keys.ENTER)
            time.sleep(2) # Aguarda carregar chat
            return True
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar grupo: {e}")
            return False

    def _copy_image_to_clipboard(self, image_path: str) -> bool:
        """Copia imagem para o clipboard usando win32 ou powershell."""
        try:
            img = Image.open(image_path)
            
            # Tenta Win32
            if win32clipboard:
                output = io.BytesIO()
                img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                win32clipboard.CloseClipboard()
                return True
            
            # Fallback PowerShell
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                img.save(tmp.name, 'PNG')
                tmp_path = tmp.name
                
            ps_cmd = f'Set-Clipboard -Path "{tmp_path}"'
            subprocess.run(['powershell', '-Command', ps_cmd], check=True)
            os.unlink(tmp_path)
            return True

        except Exception as e:
            self.logger.error(f"❌ Falha ao copiar imagem {image_path}: {e}")
            return False

    def _send_clipboard_image(self) -> bool:
        """Cola e envia a imagem do clipboard."""
        try:
            # Foco na caixa de mensagem
            box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="10"]'))
            )
            box.click()
            time.sleep(0.5)
            
            # CTRL+V
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            
            # Wait for preview
            time.sleep(3)
            
            # Click Send
            send_btn = None
            selectors = [
                'span[data-icon="send"]',
                'button[aria-label="Enviar"]',
                'button[aria-label="Send"]',
                'span[data-testid="send"]'
            ]
            
            for sel in selectors:
                try:
                    send_btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                    break
                except:
                    continue
            
            if send_btn:
                send_btn.click()
            else:
                self.logger.warning("   💡 Botão enviar não achado, tentando ENTER.")
                ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                
            return True
        except Exception as e:
            self.logger.error(f"❌ Erro ao enviar imagem colada: {e}")
            return False

    def _buscar_imagens_automaticamente(self, data_dir: Path, prefixo: str = "ranking_diario") -> List[str]:
        """
        Busca automaticamente as imagens de ranking em um diretório.
        
        Args:
            data_dir: Diretório onde buscar as imagens
            prefixo: Prefixo do nome do arquivo (ex: "ranking_diario", "ranking_vendedor")
        
        Returns:
            Lista de caminhos absolutos das imagens encontradas (ordenadas por página)
        """
        imagens = []
        
        # Procura por arquivos paginados (prefixo_p1.png, prefixo_p2.png, etc.)
        for ext in [".png", ".jpg", ".jpeg"]:
            pagina = 1
            while True:
                arquivo = data_dir / f"{prefixo}_p{pagina}{ext}"
                if arquivo.exists():
                    imagens.append(str(arquivo.absolute()))
                    pagina += 1
                else:
                    break
            
            # Se não encontrou paginado, tenta arquivo único
            if not imagens:
                arquivo_unico = data_dir / f"{prefixo}{ext}"
                if arquivo_unico.exists():
                    imagens.append(str(arquivo_unico.absolute()))
                    break  # Se encontrou único, não precisa tentar outras extensões
        
        return imagens

    def find_ranking_images(self, data_dir: Path, prefixo: str = "ranking_diario") -> List[str]:
        """
        Método público para buscar imagens de ranking automaticamente.
        
        Args:
            data_dir: Diretório onde buscar as imagens
            prefixo: Prefixo do nome do arquivo (ex: "ranking_diario", "ranking_vendedor")
        
        Returns:
            Lista de caminhos absolutos das imagens encontradas
        """
        return self._buscar_imagens_automaticamente(data_dir, prefixo)

    def _get_dynamic_message(self) -> str:
        """Gera mensagem dinâmica baseada na hora."""
        hour = datetime.now().hour
        messages = {
            10: ["*Bom dia, Time!* Largada dada!", "*Start do Dia:* Quem saiu na frente?"],
            12: ["*Giro do Meio-Dia:* Confira a parcial!", "*Resumo da Manhã:* Líderes do turno!"],
            15: ["*Modo Turbo:* Reta final do dia!", "*Sprint de Vendas:* Acelera!"],
            18: ["*Fechamento:* Veja os números finais.", "*Fim de Expediente:* Missão cumprida!"]
        }
        
        # Select range
        if 9 <= hour < 11: key = 10
        elif 11 <= hour < 13: key = 12
        elif 14 <= hour < 16: key = 15
        elif 18 <= hour < 20: key = 18
        else: return f"📊 *Ranking Atualizado* ({datetime.now().strftime('%H:%M')})"
        
        return random.choice(messages[key])

    def send_ranking(self, group_names: str | List[str], image_paths: List[str], caption: Optional[str] = None) -> bool:
        """Orquestra o envio do ranking para um ou mais grupos."""
        if isinstance(group_names, str):
            group_names = [group_names]
            
        if not self._init_driver(): return False
        if not self._wait_for_login(): return False
        
        overall_success = False
        
        for group_name in group_names:
            self.logger.info(f"👥 Preparando envio para o grupo: {group_name}")
            if not self._find_group(group_name):
                self.logger.error(f"❌ Não foi possível encontrar o grupo: {group_name}")
                continue
                
            # Send Text / Caption
            try:
                msg = caption if caption else self._get_dynamic_message()
                box = self.driver.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="10"]')
                box.send_keys(msg + Keys.ENTER)
                time.sleep(2)
            except Exception as e:
                self.logger.warning(f"Texto dinâmico falhou: {e}")

            # Send Images
            success_count = 0
            for idx, img_path in enumerate(image_paths, 1):
                if not os.path.exists(img_path):
                    continue
                    
                self.logger.info(f"📤 [{idx}/{len(image_paths)}] Enviando {Path(img_path).name} para {group_name}")
                if self._copy_image_to_clipboard(img_path):
                    if self._send_clipboard_image():
                        success_count += 1
                        time.sleep(5) # Rate limit
                    else:
                        self.logger.error(f"Falha no envio do arquivo {img_path}")
                else:
                     self.logger.error(f"Falha no clipboard do arquivo {img_path}")

            self.logger.info(f"✅ Envio concluído para {group_name}. {success_count}/{len(image_paths)} imagens.")
            if success_count > 0:
                overall_success = True
            
            time.sleep(5) # Delay entre grupos
        
        self.driver.quit()
        return overall_success

    def send_individual_message(self, phone: str, message: str) -> bool:
        """Envia mensagem de texto via pywhatkit (usa o browser padrão)."""
        try:
            # Limpa telefone
            phone_clean = "".join(filter(str.isdigit, str(phone)))
            if len(phone_clean) in [10, 11] and not phone_clean.startswith("55"):
                phone_clean = "+55" + phone_clean
            elif not phone_clean.startswith("+"):
                phone_clean = "+" + phone_clean
                
            self.logger.info(f"💬 [PYWHATKIT] Enviando para {phone_clean}...")
            
            # pywhatkit.sendwhatmsg_instantly(phone, message, wait_time, tab_close, close_time)
            wa_cfg = get_whatsapp_config()
            wait_time = wa_cfg.get("wait_time", 15)
            
            # Nota: pywhatkit abre o brownser padrão. 
            # Se for rodar muitas msgs, o wait_time deve ser decente para não encavalar.
            pywhatkit.sendwhatmsg_instantly(
                phone_no=phone_clean,
                message=message,
                wait_time=wait_time,
                tab_close=True,
                close_time=3
            )
            
            self.logger.info(f"✅ [PYWHATKIT] Comando enviado para {phone_clean}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao enviar individual via pywhatkit: {e}")
            return False


# Facade for backward compatibility if needed, or direct usage
def get_whatsapp_service():
    return WhatsAppService()
