import time
import json
import traceback
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)

# ========== CONFIGURATION ==========
URL_INICIAL = "https://auth.sieg.com/"
URL_GERENCIAMENTO = "https://app.sieg.com/configuracoes/gerenciamento?tab=meus-cadastros"
ARQUIVO_LOG = "sieg_log.json"
TEMPO_ESPERA = 2
INICIAR_DA_LINHA = 0

resultados = []

def salvar_log():
    with open(ARQUIVO_LOG, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"  [LOG] {len(resultados)} empresas registradas em {ARQUIVO_LOG}")

def log(msg):
    hora = datetime.now().strftime("%H:%M:%S")
    print(f"[{hora}] {msg}")

def esperar(segundos=None):
    time.sleep(segundos or TEMPO_ESPERA)

def xpath_literal(texto):
    if "'" not in texto:
        return f"'{texto}'"
    
    if '"' not in texto:
        return f'"{texto}"'
    
    partes = texto.split("'")
    return "concat(" + ", \"'\", ".join(f"'{parte}'" for parte in partes) + ")"


def encontrar_por_texto(driver, texto, tag="*", timeout=10, contexto=None):
    literal = xpath_literal(texto)
    prefixo = ".//" if contexto else "//"
    raiz = contexto or driver

    xpaths = [
        f"{prefixo}{tag}[normalize-space(text())={literal}]",
        f"{prefixo}{tag}[contains(normalize-space(text()), {literal})]",
    ]

    if tag != "*":
        xpaths.extend([
            f"{prefixo}{tag}[normalize-space(.)={literal}]",
            f"{prefixo}{tag}[contains(normalize-space(.), {literal})]",
        ])

    fim = time.time() + timeout
    while time.time() < fim:
        for xpath in xpaths:
            try:
                elementos = raiz.find_elements(By.XPATH, xpath)
            except StaleElementReferenceException:
                break

            for el in elementos:
                try:
                    if el.is_displayed() and el.is_enabled():
                        return el
                except StaleElementReferenceException:
                    continue

        time.sleep(0.2)

    return None

def clicar_por_texto(driver, texto, tag="*", timeout=10, contexto=None):
    el = encontrar_por_texto(driver, texto, tag, timeout, contexto=contexto)
    if el:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            esperar(0.3)
            el.click()
            
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", el)
        log(f"  Clicou: '{texto}'")
        return True
    
    log(f"  [AVISO] Não encontrou: '{texto}'")
    return False

def clicar_elemento(driver, el, descricao=""):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
        esperar(0.3)
        el.click()
        
    except (ElementClickInterceptedException, Exception):
        driver.execute_script("arguments[0].click();", el)
        
    if descricao:
        log(f"  Clicou: {descricao}")

def fechar_modal(driver):
    tentativas = [
        (By.CSS_SELECTOR, "button.modal-close-btn"),
        (By.CSS_SELECTOR, ".modal-header button"),
        (By.XPATH, "//button[contains(@class, 'modal-close')]"),
    ]
    
    for by, selector in tentativas:
        try:
            btn = driver.find_element(by, selector)
            driver.execute_script("arguments[0].click();", btn)
            log("  Modal fechado.")
            esperar(1)
            return True
        
        except NoSuchElementException:
            continue

    try:
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        esperar(1)
        return True
    
    except:
        return False


def modal_esta_aberto(driver):
    try:
        modals = driver.find_elements(By.CSS_SELECTOR, ".modal-backdrop")
        return len(modals) > 0
    
    except:
        return False

def obter_texto_botao_principal(driver):
    try:
        botoes = driver.find_elements(
            By.CSS_SELECTOR,
            ".modal-footer button.su-btn-primary"
        )
        
        for btn in botoes:
            txt = btn.text.strip()
            
            if txt in ["Salvar e continuar", "Concluir"]:
                return txt, btn
            
        if botoes:
            return botoes[-1].text.strip(), botoes[-1]
    except:
        pass
    
    return "", None


