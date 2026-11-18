# Motor conjunto (M2): la TRM frente al motor evaluado

**No es asesoría financiera**; los rangos describen incertidumbre estadística, no promesas.

**Etiqueta de todas las cifras del motor conjunto: motor conjunto, sin evaluación fuera de muestra hasta M3.** No es el motor evaluado en la
prueba final: no incluye la banda cambiaria colombiana y nunca se evaluó fuera de muestra.

## 1. Qué se compara

- **Motor evaluado** (`bootstrap_est_filtrado`, `montecarlo.simular`): remuestrea toda la historia de la TRM,
  banda incluida (desde 1991). Es el que se evaluó en la prueba final.
- **Motor conjunto** (`bootstrap_est_filtrado`, `conjunto.simular_conjunto`): simula la TRM y cada «USD por
  X» con una sola secuencia de índices de bloque, desde la muestra común de las siete divisas
  (USD, EUR, MXN, JPY, CNY, CHF, BRL): del 2005-07-23 al 2026-11-14. Los cruces X/COP salen de
  multiplicar, así que la triangulación es exacta en cada trayectoria.

Mismo origen (2026-11-14, TRM 3.316,70 COP `#53a156ef02`), mismas trayectorias
(10.000) y misma semilla (20240501). Solo se muestran cifras de la TRM.

| | Motor evaluado | Motor conjunto |
|---|---:|---:|
| Rendimientos que remuestrea | 8.386 obs. `#40de16b56b` | 5.032 obs. `#fd2a36f9fb` |
| Longitud media de bloque | 25,2 días `#cca29069c7` | 8,9 días `#23f83dde8e` |
| σ diaria prevista en el origen | 0,739 % diario `#821d4d38a1` | 0,739 % diario `#293d7f92c2` |
| Deriva con que entra la muestra | 0,0358 % diario `#cb5737f707` | 0,0110 % diario `#034e642da9` |

## 2. TRM proyectada (COP por USD)

Respaldo: motor evaluado, límites: cobertura del 95 % evaluada en la prueba final (`data/respaldo/prueba_final.json`); mediana: sin respaldo fuera de muestra. Motor conjunto, **sin evaluación fuera de muestra hasta M3**.

| h (días con TRM) | Evaluado: mediana | Evaluado: banda del 95 % | Conjunto: mediana | Conjunto: banda del 95 % | Mediana, conjunto vs evaluado | Ancho de banda, conjunto / evaluado |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3.317 `#8edcacf300` | 3.270 `#63cc47ff00` – 3.372 `#8f50808274` | 3.316 `#1704251e39` | 3.269 `#c8eed1ff0b` – 3.371 `#cc48fcc76b` | -0,0 % `#b9cbf3df77` | 1,00 veces `#e7593c0199` |
| 5 | 3.320 `#ad3b3d29da` | 3.199 `#00cba53d28` – 3.471 `#2f1b0e703f` | 3.314 `#a92b214056` | 3.200 `#85a8d938ae` – 3.459 `#67dd3a736d` | -0,2 % `#f23e33e250` | 0,95 veces `#36634e4c7c` |
| 21 | 3.339 `#8473e188f7` | 3.084 `#8892fc1692` – 3.667 `#ffcbb960fe` | 3.316 `#2077672983` | 3.070 `#a691cba2c6` – 3.640 `#c1a71dbbdf` | -0,7 % `#155910d0b4` | 0,98 veces `#1cafa167b6` |
| 63 | 3.385 `#1d01df5f00` | 2.912 `#3ad256f9e1` – 4.022 `#a9d2f010ad` | 3.329 `#2f69fa2872` | 2.892 `#b40f827a5d` – 3.893 `#c0962f0460` | -1,7 % `#3064007a72` | 0,90 veces `#63a05f5b3d` |
| 126 | 3.458 `#6d405a9d75` | 2.798 `#b773faa550` – 4.399 `#996487f7c9` | 3.354 `#e928cb93df` | 2.720 `#e4b45ed2ad` – 4.204 `#b19a4e6527` | -3,0 % `#ff80c09d60` | 0,93 veces `#0c07ab4dae` |
| 252 | 3.622 `#d0c4c32f11` | 2.664 `#1f9f6959d9` – 5.057 `#3eb5c571ea` | 3.390 `#3ba1483eb9` | 2.516 `#b8b63eb804` – 4.641 `#ae61158d73` | -6,4 % `#576c4f4a98` | 0,89 veces `#b46783790e` |

## 3. Por qué difieren

