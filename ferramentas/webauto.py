"""webauto — abre o Chromium NATIVO do celular via Selenium (nivel 3).

O Playwright nao existe para Android (nao ha wheel no PyPI), entao a automacao
de verdade aqui e chromedriver (vem no pacote `chromium` do Termux) + selenium.

Uso dentro do seu script:

    from webauto import abrir, esperar

    with abrir() as d:
        d.get("https://example.com")
        print(d.title)
        esperar(d, "button#enviar", por="css").click()
        d.save_screenshot("print.png")

Rode com:  webplay meu_script.py
"""
from __future__ import annotations

import contextlib
import os
from typing import Iterator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CHROME = os.environ.get("CHROMIUM_BIN",
                        "/data/data/com.termux/files/usr/lib/chromium/chrome")
CHROMEDRIVER = os.environ.get("CHROMEDRIVER_BIN",
                              "/data/data/com.termux/files/usr/bin/chromedriver")
TMPDIR = os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp")

FLAGS_BASE = [
    "--no-sandbox",              # sem sandbox: obrigatorio no Android sem root
    "--disable-gpu",
    "--disable-dev-shm-usage",   # sem /dev/shm utilizavel
    "--no-first-run",
    "--no-default-browser-check",
    "--hide-scrollbars",
]


def abrir(headless: bool = True, largura: int = 900, altura: int = 1200,
          perfil: str | None = None) -> webdriver.Chrome:
    """Devolve um Chrome ja configurado para o Android. Feche com d.quit()."""
    opts = Options()
    opts.binary_location = CHROME
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument(f"--window-size={largura},{altura}")
    opts.add_argument(f"--user-data-dir={perfil or os.path.join(TMPDIR, 'webauto-perfil')}")
    for flag in FLAGS_BASE:
        opts.add_argument(flag)
    return webdriver.Chrome(service=Service(executable_path=CHROMEDRIVER),
                            options=opts)


@contextlib.contextmanager
def sessao(**kwargs) -> Iterator[webdriver.Chrome]:
    """Versao context manager: fecha o navegador mesmo se seu script falhar."""
    d = abrir(**kwargs)
    try:
        yield d
    finally:
        with contextlib.suppress(Exception):
            d.quit()


def esperar(driver: webdriver.Chrome, seletor: str, timeout: float = 10,
            por: str = "css"):
    """Espera o elemento existir e devolve ele (evita sleep no escuro)."""
    mapa = {"css": By.CSS_SELECTOR, "xpath": By.XPATH, "id": By.ID,
            "texto": By.XPATH, "tag": By.TAG_NAME}
    if por == "texto":
        cond = EC.presence_of_element_located(
            (By.XPATH, f"//*[contains(text(), {seletor!r})]"))
    else:
        cond = EC.presence_of_element_located((mapa[por], seletor))
    return WebDriverWait(driver, timeout).until(cond)


def texto_visivel(driver: webdriver.Chrome) -> str:
    """Texto do body como o usuario veria (ja com o JS feito)."""
    return " ".join(driver.find_element(By.TAG_NAME, "body").text.split())
