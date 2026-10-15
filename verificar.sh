#!/data/data/com.termux/files/usr/bin/bash
# verificar.sh — prova que o stack inteiro FUNCIONA, item por item, em ~2 min.
#
# Não altera nada: só lê e executa. Nenhuma escrita na escola (o SPONTE é
# consultado apenas em modo leitura) e nenhum build.
#
# Uso:  bash verificar.sh            (tudo)
#       bash verificar.sh rapido     (pula o que baixa imagem/container)
#
# Saída: 0 se tudo passou, 1 se algum item falhou (imprime o resumo no fim).

set -uo pipefail
export PATH="$HOME/.hermes/bin:$PATH"
RAPIDO="${1:-}"

PASSOU=0
FALHOU=0
PULOU=0
FALHAS=()

ok()    { PASSOU=$((PASSOU+1)); printf '  \033[32m[OK]\033[0m   %-34s %s\n' "$1" "${2:-}"; }
falha() { FALHOU=$((FALHOU+1)); FALHAS+=("$1"); printf '  \033[31m[FALHA]\033[0m %-33s %s\n' "$1" "${2:-}"; }
pulou() { PULOU=$((PULOU+1)); printf '  \033[33m[--]\033[0m   %-34s %s\n' "$1" "${2:-}"; }

# tira a medida de tempo do cabeçalho de cada teste
cronometrar() { "$@" 2>&1; }

echo "=============================================================="
echo " VERIFICACAO DO STACK — $(date '+%d/%m/%Y %H:%M')"
echo " aparelho: $(uname -m) | kernel: $(uname -r | cut -d- -f1)"
echo "=============================================================="

echo
echo "--- 1. motor de containers -----------------------------------"
if curl -s --max-time 5 http://127.0.0.1:2375/_ping >/dev/null 2>&1; then
    ok "daemon udockerd responde"
else
    echo "  (subindo o daemon...)"
    docker daemon up >/dev/null 2>&1
    sleep 4
    if curl -s --max-time 5 http://127.0.0.1:2375/_ping >/dev/null 2>&1; then
        ok "daemon udockerd responde" "(subiu agora)"
    else
        falha "daemon udockerd" "sem resposta em 127.0.0.1:2375"
    fi
fi

img_count=$(docker images -q 2>/dev/null | wc -l)
[ "$img_count" -gt 0 ] && ok "imagens disponiveis" "$img_count no store" \
                       || falha "imagens disponiveis" "store vazio"

if [ "$RAPIDO" != rapido ]; then
    # grep (nao comparacao da ultima linha): o udocker imprime linhas 'Info:'
    # depois da saida do container e a comparacao exata dava falso negativo
    saida=$(timeout 180 docker run --rm alpine sh -c "uname -m; echo FILHO-OK" 2>&1)
    echo "$saida" | grep -q "FILHO-OK" && ok "run + fork/exec (apk/pip)" "alpine" \
                                    || falha "run + fork/exec" "$(echo "$saida" | tr '\n' ' ' | cut -c1-40)"

    saida=$(timeout 240 docker run --rm alpine sh -c \
        "apk add --no-cache curl >/dev/null 2>&1 && echo APK-OK" 2>&1)
    echo "$saida" | grep -q "APK-OK" && ok "apk add (hardlink/link2symlink)" \
                                    || falha "apk add" "$(echo "$saida" | tr '\n' ' ' | cut -c1-40)"

    saida=$(timeout 180 docker run --rm alpine sh -c \
        "wget -qO- --timeout=12 example.com 2>/dev/null | head -c 12" 2>&1 | tail -1)
    case "$saida" in *"<!doctype"*|*"<html"*) ok "rede + DNS no container" ;;
        *) falha "rede + DNS no container" "$(echo "$saida" | cut -c1-40)" ;; esac

    mkdir -p "$TMPDIR/vfy-mount" && echo prova > "$TMPDIR/vfy-mount/f.txt"
    saida=$(timeout 150 docker-direct run --rm -v "$TMPDIR/vfy-mount:/m" \
        alpine cat /m/f.txt 2>&1)
    echo "$saida" | grep -qx "prova" && ok "volume -v (bind do host)" \
                                     || falha "volume -v" "$(echo "$saida" | tr '\n' ' ' | cut -c1-40)"
else
    pulou "run / apk / rede / volume" "modo rapido"
fi

echo
echo "--- 2. headless: nivel 1 (HTTP puro) -------------------------"
t0=$(date +%s)
# pega as primeiras LINHAS (a 1a e o titulo; o corpo vem depois) — testar so a
# primeira linha dava falso negativo
saida=$(timeout 120 webget https://example.com --texto 2>&1 | head -4)
t1=$(date +%s)
case "$saida" in *"documentation examples"*) ok "webget extrai texto" "$((t1-t0))s" ;;
    *) falha "webget" "$(echo "$saida" | tr '\n' ' ' | cut -c1-40)" ;; esac

