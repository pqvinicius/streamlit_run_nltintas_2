from __future__ import annotations

import base64
import mimetypes
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.logger import get_logger

logger = get_logger(__name__)



@dataclass(slots=True)
class TemplateRenderer:
    """
    Responsável por carregar templates HTML e renderizá-los com contexto dinâmico.
    """

    templates_dir: Path
    _env: Environment = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Pasta de templates não encontrada: {self.templates_dir}")
        self._env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=False,
        )

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        template = self._env.get_template(template_name)
        return template.render(**context)


def image_to_data_uri(image_path: Path) -> str | None:
    """
    Converte um arquivo de imagem em data URI embedável em HTML.
    """
    if not image_path or not image_path.exists():
        logger.warning("Logo/Imagem não encontrada: %s", image_path)
        return None
    mime_type, _ = mimetypes.guess_type(image_path.name)
    if not mime_type:
        mime_type = "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def html_to_png(
    html_content: str,
    destino: Path,
    *,
    viewport: tuple[int, int] = (1080, 1080),
    device_scale: int = 2,
    wait_ms: int = 600,
) -> Path:
    """
    Renderiza o HTML em um browser headless (Chromium) e salva a captura como PNG.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)

    # Detecta se está rodando em um .exe
    is_frozen = getattr(sys, "frozen", False)
    
    # Verifica disponibilidade de Playwright (lazy import)
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightError = Exception
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
        PLAYWRIGHT_AVAILABLE = True
        logger.info("Playwright disponível")
    except ImportError:
        logger.info("Playwright não disponível")
        PLAYWRIGHT_AVAILABLE = False
    
    # Verifica disponibilidade de Selenium (lazy import)
    SELENIUM_AVAILABLE = False
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        SELENIUM_AVAILABLE = True
        logger.info("Selenium disponível")
    except ImportError:
        logger.info("Selenium não disponível")
        SELENIUM_AVAILABLE = False
    
    # Se estiver em .exe, configura o caminho dos browsers do Playwright
    chromium_path = None
    if is_frozen:
        import os
        exe_dir = Path(sys.executable).parent
        ms_playwright_dir = exe_dir / "ms-playwright"
        
        # Procura Chromium no diretório do executável
        if ms_playwright_dir.exists():
            for chromium_dir in ms_playwright_dir.glob("chromium-*"):
                chrome_exe = chromium_dir / "chrome-win" / "chrome.exe"
                if chrome_exe.exists():
                    chromium_path = chrome_exe
                    logger.info("Chromium encontrado em: %s", chromium_path)
                    break
        
        # Se não encontrou, procura no cache do usuário
        if not chromium_path:
            user_cache = Path.home() / ".cache" / "ms-playwright"
            if user_cache.exists():
                for chromium_dir in user_cache.glob("chromium-*"):
                    chrome_exe = chromium_dir / "chrome-win" / "chrome.exe"
                    if chrome_exe.exists():
                        chromium_path = chrome_exe
                        logger.info("Chromium encontrado no cache do usuário: %s", chromium_path)
                        break
        
        # Configura variável de ambiente do Playwright
        if ms_playwright_dir.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ms_playwright_dir)
            logger.info("PLAYWRIGHT_BROWSERS_PATH configurado para: %s", ms_playwright_dir)
        elif chromium_path:
            # Se encontrou o Chromium mas não a pasta ms-playwright, usa o diretório pai
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(chromium_path.parent.parent)
            logger.info("PLAYWRIGHT_BROWSERS_PATH configurado para: %s", chromium_path.parent.parent)
    
    # Tenta usar Playwright primeiro (se disponível e funcionando)
    if PLAYWRIGHT_AVAILABLE:
        logger.info("Playwright disponível, tentando usar...")
        try:
            result = _html_to_png_playwright(html_content, destino, viewport, device_scale, wait_ms, is_frozen, chromium_path)
            logger.info("✅ Conversão concluída via Playwright")
            return result
        except Exception as exc:
            logger.warning("⚠️ Playwright falhou: %s", exc)
            logger.warning("Tentando Selenium como fallback...")
            if not SELENIUM_AVAILABLE:
                logger.error("❌ Selenium não disponível! Erro original: %s", exc, exc_info=True)
                raise RuntimeError(
                    "Falha ao renderizar HTML para PNG. Playwright não disponível e Selenium não encontrado. "
                    "Instale: pip install playwright selenium webdriver-manager"
                ) from exc
    
    # Usa Selenium como fallback (mais confiável em .exe)
    if SELENIUM_AVAILABLE:
        logger.info("Usando Selenium para renderização...")
        try:
            result = _html_to_png_selenium(html_content, destino, viewport, device_scale, wait_ms)
            logger.info("✅ Conversão concluída via Selenium")
            return result
        except Exception as exc:
            logger.error("❌ Erro ao usar Selenium: %s", exc, exc_info=True)
            raise
    
    logger.error("❌ Nenhum renderizador disponível!")
    raise RuntimeError(
        "Nenhum renderizador disponível. Instale Playwright ou Selenium: "
        "pip install playwright selenium webdriver-manager"
    )


def _html_to_png_playwright(
    html_content: str,
    destino: Path,
    viewport: tuple[int, int],
    device_scale: int,
    wait_ms: int,
    is_frozen: bool,
    chromium_path: Path | None,
) -> Path:
    """Renderiza HTML usando Playwright."""
    from playwright.sync_api import sync_playwright
    
    logger.info("Inicializando Playwright...")
    try:
        with sync_playwright() as playwright:
            launch_options = {"headless": True}
            
            if is_frozen and chromium_path:
                launch_options["executable_path"] = str(chromium_path)
                logger.info("Usando Chromium em: %s", chromium_path)
            
            logger.info("Lançando browser Chromium...")
            browser = playwright.chromium.launch(**launch_options)
            logger.info("Browser lançado, criando nova página...")
            page = browser.new_page(
                viewport={"width": viewport[0], "height": viewport[1], "deviceScaleFactor": device_scale}
            )
            logger.info("Página criada, carregando conteúdo HTML...")
            page.set_content(html_content, wait_until="networkidle")
            logger.info("Conteúdo carregado, aguardando %dms para renderização completa...", wait_ms)
            page.wait_for_timeout(wait_ms)
            logger.info("Tirando screenshot...")
            page.screenshot(path=str(destino), full_page=False)
            logger.info("Screenshot salvo, fechando browser...")
            browser.close()
            logger.info("Browser fechado")
            logger.info("Screenshot HTML salva em %s (via Playwright)", destino)
            return destino
    except Exception as exc:
        logger.error("Erro durante renderização Playwright: %s", exc, exc_info=True)
        raise


def _html_to_png_selenium(
    html_content: str,
    destino: Path,
    viewport: tuple[int, int],
    device_scale: int,
    wait_ms: int,
) -> Path:
    """Renderiza HTML usando Selenium (mais confiável em .exe)."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    
    logger.info("Configurando opções do Chrome para Selenium...")
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument(f"--window-size={viewport[0]},{viewport[1]}")
    chrome_options.add_argument("--hide-scrollbars")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    chrome_options.add_argument(f"--force-device-scale-factor={device_scale}")
    
    # Salva HTML temporariamente
    logger.info("Criando arquivo HTML temporário...")
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tmp_file:
        tmp_file.write(html_content)
        tmp_html_path = Path(tmp_file.name)
    logger.info("Arquivo temporário criado: %s", tmp_html_path)
    
    try:
        logger.info("Instalando/verificando ChromeDriver via webdriver-manager...")
        # Usa webdriver-manager para baixar ChromeDriver automaticamente
        service = Service(ChromeDriverManager().install())
        logger.info("ChromeDriver pronto, iniciando browser...")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Browser Chrome iniciado")
        
        try:
            # Abre o arquivo HTML temporário
            file_url = f"file:///{tmp_html_path.resolve()}"
            logger.info("Carregando HTML: %s", file_url)
            driver.get(file_url)
            logger.info("HTML carregado, aguardando elemento 'body'...")
            
            # Aguarda o conteúdo carregar
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info("Elemento 'body' encontrado, aguardando %dms para renderização...", wait_ms)
            
            # Aguarda um pouco mais para garantir que tudo renderizou
            import time
            time.sleep(wait_ms / 1000.0)
            
            logger.info("Tirando screenshot...")
            driver.save_screenshot(str(destino))
            logger.info("Screenshot salvo: %s", destino)
            
        finally:
            logger.info("Fechando browser...")
            driver.quit()
            logger.info("Browser fechado")
    except Exception as exc:
        logger.error("Erro durante renderização Selenium: %s", exc, exc_info=True)
        raise
    finally:
        # Remove arquivo temporário
        if tmp_html_path.exists():
            logger.info("Removendo arquivo temporário...")
            tmp_html_path.unlink()
    
    logger.info("Screenshot HTML salva em %s (via Selenium)", destino)
    return destino


