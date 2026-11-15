# Caso: compra de dólares para una meta — comprar hoy vs. compras escalonadas

Reporte generado por `python -m laboratorio.motor compra_dolares`. Los rangos describen
incertidumbre histórica; no son pronóstico ni asesoría financiera. Cada cifra termina en un
código `#hash` que remite al apéndice con su fuente y su hash SHA-256.

## Planteamiento

- Meta: 10.000 USD `#8397039538`. Plan A: comprarlos todos hoy. Plan B: 12 `#b3a2ac0f21` compras
  iguales, una cada 1 `#e8f3aef896` mes(es), la primera hoy.
- TRM de hoy (2026-11-14 `#a5fb52d5f6`): 3.316,70 COP/USD `#ac9d82649e`.
- Costo del Plan A (cierto): 33.167.000 COP `#bcc9c6d182`. Presupuesto: 34.825.350 COP `#9e8597da5c`
  (costo de comprar hoy más un margen de 5,0 % `#61136fa9f8`).
- Las cifras de meta, número de compras, margen y ventanas son valores ilustrativos del autor.

## 1. Escenarios deterministas del Plan B

La TRM sigue `TRM0·exp(g·m/12)`; g (logarítmica anual) toma los percentiles 5, 50 y 95 de la
variación anual observada desde la flotación. Diferencia = costo de B menos costo de A (positivo = B más caro).

| Escenario | Deriva anual g | Costo Plan B | Costo medio | Diferencia vs. A | ¿Se pasa del presupuesto? |
|---|---:|---:|---:|---:|---|
| Optimista | -0,1804 `#4f72a5af0e` | 30.576.089 COP `#74e6cef07d` | 3.057,61 COP/USD `#6c3fe66e33` | -2.590.911 COP `#af7626ded0` | No `#c20c4b5ae2` |
| Base | 0,0145 `#9055dd1622` | 33.388.447 COP `#4ecc594836` | 3.338,84 COP/USD `#4ef718cbbf` | 221.447 COP `#ff69fa5242` | No `#a0818850a9` |
| Estrés | 0,2566 `#4b75c3bec3` | 37.408.078 COP `#90f47bdfd2` | 3.740,81 COP/USD `#36e7807a2f` | 4.241.078 COP `#86d2b88bd7` | Sí `#746c357c7e` |

## 2. Reproducción histórica con nombre

Se aplican al Plan B, desde la TRM de hoy, los movimientos reales de cada ventana.

| Ventana | Inicio | Fin | TRM fin / TRM inicio | Costo Plan B | Diferencia vs. A | ¿Se pasa? |
|---|---|---|---:|---:|---:|---|
| Año 2015 | 2015-01-02 `#70cff49fb1` | 2015-12-02 `#88be7f0d0f` | 1,309 `#a2f36a27c8` | 37.574.195 COP `#4328d795ce` | 4.407.195 COP `#4796a6e03e` | Sí `#aa3d2d39c2` |
| Fin de 2022 | 2022-10-03 `#74bb16f98f` | 2023-09-03 `#b816d0365c` | 0,885 `#ecb3c57cf2` | 32.896.331 COP `#0aea3f60d0` | -270.669 COP `#0ec85949f2` | No `#e6f1919d87` |

## 3. Todas las ventanas históricas del régimen de flotación

Hay 6.243 `#397a9593d2` ventanas de inicio. La más barata empieza el 2009-02-25 `#eda09685c2`
y la más cara el 2008-06-19 `#b83b928b2b`. Se traslapan: equivalen a solo
29 `#181604e73f` ventanas sin traslape, así que los percentiles extremos
descansan en pocos episodios.

