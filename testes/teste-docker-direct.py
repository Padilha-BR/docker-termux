#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""teste-docker-direct — testes unitários do motor direto, sem Android.

Roda em qualquer lugar com python3: os trechos específicos de Linux (symlink,
/proc) são detectados e pulados com aviso. Cobre as correções das revisões:

  parser de flags (tabela com/sem valor, --k=v, clusters curtos), --mount com
  source/target, :ro/readonly avisados, --env-file, filtro do `ps`, log que
  sobrevivia ao stop, prefixo ambíguo, reuso de PID, imagem_local com registry
  com porta, --name já existente, --rm garantido em Ctrl-C/SIGTERM, `-d --rm`
  removido no stop, exec/logs/stop/rm com flags, rm que não apaga container
  vivo, --platform divergente, id do create só do stdout, fix_dns contra
  symlink, state atômico, nome de log saneado e DNS configurável.

Nada aqui sinaliza processo de verdade nem chama o udocker: kill, udocker e
subprocess são SEMPRE substituídos por gravadores (o teste antigo chamava
os.killpg(os.getpgid(4242)) real no Linux e podia matar um processo do CI).

Uso:  python3 teste-docker-direct.py        (0 = tudo passou)
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
DD = AQUI.parent / "scripts" / "docker-direct"

TMP = tempfile.mkdtemp(prefix="dd-test-")
os.environ["HOME"] = TMP
os.environ["USERPROFILE"] = TMP          # o import usa expanduser("~")
os.environ["PREFIX"] = TMP
os.environ.pop("DOCKER_TERMUX_HOME", None)
os.environ.pop("DOCKER_TERMUX_DNS", None)
os.environ.pop("UDOCKER_VERSAO", None)

_loader = importlib.machinery.SourceFileLoader("docker_direct", str(DD))
_spec = importlib.util.spec_from_loader("docker_direct", _loader)
m = importlib.util.module_from_spec(_spec)
_loader.exec_module(m)

# No Windows os.kill(pid, 0) encerra o processo; e /proc nao existe.
# Os testes focam a LOGICA, nao a chamada de sistema.
m.pid_vivo = lambda pid: True
m.starttime = lambda pid: "111"

# Gravadores SEMPRE ligados, em qualquer sistema: nenhum sinal real, nenhum
# udocker real.
SINAIS = []
m.sinalizar = lambda pid, sinal: SINAIS.append((pid, sinal))
UDOCKER = []


def _udocker_falso(args, capturar=False, silencioso=False):
    UDOCKER.append(list(args))
    return 0


m.udocker = _udocker_falso
m.time.sleep = lambda s: None            # encerrar() nao precisa esperar aqui

RESULTADOS = []


def check(nome, cond, detalhe=""):
    RESULTADOS.append((nome, bool(cond), detalhe))


