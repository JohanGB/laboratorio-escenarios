# Fase 2 — Comparación de modelos (backtest de desarrollo)

Distribuciones de pronóstico del rendimiento logarítmico de la TRM a h observaciones (días de mercado). Los rangos describen incertidumbre estadística; no son recomendaciones financieras.

## Protocolo

- Orígenes: 2005-01-04 a 2019-09-26 (3493 por horizonte); inicio de desarrollo 2005-01-03. La prueba final (desde 2020-01-01) NO se cargó.
- Ventana expansiva, reajuste cada 21 orígenes (LightGBM cada 63), purga s+h ≤ t, embargo de 63 obs.
- CRPS aproximado por 11 cuantiles (0,01–0,99), en puntos porcentuales de rendimiento log; menor es mejor. IS95 = puntaje de intervalo del 95 %. cob = cobertura observada.
- **Criterio de descarte** (fijado antes de correr): en cada horizonte la referencia es la mejor línea base (caminata aleatoria, simulación histórica 756 obs., simulación histórica ponderada λ=0,994). Un candidato *supera* si su CRPS medio es menor y Diebold-Mariano unilateral (HAC, corrección HLN) da p < 0,05; si no, queda **descartado** en ese horizonte. Global: descartado si no supera en ningún horizonte.
- Los orígenes se traslapan para h>1: las coberturas a h=21 y 63 tienen pocas observaciones independientes (≈ n/h) y su error estándar es grande.

## Resumen por modelo

| modelo | tipo | supera en h | estado | segundos | fallos de estimación |
|---|---|---|---|---|---|
| caminata_aleatoria | línea base | — | línea base | 0.7 | 0 |
| egarch_t | candidato | 1 | **SUPERA** | 70.9 | 0 |
| ewma_0.94 | candidato | 1 | **SUPERA** | 0.6 | 0 |
| garch_t | candidato | 1 | **SUPERA** | 88.2 | 38 |
| gjr_t | candidato | 1 | **SUPERA** | 59.1 | 28 |
| lightgbm_cuantiles | candidato | 1 | **SUPERA** | 208.0 | 0 |
| reg_cuantiles | candidato | 1 | **SUPERA** | 598.9 | 0 |
| sim_hist_756 | línea base | — | línea base | 1.4 | 0 |
| sim_hist_pond | línea base | — | línea base | 6.5 | 0 |

## Horizonte h = 1

### Muestra completa

| modelo | CRPS | pinball | IS95 | cob90 | cob95 | cob98 | CRPS/base | DM p | estado |
|---|---|---|---|---|---|---|---|---|---|
| lightgbm_cuantiles | 0.3593 | 0.1077 | 3.405 | 0.880 | 0.932 | 0.966 | 0.963 | <0,001 | supera |
| reg_cuantiles | 0.3612 | 0.1090 | 3.544 | 0.887 | 0.942 | 0.973 | 0.968 | <0,001 | supera |
| ewma_0.94 | 0.3660 | 0.1105 | 3.562 | 0.899 | 0.938 | 0.967 | 0.981 | <0,001 | supera |
| egarch_t | 0.3662 | 0.1101 | 3.472 | 0.883 | 0.942 | 0.982 | 0.982 | <0,001 | supera |
| garch_t | 0.3666 | 0.1102 | 3.473 | 0.870 | 0.932 | 0.973 | 0.983 | <0,001 | supera |
| gjr_t | 0.3666 | 0.1102 | 3.474 | 0.871 | 0.930 | 0.973 | 0.983 | <0,001 | supera |
| sim_hist_pond *(línea base)* | 0.3730 | 0.1150 | 3.945 | 0.896 | 0.949 | 0.977 | — | — | — |
| caminata_aleatoria *(línea base)* | 0.3834 | 0.1243 | 4.989 | 0.831 | 0.879 | 0.912 | — | — | — |
| sim_hist_756 *(línea base)* | 0.3844 | 0.1216 | 4.491 | 0.879 | 0.934 | 0.965 | — | — | — |

Línea base de referencia en h=1: `sim_hist_pond`.

### Por régimen