def obter_nome_empresa(row):
    try:
        colunas = row.find_elements(By.CSS_SELECTOR, "td")
        if colunas:
            
            for col in colunas[:3]:
                texto = col.text.strip()
                
                if texto and len(texto) > 3:
                    return texto[:60]
    except:
        pass
    
    return "???"

def obter_texto_modal(driver):
    try:
        modal_body = driver.find_element(By.CSS_SELECTOR, ".modal-body")
        return modal_body.text
    
    except:
        return ""

def tela_nfse_portal_nacional(driver):
    texto_modal = obter_texto_modal(driver)
    
    return (
        "Notas de serviço" in texto_modal
        and "Configuração NF-es de Serviço" in texto_modal
        and "NFS-e Portal Nacional" in texto_modal
    )

def ativar_nfse_portal_nacional(driver):
    seletores = [
        (
            By.XPATH,
            (
                "//div[contains(@class, 'modal-body')]"
                "//label[contains(normalize-space(.), 'NFS-e Portal Nacional')]"
                "//input"
            ),
        ),
        (
            By.XPATH,
            (
                "//div[contains(@class, 'modal-body')]"
                "//*[contains(normalize-space(.), 'NFS-e Portal Nacional')]"
                "/ancestor::label[1]//input"
            ),
        ),
    ]

    toggle = None
    for by, seletor in seletores:
        try:
            elementos = driver.find_elements(by, seletor)
            
            for el in elementos:
                if el.is_displayed() and el.is_enabled():
                    toggle = el
                    break
                
        except:
            continue
        
        if toggle:
            break

    if not toggle:
        log("    [ERRO] Não encontrou o toggle 'NFS-e Portal Nacional'")
        return False

    try:
        if toggle.is_selected():
            log("    Toggle 'NFS-e Portal Nacional' já estava ativo.")
            return True
        
    except:
        pass

    log("    Ativando 'NFS-e Portal Nacional'...")
    driver.execute_script("arguments[0].click();", toggle)
    esperar(1.5)

    ciente_ok = clicar_por_texto(driver, "Ciente", "button", timeout=5)
    if not ciente_ok:
        ciente_ok = clicar_por_texto(driver, "Ciente", "span", timeout=3)

    if ciente_ok:
        log("    Confirmou 'Ciente'")
        
    else:
        log("    [AVISO] Popup 'Ciente' não apareceu após ativar o portal nacional.")

    esperar(1)

    try:
        return toggle.is_selected()
    
    except:
        return True

# ========== PROCESSING ==========