| Medida del Plan B | Valor | Diferencia vs. A |
|---|---:|---:|
| Costo esperado (media) | 33.660.196 COP `#eeb75ecf7b` | 493.196 COP `#36dfa5f819` |
| Mediana | 33.482.930 COP `#4bb0a8601f` | |
| Percentil 5 | 30.234.177 COP `#cd85d2879a` | |
| Percentil 95 | 38.822.363 COP `#aa745b31ec` | 5.655.363 COP `#ec552e8bb7` |
| Mínimo | 27.040.921 COP `#0d877ee4f5` | |
| Máximo | 43.559.893 COP `#d9066ae016` | |
| Probabilidad de superar el presupuesto | 25,5 % `#fd7ded8225` | |
| Probabilidad de salir más barato que comprar hoy | 44,0 % `#ab4c750b5d` | |

## Limitaciones

- No se modela el rendimiento del dinero mientras espera (costo de oportunidad ni tasas COP/USD).
- La distribución usa solo el pasado del régimen de flotación y supone que se repetirá; los
  episodios no vistos (ni su magnitud) no están incluidos.
- Los percentiles extremos dependen de pocos episodios (ver ventanas sin traslape).
- La TRM es la de la Superfinanciera (una fila por vigencia); el precio real de compra
  incluye comisiones y diferencial que no se modelan.

## Ficha de la corrida

- Corrida: `d6f052613b7a`; caso `compra_dolares`; semilla: ninguna (cálculo determinista).
- Hash de datos `b53d48c551ce32e1389473b63483c09efa8ae7140d299c559deb97ea25b310d6`
- Hash de supuestos `e26cfb6730179e94360fdf1f59c77945de48ea6950a79c7d7355c9e4abb2e912`
- Hash de código `8ac96d6514444c1f97217fedc50fa61bf2c8cd8a5dd1c652cf542d839e192aa9`
- Hash de entrada `d6f052613b7ab7826164634b522533d89110451b6d9daab37af7992294134842`
- Hash de resultado `dab321a52e99398326b9aa307dc540e2c5c3bc748e4e5fe2887890af41f75722`

## Apéndice: fuente y hash de cada cifra