| modelo | CRPS estres | cob95 estres | CRPS normal | cob95 normal | CRPS crisis_2008 | cob95 crisis_2008 | CRPS petroleo_2014_2015 | cob95 petroleo_2014_2015 |
|---|---|---|---|---|---|---|---|---|
| caminata_aleatoria | 0.6092 | 0.755 | 0.3455 | 0.899 | 0.8570 | 0.594 | 0.5244 | 0.810 |
| egarch_t | 0.5656 | 0.932 | 0.3327 | 0.943 | 0.7595 | 0.945 | 0.4992 | 0.928 |
| ewma_0.94 | 0.5623 | 0.934 | 0.3330 | 0.938 | 0.7639 | 0.945 | 0.4934 | 0.930 |
| garch_t | 0.5661 | 0.928 | 0.3331 | 0.932 | 0.7586 | 0.938 | 0.5002 | 0.925 |
| gjr_t | 0.5659 | 0.922 | 0.3331 | 0.932 | 0.7588 | 0.922 | 0.4999 | 0.922 |
| lightgbm_cuantiles | 0.5548 | 0.928 | 0.3265 | 0.932 | 0.7725 | 0.938 | 0.4802 | 0.925 |
| reg_cuantiles | 0.5598 | 0.918 | 0.3278 | 0.946 | 0.7995 | 0.883 | 0.4778 | 0.930 |
| sim_hist_756 | 0.6100 | 0.807 | 0.3466 | 0.955 | 0.8292 | 0.812 | 0.5350 | 0.805 |
| sim_hist_pond | 0.5769 | 0.890 | 0.3388 | 0.959 | 0.7868 | 0.906 | 0.5051 | 0.885 |

n por grupo: estres = 502, normal = 2991, crisis_2008 = 128, petroleo_2014_2015 = 374

## Horizonte h = 5

### Muestra completa

| modelo | CRPS | pinball | IS95 | cob90 | cob95 | cob98 | CRPS/base | DM p | estado |
|---|---|---|---|---|---|---|---|---|---|
| ewma_0.94 | 0.9465 | 0.2905 | 9.805 | 0.833 | 0.890 | 0.936 | 0.988 | 0.053 | **descartado** |
| reg_cuantiles | 0.9512 | 0.2908 | 9.683 | 0.870 | 0.929 | 0.974 | 0.993 | 0.189 | **descartado** |
| egarch_t | 0.9539 | 0.2936 | 9.928 | 0.824 | 0.901 | 0.958 | 0.996 | 0.300 | **descartado** |
| lightgbm_cuantiles | 0.9554 | 0.2897 | 9.329 | 0.853 | 0.920 | 0.963 | 0.998 | 0.379 | **descartado** |
| sim_hist_pond *(línea base)* | 0.9577 | 0.2955 | 10.121 | 0.889 | 0.941 | 0.971 | — | — | — |
| gjr_t | 0.9586 | 0.2976 | 10.355 | 0.798 | 0.880 | 0.941 | 1.001 | 0.544 | **descartado** |
| garch_t | 0.9588 | 0.2978 | 10.405 | 0.798 | 0.878 | 0.942 | 1.001 | 0.554 | **descartado** |
| sim_hist_756 *(línea base)* | 0.9809 | 0.3091 | 11.231 | 0.873 | 0.931 | 0.969 | — | — | — |
| caminata_aleatoria *(línea base)* | 0.9859 | 0.3255 | 13.666 | 0.779 | 0.834 | 0.882 | — | — | — |

Línea base de referencia en h=5: `sim_hist_pond`.

### Por régimen

