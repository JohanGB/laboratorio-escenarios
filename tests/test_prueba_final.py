"""F4 (R3): código de la prueba final probado SOLO con datos sintéticos.

Ninguna prueba llama a `cargar_prueba_final` ni a `correr_final` sobre la raíz real del proyecto:
los datos reales desde 2020 no se abren aquí.
"""
import contextlib
import hashlib
import io
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from laboratorio.backtest import final
from laboratorio.backtest.datos import cargar_desarrollo
from laboratorio.backtest.ejecucion import correr_uno
from laboratorio.backtest.particion import HORIZONTES, HORIZONTES_LARGOS, INICIO_PRUEBA_FINAL
from laboratorio.modelos.bootstrap import BootstrapEstacionario
from laboratorio.modelos.lineas_base import EWMA, CaminataAleatoria, SimulacionHistorica
from laboratorio.reportes.prueba_final import cobertura_motor, confirmar, sensibilidad_h1

CAT = {"caminata_aleatoria": (lambda: CaminataAleatoria(), 21),
       "sim_hist_pond": (lambda: SimulacionHistorica(ventana=None, lam=0.994), 21),
       "ewma_0.94": (lambda: EWMA(0.94), 21),
       "bootstrap_est_filtrado": (lambda: BootstrapEstacionario(filtrado=True, sims=300), 63)}
_L = HORIZONTES_LARGOS
CAT_L = {"caminata_aleatoria": (lambda: CaminataAleatoria(horizontes=_L), 21),
         "ewma_0.94": (lambda: EWMA(0.94, horizontes=_L), 21),
         "bootstrap_est_filtrado": (lambda: BootstrapEstacionario(filtrado=True, sims=300, horizontes=_L), 63)}
CONF = ((1, "ewma_0.94", "sim_hist_pond"), (5, "ewma_0.94", "sim_hist_pond"),
        (21, "ewma_0.94", "sim_hist_pond"), (63, "ewma_0.94", "caminata_aleatoria"))


