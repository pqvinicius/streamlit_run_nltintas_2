import time
import shutil
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from src.config import get_web_config, get_paths, get_base_dir, get_execution_mode
from src.logger import get_logger
import pandas as pd

# --- CONFIGURAÇÃO ---
SEU_USUARIO = "adm2019"
SUA_SENHA = "2rq!XF"

WEB_CONFIG = get_web_config()
PATHS = get_paths()
URL_SITE = WEB_CONFIG["url_site"]
DEFAULT_WAIT_SECONDS = int(WEB_CONFIG["default_wait_seconds"])
DEFAULT_POST_DOWNLOAD_WAIT = int(WEB_CONFIG["post_download_wait"])
BAIXAR_META_VENDEDOR = WEB_CONFIG.get("baixar_meta_vendedor", True)
BASE_DIR = get_base_dir()
data_cfg = PATHS.get("data_dir")
DATA_DIR = Path(data_cfg) if data_cfg else BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

logger = get_logger(__name__)


def scroll_until_visible(driver, locator, max_attempts=12, pause=0.7):
    """
    Rola a página progressivamente até que o elemento seja localizado e exibido.
    Retorna o elemento encontrado ou None em caso de falha.
    """
    for _ in range(max_attempts):
        try:
            element = driver.find_element(*locator)
        except NoSuchElementException:
            element = None

        if element:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(pause)
            if element.is_displayed():
                return element

        driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * 0.85));")
        time.sleep(pause)

    return None