| modelo | CRPS estres | cob95 estres | CRPS normal | cob95 normal | CRPS crisis_2008 | cob95 crisis_2008 | CRPS petroleo_2014_2015 | cob95 petroleo_2014_2015 |
|---|---|---|---|---|---|---|---|---|
| caminata_aleatoria | 1.6321 | 0.645 | 0.8775 | 0.866 | 1.9870 | 0.555 | 1.5107 | 0.676 |
| egarch_t | 1.5314 | 0.853 | 0.8570 | 0.909 | 1.8366 | 0.805 | 1.4269 | 0.869 |
| ewma_0.94 | 1.5161 | 0.845 | 0.8509 | 0.897 | 1.8326 | 0.859 | 1.4078 | 0.840 |
| garch_t | 1.5388 | 0.827 | 0.8614 | 0.887 | 1.8469 | 0.828 | 1.4334 | 0.826 |
| gjr_t | 1.5381 | 0.833 | 0.8613 | 0.888 | 1.8460 | 0.828 | 1.4327 | 0.834 |
| lightgbm_cuantiles | 1.4655 | 0.902 | 0.8698 | 0.923 | 1.7565 | 0.906 | 1.3658 | 0.901 |
| reg_cuantiles | 1.5058 | 0.894 | 0.8581 | 0.934 | 1.9074 | 0.797 | 1.3683 | 0.928 |
| sim_hist_756 | 1.5829 | 0.785 | 0.8799 | 0.955 | 1.8920 | 0.773 | 1.4771 | 0.789 |
| sim_hist_pond | 1.4956 | 0.871 | 0.8675 | 0.953 | 1.8077 | 0.867 | 1.3888 | 0.872 |

n por grupo: estres = 502, normal = 2991, crisis_2008 = 128, petroleo_2014_2015 = 374

## Horizonte h = 21

### Muestra completa

| modelo | CRPS | pinball | IS95 | cob90 | cob95 | cob98 | CRPS/base | DM p | estado |
|---|---|---|---|---|---|---|---|---|---|
| ewma_0.94 | 2.0864 | 0.6439 | 22.448 | 0.801 | 0.865 | 0.908 | 0.964 | 0.056 | **descartado** |
| egarch_t | 2.1250 | 0.6547 | 22.472 | 0.804 | 0.894 | 0.951 | 0.982 | 0.213 | **descartado** |
| garch_t | 2.1497 | 0.6743 | 24.534 | 0.764 | 0.853 | 0.933 | 0.994 | 0.390 | **descartado** |
| gjr_t | 2.1498 | 0.6739 | 24.442 | 0.765 | 0.856 | 0.933 | 0.994 | 0.391 | **descartado** |
| reg_cuantiles | 2.1567 | 0.6561 | 21.637 | 0.863 | 0.923 | 0.961 | 0.997 | 0.448 | **descartado** |
| sim_hist_pond *(línea base)* | 2.1634 | 0.6633 | 22.462 | 0.851 | 0.905 | 0.940 | — | — | — |
| caminata_aleatoria *(línea base)* | 2.1729 | 0.7168 | 30.162 | 0.743 | 0.807 | 0.864 | — | — | — |
| sim_hist_756 *(línea base)* | 2.1732 | 0.6763 | 22.986 | 0.859 | 0.913 | 0.951 | — | — | — |
| lightgbm_cuantiles | 2.2761 | 0.6864 | 21.792 | 0.830 | 0.891 | 0.944 | 1.052 | 0.976 | **descartado** |

Línea base de referencia en h=21: `sim_hist_pond`.

### Por régimen

| modelo | CRPS estres | cob95 estres | CRPS normal | cob95 normal | CRPS crisis_2008 | cob95 crisis_2008 | CRPS petroleo_2014_2015 | cob95 petroleo_2014_2015 |
|---|---|---|---|---|---|---|---|---|
| caminata_aleatoria | 3.9703 | 0.562 | 1.8712 | 0.848 | 4.6151 | 0.461 | 3.7496 | 0.596 |
| egarch_t | 3.7628 | 0.801 | 1.8501 | 0.909 | 4.2506 | 0.820 | 3.5959 | 0.794 |
| ewma_0.94 | 3.6909 | 0.771 | 1.8172 | 0.881 | 4.1359 | 0.859 | 3.5385 | 0.741 |
| garch_t | 3.8079 | 0.757 | 1.8713 | 0.869 | 4.2783 | 0.812 | 3.6469 | 0.738 |
| gjr_t | 3.8086 | 0.765 | 1.8714 | 0.871 | 4.2804 | 0.805 | 3.6471 | 0.751 |
| lightgbm_cuantiles | 3.7802 | 0.841 | 2.0236 | 0.900 | 4.4447 | 0.852 | 3.5528 | 0.837 |
| reg_cuantiles | 3.7564 | 0.835 | 1.8882 | 0.937 | 4.6390 | 0.750 | 3.4544 | 0.864 |
| sim_hist_756 | 3.6539 | 0.771 | 1.9247 | 0.937 | 4.2036 | 0.812 | 3.4657 | 0.757 |
| sim_hist_pond | 3.4920 | 0.847 | 1.9404 | 0.914 | 4.1407 | 0.922 | 3.2700 | 0.821 |