SRC = "src"                       # el código falso vive en <raíz>/src, como el de verdad
_GIT = ["git", "-c", "user.name=prueba", "-c", "user.email=prueba@example.invalid",
        "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", "-c", "core.autocrlf=false"]


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run([*_GIT, "-C", str(raiz), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def _sellar(raiz: Path) -> str:
    """Commit de todo lo que hay y etiqueta «prerregistro-final» en ese commit (la mueve si existía)."""
    if not (raiz / ".git").exists():
        _git(raiz, "init", "-q")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "--allow-empty", "-m", "prerregistro prueba final")
    _git(raiz, "tag", "-f", final.ETIQUETA)
    return _git(raiz, "rev-parse", "HEAD")


def _raiz_sintetica(tmp: Path, con_prerregistro: bool = True, sellar: bool = True) -> Path:
    """Proyecto de mentira: TRM GARCH simulada de 2014 a 2022, código falso, prerregistro y,
    con `sellar`, repositorio git con el commit etiquetado."""
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2014-01-02", "2022-12-30")
    n = len(idx)
    v, r = 0.5, np.empty(n)
    for k in range(n):
        r[k] = np.sqrt(v) * rng.standard_normal()
        v = 0.03 + 0.08 * r[k] ** 2 + 0.89 * v
    est = np.where((idx >= "2020-02-20") & (idx <= "2020-06-30"), "covid_2020", "")
    proc = tmp / "data" / "processed"
    proc.mkdir(parents=True)
    pd.DataFrame({"fecha": idx, "trm": 3000 * np.exp(np.cumsum(r / 100)), "regimen": "flotacion",
                  "estres": est}).to_csv(proc / "trm.csv", index=False)
    pd.DataFrame({"fecha": idx, "brent_usd": 60.0, "dolar_amplio": 100.0, "fed_funds": 1.0}).to_csv(
        proc / "externas_diario.csv", index=False)
    pd.DataFrame({"fecha": idx, "politica": 4.0}).to_csv(proc / "tasas_diarias.csv", index=False)
    (tmp / "data" / "raw").mkdir()
    (tmp / "data" / "raw" / "crudo.csv").write_bytes(b"fecha,valor\n2014-01-02,1\n")   # versionado
    (tmp / ".gitignore").write_bytes(b"data/processed/\nruns/\nreports/\n__pycache__/\n")
    src = tmp / SRC
    (src / "paquete").mkdir(parents=True)
    (src / "paquete" / "a.py").write_bytes(b"x = 1\n")
    (src / "b.py").write_bytes(b"y = 2\n")
    if con_prerregistro:
        _escribir_prerregistro(tmp, final.hashes_actuales(tmp, src))
        if sellar:
            _sellar(tmp)
    return tmp


def _escribir_prerregistro(raiz: Path, hashes: dict, adendas: dict[int, str] | None = None) -> None:
    """`adendas`: número → cuerpo de su sección «## N. Adenda N» (al final, como en el real)."""
    (raiz / "docs").mkdir(exist_ok=True)
    extra = "".join(f"\n## {9 + k}. Adenda {k}\n\n{cuerpo}\n" for k, cuerpo in (adendas or {}).items())
    (raiz / final.PRERREGISTRO).write_text(
        "# Prerregistro\n\ntexto\n\n" + "\n".join(f"- `{k}`: `{v}`" for k, v in hashes.items()) + "\n"
        + extra, encoding="utf-8")


# ---- hash del código ------------------------------------------------------------------------------
def test_hash_codigo_cambia_con_un_byte_y_con_un_nombre_pero_no_con_otros_archivos(tmp_path):
    src = _raiz_sintetica(tmp_path) / SRC
    h0 = final.hash_codigo(src)
    assert len(h0) == 64 and h0 == final.hash_codigo(src)
    (src / "notas.txt").write_text("no cuenta")
    (src / "paquete" / "__pycache__").mkdir()
    (src / "paquete" / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"\0")
    assert final.hash_codigo(src) == h0
    (src / "paquete" / "a.py").write_bytes(b"x = 2\n")
    h1 = final.hash_codigo(src)
    assert h1 != h0
    (src / "paquete" / "a.py").write_bytes(b"x = 1\n")
    assert final.hash_codigo(src) == h0
    (src / "b.py").rename(src / "c.py")                           # mismo contenido, otro nombre
    assert final.hash_codigo(src) != h0
    with pytest.raises(FileNotFoundError):
        final.hash_codigo(tmp_path / "data")


def test_hash_codigo_no_depende_del_fin_de_linea(tmp_path):
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    for d, nl in ((lf, b"\n"), (crlf, b"\r\n")):
        (d / "p").mkdir(parents=True)
        (d / "p" / "m.py").write_bytes(b"x = 1" + nl + b"y = 2" + nl)
    assert final.hash_codigo(lf) == final.hash_codigo(crlf)
    (crlf / "p" / "m.py").write_bytes(b"x = 1\r\ny = 3\r\n")       # el contenido sí cuenta
    assert final.hash_codigo(lf) != final.hash_codigo(crlf)


def test_gitattributes_fija_lf_para_el_codigo_y_el_prerregistro():
    raiz = Path(final.__file__).resolve().parents[3]
    reglas = (raiz / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "*.py text eol=lf" in reglas and "docs/prerregistro*.md text eol=lf" in reglas
    assert "* -text" in reglas                       # el resto (datos, corridas) no se convierte
    r = subprocess.run(["git", "-C", str(raiz), "ls-files", "--eol", "--", "*.py"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        pytest.skip("sin repositorio git")
    malos = [linea for linea in r.stdout.splitlines() if "crlf" in linea or "mixed" in linea]
    assert not malos, malos


def test_hash_codigo_real_cubre_el_paquete_y_este_modulo():
    base = Path(final.__file__).resolve().parents[2]
    assert (base / "laboratorio" / "backtest" / "final.py").exists()
    assert (base / "laboratorio" / "reportes" / "prueba_final.py").exists()
    assert len(final.hash_codigo()) == 64


# ---- candado del prerregistro ---------------------------------------------------------------------
def test_sin_prerregistro_no_se_abre_la_prueba_final(tmp_path):
    raiz = _raiz_sintetica(tmp_path, con_prerregistro=False)
    with pytest.raises(RuntimeError, match="sin prerregistro"):
        final.cargar_prueba_final(raiz, raiz / SRC)
    with pytest.raises(RuntimeError, match="sin prerregistro"):
        final.correr_final(raiz, raiz / SRC, CAT, CAT_L, CONF)
    assert not (raiz / "runs").exists()


@pytest.mark.parametrize("que", ["codigo", "trm", "externas", "tasas", "falta_clave", "repetida", "entorno"])
def test_cualquier_hash_distinto_detiene_todo(tmp_path, que, monkeypatch):
    raiz = _raiz_sintetica(tmp_path)
    src = raiz / SRC
    assert final.verificar_prerregistro(raiz, src) == final.hashes_actuales(raiz, src)
    assert set(final.hashes_actuales(raiz, src)) == {"hash_codigo", "hash_entorno", "hash_trm_csv",
                                                     "hash_externas_diario_csv", "hash_tasas_diarias_csv"}
    motivo = "hashes no coinciden"
    if que == "entorno":                                     # otra versión de una biblioteca
        monkeypatch.setattr(final, "entorno", lambda: {"python": "3.11.9", "numpy": "9.9.9"})
    elif que == "codigo":
        (src / "b.py").write_bytes(b"y = 3\n")
    elif que == "falta_clave":
        h = final.hashes_actuales(raiz, src); h.pop("hash_tasas_diarias_csv")
        _escribir_prerregistro(raiz, h)
    elif que == "repetida":
        motivo = "repetidas"
        p = raiz / final.PRERREGISTRO
        p.write_text(p.read_text(encoding="utf-8") + "- `hash_codigo`: `abc`\n", encoding="utf-8")
    else:
        f = raiz / "data" / "processed" / {"trm": "trm.csv", "externas": "externas_diario.csv",
                                           "tasas": "tasas_diarias.csv"}[que]
        f.write_bytes(f.read_bytes() + b"\n")
    _sellar(raiz)                 # git queda en orden: lo que detiene todo es el hash, no git
    final.verificar_git(raiz)
    with pytest.raises(RuntimeError, match=motivo):
        final.cargar_prueba_final(raiz, src)
    with pytest.raises(RuntimeError, match=motivo):
        final.correr_final(raiz, src, CAT, CAT_L, CONF)
    assert not (raiz / "runs").exists()


# ---- candado de git -------------------------------------------------------------------------------
@pytest.mark.parametrize("que", ["sin_repo", "sin_etiqueta", "etiqueta_sin_prerregistro",
                                 "prerregistro_editado", "extra_en_src", "data_modificada",
                                 "data_sin_versionar", "src_con_commit_posterior"])
def test_git_distinto_del_commit_etiquetado_detiene_todo(tmp_path, que):
    """Los hashes coinciden en todos los casos: lo único que falla es git."""
    raiz = _raiz_sintetica(tmp_path, sellar=False)
    src = raiz / SRC
    if que == "sin_repo":
        motivo = "no es la raíz de un repositorio git"
    elif que == "etiqueta_sin_prerregistro":
        pre = (raiz / final.PRERREGISTRO).read_bytes()
        (raiz / final.PRERREGISTRO).unlink()
        _sellar(raiz)                                        # etiqueta en un commit sin prerregistro
        (raiz / final.PRERREGISTRO).write_bytes(pre)         # existe, pero sin versionar
        motivo = "no contiene docs/prerregistro.md"
    else:
        _sellar(raiz)
        assert final.verificar_prerregistro(raiz, src) == final.hashes_actuales(raiz, src)
        if que == "sin_etiqueta":
            _git(raiz, "tag", "-d", final.ETIQUETA)
            motivo = "no existe la etiqueta"
        elif que == "prerregistro_editado":                  # los hashes escritos no cambian
            p = raiz / final.PRERREGISTRO
            p.write_text(p.read_text(encoding="utf-8") + "\nUna hipótesis nueva.\n", encoding="utf-8")
            motivo = "docs/prerregistro.md no coincide"
        elif que == "extra_en_src":                          # no es .py: el hash del código no lo ve
            (src / "notas.txt").write_bytes(b"apunte\n")
            motivo = "árbol sucio"
        elif que == "data_modificada":
            (raiz / "data" / "raw" / "crudo.csv").write_bytes(b"fecha,valor\n2014-01-02,2\n")
            motivo = "src/ y data/ no coinciden"
        elif que == "data_sin_versionar":
            (raiz / "data" / "raw" / "nuevo.csv").write_bytes(b"x\n")
            motivo = "árbol sucio"
        else:                                                # commit posterior sin mover la etiqueta
            (src / "notas.txt").write_bytes(b"apunte\n")
            _git(raiz, "add", "-A"); _git(raiz, "commit", "-q", "-m", "después del prerregistro")
            motivo = "src/ y data/ no coinciden"
    assert final.leer_prerregistro(raiz / final.PRERREGISTRO) == final.hashes_actuales(raiz, src)
    for abrir in (lambda: final.verificar_prerregistro(raiz, src),
                  lambda: final.cargar_prueba_final(raiz, src),
                  lambda: final.correr_final(raiz, src, CAT, CAT_L, CONF)):
        with pytest.raises(RuntimeError, match=motivo):
            abrir()
    assert not (raiz / "runs").exists()


def _commit_adenda(raiz: Path, texto: str) -> str:
    p = raiz / final.PRERREGISTRO
    p.write_text(p.read_text(encoding="utf-8") + f"\n{texto}\n", encoding="utf-8")
    _git(raiz, "add", "-A"); _git(raiz, "commit", "-q", "-m", texto)
    return _git(raiz, "rev-parse", "HEAD")


def test_una_adenda_es_una_etiqueta_nueva_y_la_original_no_se_mueve_ni_se_borra(tmp_path):
    raiz = _raiz_sintetica(tmp_path)
    src = raiz / SRC
    original = _git(raiz, "rev-parse", "HEAD")
    assert final.verificar_git(raiz) == {"etiqueta": "prerregistro-final", "commit_prerregistro": original,
                                         "commit_etiqueta_original": original}
    # Adenda 1: editar y hacer commit no basta; hace falta la etiqueta nueva. La original sigue donde estaba.
    c1 = _commit_adenda(raiz, "Adenda 1.")
    with pytest.raises(RuntimeError, match="docs/prerregistro.md no coincide"):
        final.verificar_prerregistro(raiz, src)
    _git(raiz, "tag", "prerregistro-adenda-1")
    assert final.verificar_git(raiz) == {"etiqueta": "prerregistro-adenda-1", "commit_prerregistro": c1,
                                         "commit_etiqueta_original": original}
    final.verificar_prerregistro(raiz, src)
    assert _git(raiz, "rev-parse", final.ETIQUETA) == original != c1
    # Adenda 2: vale siempre la de número más alto.
    c2 = _commit_adenda(raiz, "Adenda 2.")
    with pytest.raises(RuntimeError, match="docs/prerregistro.md no coincide"):
        final.verificar_prerregistro(raiz, src)
    _git(raiz, "tag", "prerregistro-adenda-2")
    assert final.etiqueta_vigente(raiz) == {"etiqueta": "prerregistro-adenda-2", "commit_prerregistro": c2,
                                            "commit_etiqueta_original": original}
    final.verificar_prerregistro(raiz, src)
    # Lo que no vale: saltarse un número, un nombre raro, una adenda sin commit nuevo o hacia atrás.
    for etiqueta, donde, motivo in (("prerregistro-adenda-4", "HEAD", "no son consecutivas"),
                                    ("prerregistro-adenda-x", "HEAD", "nombre inválido"),
                                    ("prerregistro-adenda-03", "HEAD", "nombre inválido"),
                                    ("prerregistro-adenda-3", c2, "no está en un commit posterior"),
                                    ("prerregistro-adenda-3", original, "no está en un commit posterior")):
        _git(raiz, "tag", etiqueta, donde)
        with pytest.raises(RuntimeError, match=motivo):
            final.verificar_prerregistro(raiz, src)
        _git(raiz, "tag", "-d", etiqueta)
    final.verificar_prerregistro(raiz, src)
    # Borrar una adenda intermedia o la original también detiene todo.
    _git(raiz, "tag", "-d", "prerregistro-adenda-1")
    with pytest.raises(RuntimeError, match="no son consecutivas"):
        final.verificar_prerregistro(raiz, src)
    _git(raiz, "tag", "prerregistro-adenda-1", c1)
    final.verificar_prerregistro(raiz, src)
    _git(raiz, "tag", "-d", final.ETIQUETA)
    with pytest.raises(RuntimeError, match="no existe la etiqueta"):
        final.verificar_prerregistro(raiz, src)
    assert not (raiz / "runs").exists()


def test_cargar_prueba_final_entrega_toda_la_historia_y_el_primer_origen(tmp_path):
    raiz = _raiz_sintetica(tmp_path)
    vista, primero = final.cargar_prueba_final(raiz, raiz / SRC)
    corte = pd.Timestamp(INICIO_PRUEBA_FINAL)
    assert vista.fechas[primero] >= corte > vista.fechas[primero - 1]
    assert vista.fechas.max() == pd.Timestamp("2022-12-30")
    # El cargador de desarrollo sigue sin ver nada desde el corte, con los mismos archivos.
    dev = cargar_desarrollo(raiz)
    assert dev.fechas.max() < corte and dev.n == primero
    assert np.array_equal(dev.logp, vista.logp[:primero])


def test_sin_datos_posteriores_al_corte_falla(tmp_path):
    raiz = _raiz_sintetica(tmp_path)
    proc = raiz / "data" / "processed"
    for a in final.ARCHIVOS_DATOS:
        d = pd.read_csv(proc / a)
        d[d["fecha"] < INICIO_PRUEBA_FINAL].to_csv(proc / a, index=False)
    _escribir_prerregistro(raiz, final.hashes_actuales(raiz, raiz / SRC))
    _sellar(raiz)
    with pytest.raises(RuntimeError, match="no hay datos posteriores"):
        final.cargar_prueba_final(raiz, raiz / SRC)


# ---- corrida única y reporte ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def corrida(tmp_path_factory):
    raiz = _raiz_sintetica(tmp_path_factory.mktemp("final"))
    impreso = io.StringIO()
    with contextlib.redirect_stdout(impreso):
        salida = final.correr_final(raiz, raiz / SRC, CAT, CAT_L, CONF)
    return raiz, salida, impreso.getvalue()


def test_la_corrida_final_solo_tiene_origenes_desde_el_corte_y_respeta_el_embargo(corrida):
    raiz, _, _ = corrida
    vista, primero = final.cargar_prueba_final(raiz, raiz / SRC)
    for carpeta, hmax, cat in ((final.SALIDA_FINAL, max(HORIZONTES), CAT),
                               (final.SALIDA_FINAL_LARGO, max(HORIZONTES_LARGOS), CAT_L)):
        for m in cat:
            d = pd.read_csv(raiz / carpeta / f"{m}.csv.gz", parse_dates=["fecha"])
            assert d["fecha"].min() == vista.fechas[primero] >= pd.Timestamp(INICIO_PRUEBA_FINAL)
            assert d["origen"].min() == primero and d["origen"].max() == vista.n - 1 - hmax
            assert d["y"].notna().all()
            j = json.loads((raiz / carpeta / f"{m}.json").read_text(encoding="utf-8"))
            assert j["prueba_final"] is True and j["hash_codigo"] == final.hash_codigo(raiz / SRC)
    # Un pronóstico de la prueba final coincide con el del mismo modelo sobre la vista recortada
    # en el origen: no usa nada posterior.
    d = pd.read_csv(raiz / final.SALIDA_FINAL / "ewma_0.94.csv.gz")
    o = int(d["origen"].iloc[100])
    from laboratorio.backtest.particion import NIVELES
    q = EWMA(0.94).pronosticar(vista.hasta(o), np.array([o]), NIVELES)[1][0]
    assert np.allclose(d[(d.origen == o) & (d.h == 1)].filter(like="q_").to_numpy()[0], q)


def test_la_prueba_final_no_se_puede_repetir(corrida):
    raiz, _, _ = corrida
    hecho = json.loads((raiz / final.SALIDA_FINAL / "HECHO.json").read_text(encoding="utf-8"))
    assert hecho["modelos"] == list(CAT) and hecho["hash_codigo"]
    antes = (raiz / "reports" / "prueba_final.md").read_bytes()
    with pytest.raises(RuntimeError, match="ya se corrió"):
        final.correr_final(raiz, raiz / SRC, CAT, CAT_L, CONF)
    assert (raiz / "reports" / "prueba_final.md").read_bytes() == antes


def test_la_corrida_final_no_imprime_cifras(corrida):
    _, _, impreso = corrida
    assert impreso.splitlines() == [f"{m}: listo" for m in CAT] + [f"{m}: listo" for m in CAT_L]


def test_iniciada_y_hecho_dejan_rastro_con_el_sha256_de_cada_resultado(corrida):
    raiz, _, _ = corrida
    d = raiz / final.SALIDA_FINAL
    ini = json.loads((d / "INICIADA.json").read_text(encoding="utf-8"))
    hecho = json.loads((d / "HECHO.json").read_text(encoding="utf-8"))
    for k, v in final.hashes_actuales(raiz, raiz / SRC).items():
        assert ini[k] == hecho[k] == v
    assert ini["entorno"] == final.entorno()
    assert ini["commit_prerregistro"] == hecho["commit_prerregistro"] == _git(raiz, "rev-parse", final.ETIQUETA)
    assert ini["etiqueta"] == hecho["etiqueta"] == "prerregistro-final"
    assert ini["commit_etiqueta_original"] == hecho["commit_etiqueta_original"] == ini["commit_prerregistro"]
    assert ini["commit_head"] == _git(raiz, "rev-parse", "HEAD")
    assert ini["reanudaciones"] == [] and hecho["reanudaciones"] == 0
    assert hecho["iniciada"] == ini["iniciada"]
    assert datetime.fromisoformat(ini["iniciada"]) <= datetime.fromisoformat(hecho["terminada"])
    en_disco = {p.relative_to(raiz).as_posix()
                for c in (final.SALIDA_FINAL, final.SALIDA_FINAL_LARGO)
                for p in (raiz / c).rglob("*") if p.is_file() and p.name != "HECHO.json"}
    en_disco |= {"reports/prueba_final.md", "reports/figs/prueba_final_pit.png"}
    assert set(hecho["sha256"]) == en_disco
    for m in CAT:
        assert f"runs/prueba_final/{m}.csv.gz" in en_disco and f"runs/prueba_final/{m}.json" in en_disco
    assert "runs/prueba_final/INICIADA.json" in en_disco
    assert any(r.startswith("runs/prueba_final/cola/") for r in en_disco)
    assert any(r.startswith("runs/prueba_final_largo/") for r in en_disco)
    for ruta, sha in hecho["sha256"].items():
        assert len(sha) == 64 and sha == hashlib.sha256((raiz / ruta).read_bytes()).hexdigest(), ruta


def test_el_cache_solo_vale_con_los_mismos_hashes(tmp_path, capsys):
    raiz = _raiz_sintetica(tmp_path)
    vista, primero = final.cargar_prueba_final(raiz, raiz / SRC)
    out, nombre = raiz / "runs" / "cache", "caminata_aleatoria"
    cat = {nombre: CAT[nombre]}
    h = {"prueba_final": True, "hash_codigo": "a" * 64, "hash_entorno": "b" * 16}

    def correr(hashes, **kw):
        return correr_uno(nombre, cat, vista, out, raiz, primero=primero, extra=hashes,
                          exigir=hashes, silencioso=True, **kw)

    def guardado():
        return json.loads((out / f"{nombre}.json").read_text(encoding="utf-8"))

    assert correr(h) is True and correr(h) is False                 # mismo código y entorno: caché
    assert capsys.readouterr().out.splitlines() == [f"{nombre}: listo", f"{nombre}: en caché"]
    for clave in ("hash_codigo", "hash_entorno"):
        otro = {**h, clave: "c" * 16}
        assert correr(otro) is True and guardado()[clave] == "c" * 16   # se vuelve a correr
        assert correr(otro) is False
        assert correr(h) is True and guardado()[clave] == h[clave]      # y de vuelta
    assert "se vuelve a correr" in capsys.readouterr().out
    (out / f"{nombre}.json").write_text("{", encoding="utf-8")       # .json dañado: no vale
    assert correr(h) is True and guardado()["hash_codigo"] == h["hash_codigo"]
    # Un resultado sin hashes (como los de desarrollo) tampoco vale para la prueba final...
    assert correr_uno(nombre, cat, vista, out, raiz, primero=primero, forzar=True) is True
    assert "hash_codigo" not in guardado()
    # ...pero sin `exigir` el caché de desarrollo se comporta como siempre.
    assert correr_uno(nombre, cat, vista, out, raiz, primero=primero) is False
    assert correr(h) is True and guardado()["prueba_final"] is True


def test_una_corrida_interrumpida_deja_rastro_y_al_reanudar_no_reusa_resultados_de_otro_codigo(
        tmp_path, monkeypatch, capsys):
    raiz = _raiz_sintetica(tmp_path)
    src, d, nombre = raiz / SRC, raiz / final.SALIDA_FINAL, "caminata_aleatoria"

    def revienta():
        raise ZeroDivisionError("error de programa simulado")

    cat = {nombre: CAT[nombre], "roto": (revienta, 21)}
    with pytest.raises(ZeroDivisionError):
        final.correr_final(raiz, src, cat, {}, CONF)
    ini = json.loads((d / "INICIADA.json").read_text(encoding="utf-8"))
    h0 = final.hash_codigo(src)
    assert ini["hash_codigo"] == h0 and ini["reanudaciones"] == []
    assert not (d / "HECHO.json").exists() and not (raiz / final.REPORTE_FINAL).exists()
    assert json.loads((d / f"{nombre}.json").read_text(encoding="utf-8"))["hash_codigo"] == h0
    capsys.readouterr()

    with pytest.raises(ZeroDivisionError):                           # mismo código: reusa el caché
        final.correr_final(raiz, src, cat, {}, CONF)
    assert capsys.readouterr().out.splitlines() == [f"{nombre}: en caché"]

    # Adenda: se corrige el programa (otro hash) y el prerregistro lleva el hash nuevo.
    original = _git(raiz, "rev-parse", final.ETIQUETA)
    (src / "b.py").write_bytes(b"y = 3\n")
    _escribir_prerregistro(raiz, final.hashes_actuales(raiz, src),
                           {1: f"Original `{h0}`; nuevo `{final.hash_codigo(src)}`."})
    _git(raiz, "add", "-A"); _git(raiz, "commit", "-q", "-m", "adenda 1")
    commit = _git(raiz, "rev-parse", "HEAD")
    h1 = final.hash_codigo(src)
    assert h1 != h0
    # Mover la etiqueta original no sirve: INICIADA.json recuerda dónde estaba al abrir la prueba.
    _git(raiz, "tag", "-f", final.ETIQUETA)
    with pytest.raises(RuntimeError, match="se movió desde que se abrió la prueba"):
        final.correr_final(raiz, src, {nombre: CAT[nombre]}, {}, CONF)
    assert len(json.loads((d / "INICIADA.json").read_text(encoding="utf-8"))["reanudaciones"]) == 1
    assert not (d / "HECHO.json").exists() and capsys.readouterr().out == ""
    # Lo correcto: la original vuelve a su commit y la adenda es una etiqueta nueva.
    _git(raiz, "tag", "-f", final.ETIQUETA, original)
    _git(raiz, "tag", "prerregistro-adenda-1")

    def generar_falso(raiz, confirmatorias=None):
        salida = Path(raiz) / final.REPORTE_FINAL
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_bytes(b"reporte de mentira\n")
        return salida

    monkeypatch.setattr("laboratorio.reportes.prueba_final.generar", generar_falso)
    final.correr_final(raiz, src, {nombre: CAT[nombre]}, {}, CONF)
    lineas = capsys.readouterr().out.splitlines()
    assert len(lineas) == 2 and "se vuelve a correr" in lineas[0] and lineas[1] == f"{nombre}: listo"
    assert json.loads((d / f"{nombre}.json").read_text(encoding="utf-8"))["hash_codigo"] == h1
    fin = json.loads((d / "INICIADA.json").read_text(encoding="utf-8"))
    assert fin["iniciada"] == ini["iniciada"] and fin["hash_codigo"] == h0     # el inicio no se pisa
    assert [r["hash_codigo"] for r in fin["reanudaciones"]] == [h0, h1]
    assert fin["reanudaciones"][-1]["commit_prerregistro"] == commit != fin["commit_prerregistro"]
    assert fin["etiqueta"] == "prerregistro-final" and fin["commit_prerregistro"] == original
    assert [r["etiqueta"] for r in fin["reanudaciones"]] == ["prerregistro-final", "prerregistro-adenda-1"]
    assert {fin["commit_etiqueta_original"], *(r["commit_etiqueta_original"] for r in fin["reanudaciones"])} == {original}
    hecho = json.loads((d / "HECHO.json").read_text(encoding="utf-8"))
    assert hecho["reanudaciones"] == 2 and hecho["hash_codigo"] == h1
    assert hecho["etiqueta"] == "prerregistro-adenda-1" and hecho["commit_prerregistro"] == commit
    assert hecho["commit_etiqueta_original"] == original
    # INICIADA.json dañado: no se corre nada.
    (d / "HECHO.json").unlink()
    (d / "INICIADA.json").write_text("{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="dañado"):
        final.correr_final(raiz, src, {nombre: CAT[nombre]}, {}, CONF)


def test_el_reporte_final_trae_exactamente_lo_prerregistrado(corrida):
    raiz, salida, _ = corrida
    texto = salida.read_text(encoding="utf-8")
    for titulo in ("## Declaraciones", "## Pruebas confirmatorias", "## Motor del caso por horizonte",
                   "## Horizonte h = 1 (descriptivo)", "## Horizonte h = 63 (descriptivo)",
                   "## Pruebas de VaR", "## Model Confidence Set", "## Semáforo de Basilea",
                   "## Expected Shortfall", "## Uniformidad del PIT", "## Horizontes largos"):
        assert titulo in texto, titulo
    assert "no son datos nunca vistos" in texto                    # R2
    assert "covid_2020" in texto and "estres_2022" in texto        # episodios aparte (aunque uno esté vacío)
    conf = texto.split("## Pruebas confirmatorias")[1].split("## Motor")[0]
    assert conf.count("| ewma_0.94 |") == 4 and "p (Holm)" in conf
    motor = texto.split("## Motor del caso por horizonte")[1].split("## Horizonte h = 1")[0]
    assert motor.count("| `bootstrap_est_filtrado` |") == 6 and "| 252 | `bootstrap_est_filtrado` | ninguno (descriptivo) |" in motor
    # Advertencia de cobertura: siempre a 63, 126 y 252, con su n efectivo; nunca «siempre» antes.
    from laboratorio.reportes.fase2 import cargar
    cm = cobertura_motor(cargar(raiz / final.SALIDA_FINAL)[0],
                         cargar(raiz / final.SALIDA_FINAL_LARGO)[0]).set_index("h")
    filas = {int(f.split("|")[1]): f for f in motor.splitlines() if "| `bootstrap_est_filtrado` |" in f}
    assert final.HORIZONTES_ADVERTENCIA == (63, 126, 252) and sorted(filas) == [1, 5, 21, 63, 126, 252]
    for h, fila in filas.items():
        if h in final.HORIZONTES_ADVERTENCIA:
            assert fila.rstrip().endswith(f"| **siempre** (n ef. = {cm.loc[h, 'n_efectivo']}) |"), fila
        else:
            assert "siempre" not in fila, fila
    assert "230 días" in motor and "costo total" in motor and "**indirecto**" in motor
    assert conf.count("Sensibilidad prerregistrada") == 1 and "no cambia el resultado" in conf
    assert (raiz / "reports" / "figs" / "prueba_final_pit.png").exists()
    assert not (raiz / "reports" / "figs" / "fase2_pit.png").exists()   # no pisa la figura de desarrollo
    assert "## Veredicto" not in texto and "## Conclusiones" not in texto   # nada de criterios de desarrollo


def test_confirmar_aplica_holm_y_exige_crps_menor(corrida):
    raiz, _, _ = corrida
    from laboratorio.reportes.fase2 import cargar
    res = cargar(raiz / final.SALIDA_FINAL)[0]
    c = confirmar(res, CONF)
    from laboratorio.evaluacion.pruebas import holm
    assert np.allclose(c["p_holm"], holm(c["p"].to_numpy())) and (c["p_holm"] >= c["p"]).all()
    assert list(c["exito"]) == list((c["relativo"] < 1) & (c["p_holm"] < 0.05))
    # Un campeón contra sí mismo no puede tener éxito; un modelo ausente es un error (lista cerrada).
    with pytest.raises(Exception):
        confirmar(res, ((1, "ewma_0.94", "ewma_0.94"),))
    with pytest.raises(RuntimeError, match="lista de modelos es cerrada"):
        confirmar(res, ((1, "no_existe", "sim_hist_pond"),))
    # DM es unilateral: invertir campeón y base da p complementario.
    a = confirmar(res, ((1, "ewma_0.94", "sim_hist_pond"),))
    b = confirmar(res, ((1, "sim_hist_pond", "ewma_0.94"),))
    assert a["p"].iloc[0] + b["p"].iloc[0] == pytest.approx(1.0, abs=1e-9)
    assert not (a["exito"].iloc[0] and b["exito"].iloc[0])


def test_la_sensibilidad_de_h1_quita_los_episodios_y_no_cambia_el_resultado(corrida):
    raiz, salida, _ = corrida
    from laboratorio.evaluacion.pruebas import diebold_mariano
    from laboratorio.reportes.fase2 import _f, cargar, crps_por_origen
    res = cargar(raiz / final.SALIDA_FINAL)[0]
    assert final.EPISODIOS == ("covid_2020", "estres_2022")
    s = sensibilidad_h1(res, CONF)
    d = res["ewma_0.94"]; d = d[d["h"] == 1]
    fuera = set(d.loc[d["estres"] == "covid_2020", "origen"])     # la serie sintética solo tiene covid
    assert len(fuera) > 50 and s["n_excluidos"] == len(fuera) and s["n"] == len(d) - len(fuera)
    a, b = crps_por_origen(res["ewma_0.94"], 1), crps_por_origen(res["sim_hist_pond"], 1)
    q = [o for o in a.index if o not in fuera]
    assert s["relativo"] == pytest.approx(a.loc[q].mean() / b.loc[q].mean())
    assert s["p"] == pytest.approx(diebold_mariano(a.loc[q].to_numpy(), b.loc[q].to_numpy(), h=1).p_valor)
    # Sin excluir nada reproduce la fila confirmatoria; solo existe para h = 1.
    c = confirmar(res, CONF).iloc[0]
    s0 = sensibilidad_h1(res, CONF, episodios=())
    assert s0["n"] == c["n"] and s0["n_excluidos"] == 0
    assert s0["relativo"] == pytest.approx(c["relativo"]) and s0["p"] == pytest.approx(c["p"])
    assert sensibilidad_h1(res, CONF[1:]) is None
    # Con muy pocos orígenes no hay prueba, solo el cociente.
    pocos = {m: x[x["origen"] < x["origen"].min() + 10] for m, x in res.items()}
    assert sensibilidad_h1(pocos, CONF, episodios=())["p"] is None
    # En el reporte: una línea con esas cifras; la columna de resultado sale de `confirmar`, no de aquí.
    texto = salida.read_text(encoding="utf-8")
    linea = next(x for x in texto.splitlines() if x.startswith("Sensibilidad prerregistrada"))
    assert f"sin los {len(fuera)} orígenes" in linea and f"= {_f(s['relativo'], 3)}," in linea
    assert f"n = {s['n']}." in linea and "aproximado" in linea
    conf = texto.split("## Pruebas confirmatorias")[1].split("Sensibilidad prerregistrada")[0]
    esperado = ["**ÉXITO**" if e else "**no confirmado**" for e in confirmar(res, CONF)["exito"]]
    assert [x.split("|")[-2].strip() for x in conf.splitlines() if x.startswith("| ") and "ewma_0.94" in x] == esperado


def test_cobertura_del_motor_usa_n_efectivo(corrida):
    raiz, _, _ = corrida
    from laboratorio.reportes.fase2 import cargar
    res = cargar(raiz / final.SALIDA_FINAL)[0]
    largo = cargar(raiz / final.SALIDA_FINAL_LARGO)[0]
    cm = cobertura_motor(res, largo, motor="ewma_0.94").set_index("h")
    assert list(cm.index) == [1, 5, 21, 63, 126, 252]
    assert cm.loc[252, "n_efectivo"] == cm.loc[252, "n"] // 252
    assert (cm["ic_inf"] <= cm["cobertura"]).all() and (cm["cobertura"] <= cm["ic_sup"]).all()


def test_lo_fijado_en_el_codigo_es_coherente_con_el_catalogo():
    from laboratorio.backtest.catalogo import FABRICAS, FABRICAS_LARGOS, LINEAS_BASE
    assert set(final.MODELOS_FINAL) == set(FABRICAS) and len(final.MODELOS_FINAL) == 17
    assert set(final.MODELOS_FINAL_LARGOS) == set(FABRICAS_LARGOS)
    assert [h for h, _, _ in final.CONFIRMATORIAS] == list(HORIZONTES)
    for _, campeon, base in final.CONFIRMATORIAS:
        assert campeon in FABRICAS and campeon not in LINEAS_BASE and base in LINEAS_BASE
    assert final.MOTOR_CASO in FABRICAS and final.MOTOR_CASO in FABRICAS_LARGOS


def test_el_comando_final_no_tiene_opcion_de_forzar():
    from laboratorio.backtest.__main__ import main
    with pytest.raises(SystemExit):
        main(["final", "--forzar"])


def test_main_final_verificar_no_corre_nada(tmp_path, monkeypatch, capsys):
    raiz = _raiz_sintetica(tmp_path, con_prerregistro=False)
    shutil.rmtree(raiz / SRC)
    _escribir_prerregistro(raiz, final.hashes_actuales(raiz))      # hash del código real
    commit = _sellar(raiz)
    final.main_final(raiz, solo_verificar=True)
    salida = capsys.readouterr().out
    assert "prerregistro verificado" in salida and f"«prerregistro-final»: {commit}" in salida
    final.main_final(raiz, solo_hashes=True)                       # las líneas que se pegan al cerrar
    salida = capsys.readouterr().out
    assert final.leer_prerregistro(raiz / final.PRERREGISTRO) == dict(final._CLAVE.findall(salida))
    assert not (raiz / "runs").exists()


# ---- O4, adenda 1: líneas de hash editadas y reanudación solo con adenda que liste los hashes -----
def test_el_candado_verifica_contra_la_adenda_mas_reciente_con_las_lineas_de_hash_editadas(tmp_path):
    raiz = _raiz_sintetica(tmp_path)
    src = raiz / SRC
    viejos = final.hashes_actuales(raiz, src)
    (src / "b.py").write_bytes(b"y = 3\n")                       # corrección del programa
    nuevos = final.hashes_actuales(raiz, src)
    assert nuevos["hash_codigo"] != viejos["hash_codigo"]
    with pytest.raises(RuntimeError, match="los hashes no coinciden"):
        final.verificar_prerregistro(raiz, src)
    # Se editan las líneas de hash (sin claves repetidas); el original solo se cita en la adenda.
    _escribir_prerregistro(raiz, nuevos, {1: f"`hash_codigo` original `{viejos['hash_codigo']}`; "
                                             f"nuevo `{nuevos['hash_codigo']}`."})
    assert final.leer_prerregistro(raiz / final.PRERREGISTRO) == nuevos
    with pytest.raises(RuntimeError, match="no coincide"):         # sin commit ni etiqueta nueva
        final.verificar_prerregistro(raiz, src)
    _git(raiz, "add", "-A"); _git(raiz, "commit", "-q", "-m", "adenda 1")
    with pytest.raises(RuntimeError, match="no coincide"):         # commit sin etiqueta: tampoco
        final.verificar_prerregistro(raiz, src)
    _git(raiz, "tag", "prerregistro-adenda-1")
    assert final.verificar_prerregistro(raiz, src) == nuevos
    assert final.etiqueta_vigente(raiz)["etiqueta"] == "prerregistro-adenda-1"
    original = _git(raiz, "show", f"{final.ETIQUETA}:{final.PRERREGISTRO.as_posix()}")
    assert viejos["hash_codigo"] in original and nuevos["hash_codigo"] not in original
    (src / "b.py").write_bytes(b"y = 2\n")                       # volver al código viejo: no vale
    with pytest.raises(RuntimeError, match="los hashes no coinciden"):
        final.verificar_prerregistro(raiz, src)


def test_reanudar_con_hashes_nuevos_exige_una_adenda_que_los_liste(tmp_path, monkeypatch, capsys):
    raiz = _raiz_sintetica(tmp_path)
    src, d, nombre = raiz / SRC, raiz / final.SALIDA_FINAL, "caminata_aleatoria"

    def revienta():
        raise ZeroDivisionError("error de programa simulado")

    with pytest.raises(ZeroDivisionError):
        final.correr_final(raiz, src, {nombre: CAT[nombre], "roto": (revienta, 21)}, {}, CONF)
    h0 = final.hash_codigo(src)
    (src / "b.py").write_bytes(b"y = 3\n")
    h1 = final.hash_codigo(src)
    cuerpos: dict[int, str] = {}

    def adenda(cuerpo: str) -> None:
        cuerpos[len(cuerpos) + 1] = cuerpo
        _escribir_prerregistro(raiz, final.hashes_actuales(raiz, src), cuerpos)
        _git(raiz, "add", "-A"); _git(raiz, "commit", "-q", "-m", f"adenda {len(cuerpos)}")
        _git(raiz, "tag", f"prerregistro-adenda-{len(cuerpos)}")

    def intento():
        return final.correr_final(raiz, src, {nombre: CAT[nombre]}, {}, CONF)

    capsys.readouterr()
    adenda("Corrección del programa, sin escribir los hashes.")     # 1: la adenda no los lista
    with pytest.raises(RuntimeError, match="no lista en la sección «Adenda 1».*hash_codigo"):
        intento()
    cuerpos[1] += f" (nuevo `{h1}`)"                                # 2: el nuevo solo aparece en la
    adenda(f"Otra corrección; el hash anterior era `{h0}`.")        #    sección 1, no en la vigente
    assert h1 in (raiz / final.PRERREGISTRO).read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="no lista en la sección «Adenda 2»"):
        intento()
    ini = json.loads((d / "INICIADA.json").read_text(encoding="utf-8"))
    assert ini["reanudaciones"] == [] and capsys.readouterr().out == ""
    assert json.loads((d / f"{nombre}.json").read_text(encoding="utf-8"))["hash_codigo"] == h0

    def generar_falso(raiz, confirmatorias=None):
        salida = Path(raiz) / final.REPORTE_FINAL
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_bytes(b"reporte de mentira\n")
        return salida

    monkeypatch.setattr("laboratorio.reportes.prueba_final.generar", generar_falso)
    adenda(f"Corrección. `hash_codigo` original `{h0}`, nuevo `{h1}`.")   # 3: la que vale
    intento()
    fin = json.loads((d / "INICIADA.json").read_text(encoding="utf-8"))
    assert [(r["etiqueta"], r["hash_codigo"]) for r in fin["reanudaciones"]] == [("prerregistro-adenda-3", h1)]
    assert json.loads((d / f"{nombre}.json").read_text(encoding="utf-8"))["hash_codigo"] == h1


def test_exigir_adenda_sin_cambios_no_pide_nada_y_con_cambios_pide_una_adenda_nueva(tmp_path):
    ant = {"hash_codigo": "a" * 64, "etiqueta": "prerregistro-final"}
    final.exigir_adenda(tmp_path, ant, {"hash_codigo": "a" * 64}, {"etiqueta": "prerregistro-final"})
    for etiqueta in ("prerregistro-final", "otra-cosa"):
        with pytest.raises(RuntimeError, match="sin una adenda nueva"):
            final.exigir_adenda(tmp_path, ant, {"hash_codigo": "b" * 64}, {"etiqueta": etiqueta})
    ant1 = {"hash_codigo": "b" * 64, "etiqueta": "prerregistro-adenda-1"}
    with pytest.raises(RuntimeError, match="sin una adenda nueva"):   # misma adenda, otro código
        final.exigir_adenda(tmp_path, ant1, {"hash_codigo": "c" * 64}, {"etiqueta": "prerregistro-adenda-1"})
    assert final.seccion_adenda("## 12. Adenda 1 (x)\n\nhola `z`\n\n## 13. Otra\n\nadiós\n", 1) == "\nhola `z`\n\n"
    assert final.seccion_adenda("## 12. Adenda 12\n\nx\n", 1) is None