def processar_empresa(driver, row_index):
    """
    Processa uma empresa na tabela.
    Retorna: dict com resultado ou None se não há mais linhas.
    """
    # Re-encontrar as linhas
    esperar(1)
    linhas = driver.find_elements(By.CSS_SELECTOR, ".p-datatable-tbody tr")

    if row_index >= len(linhas):
        return None  # Acabaram as linhas visíveis

    linha = linhas[row_index]
    nome = obter_nome_empresa(linha)

    log(f"\n{'='*60}")
    log(f"EMPRESA {row_index + 1}/{len(linhas) - 50}: {nome}")
    log(f"{'='*60}")

    resultado = {
        "empresa": nome,
        "indice": row_index,
        "horario": datetime.now().strftime("%H:%M:%S"),
        "status": "",
    }

    try:
        # ====== PASSO 1: Abrir menu de ações (três pontinhos) ======
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", linha)
        esperar(0.5)

        try:
            dots_btn = linha.find_element(
                By.CSS_SELECTOR, "button.su-btn-primary.max-w-\\[1rem\\]"
            )
            
        except NoSuchElementException:
            dots_btn = linha.find_element(By.CSS_SELECTOR, "span.ph.ph-dots-three")

        clicar_elemento(driver, dots_btn, "Menu ações (⋯)")
        esperar(0.8)

        # ====== PASSO 2: Clicar "Editar cadastro" ======
        if not clicar_por_texto(
            driver, "Editar cadastro", "li", timeout=5, contexto=linha
        ):
            log("  [ERRO] Não encontrou 'Editar cadastro'")
            resultado["status"] = "erro_menu"
            return resultado

        esperar(2.5)

        # ====== PASSO 3: "Salvar e continuar" (passo 1 - dados) ======
        if not clicar_por_texto(driver, "Salvar e continuar", "button", timeout=10):
            log("  [ERRO] Não encontrou 'Salvar e continuar' no passo 1")
            fechar_modal(driver)
            resultado["status"] = "erro_passo1"
            return resultado

        esperar(2)

        # ====== PASSO 4: Aba "Certificado do procurador" ======
        if not clicar_por_texto(driver, "Certificado do procurador", "span", timeout=10):
            if not clicar_por_texto(driver, "Certificado do procurador", "li", timeout=5):
                log("  [ERRO] Não encontrou aba 'Certificado do procurador'")
                fechar_modal(driver)
                resultado["status"] = "erro_aba_cert"
                return resultado

        esperar(2)

        # ====== PASSO 5: Verificar se já tem certificado ======
        texto_modal = obter_texto_modal(driver)

        diego_ja_existe = (
            "DIEGO RODRIGO DOS SANTOS TRIVELATTO" in texto_modal
            and "Procurações adicionadas" in texto_modal
        )

        if diego_ja_existe:
            # ====== JÁ TEM CERTIFICADO - FECHAR ======
            log("  ✓ Já tem certificado do Diego. Fechando.")
            fechar_modal(driver)
            resultado["status"] = "ja_tinha_certificado"
            return resultado

        # ====== NÃO TEM CERTIFICADO - ADICIONAR ======
        log("  → Adicionando certificado...")

        if not clicar_por_texto(driver, "Selecione um certificado", "span", timeout=5):
            log("  [AVISO] Dropdown 'Selecione um certificado' não encontrado, tentando alternativa...")
            
            try:
                dropdown = driver.find_element(
                    By.CSS_SELECTOR,
                    ".modal-body .su-dropdown-list-item, .modal-body [class*='select']"
                )
                clicar_elemento(driver, dropdown, "dropdown certificado")
                
            except:
                log("  [ERRO] Não conseguiu abrir dropdown")
                fechar_modal(driver)
                resultado["status"] = "erro_dropdown"
                return resultado

        esperar(1)

        # 5b. Selecionar Diego
        if not clicar_por_texto(driver, "DIEGO RODRIGO DOS SANTOS TRIVELATTO", "li", timeout=5):

            if not clicar_por_texto(driver, "DIEGO RODRIGO", "li", timeout=3):
                log("  [ERRO] Não encontrou Diego na lista")
                fechar_modal(driver)
                resultado["status"] = "erro_diego_nao_encontrado"
                return resultado

        esperar(1)

        if not clicar_por_texto(driver, "Adicionar certificado", timeout=5):
            log("  [AVISO] Não encontrou botão 'Adicionar certificado'")
            
            try:
                btn_add = driver.find_element(
                    By.CSS_SELECTOR, ".modal-body button.su-btn-secondary"
                )
                clicar_elemento(driver, btn_add, "Adicionar certificado (CSS)")
            except:
                pass

        esperar(1.5)

        # ====== PASSO 6: Avançar pelas etapas até "Concluir" ======
        log("  → Avançando pelas etapas...")

        for passo in range(25):  # Máximo 25 etapas (segurança)
            esperar(1.5)

            texto_btn, btn = obter_texto_botao_principal(driver)

            if not btn:
                log(f"    [AVISO] Botão principal não encontrado no passo {passo}")
                esperar(1)
                continue

            if texto_btn == "Concluir":
                
                # ====== ETAPA FINAL ======
                log("  → Etapa final detectada!")

                if tela_nfse_portal_nacional(driver):
                    
                    if not ativar_nfse_portal_nacional(driver):
                        fechar_modal(driver)
                        resultado["status"] = "erro_nfse_portal_nacional"
                        return resultado
                else:
                    log("    Etapa final sem configuração de NFS-e. Apenas concluindo.")

                esperar(0.5)
                _, btn = obter_texto_botao_principal(driver)
                
                if btn:
                    clicar_elemento(driver, btn, "Concluir")
                    
                else:
                    clicar_por_texto(driver, "Concluir", "button")

                esperar(2)

                if not clicar_por_texto(
                    driver, "Confirmar e finalizar", timeout=5
                ):
                    clicar_por_texto(
                        driver, "Confirmar e finalizar", "span", timeout=3
                    )

                esperar(2)

                log("  ✓ Certificado adicionado e finalizado!")
                resultado["status"] = "certificado_adicionado"
                break

            elif texto_btn == "Salvar e continuar":
                clicar_elemento(driver, btn, f"Salvar e continuar (etapa {passo + 1})")

            else:
                log(f"    Botão inesperado: '{texto_btn}' - tentando clicar")
                clicar_elemento(driver, btn, texto_btn)

        else:
            log("  [ERRO] Limite de 25 etapas atingido!")
            fechar_modal(driver)
            resultado["status"] = "erro_muitas_etapas"

        esperar(1)
        if modal_esta_aberto(driver):
            fechar_modal(driver)

    except Exception as e:
        log(f"  [ERRO] {e}")
        traceback.print_exc()
        resultado["status"] = f"erro: {str(e)[:100]}"
        
        try:
            fechar_modal(driver)
            
        except:
            pass

    return resultado

