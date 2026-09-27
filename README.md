# win11-26h2-insider-downloader

Script Python que automatiza o download da **ISO do Windows 11 26H2** diretamente do **Windows Insider Program**, usando cookies de sessão exportados do seu browser.

> ⚠️ **Status da 26H2 (set/2026):** ainda no canal **Release Preview**. A página pública
> `microsoft.com/software-download/windows11` só oferece a 25H2 no momento.
> Para baixar a 26H2 é preciso ter conta Microsoft inscrita no Windows Insider.

---

## Por que esse script existe?

A Microsoft ainda não publicou link público e direto para a 26H2 (build 26300.x).
A página Insider exige login e interações JavaScript para liberar a URL temporária de download.
Este script contorna a parte repetitiva pra você: faz login uma vez no browser,
exporta os cookies, e o script baixa a ISO direto pro seu disco.

---

## Pré-requisitos

- Python 3.9+
- Conta Microsoft inscrita no **Windows Insider Program**
  ([inscrição aqui](https://insider.windows.com/) — use o canal **Release Preview**)
- Extensão de browser para exportar cookies no formato Netscape:
  - Chrome/Edge: [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelgdcpojmnkncnljjggfgojpipmpi)
  - Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
- ~6 GB livres em disco (a ISO tem entre 5 e 6 GB)

---

## Instalação

```bash
git clone https://github.com/LUKAS-Dev-BR/win11-26h2-insider-downloader.git
cd win11-26h2-insider-downloader
pip install -r requirements.txt
```

---

## Como usar

### 1. Exporte os cookies

1. Abra o Chrome/Firefox e faça login em
   <https://www.microsoft.com/en-us/software-download/windows-insider>
2. Clique na extensão de cookies e exporte **apenas os cookies do domínio `microsoft.com`**
   em formato **Netscape**.
3. Salve como `cookies.txt` na raiz deste repositório.

> ⚠️ **Os cookies contêm tokens de sessão. Não commite `cookies.txt`.**
> O `.gitignore` deste projeto já ignora o arquivo.

### 2. Rode o script

```bash
# Baixa a ISO no idioma/encanamento padrão
python3 download_win11_26h2.py --cookies cookies.txt

# Especificar arquivo de saída e idioma
python3 download_win11_26h2.py \
  --cookies cookies.txt \
  --output ./Win11_26H2_brasil.iso \
  --language "Portuguese (Brazil)"

# Conferir a URL sem baixar (teste rápido)
python3 download_win11_26h2.py --cookies cookies.txt --no-download

# Validar SHA-256 após o download
python3 download_win11_26h2.py \
  --cookies cookies.txt \
  --sha256 <hash_oficial_publicado_pela_microsoft>
```

---

## Opções

| Flag | Descrição | Padrão |
|---|---|---|
| `--cookies` | Caminho do arquivo de cookies Netscape | (obrigatório) |
| `--output` | Caminho de saída da ISO | `./Windows11_26H2.iso` |
| `--channel` | `Release Preview`, `Beta` ou `Dev` | `Release Preview` |
| `--language` | Idioma da ISO | `English (United States)` |
| `--sha256` | Hash esperado para validação | (sem validação) |
| `--no-download` | Apenas resolve a URL, não baixa | `false` |

---

## Solução de problemas

**"Cookies expiraram ou conta não está inscrita no Insider"**
→ Os cookies da Microsoft expiram em ~15 min. Refaça login e reexporte.

**"Não achei link de ISO na página"**
→ A Microsoft muda o HTML com frequência. Abra `insider_page_debug.html` e abra
uma issue com o trecho relevante. Pode ser que o canal/idioma ainda não
tenha 26H2.

**Download lento / interrompe no meio**
→ Os links de download do Insider expiram. Se cair, reexecute o script;
ele pega a URL de novo do zero.

---

## Avisos importantes

1. **Termos de uso da Microsoft:** este script apenas automatiza uma operação
   que você faria manualmente no browser. Leia os termos do Windows Insider
   Program antes de redistribuir a ISO (recomendamos **não** redistribuir —
   a licença da Microsoft proíbe).
2. **Não redistribua ISOs no GitHub.** O limite por arquivo do GitHub é
   100 MB e a licença da Microsoft veta a hospedagem dos arquivos fora dos
   servidores oficiais.
3. **Cookies são credenciais.** Trate `cookies.txt` como se fosse senha:
   não compartilhe, não commite, apague depois de usar.

---

## Build atual (referência)

- Versão: **Windows 11 26H2**
- Build Insider (RP, ago/2026): **26300.9278**
- Build Enterprise Evaluation (set/2026): **26300.9457**
- Disponibilidade geral (GA): prevista para o final de 2026

Quando sair o GA, este script pode ser substituído por um simples
`curl` direto na página pública de download — a Microsoft historicamente
publica um link estático nessa hora.

---

## Licença

MIT — veja [LICENSE](LICENSE).