La diferencia sale de la muestra, no del método: los dos son el mismo bootstrap estacionario
filtrado. El conjunto usa solo las fechas comunes con las seis series H.10 (un rendimiento puede
abarcar un festivo de EE. UU.) y su longitud de bloque se estima en esa muestra. El motor evaluado remuestrea también 1991-2005, con la banda cambiaria; el análisis
posterior de F5b (`reports/compra_dolares.md`) mostró que la deriva de la banda entra al motor
amplificada unas 2,1 veces. La fila «deriva con que entra la muestra» es esa cantidad para cada
motor (media del choque estandarizado por σ de largo plazo). Las bandas también cambian con la
longitud de bloque y con la σ de largo plazo de cada muestra.

## 4. Lo que este reporte no muestra

- Ninguna cifra de EUR, MXN, JPY, CNY, CHF ni BRL. Desde 2020 sus valores no se muestran hasta
  el prerregistro de M3, y el motor conjunto no tiene evaluación fuera de muestra.
- La sensibilidad con la mediana de las longitudes de bloque (`bloque="mediana"`): depende de las
  series de las divisas nuevas hasta el origen y se reportará en M3.

## Reproducir

```
PYTHONPATH=src python -m laboratorio.reportes.m2_conjunto --trayectorias 10000 --semilla 20240501
```

## Apéndice: fuente y hash de cada cifra