def mover_arquivo_apos_download(
    diretorio_downloads: Path,
    diretorio_destino: Path,
    nome_destino: str,
    tempo_espera: int = 10,
    force: bool = True,
) -> Path:
    """
    Aguarda o download e move o arquivo mais recente para o destino.
    Ignora arquivos temporários do Excel (~$*) e aguarda até o download completar.
    
    Args:
        diretorio_downloads: Pasta onde o arquivo foi baixado
        diretorio_destino: Pasta de destino
        nome_destino: Nome do arquivo de destino
        tempo_espera: Tempo de espera inicial em segundos
        force: Se True, sempre sobrescreve o arquivo existente (padrão: True)
    """
    diretorio_destino.mkdir(parents=True, exist_ok=True)
    destino = diretorio_destino / nome_destino
    
    # Aguarda o download completar inicialmente
    time.sleep(tempo_espera)
    
    # Função auxiliar para filtrar arquivos válidos (não temporários)
    def _is_arquivo_valido(arquivo: Path) -> bool:
        """Verifica se o arquivo não é temporário do Excel."""
        return not arquivo.name.startswith("~$") and arquivo.suffix.lower() == ".xlsx"
    
    # Aguarda até encontrar um arquivo válido e que não esteja sendo usado
    max_tentativas = 30  # Máximo de 30 tentativas (5 minutos)
    tentativa = 0
    arquivo_origem = None
    
    while tentativa < max_tentativas:
        # Lista todos os arquivos .xlsx, filtra temporários e ordena por data
        todos_arquivos = list(diretorio_downloads.glob("*.xlsx"))
        arquivos_validos = [a for a in todos_arquivos if _is_arquivo_valido(a)]
        
        if not arquivos_validos:
            tentativa += 1
            logger.debug(f"Aguardando download... (tentativa {tentativa}/{max_tentativas})")
            time.sleep(2)
            continue
        
        # Pega o arquivo mais recente
        arquivo_candidato = sorted(arquivos_validos, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        
        # Verifica se o arquivo não está sendo usado (tentando abrir em modo exclusivo)
        try:
            # Tenta abrir o arquivo para verificar se está disponível
            with open(arquivo_candidato, "rb"):
                # Se conseguiu abrir, o arquivo está disponível
                arquivo_origem = arquivo_candidato
                break
        except (PermissionError, OSError):
            # Arquivo ainda está sendo usado, aguarda mais
            tentativa += 1
            logger.debug(f"Arquivo ainda em uso: {arquivo_candidato.name}. Aguardando... (tentativa {tentativa}/{max_tentativas})")
            time.sleep(2)
            continue
    
    if arquivo_origem is None:
        raise FileNotFoundError(
            f"Nenhum arquivo XLSX válido encontrado em {diretorio_downloads} após {max_tentativas} tentativas. "
            f"Verifique se o download foi concluído."
        )
    
    # Remove destino se existir (sempre sobrescreve se force=True)
    if destino.exists():
        if force:
            try:
                destino.unlink()
                logger.debug(f"Arquivo existente removido para sobrescrita: {destino.name}")
            except PermissionError as e:
                logger.warning(f"Erro ao remover arquivo existente (pode estar em uso): {e}")
                # Tenta renomear o arquivo antigo
                timestamp = datetime.now().strftime("%H%M%S")
                backup_name = destino.with_name(f"{destino.stem}_backup_{timestamp}{destino.suffix}")
                try:
                    destino.rename(backup_name)
                    logger.info(f"Arquivo existente renomeado para backup: {backup_name.name}")
                except Exception as e2:
                    raise RuntimeError(
                        f"Não foi possível sobrescrever o arquivo {destino.name}. "
                        f"Feche o arquivo se estiver aberto e tente novamente."
                    ) from e2
        else:
            # Se force=False, cria um novo arquivo com timestamp
            timestamp = datetime.now().strftime("%H%M%S")
            destino = destino.with_name(f"{destino.stem}_{timestamp}{destino.suffix}")
            logger.info(f"Arquivo existente preservado. Novo arquivo: {destino.name}")
    
    # Move o arquivo com retry em caso de erro
    max_retries = 5
    for retry in range(max_retries):
        try:
            shutil.move(str(arquivo_origem), str(destino))
            logger.info(f"Arquivo movido: {arquivo_origem.name} -> {destino.name}")
            return destino
        except (PermissionError, OSError) as e:
            if retry < max_retries - 1:
                logger.warning(f"Erro ao mover arquivo (tentativa {retry + 1}/{max_retries}): {e}. Aguardando...")
                time.sleep(2)
            else:
                raise RuntimeError(
                    f"Não foi possível mover o arquivo {arquivo_origem.name} após {max_retries} tentativas. "
                    f"O arquivo pode estar aberto em outro programa. Feche-o e tente novamente."
                ) from e


def executar_web_automation(
    usuario: str = SEU_USUARIO,
    senha: str = SUA_SENHA,
    post_download_wait: int = DEFAULT_POST_DOWNLOAD_WAIT,
    diretorio_downloads: Path | None = None,
    diretorio_destino: Path | None = None,
    somente_meta_empresa: bool = False,
    force_overwrite: bool = True,
) -> dict[str, Path]:
    """
    Executa o fluxo completo de automação web para exportar as planilhas.
    Move os arquivos imediatamente após cada download para a pasta de destino.

    Retorna um dicionário com os caminhos dos arquivos baixados.
    """
    if diretorio_downloads is None:
        cfg_dl = PATHS.get("downloads_dir") or WEB_CONFIG.get("downloads_dir") or ""
        diretorio_downloads = Path(cfg_dl) if cfg_dl else (Path.home() / "Downloads")
    if diretorio_destino is None:
        base_dir = get_base_dir()
        diretorio_destino = base_dir / "data"
        diretorio_destino.mkdir(exist_ok=True)
    
    sufixo_data = datetime.now().strftime("%d%m")
    
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.accept_insecure_certs = True
    
    exec_mode = get_execution_mode()
    
    # Modo headless (sem abrir janela do Chrome)
    # Roda headless automaticamente se for BATCH (Modo Noturno) OU se estiver explicitamente no config.ini
    is_headless = (exec_mode == "BATCH") or WEB_CONFIG.get("headless", False)
    
    if is_headless:
        motivo = "Modo Noturno (BATCH)" if exec_mode == "BATCH" else "Configuracão (config.ini)"
        logger.info(f"🌐 [WEB] Ativando Headless Moderno. Motivo: {motivo}")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
    else:
        logger.info(f"🌐 [WEB] Modo {exec_mode}: Interface visível habilitada")
        chrome_options.add_argument("--window-size=1920,1080")
    
    # Logs reduzidos
    chrome_options.add_argument("--log-level=3")  # Apenas erros fatais
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    
    # Configura diretório de download explicitamente
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": str(diretorio_downloads.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, DEFAULT_WAIT_SECONDS)
    
    arquivos_baixados = {}

    logger.info("Iniciando automação web...")
    logger.debug(f"URL do site: {URL_SITE}")
    logger.debug(f"Diretório de downloads: {diretorio_downloads}")
    logger.debug(f"Diretório de destino: {diretorio_destino}")
    
    try:
        logger.info(f"Acessando o site: {URL_SITE}")
        driver.get(URL_SITE)
        time.sleep(3)

        logger.debug("Preenchendo o campo de usuário...")
        campo_usuario = wait.until(EC.element_to_be_clickable((By.NAME, "email")))
        campo_usuario.clear()
        campo_usuario.send_keys(usuario)

        logger.debug("Preenchendo o campo de senha...")
        campo_senha = wait.until(EC.element_to_be_clickable((By.NAME, "password")))
        campo_senha.send_keys(senha)

        # Clicar no botão de Login
        logger.debug("Tentando clicar no botão de Login...")
        try:
            botao_login = wait.until(EC.element_to_be_clickable((By.ID, "logonButton")))
            botao_login.click()
        except TimeoutException:
            logger.warning("Botão de login 'logonButton' não encontrado ou não clicável. Tentando ENTER.")
            campo_senha.send_keys(Keys.ENTER)

        time.sleep(5)  # Espera processamento do login

        # Fallback: Verificar se ainda estamos na tela de login
        try:
            # Se o formulário de login ainda estiver presente, algo deu errado
            login_form = driver.find_element(By.NAME, "LogonForm")
            if login_form.is_displayed():
                logger.warning("Ainda na tela de login após clique. Tentando JS Fallback...")
                driver.execute_script("on_submit('logon');")
                time.sleep(5)
                
                # Verifica de novo
                if driver.find_element(By.NAME, "LogonForm").is_displayed():
                     logger.error("ALERTA CRÍTICO: Login falhou mesmo com fallback JS. Verifique credenciais ou captcha.")
        except NoSuchElementException:
            # Se não encontrou o form, ótimo, saímos da tela de login
            logger.debug("Login validado: Formulário de login não está mais visível.")

        logger.info("Fluxo de login finalizado.")

        try:
            logger.debug("Verificando sessões remotas anteriores...")
            remover_sessoes = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//a[contains(@href, \"on_submit('confirm')\") or contains(normalize-space(), 'Remover sessões remotas')]",
                    )
                )
            )
        except TimeoutException:
            logger.debug("Nenhuma sessão remota pendente encontrada.")
        else:
            logger.info("Removendo sessões remotas pendentes...")
            remover_sessoes.click()
            time.sleep(2)
            logger.info("Aguardando 40 segundos para estabilização do BI...")
            time.sleep(40)

        # =========================
        # META POR VENDEDOR (AGORA OBRIGATÓRIO/ÚNICO)
        # =========================
        # (Código de Meta Empresa removido conforme solicitação)
        
        # Como removemos o Meta Empresa, não temos mais o "primeiro painel".
        # O foco agora é direto no Meta Vendedor.


        # =========================
        # SEGUNDA EXPORTAÇÃO (OPCIONAL NO FLUXO DIÁRIO): META POR VENDEDOR
        # =========================
        # =========================
        # META POR VENDEDOR (AGORA OBRIGATÓRIO/ÚNICO)
        # =========================
        # Garantir que não existe arquivo anterior para forçar o download
        nome_meta_vend_check = f"MetaVendedor_{sufixo_data}.xlsx"
        caminho_check = diretorio_destino / nome_meta_vend_check
        if caminho_check.exists():
            logger.info(f"Arquivo existente encontrado: {caminho_check.name}. Removendo para garantir atualização diária.")
            try:
                caminho_check.unlink()
            except Exception as e:
                logger.warning(f"Não foi possível remover arquivo anterior {caminho_check.name}: {e}")

        logger.info("Iniciando exportação do painel de Meta por Vendedor...")
        try:
            # 1) Focar na página/rolar (se necessário)
            logger.debug("Procurando o widget 'Meta por vendedor'...")
            
            # Tenta encontrar com o título exato ou aproximado
            widget_vend_locator = (
                By.XPATH,
                "//div[contains(@class,'dashContentName') and contains(@class,'portlet-header') "
                "and (contains(normalize-space(), 'Meta por vendedor') or contains(normalize-space(), 'TELE VENDAS'))]",
            )
            
            header_vend = scroll_until_visible(driver, widget_vend_locator, max_attempts=15, pause=1.0)
            if header_vend:
                # Encontrar container
                container_vend = None
                try:
                    container_vend = header_vend.find_element(By.XPATH, "./ancestor::div[contains(@class,'portlet')][1]")
                except NoSuchElementException:
                    container_vend = header_vend

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", container_vend)
                time.sleep(0.5)
                ActionChains(driver).move_to_element(container_vend).pause(0.5).perform()
                
                # Botão Mais
                botao_mais_vend = None
                try:
                    botao_mais_vend = container_vend.find_element(By.CSS_SELECTOR, "div.btn-container.menuList.actionListMenu[title='Mais']")
                except NoSuchElementException:
                    pass
                
                if not botao_mais_vend:
                        try:
                            botao_mais_vend = driver.find_element(
                                By.CSS_SELECTOR,
                                "#\\33 3e5c5d7-f24c-44a8-99b6-426c560963b3 > div > div.dashContentPortlet > div > "
                                "report-output > div.contentActionWrapper > div > div:nth-child(2) > div"
                            )
                        except NoSuchElementException:
                            pass
                    
                # Tenta busca genérica se ainda não achou
                if not botao_mais_vend and container_vend:
                    try:
                            botao_mais_vend = container_vend.find_element(By.XPATH, ".//div[@title='Mais']")
                    except NoSuchElementException:
                        pass

                if botao_mais_vend:
                    # Implementação de Retry de Negócio (BI Reset)
                    MAX_RETRIES_BI = 3
                    arquivo_baixado_final = None

                    for tentativa_bi in range(1, MAX_RETRIES_BI + 1):
                        logger.info(f"Tentativa de Exportação BI {tentativa_bi}/{MAX_RETRIES_BI}")
                        
                        # 1. Scroll e Click (se necessário, ou se refreshou)
                        if tentativa_bi > 1:
                             # Re-localizar o botão após refresh
                             try:
                                 botao_mais_vend = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='dashboardPageBody']//div[@title='Mais']"))) # Seletor genérico tentativa
                                 if not botao_mais_vend: raise NoSuchElementException
                             except:
                                 # Fallback: Tenta relocalizar o container
                                 time.sleep(5)
                                 # (Simplificação: Assume que o estado voltou ao inicial e re-executa busca simples ou usa o seletor direto se possível)
                                 # Na prática, se der refresh, precisa refazer a navegação básica (login tá ok, mas pagina recarregou)
                                 pass 

                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_mais_vend)
                        time.sleep(0.5)
                        try:
                            driver.execute_script("arguments[0].click();", botao_mais_vend)
                        except:
                            # Se falhar clique JS, tenta normal
                            try: botao_mais_vend.click()
                            except: pass

                        # Exportar -> XLSX
                        logger.debug("Selecionando Exportar -> XLSX...")
                        time.sleep(1.0)
                            
                        seletores_exportar = [
                            (By.XPATH, "//div[@class='yfDropMenuTitle' and normalize-space()='Exportar']"),
                            (By.CSS_SELECTOR, "#dashboardPageBody > ul > li.menuItem.menuFirstItem.hasSubMenu.hasLink")
                        ]
                        
                        opcao_exportar = None
                        for loc in seletores_exportar:
                            try:
                                opcao_exportar = wait.until(EC.visibility_of_element_located(loc))
                                break
                            except TimeoutException:
                                continue
                                
                        if opcao_exportar:
                            ActionChains(driver).move_to_element(opcao_exportar).pause(0.5).perform()
                            
                            seletores_xlsx = [
                                (By.XPATH, "//div[@class='yfDropMenuTitle' and normalize-space()='XLSX']"),
                                (By.CSS_SELECTOR, "#dashboardPageBody > ul > li.menuItem.menuFirstItem.hasSubMenu.hasLink > ul > li:nth-child(5) > div.yfDropMenuTitle")
                            ]
                            
                            opcao_xlsx = None
                            for loc in seletores_xlsx:
                                try:
                                    opcao_xlsx = wait.until(EC.element_to_be_clickable(loc))
                                    break
                                except TimeoutException:
                                    continue
                            
                            if opcao_xlsx:
                                try:
                                    opcao_xlsx.click()
                                except ElementClickInterceptedException:
                                    driver.execute_script("arguments[0].click();", opcao_xlsx)
                                
                                # Botão Final Exportar
                                try:
                                    botao_exportar_final = wait.until(
                                        EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'submitMidHighlightText') and normalize-space()='Exportar']"))
                                    )
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_exportar_final)
                                    time.sleep(0.5)
                                    botao_exportar_final.click()
                                except Exception as e:
                                    logger.warning(f"Erro ao clicar Exportar Final: {e}")
                                    continue

                                logger.info("Solicitado download Meta Vendedor. Aguardando...")
                                nome_meta_vend = f"MetaVendedor_{sufixo_data}.xlsx"
                                
                                # Move e Valida
                                try:
                                    arquivo_temp = mover_arquivo_apos_download(
                                        diretorio_downloads,
                                        diretorio_destino,
                                        nome_meta_vend,
                                        tempo_espera=post_download_wait + (10 if tentativa_bi > 1 else 0), # Espera mais no retry
                                        force=True, # Sempre sobrescreve tentativas anteriores
                                    )
                                    
                                    # VALIDAÇÃO DE NEGÓCIO
                                    logger.info("Validando conteúdo do arquivo (BI Check)...")
                                    try:
                                        # Ler cabeçalho
                                        df_check = pd.read_excel(arquivo_temp, header=None, nrows=10)
                                        conteudo_str = df_check.to_string().lower()
                                        
                                        if "erro ao recuperar resultados" in conteudo_str or "error retrieving results" in conteudo_str:
                                            logger.warning(f"BI RETORNOU ERRO DE NEGÓCIO (Tentativa {tentativa_bi}). Resetando Sessão...")
                                            arquivo_temp.unlink() # Apaga arquivo ruim
                                            
                                            if tentativa_bi < MAX_RETRIES_BI:
                                                logger.info("Executando Refresh da Página...")
                                                driver.refresh()
                                                time.sleep(15) # Espera carregar
                                                
                                                # Re-localizar elementos base pós refresh
                                                # (Simplificado: loop continua e tenta re-fazer passos)
                                                # Mas precisamos garantir que 'botao_mais_vend' seja encontrado de novo
                                                # O loop assume que 'botao_mais_vend' é usado no inicio. 
                                                # Como ele foi achado fora do loop, precisamos re-achar DENTRO se der refresh.
                                                # Vamos forçar um 'continue' que vai pro topo, mas o topo usa variavel externa?
                                                # Não, o topo usa 'botao_mais_vend'.
                                                # Precisamos re-buscar o elemento.
                                                
                                                # Re-executa busca do elemento MAIS
                                                try:
                                                    # Espera container carregar
                                                    wait.until(EC.presence_of_element_located((By.XPATH, "//div[@id='dashboardPageBody']")))
                                                    # Busca botão Mais novamente
                                                    botao_mais_vend = scroll_until_visible(
                                                        driver, 
                                                        (By.XPATH, "//div[@title='Mais']"), 
                                                        max_attempts=5
                                                    )
                                                except:
                                                     logger.warning("Não consegui re-localizar botão Mais após refresh.")
                                                
                                                continue
                                            else:
                                                logger.error("Máximo de tentativas de BI excedido.")
                                        else:
                                            # Sucesso!
                                            logger.info("Arquivo validado com sucesso!")
                                            arquivos_baixados["meta_vendedor"] = arquivo_temp
                                            arquivo_baixado_final = arquivo_temp
                                            break

                                    except Exception as e_valid:
                                        logger.warning(f"Erro ao validar Excel: {e_valid}. Assumindo válido ou retry.")
                                        arquivos_baixados["meta_vendedor"] = arquivo_temp
                                        break
                                        
                                except Exception as e_dl:
                                    logger.error(f"Erro no download/move: {e_dl}")
                                    continue
                                
                            else:
                                logger.warning("Opção XLSX não encontrada.")
                        else:
                            logger.warning("Opção Exportar não encontrada.")
                    
                    if not arquivo_baixado_final:
                         logger.error("Falha ao obter Meta Vendedor Válido após retries.")

                else:
                    logger.warning("Botão MAIS não encontrado para Vendedor.")
            else:
                logger.warning("Widget Meta Vendedor não encontrado.")
        except Exception as e:
            logger.error(f"Erro ao baixar Meta Vendedor: {e}")

        if somente_meta_empresa:
            logger.info("Modo 'somente_meta_empresa' ativo. Finalizando após primeiro download.")
            return arquivos_baixados

        # =========================
        # FLUXO SIMPLIFICADO: FIM DA EXECUÇÃO
        # =========================
        logger.info("Fluxo de Meta Vendedor concluído. Finalizando automação.")

    except TimeoutException as err:
        logger.error(f"Não foi possível concluir a exportação: tempo limite excedido. Detalhes: {err}")
    except NoSuchElementException as err:
        logger.error(f"Não foi possível concluir a exportação: elementos não encontrados. Detalhes: {err}")
    except Exception as err:
        logger.exception(f"Erro durante a automação web: {err}")
    finally:
        logger.info("Fechando o navegador.")
        driver.quit()
        logger.info(f"Automação web concluída. Arquivos baixados: {list(arquivos_baixados.keys())}")

    return arquivos_baixados


if __name__ == "__main__":
    executar_web_automation()
