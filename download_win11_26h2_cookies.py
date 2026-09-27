#!/usr/bin/env python3
"""
download_win11_26h2.py
======================

Baixa a ISO do Windows 11 26H2 (build 26300.x) diretamente do
Windows Insider Program usando cookies de sessão exportados do browser.

Uso:
    # 1) Faça login em https://www.microsoft.com/en-us/software-download/windows-insider
    # 2) Exporte os cookies no formato Netscape (extensão "Get cookies.txt LOCALLY")
    #    para o arquivo cookies.txt
    # 3) Rode:
    python3 download_win11_26h2.py --cookies cookies.txt --output ./win11_26h2.iso

Aviso: este script existe porque a Microsoft ainda não expôs a 26H2 na
página pública de download. A página Insider exige conta inscrita no
programa + cookies válidos (geralmente ~15 min de vida útil).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm


INSIDER_PAGE = "https://www.microsoft.com/en-us/software-download/windows-insider"
EXPECTED_BUILD_RE = re.compile(r"Build\s*(\d{2,6}\.\d{2,6})", re.IGNORECASE)
ISO_LINK_RE = re.compile(
    r"https?://[^\"'<>]+\.(?:iso|img|vhdx)[^\"'<>]*",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Baixa a ISO do Windows 11 26H2 via Insider Program."
    )
    p.add_argument(
        "--cookies",
        type=Path,
        required=True,
        help="Caminho para o arquivo de cookies Netscape exportado do browser.",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("./Windows11_26H2.iso"),
        help="Caminho de saída para a ISO (padrão: ./Windows11_26H2.iso).",
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
        help="Idioma da ISO.",
    )
    p.add_argument(
        "--sha256",
        default=None,
        help="SHA-256 esperado (opcional). Se informado, valida após download.",
    )
    p.add_argument(
        "--no-download",
        action="store_true",
        help="Apenas resolve a URL de download sem baixar o arquivo.",
    )
    return p.parse_args()


def load_cookies(path: Path) -> requests.Session:
    if not path.exists():
        sys.exit(f"[erro] arquivo de cookies não encontrado: {path}")

    jar = MozillaCookieJar(str(path))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception as exc:
        sys.exit(f"[erro] falhei ao ler cookies Netscape: {exc}")

    session = requests.Session()
    session.cookies = jar
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def check_session(session: requests.Session) -> None:
    """Confere se os cookies ainda estão válidos."""
    print("[*] Validando sessão Microsoft…")
    r = session.get(INSIDER_PAGE, allow_redirects=True, timeout=30)
    if "Sign in" in r.text and "login.live.com" in r.text.lower():
        sys.exit(
            "[erro] Cookies expiraram ou conta não está inscrita no Insider.\n"
            "       Refaça login em " + INSIDER_PAGE + " e reexporte os cookies."
        )
    if r.status_code != 200:
        sys.exit(f"[erro] Resposta inesperada ({r.status_code}) da página Insider.")
    print("[ok] Sessão válida.")


def extract_iso_link(html: str) -> Optional[str]:
    """Procura a URL da ISO na página renderizada."""
    candidates = ISO_LINK_RE.findall(html)
    if not candidates:
        return None
    # A Microsoft geralmente serve via software-download.akamaized.net ou
    # download.microsoft.com — filtrar pelos hosts esperados.
    preferred = [
        u for u in candidates
        if any(host in u.lower() for host in (
            "software-download",
            "download.microsoft",
            "vlscppe.microsoft",
            "akamaized.net",
        ))
    ]
    return preferred[0] if preferred else candidates[0]


def fetch_iso_url(session: requests.Session, channel: str, language: str) -> tuple[str, str]:
    """Aciona o fluxo JavaScript manualmente (simplificado) para pegar a URL.

    A página usa controles webforms com __VIEWSTATE. Esta implementação
    faz fallback para raspagem direta da página renderizada.
    """
    print(f"[*] Buscando ISO no canal '{channel}', idioma '{language}'…")
    r = session.get(INSIDER_PAGE, timeout=60)
    r.raise_for_status()

    url = extract_iso_link(r.text)
    if not url:
        # Salva HTML para debug
        debug_path = Path("insider_page_debug.html")
        debug_path.write_text(r.text, encoding="utf-8", errors="ignore")
        sys.exit(
            f"[erro] Não achei link de ISO na página. HTML salvo em {debug_path}.\n"
            "       Pode ser que a Microsoft tenha mudado o layout ou que\n"
            "       o canal/idioma selecionado não tenha 26H2 ainda."
        )

    build_match = EXPECTED_BUILD_RE.search(r.text)
    build = build_match.group(1) if build_match else "desconhecido"
    print(f"[ok] Build detectado: {build}")
    print(f"[ok] URL da ISO: {url}")
    return url, build


def download_file(url: str, dest: Path, session: requests.Session) -> None:
    print(f"[*] Baixando para {dest}…")
    with session.get(url, stream=True, timeout=60, allow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        dest.parent.mkdir(parents=True, exist_ok=True)
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


def main() -> int:
    args = parse_args()
    session = load_cookies(args.cookies)
    check_session(session)

    iso_url, build = fetch_iso_url(args.channel, args.language)

    if args.no_download:
        print(f"[skip] --no-download setado. URL final: {iso_url}")
        return 0

    started = time.time()
    download_file(iso_url, args.output, session)
    elapsed = time.time() - started
    print(f"[*] Tempo total: {elapsed/60:.1f} min")

    actual = sha256_of(args.output)
    print(f"[ok] SHA-256: {actual}")

    if args.sha256:
        if actual.lower() == args.sha256.lower():
            print("[ok] Hash confere — ISO íntegra.")
            return 0
        else:
            print(
                f"[erro] Hash diverge!\n"
                f"       esperado: {args.sha256}\n"
                f"       obtido:   {actual}"
            )
            return 1

    print(
        "\n[i] Dica: confira o SHA-256 no blog oficial do Windows Insider\n"
        "    ou no site da Microsoft antes de usar a ISO."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