| Cifra | Origen | Fuente / fórmula | Hash SHA-256 |
|---|---|---|---|
| `#ab4c750b5d` | calculo | 100 × fracción de ventanas con costo < costo hoy | `ab4c750b5da2956d4e0811415cba2e6128675756d07c1040ed85387c6bfa3b50` |
| `#fd7ded8225` | calculo | 100 × fracción de ventanas con costo > presupuesto | `fd7ded8225cdc21d7d449139499f6a483c1f8f328f320a2074734d983c8da7d2` |
| `#a2f36a27c8` | calculo | TRM(inicio + horizonte) / TRM(inicio) | `a2f36a27c80cade8ffa6fee92d6966db3e333db4178c22398c89023a537fd72f` |
| `#ecb3c57cf2` | calculo | TRM(inicio + horizonte) / TRM(inicio) | `ecb3c57cf29270d201de3f17ce269daf27d36bfb36f2c17bdb2b26bdeabbfd02` |
| `#6c3fe66e33` | calculo | costo / meta_usd | `6c3fe66e33cb3ab867a5169fd8d92eb4bacba3393a9fdaec54af1908b03a7aad` |
| `#4ef718cbbf` | calculo | costo / meta_usd | `4ef718cbbf2447a74d60c0738e565b44863ba9a3b02c60cbe857a5d2d27eb723` |
| `#36e7807a2f` | calculo | costo / meta_usd | `36e7807a2f9dcdf5e60227814b2e621d3f059b63c6d6d9d6569fe391a3699a6a` |
| `#c20c4b5ae2` | calculo | costo > presupuesto | `c20c4b5ae2f93262a5e26d1029d82d4aa92edc65613e7129ac4379f209d815ef` |
| `#a0818850a9` | calculo | costo > presupuesto | `a0818850a967d8ec13a12d1b051d4388cb0e807871e019e79cde334083a45f54` |
| `#746c357c7e` | calculo | costo > presupuesto | `746c357c7e8030ed3f40305fdd58bcc392df96a9d136e7bc3c55b1a17d0ec0a8` |
| `#aa3d2d39c2` | calculo | costo > presupuesto | `aa3d2d39c29a1e1e35d3ea8d53a865f546a7e2b3dd1c1c01a18525255ccce8de` |
| `#e6f1919d87` | calculo | costo > presupuesto | `e6f1919d8744fe161fce2abdef6e4cf1fafd53985e2a1f8cea99e0614233f00b` |
| `#af7626ded0` | calculo | costo escalonado − costo hoy | `af7626ded0b0393852cf523ca6db0817ed07c22681c243a68adba1ed439a4e2f` |
| `#ff69fa5242` | calculo | costo escalonado − costo hoy | `ff69fa5242a5b376a90830a2e1d887b9df2926864f7bc775c1f7d9bdecd55194` |
| `#86d2b88bd7` | calculo | costo escalonado − costo hoy | `86d2b88bd752e6e3cafb03c773ff04b05262e628bbde7dfd5b8e5087608b0077` |
| `#4796a6e03e` | calculo | costo escalonado − costo hoy | `4796a6e03e909f700a67d8ebf3b95f96e8ff4fe39410c77e39ac536864bcb648` |
| `#0ec85949f2` | calculo | costo escalonado − costo hoy | `0ec85949f2ca379ea5c0d8a72749f255dd0678ffa5ac6de164f30b4d880cd6cd` |
| `#36dfa5f819` | calculo | costo esperado escalonado − costo hoy | `36dfa5f819e06c01ab3a532f90d09eefe817161cf926cbf44a011d75f4812694` |
| `#9e8597da5c` | calculo | costo_hoy × (1 + margen/100) | `9e8597da5c7021daf7efb682d058be7efe9495c3dcb269d4f44c10dc9daa74b0` |
| `#a5fb52d5f6` | calculo | fecha de la TRM de hoy | `a5fb52d5f6c99be5e5ca776dd85a16f84214b8c3090350c00dfb9152ae8382f6` |
| `#88be7f0d0f` | calculo | inicio + horizonte del plan | `88be7f0d0f15ce7b8baf20feb551703a7485694bbf798632054958e48d043734` |
| `#b816d0365c` | calculo | inicio + horizonte del plan | `b816d0365c319d929b7c991841e7271c30a79085ccfec23117d61f069e214552` |
| `#b83b928b2b` | calculo | inicio de la ventana de mayor costo | `b83b928b2bb60db154903a4fe7baa1985d64c80e90770815609c70c99271f180` |
| `#eda09685c2` | calculo | inicio de la ventana de menor costo | `eda09685c2ae227350bb424605f3ea6804227b55460e6783e493c91bbfd420a0` |
| `#eeb75ecf7b` | calculo | media del costo en todas las ventanas | `eeb75ecf7bf90947f607a43665f11d4b5f1f0fd58c94db47bb1632a98fc4c80d` |
| `#181604e73f` | calculo | meses cubiertos / horizonte (ventanas sin traslape) | `181604e73ffafbd833606330eac16d80bb2aeec2a2c90c2fff2cba21e43fe118` |
| `#bcc9c6d182` | calculo | meta_usd × TRM_hoy | `bcc9c6d182f42b358cb4d5b1e1a5d97cb41ac5a5529c9e9c785e62521e66b0e7` |
| `#d9066ae016` | calculo | máximo del costo | `d9066ae016bd23a88844b437a20a2a5e58dd3075d272b1a260aeb9197ff7ae36` |
| `#0d877ee4f5` | calculo | mínimo del costo | `0d877ee4f5f1f6a6f3bc2ed50eed8d80a84cde1893ef65ba092e4267dab9accc` |
| `#397a9593d2` | calculo | número de fechas de inicio con ventana completa | `397a9593d212c419d51c53438b9f897bb2a437f576026404f0a6a85009801501` |
| `#cd85d2879a` | calculo | percentil 5 del costo | `cd85d2879a0362415a8fb863203021f2963c567390faab3e8bde38b9bb9749b1` |
| `#4bb0a8601f` | calculo | percentil 50 (mediana) del costo | `4bb0a8601ffdbcebac527288b8fe2caa6700edca12d5c137c57f8184ad86451a` |
| `#aa745b31ec` | calculo | percentil 95 del costo | `aa745b31ec1fbfdb65c9432806ec940bfc74956f0ec8be86a94ff8de8aeae78e` |
| `#ec552e8bb7` | calculo | percentil 95 escalonado − costo hoy | `ec552e8bb77adc4266db188dc8cf37d3256457ab7ce841353545a46b4def2d17` |
| `#4328d795ce` | calculo | Σ (meta/n)·TRM_hoy·TRM(inicio+m_i)/TRM(inicio) | `4328d795ce8a7b129adc720b48e0d82358a543cb98c78c4f07c0e130c37c35be` |
| `#0aea3f60d0` | calculo | Σ (meta/n)·TRM_hoy·TRM(inicio+m_i)/TRM(inicio) | `0aea3f60d07d4e32720649ddebe75fd3580fc38d10a2c109df457eaa03525022` |
| `#74e6cef07d` | calculo | Σ (meta/n)·TRM_hoy·exp(g·m_i/12), m_i = i·intervalo | `74e6cef07d52f84497c5cc55d570e8ce4b1ddf5e135acf08a89e09546d8f3d08` |
| `#4ecc594836` | calculo | Σ (meta/n)·TRM_hoy·exp(g·m_i/12), m_i = i·intervalo | `4ecc594836c49cc675dcad898b06d65c15c01f9da34c7fbb4305c0817394f076` |
| `#90f47bdfd2` | calculo | Σ (meta/n)·TRM_hoy·exp(g·m_i/12), m_i = i·intervalo | `90f47bdfd2cfc554f54b9bf57c900e4505cf64845497b1c927dfad23c2ff2ae7` |
| `#ac9d82649e` | dato | processed/trm.csv#fecha=2026-11-14;columna=trm | `ac9d82649e85a0c41efb9bb796da93650898c8a971f2b2614f424c5ccf9a6497` |
| `#e8f3aef896` | supuesto | caso.intervalo_meses@v1 | `e8f3aef89601ce0e8df6a0a123d7c41fe964a14a55dcc39543348667e548b0f6` |
| `#8397039538` | supuesto | caso.meta_usd@v1 | `8397039538ed21d4d3ef2ee2a37b8de2af6dbf38b4bed9a013cd92b85959ab0d` |
| `#b3a2ac0f21` | supuesto | caso.n_compras@v1 | `b3a2ac0f2109f278f71f2d65004c8cfbfcc40fc1d5637f8b20e2c5978e6f11e7` |
| `#61136fa9f8` | supuesto | caso.presupuesto_margen_pct@v1 | `61136fa9f8245b920d937de94d6bffb8d6c215415b83e6fd10360958cacc2156` |
| `#70cff49fb1` | supuesto | historica.ventana.2015@v1 | `70cff49fb1706bed7f9ef876a595d27e1e81a47a62e80e07af83a7b6346677a2` |
| `#74bb16f98f` | supuesto | historica.ventana.fin_2022@v1 | `74bb16f98f15542d5937d1710a9459778cbc0c7fd09cdee34f833fdb5096adfd` |
| `#9055dd1622` | supuesto | trm.deriva_anual_log.base@v1 | `9055dd16227c7dd045926bb9fa285b40ffde0d7d40d766daf5afe925a24b3fcb` |
| `#4b75c3bec3` | supuesto | trm.deriva_anual_log.estres@v1 | `4b75c3bec392b3dd1ef07bc94ba97a4dd355925c0113579bf36608706fe48216` |
| `#4f72a5af0e` | supuesto | trm.deriva_anual_log.optimista@v1 | `4f72a5af0ee7416979e60dd0a488d14fe714dc2db2a590d6843ac7092415ca13` |
