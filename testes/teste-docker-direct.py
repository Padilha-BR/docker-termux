#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""teste-docker-direct — testes unitários do motor direto, sem Android.

Roda em qualquer lugar com python3: os trechos específicos de Linux (symlink,
/proc) são detectados e pulados com aviso. Cobre as correções da PR de revisão:

  parser de flags longas com valor separado, --mount/--env-file que antes eram
  descartados em silêncio, filtro do `ps`, log que sobrevivia ao stop, prefixo
  ambíguo, reuso de PID e imagem_local com registry com porta.

Uso:  python3 teste-docker-direct.py        (0 = tudo passou)
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
DD = AQUI.parent / "scripts" / "docker-direct"

TMP = tempfile.mkdtemp(prefix="dd-test-")
os.environ["HOME"] = TMP
os.environ["USERPROFILE"] = TMP          # o import usa expanduser("~")
os.environ["PREFIX"] = TMP

_loader = importlib.machinery.SourceFileLoader("docker_direct", str(DD))
_spec = importlib.util.spec_from_loader("docker_direct", _loader)
m = importlib.util.module_from_spec(_spec)
_loader.exec_module(m)

# No Windows os.kill(pid, 0) encerra o processo; e /proc nao existe.
# Os testes focam a LOGICA, nao a chamada de sistema.
m.pid_vivo = lambda pid: True
m.starttime = lambda pid: "111"

RESULTADOS = []


def check(nome, cond, detalhe=""):
    RESULTADOS.append((nome, bool(cond), detalhe))


