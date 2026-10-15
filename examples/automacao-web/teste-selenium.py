#!/usr/bin/env python3
"""Teste de automacao real no celular: chromedriver NATIVO + selenium.

Prova: JS roda, clique funciona, espera por elemento funciona, screenshot sai,
e a leitura do DOM reflete o clique. Nada disso depende de rede.
"""
import os
import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CHROME = os.environ.get(
    "CHROMIUM_BIN", "/data/data/com.termux/files/usr/lib/chromium/chrome")
DRIVER = os.environ.get(
    "CHROMEDRIVER_BIN", "/data/data/com.termux/files/usr/bin/chromedriver")
PERFIL = os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp")

opts = Options()
opts.binary_location = CHROME
for arg in ("--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--no-first-run",
            "--no-default-browser-check", f"--user-data-dir={PERFIL}/sel-perfil"):
    opts.add_argument(arg)

driver = webdriver.Chrome(service=Service(executable_path=DRIVER), options=opts)
try:
    pagina = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "interacao.html")
    driver.get(f"file://{pagina}")
    print("titulo:", driver.title)

    # 1) o JS rodou?
    print("JS executou:", driver.find_element(By.ID, "marca").text)

    # 2) o h1 começa em 'antes'
    antes = driver.find_element(By.ID, "titulo").text
    print("h1 antes do clique:", antes)

    # 3) clicar de verdade
    driver.find_element(By.ID, "botao").click()

    # 4) esperar o elemento aparecer (prova de espera explicita)
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, "alvo")))
    print("elemento revelado:", driver.find_element(By.ID, "alvo").text)

    depois = driver.find_element(By.ID, "titulo").text
    print("h1 depois do clique:", depois)

    # 5) screenshot
    destino = os.path.join(os.environ.get("PWD", "."), "selenium.png")
    driver.save_screenshot(destino)
    print("screenshot:", destino, os.path.getsize(destino), "bytes")

    ok = (antes == "antes" and depois == "depois do clique"
          and "42" in driver.find_element(By.ID, "marca").text)
    print("VEREDITO:", "AUTOMACAO FUNCIONANDO" if ok else "FALHOU")
    sys.exit(0 if ok else 1)
finally:
    driver.quit()