def elemento_esta_disponivel(el):
    """Valida se o elemento está visível e não desabilitado."""
    try:
        classes = (el.get_attribute("class") or "").lower()
        aria_disabled = (el.get_attribute("aria-disabled") or "").lower()
        disabled = el.get_attribute("disabled")
        
        return (
            el.is_displayed()
            and el.is_enabled()
            and "disabled" not in classes
            and aria_disabled != "true"
            and disabled is None
        )
    except StaleElementReferenceException:
        return False


def obter_primeira_empresa_visivel(driver):
    """Pega o nome da primeira empresa visível na tabela."""
    try:
        linhas = driver.find_elements(By.CSS_SELECTOR, ".p-datatable-tbody tr")
        for linha in linhas:
            nome = obter_nome_empresa(linha)
            
            if nome and nome != "???":
                return nome
            
    except:
        pass
    
    return ""


def obter_pagina_atual(driver):
    seletores = [
        ".p-paginator-page.p-highlight",
        ".p-paginator-page[aria-current='page']",
        "[class*='paginator'] [aria-current='page']",
        "[class*='paginator'] .p-highlight",
    ]
    
    for seletor in seletores:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, seletor):
                if not el.is_displayed():
                    continue
                
                texto = el.text.strip()
                if texto.isdigit():
                    return int(texto)
        except:
            pass
    return None

def aguardar_mudanca_pagina(driver, pagina_anterior, primeira_empresa_anterior, timeout=10):
    fim = time.time() + timeout
    while time.time() < fim:
        esperar(0.5)

        pagina_atual = obter_pagina_atual(driver)
        if (
            pagina_anterior is not None
            and pagina_atual is not None
            and pagina_atual != pagina_anterior
        ):
            return True

        primeira_empresa_atual = obter_primeira_empresa_visivel(driver)
        
        if (
            primeira_empresa_anterior
            and primeira_empresa_atual
            and primeira_empresa_atual != primeira_empresa_anterior
        ):
            return True

    return False


def verificar_paginacao(driver):
    try:
        log("Verificando próxima página...")

        primeira_empresa_antes = obter_primeira_empresa_visivel(driver)

        next_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".p-paginator-next"))
        )

        classes = (next_btn.get_attribute("class") or "").lower()
        
        if "disabled" in classes:
            log("Última página atingida.")
            return False
        
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_btn)
        time.sleep(0.5)

        driver.execute_script("arguments[0].click();", next_btn)

        mudou = aguardar_mudanca_pagina(
            driver,
            pagina_anterior=None,
            primeira_empresa_anterior=primeira_empresa_antes,
            timeout=10
        )

        if mudou:
            log("✅ Mudou de página com sucesso!")
            return True
        
        else:
            log("⚠️ Clicou mas a tabela não mudou.")
            return False

    except Exception as e:
        log(f"❌ Erro ao trocar página: {e}")
        return False
    