| Cifra | Origen | Fuente / fórmula | Hash SHA-256 |
|---|---|---|---|
| `#53a156ef02` | calculo | TRM en el origen (2026-11-14) | `53a156ef02916ab21d7cda76de1b9595aedce4d36994eb531d928b72fbfc9aa1` |
| `#c8eed1ff0b` | calculo | TRM, percentil 2.5 a 1 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `c8eed1ff0b84d45bd416006f8eee00b9a70084604ad06f6edf86ee7a0a2cc535` |
| `#63cc47ff00` | calculo | TRM, percentil 2.5 a 1 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `63cc47ff0027933bcbd161a89782f2f7160c8f58394c56ebbd393f48779a4574` |
| `#e4b45ed2ad` | calculo | TRM, percentil 2.5 a 126 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `e4b45ed2ad71b58f76812c5438bb21602ad94f68902bda2dd2635bc1af594f0a` |
| `#b773faa550` | calculo | TRM, percentil 2.5 a 126 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `b773faa550cab4b808946e3f3a4ecd944b3f52184a470b4461f70b9d3c03fad9` |
| `#a691cba2c6` | calculo | TRM, percentil 2.5 a 21 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `a691cba2c62a679fe817481c7efaf1f3892c8e487788173d8b72552c8c1907cb` |
| `#8892fc1692` | calculo | TRM, percentil 2.5 a 21 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `8892fc1692c027a7538dd4f2f50ab7922d04d7a5c6895945de24cbd774cc787e` |
| `#b8b63eb804` | calculo | TRM, percentil 2.5 a 252 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `b8b63eb804302bf75900de76df1d7a1acc45c84fad2f206676d8b1afc801c887` |
| `#1f9f6959d9` | calculo | TRM, percentil 2.5 a 252 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `1f9f6959d96711008c7312c00cb97820d5bfd01246ba75679f8cd70dd11b5fbb` |
| `#85a8d938ae` | calculo | TRM, percentil 2.5 a 5 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `85a8d938aebf7d4b21278bc11bfc439108015e2ab2effdd436c4a993db9cccee` |
| `#00cba53d28` | calculo | TRM, percentil 2.5 a 5 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `00cba53d2818dbd3a2ea5d095a79b7e7257f885c4d39ac3a2c563c6693e79b56` |
| `#b40f827a5d` | calculo | TRM, percentil 2.5 a 63 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `b40f827a5d3d3a0705d57c4535a98176a4a6dbd14a9dc386f00c8a9ae2a5179e` |
| `#3ad256f9e1` | calculo | TRM, percentil 2.5 a 63 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `3ad256f9e1936ad95daf0b6053f529a78f6864447214bf27eac93d87d5ccbcad` |
| `#1704251e39` | calculo | TRM, percentil 50 a 1 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `1704251e391ac4ee529f2e09d010c2510711cd8b146d5a7b851e4e1ecda55355` |
| `#8edcacf300` | calculo | TRM, percentil 50 a 1 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `8edcacf300d8197d4780939b68754248d75de6b491bbf6ba0f297f662c2026d0` |
| `#e928cb93df` | calculo | TRM, percentil 50 a 126 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `e928cb93dfd44905f5f5ac8393b65fd1f78799800b86beeb3cbebd4ac7474fb6` |
| `#6d405a9d75` | calculo | TRM, percentil 50 a 126 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `6d405a9d759388528a866087b4d33e7ef554c7ca00291c30f6c66163aa2becc0` |
| `#2077672983` | calculo | TRM, percentil 50 a 21 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `2077672983676cd01dfaa2c46a38e87a3062fb5305fc526f04a42fccb281c4d8` |
| `#8473e188f7` | calculo | TRM, percentil 50 a 21 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `8473e188f78ab0b92c69062302be7b1372151288b1f98292e3713da222c74594` |
| `#3ba1483eb9` | calculo | TRM, percentil 50 a 252 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `3ba1483eb94e02934cdaae67d0f50e32f6f0ae8aefe2fb6c85835dc3c8f9f5ef` |
| `#d0c4c32f11` | calculo | TRM, percentil 50 a 252 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `d0c4c32f111e8cb69cbf442ff231fdb60c3d17644e7892154e4750208ad37ebc` |
| `#a92b214056` | calculo | TRM, percentil 50 a 5 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `a92b2140565abec42f5e372d6f1c6f7eb11f65a8ff2e12edca5c8c01adefadf8` |
| `#ad3b3d29da` | calculo | TRM, percentil 50 a 5 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `ad3b3d29da42c5507d21b72dd8f8762518edf983311bfc935c577f87cf7370fa` |
| `#2f69fa2872` | calculo | TRM, percentil 50 a 63 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `2f69fa2872ff908a29db8b57a7c0795f22484692ccfa551cc894c5c8b0a0c4d7` |
| `#1d01df5f00` | calculo | TRM, percentil 50 a 63 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `1d01df5f0063d99fea735bd2c306227349c82c8bcfe6e7869dc6f60e56703033` |
| `#cc48fcc76b` | calculo | TRM, percentil 97.5 a 1 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `cc48fcc76b7db108d29ff2f8a3d40a3c6f159c2663874765dc676b3c80453096` |
| `#8f50808274` | calculo | TRM, percentil 97.5 a 1 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `8f5080827401da07c0e34507b862fa8650a791e73caf7aa5230240ff8186679a` |
| `#b19a4e6527` | calculo | TRM, percentil 97.5 a 126 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `b19a4e65272de4900263ebacda7f6dee266a3f1c1a958453a6c9b0e67950c112` |
| `#996487f7c9` | calculo | TRM, percentil 97.5 a 126 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `996487f7c9fab86ffb5bb0ccdb7bf62693dc8806ccaae7a1562c669f252360db` |
| `#c1a71dbbdf` | calculo | TRM, percentil 97.5 a 21 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `c1a71dbbdf6f9f1a186e970cdad3cb55fb8bf2d8b44b2a1e8e821521a0ec1509` |
| `#ffcbb960fe` | calculo | TRM, percentil 97.5 a 21 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `ffcbb960fecfa0811eef8041f2ab214d10ebbdb57987ae55839f6eddc858f932` |
| `#ae61158d73` | calculo | TRM, percentil 97.5 a 252 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `ae61158d7372b697b9df8e2acfd1250eeab45cab27aaa8d30c7aa051f3cad2ad` |
| `#3eb5c571ea` | calculo | TRM, percentil 97.5 a 252 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `3eb5c571eae3543dc340d4921adb083ef1e68a5fe19b2c46e43b175f98f06cb6` |
| `#67dd3a736d` | calculo | TRM, percentil 97.5 a 5 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `67dd3a736d5083e1aa34d1f9cda27b7dbd84a58c11782a8ddf82822cc8c1f506` |
| `#2f1b0e703f` | calculo | TRM, percentil 97.5 a 5 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `2f1b0e703f7a4a281b3f385f76d337f3dea667d7e78c092d6784b79c973e3aa9` |
| `#c0962f0460` | calculo | TRM, percentil 97.5 a 63 pasos, motor conjunto, sin evaluación fuera de muestra hasta M3 (bootstrap_est_filtrado, muestra común de USD, EUR, MXN, JPY, CNY, CHF, BRL), 10000 trayectorias, semilla 20240501 | `c0962f0460efdbd4c8d38b1f1363a1fa56458b97f77edbebf7f8ba0fbeb5b268` |
| `#a9d2f010ad` | calculo | TRM, percentil 97.5 a 63 pasos, motor evaluado (bootstrap_est_filtrado, toda la historia), 10000 trayectorias, semilla 20240501 | `a9d2f010ad547ff62153ccfccc323dbafcb7551a960d9d2b9da8c647c1d0bc06` |
| `#e7593c0199` | calculo | ancho de la banda del 95 % a 1 pasos, conjunto / evaluado | `e7593c01994892c210c91655f0ef667477b5709d285ab2ebbfe19cd900c7b4d7` |
| `#0c07ab4dae` | calculo | ancho de la banda del 95 % a 126 pasos, conjunto / evaluado | `0c07ab4daee26c5ee61fa6003a5758e074fb5f42772dd78325cbf998ea23ae65` |
| `#1cafa167b6` | calculo | ancho de la banda del 95 % a 21 pasos, conjunto / evaluado | `1cafa167b614980576814536f8a43a4e2a6b2afbd14ebf980bd1f40c645c8813` |
| `#b46783790e` | calculo | ancho de la banda del 95 % a 252 pasos, conjunto / evaluado | `b46783790e5c3b365574b186374ddc2884577f25e24cfd0a61a0d7b57953c0fb` |
| `#36634e4c7c` | calculo | ancho de la banda del 95 % a 5 pasos, conjunto / evaluado | `36634e4c7c01676730b7f2b4914caa245fe4504f979fa15a5bbe71fcb4673592` |
| `#63a05f5b3d` | calculo | ancho de la banda del 95 % a 63 pasos, conjunto / evaluado | `63a05f5b3d8a7bda702a4a9608b9e8a3b712f4f35057097f9f45429dab3411a6` |
| `#b9cbf3df77` | calculo | diferencia de la mediana a 1 pasos, conjunto vs evaluado | `b9cbf3df77f0d941bfc7484c2bb6718839877894300dec87f6df6a2efd3e7b78` |
| `#ff80c09d60` | calculo | diferencia de la mediana a 126 pasos, conjunto vs evaluado | `ff80c09d607c63b4ac95c6b2db861d7abe6f98eef3fa973a4380c23175d37c44` |
| `#155910d0b4` | calculo | diferencia de la mediana a 21 pasos, conjunto vs evaluado | `155910d0b4c0638355acb8a897756ecbd7271d2aa5ad5b0990f5573053158a03` |
| `#576c4f4a98` | calculo | diferencia de la mediana a 252 pasos, conjunto vs evaluado | `576c4f4a981e89b79cc924c299b6d6849c986d4890419ab214f0c9b2bdd45430` |
| `#f23e33e250` | calculo | diferencia de la mediana a 5 pasos, conjunto vs evaluado | `f23e33e250d7f8197c109e8389c5931a158dda688424fd2303d498a8dafafcc0` |
| `#3064007a72` | calculo | diferencia de la mediana a 63 pasos, conjunto vs evaluado | `3064007a72e0318f9423908250220b7be55fad5df59311eaabad2be2355e9d9c` |
| `#fd2a36f9fb` | calculo | fechas comunes que remuestrea el motor conjunto, sin evaluación fuera de muestra hasta M3 | `fd2a36f9fba1cc09ab53643a55b8d80dbc5e2f829c1826824651c1af7a84c918` |
| `#23f83dde8e` | calculo | longitud media de bloque común: Politis-White de la TRM en la muestra común | `23f83dde8e7dd96ff396c7d031fab051ff1af1931b3ea0ab21df3447626561bf` |
| `#cca29069c7` | calculo | longitud media de bloque, motor evaluado (Politis-White, toda la historia) | `cca29069c72139aeaaa945dcdf6f725f3f0708e191b7f0bd9b2a28171ef3ed14` |
| `#034e642da9` | calculo | media de z de la TRM en la muestra común × σ de largo plazo, motor conjunto, sin evaluación fuera de muestra hasta M3 | `034e642da9e0c3bf6752cf64687c382404c836e2e259a9c3c6673b903f68575b` |
| `#cb5737f707` | calculo | media de z de toda la historia × σ de largo plazo, motor evaluado | `cb5737f707427b4a8ac57156a3ff1ba8c581cdd00138981dddc2018eafc063bb` |
| `#40de16b56b` | calculo | rendimientos de la TRM que remuestrea el motor evaluado | `40de16b56b6399c39fba2810b1dee8674080418e799473825a99839ce4714e22` |
| `#293d7f92c2` | calculo | σ EWMA de la TRM prevista en el origen, muestra común | `293d7f92c20b2422599ac1654597c8de98bb4b26b5cc443e2714421ef044aa20` |
| `#821d4d38a1` | calculo | σ EWMA prevista en el origen, motor evaluado | `821d4d38a17660f83fc2c96353e920a563ddc98c9961beb8f8614264d2fc5f17` |
