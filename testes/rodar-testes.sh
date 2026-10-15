#!/data/data/com.termux/files/usr/bin/bash
# Bateria de testes adversariais do comando `pdf` (Markdown -> PDF via Docker).
# Cada caso valida: codigo de saida, mensagem e/ou o PDF produzido de verdade.
# Uso: bash rodar-testes.sh
set -uo pipefail
export PATH="$HOME/.hermes/bin:$PATH"
BASE="$HOME/testes-pdf"
cd "$BASE" || exit 1

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31mFALHA\033[0m %s\n' "$1"; }
titulo(){ printf '\n\033[36m== %s\033[0m\n' "$1"; }

# roda `pdf` e devolve "exit|saida"
rodar() { out=$("$@" 2>&1); echo "$?|$out"; }

espera_exit() { # nome, esperado, comando...
  local nome="$1" esp="$2"; shift 2
  local r; r=$(rodar "$@")
  local rc="${r%%|*}" saida="${r#*|}"
  if [ "$rc" = "$esp" ]; then ok "$nome (exit $rc)"; else bad "$nome — esperava exit $esp, veio $rc :: $saida"; fi
  ULTIMA_SAIDA="$saida"
}

espera_msg() { # nome, padrao (grep -i)
  if printf '%s' "$ULTIMA_SAIDA" | grep -qi -- "$2"; then ok "$1"; else bad "$1 — mensagem nao continha '$2' :: $ULTIMA_SAIDA"; fi
}

# helper: inspeciona PDF via container (pdfinfo/pdftotext)
pdfinfo_() { docker-direct run --rm --entrypoint pdfinfo -v "$BASE:/dados" pdf-tool:1 "/dados/$1" 2>&1; }
pdftxt_()  { docker-direct run --rm --entrypoint pdftotext -v "$BASE:/dados" pdf-tool:1 "/dados/$1" - 2>/dev/null; }

titulo "1. entradas invalidas"
espera_exit "sem argumentos" 2 pdf
espera_exit "--help" 2 pdf --help
espera_exit "arquivo inexistente" 2 pdf nao-existe.md
espera_msg  "mensagem clara para arquivo ausente" "nao encontrado"
mkdir -p uma-pasta
espera_exit "diretorio como entrada" 2 pdf uma-pasta
espera_exit "-o sem valor" 2 pdf aula.md -o
espera_msg  "-o sem valor explica" "exige um valor"
espera_exit "-o para pasta inexistente" 2 pdf aula.md -o /nao/existe/la.pdf
espera_msg  "destino invalido explica" "nao existe"
: > vazio.md
espera_exit "arquivo vazio" 2 pdf vazio.md
espera_msg  "vazio explica" "vazia"

titulo "2. caminho felizes"
rm -f aula.pdf
espera_exit "markdown normal" 0 pdf aula.md
espera_msg  "reporta o caminho do PDF" "aula.pdf"
[ -s aula.pdf ] && ok "PDF existe e nao esta vazio ($(stat -c%s aula.pdf) bytes)" || bad "PDF nao foi gerado"

espera_exit "stdin (-)" 0 bash -c 'cat aula.md | pdf - -o do-stdin.pdf'
[ -s do-stdin.pdf ] && ok "PDF a partir do stdin" || bad "stdin nao gerou PDF"

cp aula.md "material com espaços e ção.md"
rm -f "material com espaços e ção.pdf"
espera_exit "nome com espacos e acentos" 0 pdf "material com espaços e ção.md"
[ -s "material com espaços e ção.pdf" ] && ok "PDF com nome acentuado" || bad "PDF com nome acentuado nao saiu"

cp aula.md "it's \"aspas\".md"
espera_exit "nome com apostrofo e aspas" 0 pdf "it's \"aspas\".md"
[ -s "it's \"aspas\".pdf" ] && ok "PDF com aspas no nome" || bad "PDF com aspas no nome nao saiu"

mkdir -p sub
cp aula.md sub/aninhado.md
espera_exit "caminho relativo em subpasta" 0 pdf sub/aninhado.md
[ -s sub/aninhado.pdf ] && ok "PDF em subpasta" || bad "PDF em subpasta nao saiu"

espera_exit "-o em outro diretorio" 0 pdf aula.md -o sub/outro-nome.pdf
[ -s sub/outro-nome.pdf ] && ok "PDF com -o em outro dir" || bad "-o em outro dir falhou"

cp aula.md extensao.txt
espera_exit "entrada .txt" 0 pdf extensao.txt
[ -s extensao.pdf ] && ok "trocou a extensao para .pdf" || bad "extensao .txt nao virou .pdf"

titulo "3. conteudo"
espera_exit "opcoes de capa + numeracao" 0 pdf aula.md -o capa.pdf --titulo "Prova" --subtitulo "Unit 3" --autor "Prof." --numerar-paginas
info=$(pdfinfo_ capa.pdf)
echo "$info" | grep -q "Pages: *1" && ok "1 pagina" || bad "numero de paginas inesperado: $(echo "$info" | grep Pages)"
echo "$info" | grep -qi "A4" && ok "tamanho A4 por padrao" || bad "tamanho de pagina nao e A4"

espera_exit "--paper letter" 0 pdf aula.md -o letter.pdf --paper letter
pdfinfo_ letter.pdf | grep -qiE "612 x 792" && ok "paper letter aplicado" || bad "letter nao aplicado: $(pdfinfo_ letter.pdf | grep -i 'Page size')"

texto=$(pdftxt_ capa.pdf)
echo "$texto" | grep -q "present perfect" && ok "texto do markdown chegou no PDF" || bad "texto ausente no PDF"
echo "$texto" | grep -q "duração" && ok "acentuacao preservada" || bad "acentuacao perdida"
echo "$texto" | grep -q "🎧" && ok "emoji preservado" || bad "emoji perdido (fonte faltando?)"
echo "$texto" | grep -q "Prova" && ok "capa com titulo" || bad "capa sem titulo"

titulo "4. robustez"
# arquivo grande: 40 secoes -> varias paginas
{ for i in $(seq 1 40); do printf '## Secao %s\n\nTexto de teste da secao %s com acento ção.\n\n- item A\n- item B\n\n' "$i" "$i"; done; } > grande.md
espera_exit "markdown grande (40 secoes)" 0 pdf grande.md --numerar-paginas
pages=$(pdfinfo_ grande.pdf | awk '/^Pages/{print $2}')
[ "${pages:-0}" -ge 5 ] && ok "multiplas paginas ($pages)" || bad "esperava >=5 paginas, veio $pages"

espera_exit "entrada HTML pura" 0 bash -c 'printf "<h1>Oi</h1><p>HTML direto</p>" | pdf - --html -o html.pdf'
pdftxt_ html.pdf | grep -q "HTML direto" && ok "--html renderizou" || bad "--html nao renderizou"

espera_exit "opcao invalida do motor" 2 pdf aula.md --paper tabloide
espera_msg  "motor rejeita opcao invalida" "invalid choice"

m1=$(stat -c%Y aula.pdf); sleep 1
espera_exit "rodar de novo (sobrescreve)" 0 pdf aula.md
m2=$(stat -c%Y aula.pdf)
[ "$m2" -ge "$m1" ] && ok "sobrescreveu sem erro" || bad "segunda execucao nao atualizou"

espera_exit "margem grande (5cm)" 0 pdf aula.md -o margem.pdf --margem 5
[ -s margem.pdf ] && ok "margem custom aceita" || bad "margem custom falhou"

espera_exit "fonte inexistente (deve cair no fallback)" 0 pdf aula.md -o fonte.pdf --fonte "Fonte Que Nao Existe"
[ -s fonte.pdf ] && ok "fonte desconhecida nao quebra (fallback DejaVu)" || bad "fonte desconhecida quebrou"

titulo "5. daemon fora do ar"
docker daemon down >/dev/null 2>&1
rm -f sem-daemon.pdf
espera_exit "gera PDF com daemon parado" 0 pdf aula.md -o sem-daemon.pdf
[ -s sem-daemon.pdf ] && ok "funciona no modo direto" || bad "falhou sem daemon"
docker daemon up >/dev/null 2>&1

titulo "RESULTADO"
printf '  passaram: %s\n  falharam: %s\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && printf '  \033[32mTUDO OK\033[0m\n' || printf '  \033[31mTEM FALHA\033[0m\n'
rm -rf uma-pasta sub vazio.md grande.md extensao.txt 2>/dev/null
exit $((FAIL > 0))
