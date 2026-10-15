#!/data/data/com.termux/files/usr/bin/bash
# Benchmark dos tres niveis de "headless" no celular: tempo e PICO DE RAM.
#
# A RAM e amostrada lendo /proc (soma de RSS dos processos que pertencem ao
# container em execucao), em paralelo com o comando — nao e estimativa.
#
# Uso: bash benchmark-headless.sh [url-estatica] [url-js]

set -uo pipefail
export PATH="$HOME/.hermes/bin:$PATH"
BASE="${1:-https://example.com}"
JS="${2:-https://react.dev}"
cd "$HOME" || exit 1

pico_ram() {   # $1 = pid a monitorar, $2 = arquivo de saida
    local pid="$1" arq="$2" pico=0
    while kill -0 "$pid" 2>/dev/null; do
        local soma=0 exe
        for p in /proc/[0-9]*; do
            exe=$(readlink "$p/exe" 2>/dev/null) || continue
            case "$exe" in
                *chrome*|*headless_shell*|*chromium*|*proot*)
                    local rss
                    rss=$(awk '/^VmRSS/{print $2}' "$p/status" 2>/dev/null)
                    [ -n "$rss" ] && soma=$((soma + rss)) ;;
            esac
        done
        [ "$soma" -gt "$pico" ] && pico=$soma
        sleep 0.4
    done
    echo "$pico" > "$arq"
}

medir() {      # medir "rotulo" comando...
    local rotulo="$1"; shift
    local TMPD="${TMPDIR:-$PREFIX/tmp}"
    local saida_arq="$TMPD/benc-out.$$" ram_arq="$TMPD/benc-ram.$$"
    : > "$saida_arq"; : > "$ram_arq"
    local ini fim rc pico
    ini=$(date +%s.%N)
    "$@" > "$saida_arq" 2>&1 &
    local pid=$!
    pico_ram "$pid" "$ram_arq" &
    local spid=$!
    wait "$pid"; rc=$?
    wait "$spid" 2>/dev/null
    fim=$(date +%s.%N)
    pico=$(cat "$ram_arq" 2>/dev/null || echo 0)
    printf '  %-30s %6.1fs  RAM pico ~%4s MB  exit=%s\n' \
        "$rotulo" "$(awk -v a="$ini" -v b="$fim" 'BEGIN{printf "%.1f", b-a}')" "$((pico / 1024))" "$rc"
    printf '      saida: %s chars | %s\n' "$(wc -c < "$saida_arq")" \
        "$(tr '\n' ' ' < "$saida_arq" | cut -c1-80)"
    rm -f "$saida_arq" "$ram_arq"
}

echo "ALVO 1 (pagina estatica): $BASE"
rm -f benc1.* benc2.* benc3.*
medir "nivel 1: webget --texto"      webget "$BASE" --texto -o benc1.txt
medir "nivel 2: webprint --dom"      webprint "$BASE" --dom -o benc2.html
cat > /tmp/benc3.py <<'PY'
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    pg = b.new_page()
    pg.goto(sys.argv[1], timeout=45000)
    print("titulo:", pg.title())
    b.close()
PY
cp /tmp/benc3.py "$HOME/benc3.py" 2>/dev/null
medir "nivel 3: webplay (Playwright)" webplay benc3.py "$BASE"

echo
echo "ALVO 2 (pagina que renderiza via JS): $JS"
medir "nivel 1: webget --texto"      webget "$JS" --texto -o benc4.txt
medir "nivel 2: webprint --dom"      webprint "$JS" --dom -o benc5.html

echo
echo "tamanhos de imagem em disco:"
for img in web:1 pdf-tool:1 navegador:1; do
    t=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null)
    [ -n "$t" ] && printf '  %-12s %s MB\n' "$img" "$((t / 1000000))"
done
rm -f benc1.txt benc2.html benc4.txt benc5.html benc3.py 2>/dev/null