def run(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = fn(*args)
    return rc, out.getvalue(), err.getvalue()


def sai_com(fn, *args):
    """Codigo do sys.exit que fn levanta (None se nao levantou)."""
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            fn(*args)
    except SystemExit as e:
        return e.code
    return None


def novo_container(cid, base=None):
    os.makedirs(os.path.join(base or cont, cid), exist_ok=True)
    with open(os.path.join(base or cont, cid, "container.json"), "w") as f:
        json.dump({}, f)


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

# D-M1: --k=v de flag repetivel ia para opts e sumia
opts, multi, alvo, _ = m.parse_exec_style(
    ["--volume=/a:/b", "--env=X=1", "--publish=8080:80",
     "--mount=type=bind,source=/c,target=/d", "alpine"])
check("parser: --volume=/--env=/--publish=/--mount= chegam a multi",
      alvo == "alpine" and multi["-v"] == ["/a:/b"] and multi["-e"] == ["X=1"]
      and multi["-p"] == ["8080:80"]
      and multi["--mount"] == ["type=bind,source=/c,target=/d"]
      and not any(k in opts for k in ("--volume", "--env", "--publish", "--mount")),
      "opts=%r multi=%r" % (opts, multi))

# D-M14: heuristica antiga transformava estes em booleanos ou comia a imagem
opts, multi, alvo, _ = m.parse_exec_style(["-m", "512m", "alpine"])
check("parser: -m 512m e valor (antes 512m virava a imagem)",
      alvo == "alpine" and opts.get("-m") == "512m", "alvo=%r" % alvo)
opts, multi, alvo, _ = m.parse_exec_style(["-h", "maquina", "-c", "2", "alpine"])
check("parser: -h/-c levam valor",
      alvo == "alpine" and opts.get("-h") == "maquina" and opts.get("-c") == "2",
      "alvo=%r opts=%r" % (alvo, opts))
opts, multi, alvo, _ = m.parse_exec_style(["--rm=true", "--detach=false", "alpine"])
check("parser: --rm=true / --detach=false nao comem a imagem",
      alvo == "alpine" and opts.get("--rm") is True and opts.get("-d") is False,
      "alvo=%r opts=%r" % (alvo, opts))
opts, multi, alvo, _ = m.parse_exec_style(["--publish-all", "alpine"])
check("parser: --publish-all e booleano",
      alvo == "alpine" and opts.get("--publish-all") is True, "alvo=%r" % alvo)
opts, multi, alvo, _ = m.parse_exec_style(["-eX=1", "-itv", "/a:/b", "alpine"])
check("parser: -eX=1 e -itv /a:/b (cluster que termina em letra com valor)",
      alvo == "alpine" and multi["-e"] == ["X=1"] and multi["-v"] == ["/a:/b"]
      and opts.get("-i") is True and opts.get("-t") is True,
      "opts=%r multi=%r" % (opts, multi))
opts, multi, alvo, _ = m.parse_exec_style(["-it", "-e", "A=1", "--tty", "alpine"])
check("parser: -it pega i e t (sem a.index pegar a 1a letra repetida)",
      opts.get("-i") is True and opts.get("-t") is True and multi["-e"] == ["A=1"],
      "opts=%r" % opts)
check("parser: flag longa desconhecida -> exit 2 (nao adivinha valor)",
      sai_com(m.parse_exec_style, ["--naoexiste", "alpine"]) == 2)
check("parser: letra curta desconhecida -> exit 2",
      sai_com(m.parse_exec_style, ["-k", "alpine"]) == 2)
check("parser: flag com valor no fim -> exit 2",
      sai_com(m.parse_exec_style, ["alpine", "-v"]) is None
      and sai_com(m.parse_exec_style, ["-v"]) == 2)

# ------------------------------------------------- B. mounts / env / aviso
VAZIO = {"-v": [], "-e": [], "-p": [], "--mount": []}
flags = m.montar_flags_udocker(
    {}, dict(VAZIO, **{"--mount": ["type=bind,src=/host/dados,dst=/ctr/d"]}), [])
check("--mount type=bind,src,dst -> -v /host/dados:/ctr/d",
      flags == ["-v", "/host/dados:/ctr/d"], str(flags))

flags = m.montar_flags_udocker(
    {}, dict(VAZIO, **{"--mount": ["type=bind,source=/h,target=/c",
                                   "type=bind,source=/h2,destination=/c2"]}), [])
check("D-M2: --mount source=/target= e destination= (sintaxe mais comum)",
      flags == ["-v", "/h:/c", "-v", "/h2:/c2"], str(flags))

rc, _, err = run(m.montar_mount, "type=bind,source=/x,target=/y,readonly")
check("--mount readonly: monta com aviso alto (ro nao e garantido)",
      rc == (("/x", "/y"), None) and "readonly" in err and "ESCRITA" in err,
      "rc=%r err=%r" % (rc, err))
par, erro = m.montar_mount("type=bind,source=/x")
check("--mount sem target -> erro", par is None and "target" in erro, str(erro))
par, erro = m.montar_mount("type=volume,source=v,target=/y")
check("--mount type=volume -> erro", par is None and "type=volume" in erro, str(erro))

rc, _, err = run(m.limpar_volume, "/a:/b:ro")
check("D-M3: -v /a:/b:ro -> /a:/b com aviso (antes criava o arquivo-lixo b:ro)",
      rc == "/a:/b" and "ro nao e garantido" in err, "rc=%r err=%r" % (rc, err))
with contextlib.redirect_stderr(io.StringIO()):
    check("-v /a:/b:rw,z -> /a:/b", m.limpar_volume("/a:/b:rw,z") == "/a:/b")
check("-v /a:/b fica igual", m.limpar_volume("/a:/b") == "/a:/b")
with contextlib.redirect_stderr(io.StringIO()):
    flags = m.montar_flags_udocker({}, dict(VAZIO, **{"-v": ["/a:/b:ro"]}), [])
check("montar_flags: -v com :ro chega limpo ao udocker",
      flags == ["-v", "/a:/b"], str(flags))

envf = os.path.join(TMP, "envs")
with open(envf, "w") as f:
    f.write("A=1\n#comentario\nB=2\n")
flags = m.montar_flags_udocker({"--env-file": envf}, VAZIO, [])
check("--env-file: 2 vars, comentario pulado",
      flags == ["-e", "A=1", "-e", "B=2"], str(flags))

flags = m.montar_flags_udocker({"-i": True, "-t": True}, VAZIO, [])
check("--interactive/--tty canonicos viram -i -t", flags == ["-i", "-t"], str(flags))

desc = m.opcoes_descartadas({"--label": "x=1", "--cpus": "1", "--name": "n",
                             "--rm": True, "--mount": "y", "--env-file": envf,
                             "-t": True})
check("descartadas: so o que o udocker NAO recebe",
      desc == ["--cpus", "--label"], str(desc))

# ------------------------------------------------------------------ C. ps
cont = os.path.join(TMP, ".udocker", "containers")
for cid in ("uuidA", "uuidB"):
    novo_container(cid)
statedir = os.path.join(TMP, "state")
os.makedirs(statedir)
m.CONTAINERS, m.STATEDIR = cont, statedir
m.LOGDIR = os.path.join(TMP, "logs")
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
with open(logf, "wb") as f:              # binario: no Windows "w" grava \r\n
    f.write(b"linha 1\nlinha 2\nsaida do container\n")

m.gravar_state("uuidB", {"pid": 4242, "starttime": "111", "log": logf})
m.starttime = lambda pid: "999"              # PID reciclado: assinatura trocada
SINAIS.clear()
rc, _, err = run(m.cmd_stop, ["uuidB"])
check("stop com PID reciclado: rc=1, nada sinalizado",
      rc == 1 and "reciclado" in err and SINAIS == [],
      "rc=%s err=%r sinais=%r" % (rc, err.strip(), SINAIS))
check("stop reciclado: log preservado no state",
      m.ler_state("uuidB").get("log") == logf, str(m.ler_state("uuidB")))

m.starttime = lambda pid: "111"
m.gravar_state("uuidB", {"pid": 4242, "starttime": "111", "log": logf})
_chamadas = {"n": 0}


def _pid_vivo_primeira_chamada(pid):
    _chamadas["n"] += 1
    return _chamadas["n"] == 1     # vivo na checagem inicial, morto no loop


m.pid_vivo = _pid_vivo_primeira_chamada
SINAIS.clear()
rc, _, _ = run(m.cmd_stop, ["-t", "1", "uuidB"])
m.pid_vivo = lambda pid: True
_, lout, _ = run(m.cmd_logs, ["uuidB"])
check("stop -t 1: rc=0, SIGTERM no pid gravado e marcado parado",
      rc == 0 and SINAIS == [(4242, signal.SIGTERM)]
      and m.ler_state("uuidB").get("parado") is True,
      "rc=%s sinais=%r" % (rc, SINAIS))
check("logs APOS stop: continua respondendo",
      "saida do container" in lout, repr(lout))
_, lout, _ = run(m.cmd_logs, ["-n", "1", "uuidB"])
check("D-M6: logs -n 1 (antes: 'sem log para -n')",
      lout == "saida do container\n", repr(lout))
_, lout, _ = run(m.cmd_logs, ["--tail=2", "uuidB"])
check("logs --tail=2", lout == "linha 2\nsaida do container\n", repr(lout))
check("stop sem container -> exit 2", run(m.cmd_stop, ["-t", "1"])[0] == 2)

# D-M4: run -d --rm -> removido no stop
novo_container("uuidR")
m.gravar_state("uuidR", {"pid": 777, "starttime": "111", "log": logf, "rm": True})
_chamadas["n"] = 0
m.pid_vivo = _pid_vivo_primeira_chamada
UDOCKER.clear()
rc, _, _ = run(m.cmd_stop, ["uuidR"])
m.pid_vivo = lambda pid: True
check("D-M4: stop de `run -d --rm` remove o container e o state",
      rc == 0 and ["rm", "uuidR"] in UDOCKER
      and not os.path.exists(m.state_path("uuidR")), "rc=%s ud=%r" % (rc, UDOCKER))

m.gravar_state("uuidR", {"pid": 778, "starttime": "111", "rm": True})
m.pid_vivo = lambda pid: False
UDOCKER.clear()
run(m.cmd_ps, ["-a"])
m.pid_vivo = lambda pid: True
check("`-d --rm` que saiu sozinho: o ps remove (o docker ja teria removido)",
      ["rm", "uuidR"] in UDOCKER and not os.path.exists(m.state_path("uuidR")),
      str(UDOCKER))

# --------------------------------------------------- E. prefixo ambíguo
for cid in ("abc111", "abc222"):
    novo_container(cid)
check("prefixo ambiguo: recusa com exit 2", sai_com(m.resolve_container, "abc") == 2)
check("nome exato: resolve", m.resolve_container("uuidB") is not None)
check("prefixo unico: resolve", m.resolve_container("abc111") is not None)
check("prefixo=False: so nome exato",
      m.resolve_container("abc1", prefixo=False) is None
      and m.resolve_container("abc111", prefixo=False) is not None)
check("resolve_container recusa ../ e /",
      m.resolve_container("../x") is None and m.resolve_container("..") is None)

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

# D-M8: --platform divergente da tag local -> puxa de novo
tagdir = os.path.join(m.REPO, "repos", "alpine", "3.20")
with open(os.path.join(tagdir, "manifest"), "w") as f:
    json.dump({"layers": [], "config": {"digest": "sha256_cfg"}}, f)
with open(os.path.join(tagdir, "sha256_cfg"), "w") as f:
    json.dump({"architecture": "arm64", "os": "linux"}, f)
check("arquitetura_imagem le o config do manifest",
      m.arquitetura_imagem("alpine:3.20") == "arm64")
UDOCKER.clear()
rc, _, err = run(m.garantir_imagem, "alpine:3.20", "linux/amd64")
check("D-M8: --platform=linux/amd64 com tag local arm64 -> pull de novo + aviso",
      rc is True and ["pull", "--platform=linux/amd64", "alpine:3.20"] in UDOCKER
      and "arm64" in err, "ud=%r err=%r" % (UDOCKER, err))
UDOCKER.clear()
rc, _, _ = run(m.garantir_imagem, "alpine:3.20", "linux/arm64/v8")
check("--platform igual a tag local -> nao puxa", rc is True and UDOCKER == [],
      str(UDOCKER))

# ------------------------------------------------------- G. criar_container
_run_real = m.subprocess.run
try:
    novo_container("uuidN")
    m.subprocess.run = lambda *a, **k: subprocess.CompletedProcess(
        a[0], 0, stdout="uuidN\n", stderr="Warning: algo no stderr\n")
    cid = m.criar_container("alpine")
    m.subprocess.run = lambda *a, **k: subprocess.CompletedProcess(
        a[0], 0, stdout="Warning: so aviso\n", stderr="")
    with contextlib.redirect_stderr(io.StringIO()):
        cid2 = m.criar_container("alpine")
finally:
    m.subprocess.run = _run_real
check("D-M15: id vem so do stdout (aviso no stderr nao vira id)", cid == "uuidN",
      repr(cid))
check("D-M15: 'id' que nao existe como container -> erro", cid2 is None, repr(cid2))

# ------------------------------------------------------------ H. run
novo_container("dev")
UDOCKER.clear()
rc, _, err = run(m.cmd_run, ["--rm", "--name", "dev", "alpine", "true"])
check("D-M5: --name ja existente -> erro 125, nada criado/apagado",
      rc == 125 and "em uso" in err and UDOCKER == [], "rc=%s ud=%r" % (rc, UDOCKER))
rc, _, err = run(m.cmd_run, ["--name=../x", "alpine"])
check("--name=../x recusado (nome de log/state nao escapa)", rc == 125, "rc=%s" % rc)
check("log_path/state_path ficam na pasta mesmo com '../'",
      os.path.dirname(m.log_path("../x")) == m.LOGDIR
      and os.path.dirname(m.state_path("../..")) == m.STATEDIR)

novo_container("python-web")
_garantir = m.garantir_imagem
m.garantir_imagem = lambda img, plat=None: False
rc, _, err = run(m.cmd_run, ["python", "true"])
m.garantir_imagem = _garantir
check("run python NAO reusa o container python-web por prefixo",
      rc == 1 and "ja existe" not in err, "rc=%s err=%r" % (rc, err))

# --rm garantido em Ctrl-C / SIGTERM / excecao
class _ProcFalso:
    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.sinais = []

    def wait(self, timeout=None):
        passo = self.roteiro.pop(0)
        if callable(passo):
            return passo()
        if isinstance(passo, BaseException):
            raise passo
        return passo

    def send_signal(self, s):
        self.sinais.append(s)

    def kill(self):
        self.sinais.append("kill")


_popen_real = m.subprocess.Popen
_sigterm_antes = signal.getsignal(signal.SIGTERM)


def rodar_com(proc):
    limpou = []
    m.subprocess.Popen = lambda *a, **k: proc
    try:
        try:
            rc = m.rodar_primeiro_plano(["run", "x"], lambda: limpou.append(1))
        except RuntimeError:
            rc = "excecao"
    finally:
        m.subprocess.Popen = _popen_real
    return rc, limpou


rc, limpou = rodar_com(_ProcFalso([KeyboardInterrupt(), -2]))
check("D-M4: Ctrl-C -> --rm roda e rc=130", rc == 130 and limpou == [1],
      "rc=%r limpou=%r" % (rc, limpou))


def _sigterm_no_meio():
    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
    return -signal.SIGTERM


p = _ProcFalso([_sigterm_no_meio])
rc, limpou = rodar_com(p)
check("D-M4: SIGTERM e repassado ao udocker, --rm roda, rc=143",
      rc == 128 + signal.SIGTERM and limpou == [1] and p.sinais == [signal.SIGTERM],
      "rc=%r limpou=%r sinais=%r" % (rc, limpou, p.sinais))
check("handler de SIGTERM restaurado depois",
      signal.getsignal(signal.SIGTERM) == _sigterm_antes)
rc, limpou = rodar_com(_ProcFalso([RuntimeError("boom")]))
check("D-M4: excecao inesperada -> --rm roda mesmo assim",
      rc == "excecao" and limpou == [1], "rc=%r limpou=%r" % (rc, limpou))
rc, limpou = rodar_com(_ProcFalso([3]))
check("saida normal propaga o codigo do container", rc == 3 and limpou == [1])

# ---------------------------------------------------------- I. exec / rm
UDOCKER.clear()
rc, _, err = run(m.cmd_exec, ["-it", "-e", "A=1", "-w", "/srv", "uuidA", "sh"])
check("D-M6: exec -it -e -w (antes: 'container nao encontrado: -it')",
      rc == 0 and UDOCKER and UDOCKER[-1][0] == "run"
      and UDOCKER[-1][-2:] == ["uuidA", "sh"]
      and "-i" in UDOCKER[-1] and "-t" in UDOCKER[-1]
      and ["-e", "A=1"] == UDOCKER[-1][2:4] and "/srv" in UDOCKER[-1],
      "rc=%s ud=%r err=%r" % (rc, UDOCKER, err))
check("exec -d recusado no modo direto", run(m.cmd_exec, ["-d", "uuidA", "sh"])[0] == 2)

novo_container("vivo1")
m.gravar_state("vivo1", {"pid": 5150, "starttime": "111", "log": logf})
UDOCKER.clear()
rc, _, err = run(m.cmd_rm, ["vivo1"])
check("D-M7: rm de container rodando sem -f -> recusa, nada apagado",
      rc == 1 and UDOCKER == [] and "rodando" in err, "rc=%s ud=%r" % (rc, UDOCKER))
SINAIS.clear()
_chamadas["n"] = 0
m.pid_vivo = lambda pid: _chamadas.__setitem__("n", _chamadas["n"] + 1) or _chamadas["n"] <= 2
m.gravar_state("uuidA", {"log": None, "parado": True})
logv = os.path.join(TMP, "vivo1.log")
open(logv, "w").close()
m.gravar_state("vivo1", {"pid": 5150, "starttime": "111", "log": logv})
rc, _, err = run(m.cmd_rm, ["-f", "vivo1", "uuidA"])
m.pid_vivo = lambda pid: True
check("D-M7: rm -f mata (SIGKILL) e remove; state/log de TODOS os argumentos",
      rc == 0 and ["rm", "vivo1"] in UDOCKER and ["rm", "uuidA"] in UDOCKER
      and SINAIS and SINAIS[0][0] == 5150
      and not os.path.exists(m.state_path("vivo1"))
      and not os.path.exists(m.state_path("uuidA")) and not os.path.exists(logv),
      "rc=%s ud=%r sinais=%r err=%r" % (rc, UDOCKER, SINAIS, err))
check("rm sem argumento -> exit 2", run(m.cmd_rm, ["-f"])[0] == 2)

# ------------------------------------------------------------- J. fix_dns
ctr = os.path.join(cont, "uuidA")
os.makedirs(os.path.join(ctr, "ROOT", "etc"), exist_ok=True)
check("fix_dns: arquivo normal escrito",
      m.fix_dns("uuidA") is True
      and "nameserver 8.8.8.8"
      in open(os.path.join(ctr, "ROOT", "etc", "resolv.conf")).read())

codigo_dd = DD.read_text(encoding="utf-8")
check("fix_dns: O_NOFOLLOW presente (escrita nao segue symlink)",
      "O_NOFOLLOW" in codigo_dd and "os.open(destino" in codigo_dd)
check("fix_dns: realpath + commonpath no ROOT/etc",
      "commonpath" in codigo_dd and 'os.path.join(raiz, "etc")' in codigo_dd)

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
        check("D-M12: resolv.conf symlink -> link trocado por arquivo, alvo intocado",
              ok is True and intocado and not os.path.islink(destino)
              and "nameserver" in open(destino).read(), "ok=%s" % ok)

        novo_container("uuidE")
        fora = os.path.join(TMP, "etc-do-host")
        os.makedirs(fora)
        os.makedirs(os.path.join(cont, "uuidE", "ROOT"))
        os.symlink(fora, os.path.join(cont, "uuidE", "ROOT", "etc"))
        with contextlib.redirect_stderr(io.StringIO()):
            ok = m.fix_dns("uuidE")
        check("D-M12: ROOT/etc symlink para fora do rootfs -> recusa",
              ok is False and os.listdir(fora) == [], "ok=%s %r" % (ok, os.listdir(fora)))
    except OSError as e:
        check("fix_dns: symlink (posix)", True, "pulado: %s" % e)
else:
    print("aviso: testes de symlink do fix_dns pulados (nao-posix)")

# --------------------------------------------------- K. state / dns / versao
m.gravar_state("atom", {"a": 1})
check("gravar_state atomico: sem .tmp sobrando, conteudo integro",
      m.ler_state("atom") == {"a": 1}
      and not [f for f in os.listdir(statedir) if f.endswith(".tmp")])

with contextlib.redirect_stderr(io.StringIO()):
    dns = m.dns_configurado("1.1.1.1, lixo\nnameserver 9.9.9.9 2001:4860:4860::8888")
check("DOCKER_TERMUX_DNS: so IP valido entra",
      dns == ["1.1.1.1", "9.9.9.9", "2001:4860:4860::8888"], str(dns))
check("DOCKER_TERMUX_DNS vazio -> padrao 8.8.8.8/8.8.4.4",
      m.dns_configurado("") == ["8.8.8.8", "8.8.4.4"])

os.environ["UDOCKER_VERSAO"] = "1.3.99"
v_env = m.versao_udocker()
del os.environ["UDOCKER_VERSAO"]
os.makedirs(m.BASE, exist_ok=True)
with open(os.path.join(m.BASE, "udocker-versao"), "w") as f:
    f.write("1.3.18\n")
v_arq = m.versao_udocker()
check("versao do udocker: UDOCKER_VERSAO > arquivo do setup > padrao",
      v_env == "1.3.99" and v_arq == "1.3.18" and m.VERSAO_UDOCKER == "1.3.17",
      "%s %s %s" % (v_env, v_arq, m.VERSAO_UDOCKER))

# ------------------------------------------------------- L. webcdp (fonte)
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