n por grupo: estres = 502, normal = 2991, crisis_2008 = 128, petroleo_2014_2015 = 374

## Horizonte h = 63

### Muestra completa

| modelo | CRPS | pinball | IS95 | cob90 | cob95 | cob98 | CRPS/base | DM p | estado |
|---|---|---|---|---|---|---|---|---|---|
| ewma_0.94 | 3.7942 | 1.2207 | 48.002 | 0.783 | 0.834 | 0.884 | 0.976 | 0.125 | **descartado** |
| egarch_t | 3.8343 | 1.2130 | 45.055 | 0.798 | 0.885 | 0.940 | 0.986 | 0.056 | **descartado** |
| caminata_aleatoria *(línea base)* | 3.8874 | 1.3148 | 58.950 | 0.745 | 0.805 | 0.852 | — | — | — |
| garch_t | 3.9015 | 1.2564 | 48.966 | 0.723 | 0.843 | 0.920 | 1.004 | 0.625 | **descartado** |
| gjr_t | 3.9044 | 1.2557 | 48.857 | 0.726 | 0.842 | 0.923 | 1.004 | 0.648 | **descartado** |
| sim_hist_756 *(línea base)* | 3.9691 | 1.2946 | 52.512 | 0.855 | 0.883 | 0.902 | — | — | — |
| sim_hist_pond *(línea base)* | 4.1729 | 1.3713 | 55.996 | 0.780 | 0.833 | 0.889 | — | — | — |
| reg_cuantiles | 4.2113 | 1.4035 | 59.474 | 0.867 | 0.912 | 0.934 | 1.083 | 0.965 | **descartado** |
| lightgbm_cuantiles | 4.4196 | 1.3618 | 46.002 | 0.787 | 0.880 | 0.933 | 1.137 | 0.995 | **descartado** |

Línea base de referencia en h=63: `caminata_aleatoria`.

### Por régimen

| modelo | CRPS estres | cob95 estres | CRPS normal | cob95 normal | CRPS crisis_2008 | cob95 crisis_2008 | CRPS petroleo_2014_2015 | cob95 petroleo_2014_2015 |
|---|---|---|---|---|---|---|---|---|
| caminata_aleatoria | 7.5198 | 0.490 | 3.2777 | 0.858 | 6.7346 | 0.531 | 7.7885 | 0.476 |
| egarch_t | 7.3229 | 0.669 | 3.2488 | 0.921 | 6.4319 | 0.836 | 7.6278 | 0.612 |
| ewma_0.94 | 7.2753 | 0.659 | 3.2099 | 0.863 | 6.3136 | 0.891 | 7.6044 | 0.580 |
| garch_t | 7.5047 | 0.651 | 3.2968 | 0.875 | 6.6222 | 0.844 | 7.8067 | 0.586 |
| gjr_t | 7.5106 | 0.655 | 3.2992 | 0.873 | 6.6159 | 0.836 | 7.8169 | 0.594 |
| lightgbm_cuantiles | 7.9395 | 0.729 | 3.8288 | 0.905 | 8.1141 | 0.883 | 7.8798 | 0.676 |
| reg_cuantiles | 7.9599 | 0.789 | 3.5822 | 0.933 | 8.3397 | 0.750 | 7.8299 | 0.802 |
| sim_hist_756 | 6.6967 | 0.657 | 3.5113 | 0.921 | 6.4837 | 0.805 | 6.7696 | 0.607 |
| sim_hist_pond | 6.5109 | 0.671 | 3.7805 | 0.860 | 7.2013 | 0.789 | 6.2746 | 0.631 |