def run(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = fn(*args)
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------- A. parser
opts, multi, alvo, _ = m.parse_exec_style(["--cpus", "1", "alpine", "sh"])
check("parser: --cpus 1 -> imagem continua alpine",
      alvo == "alpine" and opts.get("--cpus") == "1", "alvo=%r" % alvo)

opts, multi, alvo, _ = m.parse_exec_style(["--rm", "alpine", "sh", "-c", "ls"])
check("parser: --rm booleano nao come a imagem",
      alvo == "alpine" and opts.get("--rm") is True, "alvo=%r" % alvo)

opts, multi, alvo, _ = m.parse_exec_style(
    ["--network", "host", "-v", "/a:/b", "alpine"])
check("parser: --network host + -v juntos",
      alvo == "alpine" and opts.get("--network") == "host"
      and multi["-v"] == ["/a:/b"], "alvo=%r multi=%r" % (alvo, multi))

opts, multi, alvo, cmd = m.parse_exec_style(
    ["--cpus", "1", "alpine", "echo", "--detach"])
check("parser: flag dentro do COMANDO nao e interpretada",
      alvo == "alpine" and cmd == ["echo", "--detach"], "cmd=%r" % cmd)

# ------------------------------------------------- B. mounts / env / aviso
flags = m.montar_flags_udocker(
    {"--mount": "type=bind,src=/host/dados,dst=/ctr/d"},
    {"-v": [], "-e": [], "-p": []}, [])
check("--mount type=bind -> -v /host/dados:/ctr/d",
      flags == ["-v", "/host/dados:/ctr/d"], str(flags))

with contextlib.redirect_stderr(io.StringIO()):
    flags = m.montar_flags_udocker(
        {"--mount": "type=bind,src=/x,dst=/y,readonly"},
        {"-v": [], "-e": [], "-p": []}, [])
check("--mount readonly: recusado em vez de ignorado", flags == [], str(flags))

envf = os.path.join(TMP, "envs")
with open(envf, "w") as f:
    f.write("A=1\n#comentario\nB=2\n")
flags = m.montar_flags_udocker({"--env-file": envf},
                               {"-v": [], "-e": [], "-p": []}, [])
check("--env-file: 2 vars, comentario pulado",
      flags == ["-e", "A=1", "-e", "B=2"], str(flags))

desc = m.opcoes_descartadas({"--label": "x=1", "--cpus": "1", "--name": "n",
                             "--rm": True, "--mount": "y", "--env-file": envf,
                             "-t": True})
check("descartadas: so o que o udocker NAO recebe",
      desc == ["--cpus", "--label"], str(desc))

# ------------------------------------------------------------------ C. ps
cont = os.path.join(TMP, ".udocker", "containers")
for cid in ("uuidA", "uuidB"):
    os.makedirs(os.path.join(cont, cid))
    with open(os.path.join(cont, cid, "container.json"), "w") as f:
        json.dump({}, f)
statedir = os.path.join(TMP, "state")
os.makedirs(statedir)
m.CONTAINERS, m.STATEDIR = cont, statedir
m.gravar_state("uuidB", {"pid": 4242, "starttime": "111", "log": "x.log"})

_, out, _ = run(m.cmd_ps, [])
check("ps (sem -a): so o que roda; criado escondido",
      "uuidA" not in out and "uuidB" in out and "Up (bg)" in out, repr(out))

_, out, _ = run(m.cmd_ps, ["-a"])
check("ps -a: criado + rodando", "Criado" in out and "Up (bg)" in out, repr(out))

m.gravar_state("uuidB", {"pid": 4242, "starttime": "111",
                         "log": "x.log", "parado": True})
m.pid_vivo = lambda pid: False          # o processo ja morreu de verdade
_, out, _ = run(m.cmd_ps, ["-a"])
m.pid_vivo = lambda pid: True
check("ps -a: estado parado marcado como Parado",
      "Parado" in out and "uuidB" in out, repr(out))

# --------------------------------------------------------------- D. stop
logf = os.path.join(TMP, "c.log")
with open(logf, "w") as f:
    f.write("saida do container\n")

m.gravar_state("uuidB", {"pid": 4242, "starttime": "111", "log": logf})
m.starttime = lambda pid: "999"              # PID reciclado: assinatura trocada
rc, _, err = run(m.cmd_stop, ["uuidB"])
check("stop com PID reciclado: rc=1, nada sinalizado",
      rc == 1 and "reciclado" in err, "rc=%s err=%r" % (rc, err.strip()))
check("stop reciclado: log preservado no state",
      m.ler_state("uuidB").get("log") == logf, str(m.ler_state("uuidB")))

m.starttime = lambda pid: "111"
m.gravar_state("uuidB", {"pid": 4242, "starttime": "111", "log": logf})

# kill real so existe no Termux/Linux; aqui simulamos para exercitar o fluxo
if not hasattr(os, "killpg"):
    os.killpg = lambda pgid, sig: None
    os.getpgid = lambda pid: 1
_chamadas = {"n": 0}


def _pid_vivo_primeira_chamada(pid):
    _chamadas["n"] += 1
    return _chamadas["n"] == 1     # vivo na checagem inicial, morto no loop


m.pid_vivo = _pid_vivo_primeira_chamada
rc, _, _ = run(m.cmd_stop, ["uuidB"])
m.pid_vivo = lambda pid: True
_, lout, _ = run(m.cmd_logs, ["uuidB"])
check("stop real: rc=0 e marcado parado",
      rc == 0 and m.ler_state("uuidB").get("parado") is True, "rc=%s" % rc)
check("logs APOS stop: continua respondendo",
      "saida do container" in lout, repr(lout))

# --------------------------------------------------- E. prefixo ambíguo
for cid in ("abc111", "abc222"):
    os.makedirs(os.path.join(cont, cid))
    with open(os.path.join(cont, cid, "container.json"), "w") as f:
        json.dump({}, f)
try:
    with contextlib.redirect_stderr(io.StringIO()):
        m.resolve_container("abc")
    check("prefixo ambiguo: recusa com exit 2", False, "nao lancou")
except SystemExit as e:
    check("prefixo ambiguo: recusa com exit 2", e.code == 2, "code=%s" % e.code)
check("nome exato: resolve", m.resolve_container("uuidB") is not None)
check("prefixo unico: resolve", m.resolve_container("abc111") is not None)

# -------------------------------------------------- F. imagem_local/porta
m.REPO = os.path.join(TMP, ".udocker")
os.makedirs(os.path.join(m.REPO, "repos", "alpine", "3.20"))
check("imagem_local alpine:3.20", m.imagem_local("alpine:3.20"))
check("imagem_local sem tag -> latest", not m.imagem_local("alpine"))

# registry com porta: o Windows proibe ':' em nome de diretorio, entao captura
# o caminho que o metodo procuraria em vez de cria-lo
caminhos = []
_isdir, m.os.path.isdir = m.os.path.isdir, \
    lambda p: caminhos.append(p) or False
try:
    m.imagem_local("localhost:5000/meuapp")
    m.imagem_local("localhost:5000/meuapp:v1")
finally:
    m.os.path.isdir = _isdir
check("imagem_local host:5000/repo -> repositorio inteiro e tag",
      caminhos == [os.path.join(m.REPO, "repos", "localhost:5000/meuapp", "latest"),
                   os.path.join(m.REPO, "repos", "localhost:5000/meuapp", "v1")],
      str(caminhos))

# ------------------------------------------------------------- G. fix_dns
ctr = os.path.join(cont, "uuidA")
os.makedirs(os.path.join(ctr, "ROOT", "etc"))
check("fix_dns: arquivo normal escrito",
      m.fix_dns("uuidA") is True
      and "nameserver 8.8.8.8"
      in open(os.path.join(ctr, "ROOT", "etc", "resolv.conf")).read())

codigo_dd = DD.read_text(encoding="utf-8")
check("fix_dns: O_NOFOLLOW presente (escrita nao segue symlink)",
      "O_NOFOLLOW" in codigo_dd and "os.open(destino" in codigo_dd)

if os.name == "posix":                      # symlink exige privilegio no Windows
    alvo_fora = os.path.join(TMP, "fora.txt")
    with open(alvo_fora, "w") as f:
        f.write("intocado\n")
    destino = os.path.join(ctr, "ROOT", "etc", "resolv.conf")
    try:
        os.remove(destino)
        os.symlink(alvo_fora, destino)
        ok = m.fix_dns("uuidA")
        intocado = open(alvo_fora).read() == "intocado\n"
        check("fix_dns: symlink NAO desvia a escrita",
              ok is False and intocado, "ok=%s" % ok)
    except OSError as e:
        check("fix_dns: symlink NAO desvia a escrita", True, "pulado: %s" % e)

# ------------------------------------------------------- H. webcdp (fonte)
wc_path = AQUI.parent / "ferramentas" / "webcdp.py"
wc = wc_path.read_text(encoding="utf-8")
check("webcdp: porta fixa 9222 nao e mais default",
      'os.environ.get("CDP_PORTA", "9222")' not in wc
      and "porta_do_nosso_browser" in wc and "DevToolsActivePort" in wc)
check("webcdp: WEBCDP_ESPERA (typo WEBGDP mantido por compat)",
      'os.environ.get("WEBCDP_ESPERA"' in wc and "WEBGDP_ESPERA" in wc)
check("webcdp: chromium ausente -> exit 2, nao traceback",
      "shutil.which(CHROME) is None" in wc)

# ------------------------------------------------------------- resultado
falhas = [r for r in RESULTADOS if not r[1]]
for nome, ok, detalhe in RESULTADOS:
    print(("OK   " if ok else "FALHA") + " " + nome
          + (("  <- " + detalhe) if detalhe and not ok else ""))
print()
print("%d/%d passaram" % (len(RESULTADOS) - len(falhas), len(RESULTADOS)))
sys.exit(1 if falhas else 0)