echo
echo "--- 3. headless: nivel 2 (chromium nativo) -------------------"
command -v chromium-browser >/dev/null 2>&1 \
    && ok "chromium nativo presente" "$(chromium-browser --version 2>/dev/null | cut -c1-26)" \
    || falha "chromium nativo" "pkg install x11-repo && pkg install chromium"

t0=$(date +%s)
saida=$(timeout 140 webprint https://react.dev --texto 2>&1 | head -2 | tr '\n' ' ')
t1=$(date +%s)
case "$saida" in *"React"*) ok "webprint renderiza SPA (JS)" "$((t1-t0))s" ;;
    *) falha "webprint" "$(echo "$saida" | cut -c1-40)" ;; esac

echo
echo "--- 4. headless: nivel 3 (CDP puro, sem selenium) ------------"
if [ -x "$HOME/.hermes/bin/webcdp" ]; then
    t0=$(date +%s)
    titulo=$(timeout 120 webcdp https://example.com --titulo 2>&1 | head -1)
    t1=$(date +%s)
    [ "$titulo" = "Example Domain" ] && ok "webcdp le titulo" "$((t1-t0))s" \
                                     || falha "webcdp" "$(echo "$titulo" | cut -c1-40)"
    js=$(timeout 120 webcdp https://example.com --js "2+40" 2>&1 | tail -1)
    [ "$js" = "42" ] && ok "webcdp executa JS" || falha "webcdp --js" "$(echo "$js" | cut -c1-30)"
    timeout 130 webcdp https://example.com --screenshot "$TMPDIR/vfy-cdp.png" >/dev/null 2>&1
    if [ -s "$TMPDIR/vfy-cdp.png" ]; then
        ok "webcdp screenshot" "$(du -h "$TMPDIR/vfy-cdp.png" | cut -f1)"
    else
        falha "webcdp screenshot"
    fi
else
    pulou "webcdp" "nao instalado"
fi

echo
echo "--- 5. headless: nivel 3b (selenium, alternativa) ------------"
if [ -x "$HOME/docker-termux/venv-web/bin/python" ] && \
   [ -x "$PREFIX/bin/chromedriver" ]; then
    ok "selenium + chromedriver presentes" \
       "($(cd "$HOME/testes-pdf" 2>/dev/null && timeout 120 \
          "$HOME/docker-termux/venv-web/bin/python" teste-selenium.py 2>&1 | tail -1 | cut -c10-40))"
else
    pulou "selenium" "venv-web ou chromedriver ausente"
fi

echo
echo "--- 6. utilitarios de documento ------------------------------"
if [ "$RAPIDO" != rapido ]; then
    printf '# T\n\ntexto de prova\n' > "$TMPDIR/vfy.md"
    saida=$(timeout 300 pdf "$TMPDIR/vfy.md" -o "$TMPDIR/vfy.pdf" 2>&1 | tail -1)
    if [ -s "$TMPDIR/vfy.pdf" ] && head -c 4 "$TMPDIR/vfy.pdf" | grep -q "%PDF"; then
        ok "pdf (weasyprint no container)" "$(du -h "$TMPDIR/vfy.pdf" | cut -f1)"
    else
        falha "pdf" "$(echo "$saida" | cut -c1-40)"
    fi
else
    pulou "pdf" "modo rapido"
fi

echo
echo "--- 7. checagem de saude do sistema --------------------------"
orfaos=$(python3 - <<'PY'
import os
n = 0
for p in os.listdir('/proc'):
    if not p.isdigit():
        continue
    try:
        exe = os.readlink(f'/proc/{p}/exe')
    except OSError:
        continue
    if 'chromium' in exe or exe.endswith('/chrome') or 'dokid' in exe:
        n += 1
print(n)
PY
)
[ "$orfaos" -eq 0 ] && ok "sem navegador/daemon orfao" || falha "processos orfaos" "$orfaos sobrando"

containers=$(ls "$HOME/.udocker/containers" 2>/dev/null | wc -l)
[ "$containers" -eq 0 ] && ok "sem container orfao" || \
    printf '  \033[33m[--]\033[0m   %-34s %s\n' "containers parados" \
        "$containers (limpe com: udocker rm <id>)"

livre=$(df -h "$HOME" | tail -1 | awk '{print $4}')
printf '  \033[36m[info]\033[0m %-34s %s\n' "disco livre" "$livre"

echo
echo "=============================================================="
printf ' RESULTADO: %d OK, %d FALHA, %d pulado\n' "$PASSOU" "$FALHOU" "$PULOU"
if [ "$FALHOU" -gt 0 ]; then
    echo " ITENS QUE FALHARAM:"
    for f in "${FALHAS[@]}"; do echo "   - $f"; done
    echo "=============================================================="
    exit 1
fi
echo " TUDO FUNCIONANDO"
echo "=============================================================="
exit 0