n por grupo: estres = 502, normal = 2991, crisis_2008 = 128, petroleo_2014_2015 = 374

## Pruebas de VaR a h = 1 (Kupiec y Christoffersen)

Tasa = proporción de violaciones (esperada 0,01 o 0,05). p_uc = Kupiec; p_ind = independencia de Christoffersen; p_cc = cobertura condicional. p < 0,05 rechaza la calibración de esa cola.

| modelo | cola | tasa | p_uc | p_ind | p_cc |
|---|---|---|---|---|---|
| caminata_aleatoria | inf 1 % | 0.0407 | <0,001 | <0,001 | <0,001 |
| caminata_aleatoria | inf 5 % | 0.0813 | <0,001 | <0,001 | <0,001 |
| caminata_aleatoria | sup 5 % | 0.0873 | <0,001 | <0,001 | <0,001 |
| caminata_aleatoria | sup 1 % | 0.0475 | <0,001 | <0,001 | <0,001 |
| egarch_t | inf 1 % | 0.0069 | 0.049 | 0.564 | 0.122 |
| egarch_t | inf 5 % | 0.0541 | 0.271 | 0.075 | 0.112 |
| egarch_t | sup 5 % | 0.0633 | <0,001 | <0,001 | <0,001 |
| egarch_t | sup 1 % | 0.0115 | 0.399 | 0.336 | 0.441 |
| ewma_0.94 | inf 1 % | 0.0135 | 0.051 | 0.162 | 0.056 |
| ewma_0.94 | inf 5 % | 0.0441 | 0.102 | 0.004 | 0.004 |
| ewma_0.94 | sup 5 % | 0.0573 | 0.054 | <0,001 | <0,001 |
| ewma_0.94 | sup 1 % | 0.0195 | <0,001 | 0.002 | <0,001 |
| garch_t | inf 1 % | 0.0106 | 0.727 | 0.411 | 0.671 |
| garch_t | inf 5 % | 0.0593 | 0.015 | 0.172 | 0.020 |
| garch_t | sup 5 % | 0.0710 | <0,001 | <0,001 | <0,001 |
| garch_t | sup 1 % | 0.0163 | <0,001 | 0.326 | 0.002 |
| gjr_t | inf 1 % | 0.0106 | 0.727 | 0.411 | 0.671 |
| gjr_t | inf 5 % | 0.0587 | 0.022 | 0.149 | 0.025 |
| gjr_t | sup 5 % | 0.0707 | <0,001 | <0,001 | <0,001 |
| gjr_t | sup 1 % | 0.0160 | <0,001 | 0.307 | 0.003 |
| lightgbm_cuantiles | inf 1 % | 0.0186 | <0,001 | 0.841 | <0,001 |
| lightgbm_cuantiles | inf 5 % | 0.0575 | 0.046 | 0.461 | 0.103 |
| lightgbm_cuantiles | sup 5 % | 0.0621 | 0.002 | 0.292 | 0.004 |
| lightgbm_cuantiles | sup 1 % | 0.0152 | 0.004 | 0.253 | 0.009 |
| reg_cuantiles | inf 1 % | 0.0129 | 0.101 | 0.612 | 0.229 |
| reg_cuantiles | inf 5 % | 0.0524 | 0.520 | 0.428 | 0.593 |
| reg_cuantiles | sup 5 % | 0.0601 | 0.008 | 0.330 | 0.018 |
| reg_cuantiles | sup 1 % | 0.0137 | 0.035 | 0.693 | 0.101 |
| sim_hist_756 | inf 1 % | 0.0163 | <0,001 | <0,001 | <0,001 |
| sim_hist_756 | inf 5 % | 0.0573 | 0.054 | <0,001 | <0,001 |
| sim_hist_756 | sup 5 % | 0.0638 | <0,001 | <0,001 | <0,001 |
| sim_hist_756 | sup 1 % | 0.0186 | <0,001 | <0,001 | <0,001 |
| sim_hist_pond | inf 1 % | 0.0112 | 0.497 | <0,001 | <0,001 |
| sim_hist_pond | inf 5 % | 0.0515 | 0.679 | <0,001 | <0,001 |
| sim_hist_pond | sup 5 % | 0.0527 | 0.472 | <0,001 | <0,001 |
| sim_hist_pond | sup 1 % | 0.0123 | 0.185 | 0.002 | 0.003 |

