"""Cada prueba se compara con un resultado calculado a mano (pasos escritos en el comentario)."""
import numpy as np
import pytest

from laboratorio.evaluacion.pruebas import (christoffersen, diebold_mariano, kupiec,
                                            transiciones, varianza_largo_plazo)


def test_kupiec_caso_clasico_250_dias_5_violaciones_al_1pct():
    # A mano (ejemplo de Jorion): n=250, x=5, p=0,01, p̂=0,02
    # ln L0 = 245·ln 0,99 + 5·ln 0,01 = 245·(−0,01005034) + 5·(−4,6051702) = −2,4623323 − 23,0258509 = −25,4881832
    # ln L1 = 245·ln 0,98 + 5·ln 0,02 = 245·(−0,02020271) + 5·(−3,9120230) = −4,9496633 − 19,5601150 = −24,5097783
    # LR = −2(−25,4881832 + 24,5097783) = 1,9568098 ; p = P(χ²₁ > 1,9568) = 0,16186
    v = np.zeros(250, bool); v[[10, 60, 110, 160, 210]] = True
    r = kupiec(v, 0.01)
    assert r.estadistico == pytest.approx(1.9568098, abs=1e-6)
    assert r.p_valor == pytest.approx(0.16186, abs=1e-4)
    assert r.detalle["x"] == 5 and r.detalle["tasa"] == 0.02


def test_kupiec_tasa_exacta_da_cero_y_cero_violaciones_es_finito():
    v = np.zeros(100, bool); v[[3, 50, 97, 20, 70]] = True        # 5/100 = p
    assert kupiec(v, 0.05).estadistico == pytest.approx(0.0, abs=1e-12)
    # x=0: LR = −2·n·ln(1−p) = −2·100·ln 0,99 = 2,0100672
    assert kupiec(np.zeros(100, bool), 0.01).estadistico == pytest.approx(2.0100672, abs=1e-6)


def test_christoffersen_violaciones_agrupadas():
    # Secuencia 1,1,1,1,0,0,0,0 → transiciones: n11=3, n10=1, n00=3, n01=0
    # π01 = 0, π11 = 3/4, π = 3/7
    # ln L(π)      = (n00+n10)·ln(4/7) + (n01+n11)·ln(3/7) = 4·(−0,5596158) + 3·(−0,8472979) = −4,7803567
    # ln L(π01,π11) = 3·ln 1 + 0 + 1·ln(1/4) + 3·ln(3/4) = −1,3862944 − 0,8630462 = −2,2493406
    # LR_ind = −2(−4,7803567 + 2,2493406) = 5,0620322
    v = [1, 1, 1, 1, 0, 0, 0, 0]
    assert transiciones(v) == {"n00": 3, "n01": 0, "n10": 1, "n11": 3}
    r = christoffersen(v, 0.5)
    assert r["independencia"].estadistico == pytest.approx(5.0620322, abs=1e-6)
    # Cobertura condicional: LR_uc con x=4, n=8, p=0,5 → p̂ = p → 0;  LR_cc = 0 + 5,0620322
    assert r["condicional"].estadistico == pytest.approx(5.0620322, abs=1e-6)
    assert r["condicional"].p_valor == pytest.approx(np.exp(-5.0620322 / 2), abs=1e-7)   # χ²₂: e^(−x/2)


def test_christoffersen_sin_dependencia_da_cero():
    # 0,0,1,1,0,0,0,1,0,0 → n00=4, n01=2, n10=2, n11=1; π01 = 2/6 = π11 = 1/3 = π = 3/9 → LR_ind = 0
    r = christoffersen([0, 0, 1, 1, 0, 0, 0, 1, 0, 0], 0.3)
    assert r["independencia"].estadistico == pytest.approx(0.0, abs=1e-12)
    assert r["independencia"].p_valor == pytest.approx(1.0)


def test_diebold_mariano_sin_rezagos():
    # d = a − b = 1,2,3,4,5 ; d̄ = 3 ; γ0 = (4+1+0+1+4)/5 = 2
    # DM = 3 / √(2/5) = 4,7434165 ; HLN (h=1): √((5+1−2)/5) = √0,8 → t = 4,2426407
    # p (una cola, H1: A peor... aquí se pide alternativa 'dos_colas'): 2·P(t₄ > 4,2426) = 0,013236
    a = np.array([2, 4, 6, 8, 10.0]); b = np.array([1, 2, 3, 4, 5.0])
    r = diebold_mariano(a, b, h=1, rezagos=0, alternativa="dos_colas")
    assert r.detalle["dm_sin_corregir"] == pytest.approx(4.7434165, abs=1e-6)
    assert r.estadistico == pytest.approx(4.2426407, abs=1e-6)
    assert r.p_valor == pytest.approx(0.013236, abs=1e-5)
    # Alternativa 'menor' (A mejor): con d̄ > 0 el p-valor es 1 − 0,013236/2
    assert diebold_mariano(a, b, h=1, rezagos=0).p_valor == pytest.approx(1 - 0.013236 / 2, abs=1e-5)


def test_diebold_mariano_con_un_rezago_bartlett():
    # e = d − d̄ = −2,−1,0,1,2 ; γ1 = [(−1)(−2) + 0(−1) + 1·0 + 2·1]/5 = 0,8
    # V = γ0 + 2·(1 − 1/2)·γ1 = 2 + 0,8 = 2,8 ; DM = 3/√(2,8/5) = 4,0089186
    # HLN con h=2: √((5+1−4+2·1/5)/5) = √0,48 = 0,6928203 → t = 2,7774602
    d = np.array([1, 2, 3, 4, 5.0])
    assert varianza_largo_plazo(d, 1) == pytest.approx(2.8)
    r = diebold_mariano(d, np.zeros(5), h=2, rezagos=1, alternativa="dos_colas")
    assert r.detalle["dm_sin_corregir"] == pytest.approx(4.0089186, abs=1e-6)
    assert r.estadistico == pytest.approx(2.7774602, abs=1e-6)


def test_diebold_mariano_detecta_mejor_modelo_y_no_inventa_diferencias():
    rng = np.random.default_rng(0)
    base = rng.gamma(2, 1, 2000)
    assert diebold_mariano(base * 0.9, base, h=1).p_valor < 0.01
    iguales = [diebold_mariano(rng.gamma(2, 1, 500), rng.gamma(2, 1, 500)).p_valor for _ in range(400)]
    assert 0.02 < np.mean(np.array(iguales) < 0.05) < 0.09        # tamaño ≈ 5 % bajo H0
