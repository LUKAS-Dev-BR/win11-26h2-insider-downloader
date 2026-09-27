# win11-26h2-insider-downloader

Baixa a **ISO do Windows 11 26H2** (build 26300.x) direto do **Windows Insider Program** automatizando o browser com Playwright. **Sem extensão de cookie, sem etapas manuais repetitivas** — você só loga uma vez.

> ⚠️ **Status da 26H2 (set/2026):** ainda no canal **Release Preview**.
> A página pública `microsoft.com/software-download/windows11` só oferece a 25H2.
> Pra baixar a 26H2 é preciso ter conta Microsoft inscrita no Windows Insider.

---

## ✨ Como funciona

1. Abre o Chromium (headed na 1ª vez).
2. Vai na página do Insider. Se não tiver logado, **espera você logar manualmente** (inclusive com 2FA / Authenticator).
3. Salva o estado de autenticação em `storage_state.json` — nas próximas execuções, **não precisa logar de novo**.
4. Preenche canal / edição / idioma / arquitetura automaticamente.
5. Clica em **Download** e captura a URL gerada pela Microsoft.
6. Baixa a ISO com barra de progresso e (opcionalmente) valida o SHA-256.

---

## 📦 Instalação

```bash
git clone https://github.com/LUKAS-Dev-BR/win11-26h2-insider-downloader.git
cd win11-26h2-insider-downloader
pip install -r requirements.txt
playwright install chromium    # baixa ~150 MB do Chromium
```

> **Sem o `playwright install chromium`, o script não roda** — ele precisa do binário do browser.

---

## 🚀 Uso

### 1ª vez — login interativo (browser abre)

```bash
python3 download_win11_26h2.py
```

O browser vai abrir, ir pra página do Insider, e esperar você logar com sua conta Microsoft (incluindo 2FA). Depois ele preenche o formulário sozinho e baixa a ISO.

### 2ª vez em diante — totalmente automático

```bash
# Como já tem storage_state.json salvo, o login é pulado
python3 download_win11_26h2.py

# Ou em modo headless (sem janela) — ideal pra CI/scripts
python3 download_win11_26h2.py --headless
```

### Personalizando

```bash
# Idioma diferente
python3 download_win11_26h2.py --language "Portuguese (Brazil)"

# Canal Beta em vez de Release Preview
python3 download_win11_26h2.py --channel Beta

# Arquitetura ARM64
python3 download_win11_26h2.py --arch Arm64

# Pegar só a URL (sem baixar a ISO)
python3 download_win11_26h2.py --url-only

# Forçar novo login (apaga o storage_state salvo)
python3 download_win11_26h2.py --reset-state

# Validar SHA-256 depois do download
python3 download_win11_26h2.py --sha256 <hash_oficial>
```

---

## 📋 Opções

| Flag | Descrição | Padrão |
|---|---|---|
| `--channel` | `Release Preview`, `Beta` ou `Dev` | `Release Preview` |
| `--language` | Idioma da ISO | `English (United States)` |
| `--arch` | `x64` ou `Arm64` | `x64` |
| `--output` | Caminho de saída da ISO | `./Windows11_26H2.iso` |
| `--state` | Arquivo de storage_state (cookies + localStorage) | `./storage_state.json` |
| `--headless` | Roda sem janela (exige `--state` já existente) | `false` |
| `--url-only` | Só captura a URL de download, sem baixar | `false` |
| `--sha256` | Valida SHA-256 após download | (sem validação) |
| `--reset-state` | Apaga `--state` e força novo login | `false` |
| `--debug-dir` | Pasta pra screenshots quando algo dá errado | `./debug/` |

---

## 🔁 Script alternativo (cookies Netscape)

Se você preferir **não instalar o Playwright/Chromium**, tem um script alternativo baseado em cookies exportados do browser (extensão `Get cookies.txt LOCALLY`):

```bash
python3 download_win11_26h2_cookies.py --cookies cookies.txt
```

Útil pra:
- Ambientes CI sem browser
- Servidores remotos sem GUI
- Quem prefere não instalar 150 MB de Chromium

---

## 🛠️ Solução de problemas

**"Botão de Download não encontrado" / "URL não apareceu"**
→ A Microsoft muda o HTML da página com certa frequência. O script salva
`screenshots` e `HTML` em `./debug/` automaticamente. Abra uma issue
no repo com esses arquivos que eu ajusto os seletores.

**"Não autenticado" em modo `--headless`**
→ O `--headless` exige `--state` válido. Rode primeiro sem `--headless`
pra fazer o login interativo uma vez.

**2FA não completa**
→ O script espera até 5 minutos pra você terminar o 2FA no browser.
Se passar disso, ele aborta. Aumente editando `LOGIN_TIMEOUT_MS` no
script.

**Seletores de dropdown errados**
→ Se você ver "channel/language/architecture" mas o script não está
preenchendo, abra `debug/fatal.html` e veja qual é o `id`/`name` real
dos `<select>`. Daí abre uma issue ou ajusta direto em `fill_form()`.

---

## ⚠️ Avisos

1. **Termos da Microsoft:** este script só automatiza o que você faria
   manualmente. Leia os termos do Windows Insider Program.
2. **Não redistribua ISOs no GitHub.** Limite de 100 MB/arquivo e a
   licença da Microsoft proíbe hosting fora dos servidores oficiais.
3. **`storage_state.json` é uma credencial.** Ele contém cookies válidos
   da sua conta Microsoft. **Não commita, não compartilha.** O `.gitignore`
   deste projeto já o ignora.

---

## 📊 Build de referência

- **Windows 11 26H2**
- Build Insider RP (ago/2026): `26300.9278`
- Build Enterprise Evaluation (set/2026): `26300.9457`
- GA público: previsto pro final de 2026

---

## 📄 Licença

MIT — veja [LICENSE](LICENSE).