## Detalle Diebold-Mariano (candidato vs. mejor línea base)

| modelo | h | línea base | CRPS/base | t (HLN) | p | rezagos | n | estado |
|---|---|---|---|---|---|---|---|---|
| egarch_t | 1 | sim_hist_pond | 0.982 | -4.24 | <0,001 | 8 | 3493 | supera |
| ewma_0.94 | 1 | sim_hist_pond | 0.981 | -4.50 | <0,001 | 8 | 3493 | supera |
| garch_t | 1 | sim_hist_pond | 0.983 | -3.77 | <0,001 | 8 | 3493 | supera |
| gjr_t | 1 | sim_hist_pond | 0.983 | -3.81 | <0,001 | 8 | 3493 | supera |
| lightgbm_cuantiles | 1 | sim_hist_pond | 0.963 | -6.67 | <0,001 | 8 | 3493 | supera |
| reg_cuantiles | 1 | sim_hist_pond | 0.968 | -5.13 | <0,001 | 8 | 3493 | supera |
| egarch_t | 5 | sim_hist_pond | 0.996 | -0.52 | 0.300 | 12 | 3493 | descartado |
| ewma_0.94 | 5 | sim_hist_pond | 0.988 | -1.62 | 0.053 | 12 | 3493 | descartado |
| garch_t | 5 | sim_hist_pond | 1.001 | 0.14 | 0.554 | 12 | 3493 | descartado |
| gjr_t | 5 | sim_hist_pond | 1.001 | 0.11 | 0.544 | 12 | 3493 | descartado |
| lightgbm_cuantiles | 5 | sim_hist_pond | 0.998 | -0.31 | 0.379 | 12 | 3493 | descartado |
| reg_cuantiles | 5 | sim_hist_pond | 0.993 | -0.88 | 0.189 | 12 | 3493 | descartado |
| egarch_t | 21 | sim_hist_pond | 0.982 | -0.80 | 0.213 | 28 | 3493 | descartado |
| ewma_0.94 | 21 | sim_hist_pond | 0.964 | -1.59 | 0.056 | 28 | 3493 | descartado |
| garch_t | 21 | sim_hist_pond | 0.994 | -0.28 | 0.390 | 28 | 3493 | descartado |
| gjr_t | 21 | sim_hist_pond | 0.994 | -0.28 | 0.391 | 28 | 3493 | descartado |
| lightgbm_cuantiles | 21 | sim_hist_pond | 1.052 | 1.98 | 0.976 | 28 | 3493 | descartado |
| reg_cuantiles | 21 | sim_hist_pond | 0.997 | -0.13 | 0.448 | 28 | 3493 | descartado |
| egarch_t | 63 | caminata_aleatoria | 0.986 | -1.59 | 0.056 | 70 | 3493 | descartado |
| ewma_0.94 | 63 | caminata_aleatoria | 0.976 | -1.15 | 0.125 | 70 | 3493 | descartado |
| garch_t | 63 | caminata_aleatoria | 1.004 | 0.32 | 0.625 | 70 | 3493 | descartado |
| gjr_t | 63 | caminata_aleatoria | 1.004 | 0.38 | 0.648 | 70 | 3493 | descartado |
| lightgbm_cuantiles | 63 | caminata_aleatoria | 1.137 | 2.58 | 0.995 | 70 | 3493 | descartado |
| reg_cuantiles | 63 | caminata_aleatoria | 1.083 | 1.81 | 0.965 | 70 | 3493 | descartado |

## Reproducir

```
PYTHONPATH=src python -m laboratorio.backtest correr
PYTHONPATH=src python -m laboratorio.backtest reporte
```

Hash (SHA-256, 16 hex) de data/processed/trm.csv usado: 641393c5df0c869b.
