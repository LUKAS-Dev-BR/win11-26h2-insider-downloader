#!/usr/bin/env python3
"""
download_win11_26h2.py
======================

Baixa a ISO do Windows 11 26H2 (build 26300.x) diretamente do
**Windows Insider Program** automatizando o browser com Playwright.

Fluxo:
  1. Abre o Chromium (headed por padrão na primeira vez).
  2. Vai na página do Insider e, se você não estiver logado, **espera
     você fazer login manualmente** (lida com 2FA/MFA certinho).
  3. Salva o estado de autenticação num arquivo (`storage_state.json`)
     pra você não precisar logar de novo nas próximas vezes.
  4. Preenche automaticamente canal / idioma / arquitetura.
  5. Clica em "Download", captura a URL gerada e baixa a ISO com
     barra de progresso.
  6. (Opcional) Valida o SHA-256.

Não precisa de extensão nenhuma.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)
from tqdm import tqdm


INSIDER_URL = "https://www.microsoft.com/en-us/software-download/windows-insider"
DEFAULT_STATE = Path("storage_state.json")
DEFAULT_OUTPUT = Path("./Windows11_26H2.iso")

# Timeout pra esperar o login manual (5 min)
LOGIN_TIMEOUT_MS = 5 * 60 * 1000

# Mensagens de UI conhecidas
ACCEPT_TERMS_PATTERNS = [
    re.compile(r"\bi\s+accept\b", re.IGNORECASE),
    re.compile(r"\bi\s+agree\b", re.IGNORECASE),
    re.compile(r"\baceito\b", re.IGNORECASE),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Baixa a ISO do Windows 11 26H2 via Windows Insider Program."
    )
    p.add_argument(
        "--channel",
        choices=["Release Preview", "Beta", "Dev"],
        default="Release Preview",
        help="Canal do Insider (padrão: Release Preview).",
    )
    p.add_argument(
        "--language",
        default="English (United States)",
        help="Idioma da ISO (ex: 'Portuguese (Brazil)').",
    )
    p.add_argument(
        "--arch",
        choices=["x64", "Arm64"],
        default="x64",
        help="Arquitetura (padrão: x64).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Caminho de saída da ISO.",
    )
    p.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE,
        help="Arquivo de storage_state do Playwright (cookies + localStorage).",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Roda o browser sem janela. Só funciona se --state já existe.",
    )
    p.add_argument(
        "--url-only",
        action="store_true",
        help="Apenas captura a URL de download gerada, sem baixar a ISO.",
    )
    p.add_argument(
        "--sha256",
        default=None,
        help="SHA-256 esperado. Se informado, valida após o download.",
    )
    p.add_argument(
        "--reset-state",
        action="store_true",
        help="Apaga o storage_state salvo e força novo login interativo.",
    )
    p.add_argument(
        "--debug-dir",
        type=Path,
        default=Path("./debug"),
        help="Diretório pra screenshots e HTML em caso de erro.",
    )
    return p.parse_args()


# --------------------------------------------------------------------------- #
# Helpers de Playwright
# --------------------------------------------------------------------------- #


def find_select_by_label(page: Page, label_text: str):
    """Retorna o <select> cujo rótulo próximo contém `label_text`."""
    return page.locator(
        f"select:near(:text('{label_text}'))"
    ).first


def dump_debug(page: Page, dest: Path, tag: str) -> None:
    """Salva screenshot e HTML pra debug quando algo dá errado."""
    dest.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(dest / f"{tag}.png"), full_page=True)
        (dest / f"{tag}.html").write_text(page.content(), encoding="utf-8")
    except Exception as exc:
        print(f"[warn] não consegui salvar debug em {tag}: {exc}")


def is_logged_in(page: Page) -> bool:
    """Heurística: na página Insider logada, aparecem dropdowns de produto."""
    try:
        # Procura qualquer <select> visível na página
        return page.locator("select").count() > 0
    except Exception:
        return False


def wait_for_login(page: Page, timeout_ms: int = LOGIN_TIMEOUT_MS) -> None:
    """Espera o usuário terminar o login (lidando com 2FA)."""
    print("\n" + "=" * 70)
    print("  AÇÃO NECESSÁRIA: faça login com sua conta Microsoft Insider")
    print("  (pode levar 2FA / Microsoft Authenticator — faça tudo no browser)")
    print("=" * 70 + "\n")

    # Espera a URL sair dos domínios de login
    page.wait_for_function(
        """() => {
            const u = window.location.href.toLowerCase();
            return !u.includes('login.live.com')
                && !u.includes('login.microsoftonline.com')
                && !u.includes('account.microsoft.com');
        }""",
        timeout=timeout_ms,
    )

    # Espera os controles do formulário de download aparecerem
    page.wait_for_selector("select", timeout=timeout_ms)
    print("[ok] Login concluído e formulário detectado.")


def accept_terms_if_present(page: Page) -> None:
    """Marca checkbox/aceite de termos se existir."""
    for pattern in ACCEPT_TERMS_PATTERNS:
        try:
            box = page.locator(
                f"input[type='checkbox']:near(:text(\"{pattern.pattern}\"))"
            ).first
            if box.count() > 0 and not box.is_checked():
                box.check()
                print(f"[ok] Aceite de termos marcado: {pattern.pattern!r}")
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Fluxo principal: preencher formulário e pegar URL
# --------------------------------------------------------------------------- #


def fill_form(page: Page, channel: str, language: str, arch: str) -> None:
    """Seleciona canal/edição, idioma e arquitetura nos dropdowns."""
    print(f"[*] Preenchendo formulário: canal={channel!r}, idioma={language!r}, arch={arch!r}")

    # Espera a página ter pelo menos um <select>
    page.wait_for_selector("select", timeout=60_000)

    selects = page.locator("select")
    n = selects.count()
    print(f"[*] {n} <select>(s) encontrados na página.")

    if n == 0:
        raise RuntimeError("Nenhum <select> encontrado. A página pode ter mudado.")

    # Tenta casar cada dropdown por heurística de label próximo
    def try_select(label_re: str, target_label: str, kind: str) -> bool:
        for i in range(n):
            sel = selects.nth(i)
            try:
                # Texto de label associado (heurística: label/legend/spans próximos)
                surrounding = sel.evaluate(
                    """el => {
                        const ids = [el.id, el.name];
                        const labels = Array.from(document.querySelectorAll('label'))
                            .filter(l => l.htmlFor && ids.includes(l.htmlFor))
                            .map(l => l.textContent);
                        return (labels.join(' ') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
                    }"""
                )
                if label_re.lower() in surrounding:
                    sel.select_option(label=target_label)
                    print(f"[ok] {kind}: {target_label!r}")
                    return True
            except Exception:
                continue
        return False

    # 1) Canal (Edition) — em algumas builds aparece como radio, em outras como select
    if not try_select("edition", channel, "Edition"):
        # Tenta por valor exato também
        try_select("channel", channel, "Channel")

    # Pequena pausa pra AJAX repopular listas dependentes
    page.wait_for_timeout(1500)

    # Re-busca selects (podem ter sido recriados)
    selects = page.locator("select")

    # 2) Idioma
    try_select("language", language, "Language")
    page.wait_for_timeout(1000)

    # 3) Arquitetura
    try_select("architecture", arch, "Architecture")
    page.wait_for_timeout(1000)


def click_download_and_capture_url(page: Page, debug_dir: Path) -> str:
    """Clica no botão Download e captura a URL gerada."""
    print("[*] Clicando em Download…")

    # A Microsoft exibe a URL num <input readonly> ou como texto na página
    # após o clique. Vamos esperar pelo link aparecer.

    download_btn = page.locator(
        "button:has-text('Download'), input[type='submit'][value*='Download'], a:has-text('Download')"
    ).first

    if download_btn.count() == 0:
        dump_debug(page, debug_dir, "no_download_button")
        raise RuntimeError("Botão de Download não encontrado.")

    with page.expect_navigation(wait_until="domcontentloaded", timeout=120_000):
        try:
            download_btn.click()
        except PlaywrightTimeout:
            # Alguns fluxos não navegam — só trocam o conteúdo
            pass

    # Espera a URL aparecer no HTML
    print("[*] Esperando URL de download ser gerada…")
    url_re = re.compile(r"https?://[^\"'<>]+\.(?:iso|img|vhdx)[^\"'<>]*", re.IGNORECASE)
    deadline = time.time() + 180
    last_html = ""
    while time.time() < deadline:
        html = page.content()
        if html != last_html:
            last_html = html
        m = url_re.search(html)
        if m:
            url = m.group(0)
            print(f"[ok] URL capturada: {url}")
            return url
        page.wait_for_timeout(2000)

    dump_debug(page, debug_dir, "no_download_url")
    raise RuntimeError(
        "URL de download não apareceu após o clique. "
        f"Veja screenshots em {debug_dir}/."
    )


# --------------------------------------------------------------------------- #
# Download em si (com progresso)
# --------------------------------------------------------------------------- #


def download_iso(url: str, dest: Path) -> None:
    print(f"[*] Baixando ISO para {dest}…")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=60, allow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        with open(dest, "wb") as f, tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=dest.name,
        ) as bar:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
    print("[ok] Download concluído.")


def sha256_of(path: Path) -> str:
    print("[*] Calculando SHA-256…")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #


def build_context(p: Playwright, headless: bool, state_path: Path) -> BrowserContext:
    """Cria BrowserContext, carregando state salvo se existir."""
    browser: Browser = p.chromium.launch(headless=headless)
    if state_path.exists():
        ctx = browser.new_context(storage_state=str(state_path))
        print(f"[ok] storage_state carregado de {state_path}")
    else:
        ctx = browser.new_context()
    return ctx


def main() -> int:
    args = parse_args()

    if args.reset_state and args.state.exists():
        args.state.unlink()
        print(f"[ok] {args.state} apagado — novo login será necessário.")

    if args.headless and not args.state.exists():
        print(
            "[erro] --headless exige um storage_state existente.\n"
            "       Rode primeiro sem --headless pra fazer login uma vez."
        )
        return 2

    with sync_playwright() as p:
        # headless só é seguro se já temos state salvo
        ctx = build_context(p, headless=args.headless, state_path=args.state)
        page: Page = ctx.new_page()

        try:
            page.goto(INSIDER_URL, wait_until="domcontentloaded", timeout=60_000)

            if not is_logged_in(page):
                if args.headless:
                    dump_debug(page, args.debug_dir, "not_logged_in_headless")
                    print("[erro] Não autenticado. Rode sem --headless primeiro.")
                    return 3
                wait_for_login(page)

                # Salva estado pra próximas execuções
                ctx.storage_state(path=str(args.state))
                print(f"[ok] Estado salvo em {args.state} (próximas runs não precisam de login).")

            accept_terms_if_present(page)
            fill_form(page, args.channel, args.language, args.arch)

            iso_url = click_download_and_capture_url(page, args.debug_dir)

            # Re-salva estado (login + seleções podem mudar storage)
            ctx.storage_state(path=str(args.state))

            if args.url_only:
                print(f"\n[URL de download (válida por tempo limitado)]\n{iso_url}\n")
                return 0

            download_iso(iso_url, args.output)
            digest = sha256_of(args.output)
            print(f"[ok] SHA-256: {digest}")

            if args.sha256:
                if digest.lower() == args.sha256.lower():
                    print("[ok] Hash confere — ISO íntegra.")
                    return 0
                print(
                    f"[erro] Hash diverge!\n"
                    f"       esperado: {args.sha256}\n"
                    f"       obtido:   {digest}"
                )
                return 1

            print("\n[i] Confira o SHA-256 no blog oficial antes de usar a ISO.")
            return 0

        except Exception as exc:
            print(f"\n[erro] {exc}")
            dump_debug(page, args.debug_dir, "fatal")
            return 1
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