# ========== MAIN ==========

def main():
    print("=" * 60)
    print("  SIEG - Automação de Procurações")
    print("  Certificado: DIEGO RODRIGO DOS SANTOS TRIVELATTO")
    print("=" * 60)
    print()

    # Configurar Chrome
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    print("[1] Abrindo Chrome...")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(URL_INICIAL)
        print()
        print("[2] Faça login no Sieg.")
        print("    Após fazer login, pressione ENTER aqui no terminal.")
        input("\n>>> Pressione ENTER quando estiver logada... ")

        print()
        print("[3] Navegando para a página de gerenciamento...")
        esperar(5)

        print()
        print("[4] Iniciando processamento das empresas!")
        print(f"    Começando da linha: {INICIAR_DA_LINHA}")
        print(f"    Tempo entre ações: {TEMPO_ESPERA}s")
        print()
        print("    Pressione Ctrl+C a qualquer momento para parar.")
        print("    O progresso é salvo automaticamente em sieg_log.json")
        print()

        pagina = 1
        indice_global = 0

        while True:
            log(f"\n--- Página {pagina} ---")

            # Contar linhas visíveis
            linhas = driver.find_elements(By.CSS_SELECTOR, ".p-datatable-tbody tr")
            total_linhas = len(linhas) - 50
            log(f"Linhas visíveis: {total_linhas}")

            if total_linhas == 0:
                log("Nenhuma linha encontrada. Fim!")
                break

            # Processar cada linha da página atual
            for i in range(total_linhas):
                indice_real = indice_global + i

                if indice_real < INICIAR_DA_LINHA:
                    log(f"Pulando linha {indice_real + 1} (antes de INICIAR_DA_LINHA)")
                    continue

                resultado = processar_empresa(driver, i)

                if resultado is None:
                    log("Sem mais linhas para processar.")
                    break

                resultados.append(resultado)
                salvar_log()

                status = resultado.get("status", "?")
                nome = resultado.get("empresa", "?")
                log(f"  RESULTADO: [{status}] {nome}")
                esperar(1)

            # Tentar ir para próxima página
            indice_global += total_linhas
            if verificar_paginacao(driver):
                pagina += 1
                esperar(2)
                
            else:
                # Tentar scroll para carregar mais
                try:
                    container = driver.find_element(
                        By.CSS_SELECTOR, ".p-datatable-table-container"
                    )
                    
                    driver.execute_script(
                        "arguments[0].scrollTop = arguments[0].scrollHeight;",
                        container
                    )
                    
                    esperar(2)
                    novas_linhas = driver.find_elements(
                        By.CSS_SELECTOR, ".p-datatable-tbody tr"
                    )
                    
                    if len(novas_linhas) <= total_linhas:
                        log("Sem mais empresas para processar!")
                        break
                    
                except:
                    log("Fim do processamento!")
                    break

        print()
        print("=" * 60)
        print("  PROCESSAMENTO CONCLUÍDO!")
        print("=" * 60)

        total = len(resultados)
        adicionados = sum(1 for r in resultados if r["status"] == "certificado_adicionado")
        ja_tinham = sum(1 for r in resultados if r["status"] == "ja_tinha_certificado")
        erros = sum(1 for r in resultados if r["status"].startswith("erro"))

        print(f"  Total processado: {total}")
        print(f"  Certificado adicionado: {adicionados}")
        print(f"  Já tinham certificado: {ja_tinham}")
        print(f"  Erros: {erros}")
        print(f"\n  Log salvo em: {ARQUIVO_LOG}")
        print()

        input("Pressione ENTER para fechar o navegador...")

    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário!")
        salvar_log()
        print(f"Progresso salvo. Para continuar, altere INICIAR_DA_LINHA = {len(resultados)}")

    finally:
        salvar_log()
        
        try:
            driver.quit()
            
        except:
            pass

if __name__ == "__main__":
    main()
