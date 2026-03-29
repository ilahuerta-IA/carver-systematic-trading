# Carver Systematic Trading — Contexto Core para IA
> Archivo privado (en .gitignore). Leer SIEMPRE al inicio de cada sesión.
> **Heredado de TradingSystem** (mismo workspace). Las lecciones de 6 meses de desarrollo
> y 2 meses de live trading se preservan aquí como axiomas y directrices.

> **📂 Navegación entre archivos de contexto:**
> - **[CONTEXT.md](CONTEXT.md)** ← ESTÁS AQUÍ — Axiomas, reglas, directrices, estado actual
> - [CONTEXT_STRATEGIES.md](CONTEXT_STRATEGIES.md) — Framework Carver: EWMAC, Carry, vol targeting, instrumentos
> - [CONTEXT_LIVE.md](CONTEXT_LIVE.md) — Análisis live, paper trading, match rate (cuando exista)

---

## ⚠️ NOTA PARA LA IA - Leer al inicio de cada sesión

**Auto-diagnóstico de contexto:**
1. Si la conversación se siente "pesada" o larga, avisa al usuario
2. Si empiezas a olvidar detalles o contradecirte, sugiere cerrar y abrir nueva sesión
3. Este archivo `CONTEXT.md` existe para preservar información entre sesiones
4. Ante la duda, relee este archivo completo antes de responder

**Límites conocidos:**
- Ventana de contexto: ~200K tokens
- Conversaciones muy largas → partes antiguas se resumen/truncan
- Síntomas de degradación: respuestas genéricas, repeticiones, olvidos

**OBLIGATORIO:**
- ✅ **SIEMPRE registrar resultados de backtest/análisis en context/** — no esperar a que Iván lo pida
- ✅ Después de cada análisis/cambio relevante, actualizar la sección correspondiente inmediatamente

**NO REPETIR:**
- ❌ No inventar datos visuales de imágenes — si hay dudas sobre lo que se ve, PREGUNTAR
- ❌ NO olvidar hacer `git commit` después de cada cambio
- ❌ No sugerir cambios fuera del scope pedido

---

## 🔴 AXIOMAS — LEER SIEMPRE AL INICIO DE CADA SESIÓN

> **Todos los axiomas están aquí juntos. Heredados de TradingSystem + nuevos.**
> **Si se añade uno nuevo, ponerlo aquí.**

### AXIOMA 1: BACKTESTING ≠ LIVE — NUNCA MEZCLAR
> Son sistemas TOTALMENTE independientes:
> - `core/` + `backtest/` + `config/` + `tools/` = **BACKTESTING**
> - `live/` = **EJECUCIÓN REAL / PAPER**
>
> 1. NO tocar archivos `live/` cuando se trabaja en backtesting
> 2. Los cambios se prueban PRIMERO en backtest
> 3. Solo hacer commit de archivos live cuando se implementa algo ESPECÍFICAMENTE para live
>
> **Origen:** TradingSystem Axioma 1. Validado empíricamente: bugs en live checkers vs BT strategies.

### AXIOMA 2: NO MODIFICAR ARCHIVOS COMPARTIDOS SIN PENSAR IMPACTO
> Los archivos en `core/` son usados por backtest Y live. Modificarlos para satisfacer
> un solo caso de uso puede romper los demás.
>
> 1. Antes de tocar un archivo compartido, preguntarse: "¿qué otros módulos lo usan?"
> 2. Si un cambio en `core/forecast.py` afecta al backtest, verificar que live también lo refleje
>
> **Origen:** TradingSystem Axioma 2.

### AXIOMA 3: IDIOMA
> - **Carpeta `context/`** = únicos archivos en **español** (documentación privada para Iván)
> - **TODO lo demás** (código, comentarios, docstrings, commits, logs, configs) = **inglés**
> - Sin excepciones.
>
> **Origen:** TradingSystem Axioma 3.

### AXIOMA 4: SOLO ASCII EN CÓDIGO
> - **TODO el código fuente (.py)** debe usar SOLO caracteres ASCII (0x00-0x7F)
> - NO usar: `—` (em dash), `→` (flecha), `×` (multiplicación), `⚠️` (emoji), acentos, ñ, etc.
> - **Carpeta `context/`** está exenta (es español, puede tener Unicode)
>
> **Origen:** TradingSystem Axioma 4. La IA genera Unicode involuntariamente en código.

### AXIOMA 5: CARPETA context/ ESTÁ EN .gitignore
> - **Toda la carpeta `context/`** es documentación privada y **NO se versiona** en Git.
> - **Nunca** hacer `git add -f context/` ni sacarla del `.gitignore`.
>
> **Origen:** TradingSystem Axioma 5.

### AXIOMA 6: CERO EMOCIÓN, CERO EGO — EL MERCADO NO TIENE BONDAD
> El mercado no tiene bondad, ni respeto, ni memoria. Le da igual si ganas o pierdes.
>
> **Para Copilot (obligatorio en CADA sesión):**
> 1. NUNCA priorizar las emociones o el ego de Iván sobre los datos
> 2. Si los números dicen que algo no funciona, comunicarlo con contundente coherencia
> 3. No suavizar malas noticias. No celebrar prematuramente buenas noticias.
> 4. La prisa es un pecado capital. No correr hacia features nuevas abandonando lo pendiente.
> 5. No emocionarse con diseños elegantes que no han tocado datos reales.
> 6. Si Iván muestra sesgo (aferrarse a una idea, evitar un descarte doloroso), señalarlo.
>
> **Para el proceso:**
> - Cada decisión debe sobrevivir la pregunta: "¿esto lo hago porque los datos lo dicen, o porque quiero que funcione?"
> - Descartar algo querido cuando los números lo piden = fortaleza, no fracaso
> - El objetivo es vivir del trading. Eso requiere paciencia industrial, no sprints emocionales.
>
> **Origen:** TradingSystem Axioma 6.

### AXIOMA 7: NO CAMBIAR NADA SIN CONSULTAR A IVÁN — INMUTABLE
> **Este es el axioma principal. No se puede modificar ni relajar en el futuro.**
>
> Copilot **NO puede modificar, añadir ni eliminar** NADA en ningún archivo sin que Iván
> lo haya pedido explícitamente o haya dado su aprobación previa.
>
> **Procedimiento obligatorio:**
> - Si durante una tarea Copilot ve algo que "convendría" cambiar pero NO fue pedido → PREGUNTAR
> - Si hay duda sobre si un cambio está dentro del scope → PREGUNTAR
> - Si Copilot necesita cambiar algo adicional para que lo pedido funcione → EXPLICAR por qué y PEDIR permiso
>
> **Origen:** TradingSystem Axioma 7. Incidente: Copilot cambió configs sin permiso.

### AXIOMA 8: COSTES DE TRANSACCIÓN SON FILTRO DE PRIMER ORDEN
> Cualquier edge cuyo beneficio esperado sea del orden del spread/comisión queda destruido.
>
> **Regla operativa:**
> 1. Antes de investigar cualquier patrón/edge, verificar que el movimiento esperado sea >> coste
> 2. El buffering de Carver existe precisamente para esto — no operar cuando el ajuste
>    de posición cuesta más de lo que ahorra
> 3. Si una estrategia requiere spreads ultra-bajos para ser viable → descartar inmediatamente
>
> **Evidencia acumulada (TradingSystem):** USDCAD (spread ~8 pips destruye edge),
> NI225 (spread 3.0 pts), SPA35 (spread 5.2), Phase E rollover AUDUSD (+1.5 bps edge
> destruido por 2 pips spread).
>
> **Origen:** TradingSystem Axioma 8. Adaptado: ahora incluye buffering como mecanismo.

### AXIOMA 9: NO BORRAR HISTORIAL DE ACCIONES — PRESERVAR TRAZA COMPLETA
> Todo experimento, configuración, backtest o decisión debe quedar registrado permanentemente.
>
> 1. Los resultados de backtests fallidos van a context/ **siempre** — incluso si fueron catastróficos
> 2. Si un instrumento se descarta, documentar por qué antes de eliminarlo del config
> 3. El historial de decisiones es tan valioso como los resultados positivos
>
> **Origen:** TradingSystem Axioma 9. Incidente: configs eliminadas sin traza.

### AXIOMA 10: LA COMPLEJIDAD ES EL ENEMIGO
> Cada parámetro adicional es una oportunidad de overfitting.
> Si no puedes explicar la estrategia en una frase, tiene demasiados parámetros.
>
> **Regla operativa (Carver framework):**
> 1. **CERO parámetros optimizados** — todos los valores vienen de literatura publicada
> 2. EWMAC speeds (8/32, 16/64, 32/128, 64/256) son fijos, NO se tocan
> 3. Vol target, FDM, IDM se calculan de datos, no se optimizan
> 4. Si algo necesita "ajuste fino" para funcionar → no funciona
>
> **Evidencia (TradingSystem):** 4 estrategias con 10-20 params cada una, PF 2.0+ en BT,
> resultado live: -16% en 6 semanas. Gap de $15,000 entre BT y live = overfitting puro.
>
> **Origen:** TradingSystem CONSOLIDATION §3.1 + confirmación live §"Conclusión definitiva".

### AXIOMA 11: DAILY TIMEFRAME — NO OPERAR EN TIMEFRAMES DONDE LOS DATOS DIVERGEN
> Los datos M5 de diferentes fuentes producen candles diferentes (bid vs mid, tick aggregation).
> Los datos daily son prácticamente idénticos entre cualquier fuente.
>
> **Regla operativa:**
> 1. Timeframe base: **DAILY** (o mínimo H4 si hay justificación clara)
> 2. Los datos de backtest (Yahoo Finance) y los del broker deben coincidir en OHLC daily ±0.01%
> 3. Si el match rate paper↔BT es <90%, investigar divergencia de datos PRIMERO
> 4. Nunca más M5 para señales de trading
>
> **Evidencia:** TradingSystem live match rate 11-30% en M5. En daily, el cierre es universal.
>
> **Origen:** 6 semanas de live trading (Feb-Mar 2026). Conclusión en CONTEXT_LIVE.md TradingSystem.

### AXIOMA 12: GIT PUSH LO HACE IVÁN — NUNCA COPILOT
> Copilot puede hacer `git add` y `git commit`, pero **jamás `git push`**.
> El push es una acción irreversible que publica código en el repo remoto.
> Iván revisa el commit antes de hacer push manualmente.
>
> **Regla operativa:**
> 1. `git add` + `git commit` → Copilot puede hacerlo si Iván lo pide
> 2. `git push` → **PROHIBIDO** para Copilot — siempre lo hace Iván
> 3. Si Copilot necesita que se haga push, debe decir "listo para push" y esperar
>
> **Origen:** Sesión 2026-03-28. Push requiere SSH passphrase interactivo + revisión humana.

---

## 📌 Estado Actual

- **Version:** v0.0.0 (estructura inicial)
- **Fecha creación:** 2026-03-28
- **Origen:** Pivot desde TradingSystem (ver CONSOLIDATION_AND_NEW_APPROACH.md §6)
- **Framework:** Robert Carver "Advanced Futures Trading Strategies"
- **Broker target:** Darwinex (CFDs: equity, commodities, FX, bonds)
- **Broker paper:** Darwinex demo MT5
- **Datos backtest:** Yahoo Finance daily (gratuito, 20+ años)

---

## 🤖 Rol Copilot: Directrices específicas para este proyecto

### Lo que debe hacer
1. **Detectar overfitting agresivamente** — si cualquier resultado de backtest parece "demasiado bueno"
   (Sharpe >2, PF >3, DD <5%), cuestionarlo inmediatamente.
2. **Comparar siempre contra baseline** — todo resultado debe contextualizarse vs buy&hold o vs random.
3. **Señalar correlaciones entre instrumentos** — si 2 instrumentos se mueven juntos, el IDM real baja.
4. **Mantener reproducibilidad** — todo cálculo debe ser determinista y documentado.

### Lo que NO debe hacer
1. **NO optimizar parámetros** — los speeds de EWMAC, el FDM, el buffer son de literatura o calculados.
   NUNCA probar "qué pasa si cambio 64/256 a 60/240".
2. **NO añadir filtros** — si la señal cruda no funciona, el instrumento se descarta, no se filtra.
3. **NO celebrar backtests** — hasta que paper trading confirme match rate >90%, ningún resultado es real.
4. **NO hacer cambios fuera del scope pedido** (Axioma 7).

### Lecciones heredadas de TradingSystem (no repetir)
- Si Copilot genera Unicode en código .py → violar Axioma 4 → bugs de encoding en producción
- Si Copilot modifica configs sin permiso → violar Axioma 7 → pérdida de confianza
- Si se priorizan "mejoras obvias" sobre lo solicitado → trabajo no pedido = trabajo perdido
- Si un resultado de BT no se valida en paper → falsa confianza → pérdida de dinero real
- 6 meses de backtesting sin paper trading real = tiempo potencialmente desperdiciado

---

## 📋 Instrumentos — UNIVERSO CONFIRMADO (2026-03-28)

> Disponibilidad verificada por Iván en Darwinex demo y real MT5.
> Ver detalle completo en [INSTRUMENT_AVAILABILITY.md](INSTRUMENT_AVAILABILITY.md).

### Universo seleccionado (10 instrumentos, 3 clases)

| # | Clase | Instrumento | Datos BT | Demo MT5 | Real MT5 | Justificación |
|---|-------|------------|----------|----------|----------|---------------|
| 1 | Equity | S&P 500 | SPY / datos propios H4 | ✅ | ✅ | Core US, mayor liquidez |
| 2 | Equity | NASDAQ 100 | QQQ / datos propios H4 | ✅ | ✅ | Tech/growth, complemento SP500 |
| 3 | Equity | DAX 40 | ^GDAXI / datos propios H4 | ✅ | ✅ | Europa, corr ~0.7 con US |
| 4 | Equity | Nikkei 225 | ^N225 / datos propios H4 | ✅ | ✅ | Asia, corr ~0.5-0.6 con US — mejor diversificación |
| 5 | Commodity | Oro | GC=F / XAUUSD datos propios H4 | ✅ | ✅ | Refugio, baja corr con equity |
| 6 | Commodity | Plata | SI=F / XAGUSD datos propios H4 | ✅ | ✅ | Corr ~0.7 con oro pero más volátil |
| 7 | FX | EUR/USD | EURUSD=X / datos propios H4 | ✅ | ✅ | Par principal |
| 8 | FX | USD/JPY | USDJPY=X / datos propios H4 | ✅ | ✅ | Baja corr con EUR, proxy risk-on/off |
| 9 | FX | AUD/USD | AUDUSD=X / datos propios H4 | ✅ | ✅ | Proxy commodities en FX |
| 10 | FX | GBP/USD | GBPUSD=X / datos propios H4 | ✅ | ✅ | Complemento EUR, corr ~0.6 |

**IDM estimado: ~1.6-1.8** (sin bonds, menor que ideal 2.0+)

### Descartados y por qué

| Instrumento | Razón del descarte |
|------------|-------------------|
| FTSE, EuroStoxx, ASX200 | Demasiado correlados con SP500/DAX sin añadir diversificación |
| USDCAD, NZDUSD, USDCHF | Demasiado correlados con los 4 FX elegidos |
| GLD (ETF) | Duplicado de XAUUSD (mismo subyacente) |
| Hang Seng | No disponible en demo ni real |
| Petróleo WTI/Brent | No disponible en demo ni real |
| Gas Natural, Cobre, Platino, Paladio | No disponible |
| TLT / Bonds | **Solo en real, no en demo** — no se puede paper test. Candidato a añadir en Fase 8 (live) |

### Limitaciones del universo actual

1. **Sin bonds** — TLT (anti-correlación con equity, corr -0.3/-0.5) solo está en real.
   En un crash, equity + commodities + FX risk-on caen juntos. Sin bonds, no hay "hedge natural".
   Impacto: DD en crisis será mayor de lo que sería con bonds incluidos.
2. **7 equity indices en demo pero solo usamos 4** — reducimos correlación intra-clase,
   pero la clase equity sigue dominando (4 de 10 = 40%).
3. **GLD solo en real como ETF, pero oro está cubierto por XAUUSD** — sin impacto.

### Datos de backtest

Iván tiene acceso a datos H4 de hasta 20 años para algunos activos.
Fuentes combinables:
- **Yahoo Finance** — daily OHLCV gratuito, 20+ años (equity, ETFs, FX, commodities futures)
- **Datos propios H4** — hasta 20 años en algunos activos (formato CSV existente de TradingSystem)

Timeframe de operación: **Daily o H4** (por confirmar). H4 da 6x más barras = más muestra estadística,
y sigue siendo un timeframe donde los datos entre fuentes son consistentes.

### Criterios de selección (permanentes)
1. **Disponible en broker demo Y real** — sino no se puede validar en paper
2. **Datos históricos disponibles** (20+ años idealmente) — Yahoo Finance o datos propios
3. **Baja correlación entre clases** — no más de 4 del mismo tipo
4. **Liquidez suficiente** — spread razonable en el broker (Axioma 8)
5. **Máximo 4 pares FX** — más forex no suma diversificación real

---

## 🏗️ Estructura del Repositorio

```
carver-systematic-trading/
├── context/          ← Documentación privada (español, .gitignore)
│   ├── CONTEXT.md            ← ESTE ARCHIVO — Axiomas, estado, directrices
│   ├── CONTEXT_STRATEGIES.md ← Framework Carver: formulas, decisiones, resultados
│   └── CONTEXT_LIVE.md       ← Paper/live trading: match rate, incidentes
├── data/             ← Daily OHLCV (Yahoo Finance, .gitignore para CSVs)
├── core/             ← Motor: forecast, sizing, buffering, vol targeting
├── backtest/         ← Engine pandas: loop diario, métricas, plotting
├── live/             ← MT5 connector, ejecución 1x/día
├── config/           ← Instrumentos, portfolio, broker params
├── tools/            ← Descarga datos, análisis, validación
├── logs/             ← Logs de ejecución (.gitignore)
├── analysis/         ← Notebooks de investigación
├── README.md         ← Documentación pública
├── requirements.txt  ← Dependencias
├── LICENSE
└── .gitignore
```

---

## 📊 Roadmap

| Fase | Qué | Criterio de paso | Estado |
|------|-----|-----------------|--------|
| **0** | Verificar instrumentos Darwinex demo/real | Tabla de disponibilidad completa | ✅ HECHO |
| **1** | Descargar datos daily/H4 de los 10 instrumentos | Datos limpios, sin gaps relevantes | ✅ HECHO |
| **2** | EWMAC single-speed (64/256) en 1 activo | Forecast distribution ~N(0,10) | ✅ HECHO |
| **3** | EWMAC multi-speed (4 velocidades) + vol targeting | DD respeta vol target ±20% | ✅ HECHO |
| **4** | Carry como segunda señal | Sharpe combinado > Sharpe EWMAC solo | ❌ NO CUMPLIDO (carry descartado) |
| **5** | Portfolio multi-instrumento + IDM | IDM calculado, correlaciones OK | ✅ HECHO |
| **6** | Buffering + costes reales | Turnover aceptable, PF > 1.1 neto | ⬜ |
| **7** | Paper trading 3 meses (Darwinex demo) | Match rate >90% | ⬜ |
| **8** | Live con safety net (SL catastrófico) + añadir TLT | — | ⬜ |

### Resultados Fase 2: EWMAC(64/256) en SP500

**Forecast validation (scalar = 1.87):**
- Mean: 7.94 (sesgo alcista esperado en SP500)
- Std: 9.68 ≈ 10 ✅
- Abs Mean: 10.94 ≈ 10 ✅
- % en cap (±20): 13.2% — aceptable

**Backtest (100K, 26.2 años, daily, capital dinámico, SIN COSTES):**

| Métrica | Valor | Nota |
|---------|-------|------|
| Total Return | 441.48% | Bruto, sin spread/swap/comisión |
| CAGR | 6.65% | |
| Annual Vol | 16.32% | vs target 12% (forecast medio>0 → pos>base) |
| Max Drawdown | -30.49% | Max DD Duration: 865 días (~2.4 años) |
| Sharpe | 0.48 | Rango Carver: 0.3-0.5 individual ✅ |
| Sortino | 0.53 | |
| Calmar | 0.22 | CAGR/MaxDD — bajo, mejorará con diversificación |
| Profit Factor | 1.09 | MUY AJUSTADO — costes pueden destruir edge |
| Win Rate (daily) | 54.0% | |
| Payoff Ratio | 0.93 | Avg Win $1,634 / Avg Loss $1,765 |
| Meses positivos | 54.3% | |
| Años ganadores | 15/27 (56%) | Peor racha: 2 años consecutivos |
| Ajustes/año | 71.5 | ~1.4/semana — poco turnover |

**⚠️ IMPORTANTE: Todos estos resultados son BRUTOS (sin costes).**
- Sin spread, sin comisión, sin swap/overnight, sin slippage
- PF 1.09 = por cada $1 perdido, $1.09 ganado → margen mínimo
- Con costes reales (Fase 6), PF podría bajar a <1.0
- Es la línea base MÍNIMA: 1 instrumento, 1 velocidad, 0 diversificación

**Bugs detectados y corregidos (sesión 2026-03-28):**
1. **Scalar único 10.6 → tabla per-speed** — EWMAC(64/256) requiere scalar=1.87 (Carver Ch.15)
2. **Capital fijo → capital dinámico (mark-to-market)** — position sizing escala con equity
3. **Vol métrica en $ → % returns** — vol calculada correctamente como pct_returns.std()

**Herramientas añadidas (sesión 2026-03-28):**
- `backtest/metrics.py`: Sortino, Calmar, Payoff Ratio, monthly stats, DD duration
- `plot_equity_drawdown()`: Gráfico equity + drawdown con anotaciones
- `plot_position_on_price()`: Precio con posición coloreada + forecast (3 paneles)
- `plot_forecast_distribution()`: Histograma sin spike en cap + anotación %
- `generate_adjustment_log()`: Log CSV de cada ajuste de posición (acción, delta, precio, forecast)
- `print_adjustment_summary()`: Resumen de ajustes por tipo + últimos 10
- Flag `--save-only` en runner para generar charts sin display interactivo

**Gráficos guardados en `analysis/`:**
- `phase2_equity_SP500.png` — Equity curve + drawdown
- `phase2_position_SP500.png` — Posición sobre precio (3 paneles)
- `phase2_forecast_dist_SP500.png` — Distribución forecast (sin spike cap)
- `phase2_adjustments_SP500.csv` — Log de 1,803 ajustes

### Resultados Fase 3: EWMAC Multi-Speed (4 velocidades) en 10 instrumentos

**Configuración:**
- 4 velocidades: (8/32), (16/64), (32/128), (64/256)
- Pesos iguales (0.25 cada uno)
- FDM empírico calculado de correlaciones entre forecasts (~1.10-1.16)
- Mismo vol target 12%, buffer 10%, capital $100K

**Tabla resumen (todos los instrumentos, SIN COSTES):**

| Instrumento | Sharpe | Sortino | CAGR% | Vol% | MaxDD% | PF | Calmar | FDM | Años |
|-------------|--------|---------|-------|------|--------|------|--------|------|------|
| SP500 | 0.32 | 0.34 | 3.67 | 14.7 | -32.8 | 1.06 | 0.112 | 1.11 | 26.2 |
| NASDAQ100 | 0.35 | 0.38 | 4.09 | 14.6 | -29.9 | 1.07 | 0.137 | 1.11 | 26.2 |
| DAX40 | 0.23 | 0.27 | 2.14 | 13.4 | -39.9 | 1.03 | 0.054 | 1.12 | 26.2 |
| NIKKEI225 | 0.25 | 0.30 | 2.32 | 13.0 | -34.2 | 1.04 | 0.068 | 1.13 | 26.2 |
| **GOLD** | **0.47** | **0.51** | **5.50** | 13.8 | -41.2 | **1.11** | 0.133 | 1.13 | 25.6 |
| SILVER | 0.19 | 0.21 | 1.55 | 12.3 | -50.0 | 1.03 | 0.031 | 1.14 | 25.6 |
| EURUSD | 0.06 | 0.08 | 0.04 | 12.4 | -37.1 | 1.00 | 0.001 | 1.15 | 22.3 |
| USDJPY | 0.13 | 0.15 | 0.85 | 13.0 | -50.9 | 1.01 | 0.017 | 1.13 | 26.2 |
| AUDUSD | **-0.01** | -0.01 | -0.85 | 11.9 | -43.6 | **0.99** | 0.020 | 1.14 | 19.9 |
| GBPUSD | **-0.04** | -0.05 | -1.22 | 11.8 | -37.8 | **0.98** | 0.032 | 1.16 | 22.3 |

**Comparación Phase 2 vs Phase 3 (SP500):**
- Sharpe: 0.48 → 0.32 (-0.16) — esperado: velocidades rápidas diluyen señal en activo trending
- Vol: 16.3% → 14.7% (más cercano al target 12%) — mejor disciplina de sizing
- FDM empírico: 1.1058 — correlaciones entre speeds son altas (0.48-0.91)

**Análisis por clase de activo:**

| Clase | Mejor | Sharpe | Peor | Sharpe | Observación |
|-------|-------|--------|------|--------|-------------|
| Equity | NASDAQ100 | 0.35 | DAX40 | 0.23 | Sesgo alcista funciona con trend following |
| Commodity | GOLD | **0.47** | SILVER | 0.19 | Oro es el mejor activo individual |
| FX | USDJPY | 0.13 | GBPUSD | -0.04 | FX no tiene tendencia individual clara |

**Conclusiones clave (Axioma 6 — sin emoción):**
1. **Gold es el mejor activo para EWMAC puro** (Sharpe 0.47, PF 1.11) — tendencia fuerte desde 2000
2. **Equity funciona moderadamente** (Sharpe 0.23-0.35) — bias alcista ayuda
3. **FX individual es esencialmente ruido** (Sharpe -0.04 a 0.13) — sin tendencia, EWMAC no tiene edge
4. **AUDUSD y GBPUSD son negativos** — candidatos a excluir si no aportan diversificación en portfolio
5. **Vol targeting funciona**: la mayoría de instrumentos están en 11.8-14.7% vs target 12%
6. **FDM ~1.10-1.16 es bajo** — correlaciones entre speeds son altas (adjacent pair ~0.88)
   Carver dice FDM 1.2-1.3, pero con solo 4 speeds muy correlacionadas es lógico que sea menor
7. **Max DD en todos excede vol target**: -30% a -51% vs target 12%
   Esto es normal para instrumento individual. Portfolio + IDM reducirá DD (Fase 5)
8. **⚠️ Sin costes, 4 de 10 instrumentos tienen PF ≤ 1.01** — con costes serán negativos

**Decisión pendiente (para Fase 5):**
- ¿Incluir AUDUSD/GBPUSD en portfolio aunque sean negativos individualmente?
  Depende de si su baja correlación con equity/commodities compensa el drag.
  Hay que calcular correlación de returns entre instrumentos (no de forecasts).

**Herramientas añadidas (sesión 2026-03-28):**
- `tools/run_phase3_multispeed.py`: Runner multi-speed con --all-instruments, --save-only
- Función `calculate_fdm()`: FDM empírico de correlación entre forecasts
- Tabla comparativa multi-instrumento automática
- Comparación Phase 2 vs Phase 3 integrada

**Gráficos guardados en `analysis/` (3 por instrumento × 10 = 30 gráficos):**
- `phase3_equity_{INST}.png` — Equity + drawdown
- `phase3_position_{INST}.png` — Posición sobre precio (3 paneles)
- `phase3_forecast_dist_{INST}.png` — Distribución forecast combinado
- `phase3_adjustments_{INST}.csv` — Log de ajustes

### Resultados Fase 4: EWMAC + Carry (60% trend / 40% carry)

**Configuración:**
- Carry basada en diferenciales de tipos de interés (datos FRED, mensuales, 2000-2026)
- FX: carry = tasa_base - tasa_quote
- Equity: carry = div_yield_aprox - tasa_funding
- Commodities: carry = -(tasa_funding) (siempre negativo, sin datos de term structure)
- Carry scalar: 30.0 (fijo para todos)
- Pesos: 60% EWMAC combinado + 40% Carry
- FDM trend-carry calculado empíricamente de correlación entre señales
- Mismo vol target 12%, buffer 10%, capital $100K

**Tabla resumen (todos los instrumentos, SIN COSTES):**

| Instrumento | Sharpe_EW | Sharpe_EC | Delta | CAGR%_EC | MaxDD% | PF_EC | Corr_TC | FDM_TC | Carry AbsMean |
|-------------|-----------|-----------|-------|----------|--------|-------|---------|--------|---------------|
| SP500 | 0.32 | 0.33 | +0.003 | 3.24 | -27.1 | 1.06 | -0.038 | 1.41 | 3.69 |
| NASDAQ100 | 0.35 | 0.29 | -0.066 | 2.70 | -33.6 | 1.05 | -0.076 | 1.44 | 2.71 |
| DAX40 | 0.23 | 0.24 | +0.009 | 2.04 | -38.3 | 1.03 | +0.239 | 1.26 | 3.27 |
| NIKKEI225 | 0.25 | 0.29 | +0.040 | 2.25 | -25.1 | 1.06 | +0.489 | 1.15 | 2.26 |
| **GOLD** | **0.47** | **0.17** | **-0.294** | 1.30 | -45.5 | 1.03 | -0.259 | 1.59 | 3.91 |
| SILVER | 0.19 | 0.07 | -0.123 | 0.13 | -50.5 | 1.00 | -0.218 | 1.55 | 2.40 |
| EURUSD | 0.07 | -0.01 | -0.074 | -0.78 | -41.7 | 0.99 | -0.108 | 1.46 | 4.89 |
| USDJPY | 0.13 | 0.17 | +0.037 | 1.31 | -47.0 | 1.02 | +0.220 | 1.26 | 6.40 |
| AUDUSD | -0.01 | -0.10 | -0.087 | -1.54 | -40.6 | 0.97 | +0.233 | 1.26 | 4.91 |
| GBPUSD | -0.04 | -0.13 | -0.091 | -1.86 | -40.5 | 0.96 | -0.006 | 1.39 | 2.43 |

**Sharpe mejoró en 4/10 instrumentos. Criterio de Fase 4 NO cumplido.**

**Diagnóstico — Dos problemas detectados:**

1. **Carry scalar = 30 es demasiado bajo (carry forecast infraescalada).**
   Target de Carver: abs(carry_forecast).mean() ≈ 10. Resultados: 2.26 a 6.40.
   El 40% de peso asignado a carry va a una señal 3x más débil que EWMAC →
   carry DILUYE la señal EWMAC sin aportar suficiente información propia.
   
2. **Modelo de carry para commodities es incorrecto.**
   Gold carry = -(funding_rate) → siempre negativo → PELEA contra trend positivo.
   Gold fue el mejor activo en EWMAC (Sharpe 0.47), carry lo destruyó (→ 0.17).
   En Carver-futures, el carry de gold viene del term structure (backwardation/contango),
   no del tipo de interés libre de riesgo. Sin datos de term structure en Yahoo Finance.
   Silver sufre el mismo problema (0.19 → 0.07).

**⚠️ DECISIÓN PENDIENTE — Soluciones para próxima sesión:**

**Solución A: Carry scalar per-instrument (calibración, NO optimización)**
- Igual que los EWMAC scalars per-speed (Carver Ch.15), cada instrumento debería
  tener su propio carry scalar calibrado para que abs(carry_forecast).mean() ≈ 10.
- Procedimiento: para cada instrumento, calcular carry_raw / vol, medir abs_mean,
  y derivar scalar = 10 / abs_mean_raw. Esto es NORMALIZACIÓN, no optimización.
- Carver hace esto exactamente en pysystemtrade: forecast scalar = 10 / observed_abs_mean.
- Implementación: función `calibrate_carry_scalar()` en carry.py que calcula el scalar
  empírico usando 80% de los datos (in-sample), validado en el 20% restante.

**Solución B: Excluir carry para commodities (Gold y Silver)**
- Sin datos de term structure, el carry de commodities = -(funding_rate) = basura.
- Gold/Silver deberían usar SOLO EWMAC (como en Phase 3).
- Implementación: en el runner, si asset_class == "commodity" → skip carry, usar
  100% EWMAC con su propio FDM de speeds.

**Ambas soluciones son compatibles y se implementan juntas.**
Orden: B primero (excluir commodities), luego A (recalibrar scalars).

---

### Resultados Fase 4 v2: Tras correcciones (Solución A + B)

**Cambios aplicados (sesión 2026-03-29):**
1. **Solución B**: Commodities (GOLD, SILVER) → 100% EWMAC, 0% carry. Sin datos de term structure.
2. **Solución A**: `calibrate_carry_scalar()` en carry.py. scalar = 10 / abs(raw).mean().
   Auto-calibrado per-instrument (normalización, no optimización — mismo principio que EWMAC scalars).
3. `carry_forecast()` con `carry_scalar=None` → auto-calibra desde los datos.

**Tabla resumen v2 (todos los instrumentos, SIN COSTES):**

| Instrumento | Sharpe_EW | Sharpe_EC | Delta | Scalar | CAGR%_EC | MaxDD% | PF_EC | Corr_TC | FDM_TC | Abs_Mean | Modo |
|-------------|-----------|-----------|-------|--------|----------|--------|-------|---------|--------|----------|------|
| SP500 | 0.32 | 0.31 | -0.015 | 81.4 | 3.20 | -31.2 | 1.05 | +0.052 | 1.35 | 8.93 | EWMAC+Carry |
| NASDAQ100 | 0.35 | 0.17 | **-0.185** | 110.9 | 1.28 | -44.1 | 1.02 | +0.012 | 1.38 | 8.07 | EWMAC+Carry |
| DAX40 | 0.23 | 0.28 | **+0.055** | 91.6 | 3.01 | -44.3 | 1.03 | +0.210 | 1.27 | 9.60 | EWMAC+Carry |
| NIKKEI225 | 0.25 | 0.37 | **+0.121** | 132.9 | 3.81 | -31.8 | 1.07 | +0.496 | 1.15 | 9.95 | EWMAC+Carry |
| **GOLD** | **0.47** | **0.47** | **0.000** | N/A | 5.50 | -41.2 | 1.11 | — | — | — | EWMAC only |
| **SILVER** | **0.19** | **0.19** | **0.000** | N/A | 1.55 | -50.0 | 1.03 | — | — | — | EWMAC only |
| EURUSD | 0.07 | -0.01 | -0.073 | 61.2 | -0.97 | -50.3 | 0.98 | -0.133 | 1.48 | 8.81 | EWMAC+Carry |
| USDJPY | 0.13 | 0.17 | **+0.037** | 45.0 | 1.35 | -49.6 | 1.02 | +0.173 | 1.29 | 8.52 | EWMAC+Carry |
| AUDUSD | -0.01 | -0.09 | -0.082 | 61.1 | -1.83 | -48.8 | 0.97 | +0.200 | 1.27 | 9.06 | EWMAC+Carry |
| GBPUSD | -0.04 | -0.26 | **-0.214** | 123.5 | -3.61 | -61.7 | 0.93 | -0.020 | 1.40 | 7.97 | EWMAC+Carry |

**Resultado: Sharpe mejoró en 3/8 instrumentos con carry. Criterio Fase 4 sigue NO cumplido.**

**Comparación v1 (scalar fijo 30) vs v2 (scalar auto-calibrado):**

| Problema | v1 (scalar=30) | v2 (auto-calibrado) | Veredicto |
|----------|----------------|---------------------|-----------|
| Carry abs_mean muy bajo | 2.26-6.40 (CHECK) | 7.97-9.95 (OK) | **RESUELTO** |
| Commodities destruidas | GOLD 0.47→0.17 | GOLD 0.47→0.47 | **RESUELTO** |
| Carry mejora Sharpe | 4/10 | 5/10 (3 carry + 2 commodity neutras) | **SIN CAMBIO NETO** |
| GBPUSD | -0.04→-0.13 | -0.04→-0.26 | **PEOR** (señal amplificada pero incorrecta) |
| NASDAQ100 | 0.35→0.29 | 0.35→0.17 | **PEOR** |

**Diagnóstico v2 — El problema ya NO es de escalado, es de la señal:**

1. Escalado FIJO: todos los abs_mean están en 8-10 ahora ✅
2. Pero escalar correctamente una señal inútil amplifica ruido, no la hace útil.
3. GBPUSD y NASDAQ100 empeoran MÁS con scalars altos (123.5 y 110.9) que con scalar 30.
   Un scalar alto en una señal que no predice = amplificar ruido puro.
4. Los 3 que mejoran (DAX40, NIKKEI225, USDJPY) tienen carry con sentido económico:
   - DAX40: div yield EUR ~2.5% vs funding EUR → carry moderado y estable
   - NIKKEI225: carry JPY (std=3.71, muy suave) → correlación alta con EWMAC (0.50) = refuerzo
   - USDJPY: carry = USD-JPY, diferencial claro y persistente
5. Los que empeoran tienen carry ruidoso o sin edge:
   - NASDAQ100: div yield 0.6% → carry casi siempre negativo (funding > yield) = short bias constante
   - GBPUSD: diferencial GBP-USD sin tendencia persistente, carry flip frecuente
   - EURUSD/AUDUSD: señal carry sin dirección clara a long-term

**⚠️ DECISIÓN PARA FASE 5 — Tres opciones:**

**Opción 1: Usar carry selectivo (solo DAX40, NIKKEI225, USDJPY)**
- Pro: maximiza resultado individual
- **Contra: SELECCIÓN IN-SAMPLE → esto ES optimización encubierta (viola Axioma 10)**
- Veredicto: DESCARTADA por principio

**Opción 2: Descartar carry, ir a Fase 5 con EWMAC puro**
- Pro: simple, predecible, sin riesgo de overfitting
- Contra: descarta una fuente de información que Carver usa
- Veredicto: VIABLE, conservadora

**Opción 3: Mantener carry 60/40 para todos los no-commodity, evaluar a nivel PORTFOLIO**
- Pro: Carver dice que carry puede ayudar a nivel portfolio (diversificación de señales)
  aunque no ayude individualmente. El test individual no es el test correcto.
- Contra: la mayoría de instrumentos empeoran
- Veredicto: **RECOMENDADA** — testear el impacto AGREGADO en Fase 5 antes de descartar.
  Si el portfolio Sharpe con carry < sin carry → descartar carry definitivamente.

**Recomendación (Axioma 6 — sin emoción):**
Opción 3. El test correcto de carry es a nivel portfolio, no individual.
En Fase 5, ejecutar dos backtests multi-instrumento:
- A) EWMAC only (10 instrumentos)
- B) EWMAC + Carry (8 carry + 2 EWMAC-only commodity)
Comparar Sharpe de portfolio. Si B > A → carry se queda. Si no → descarte limpio.

**Archivos modificados (sesión 2026-03-29):**
- `core/carry.py`: Añadida `calibrate_carry_scalar()`, `carry_forecast()` con scalar=None (auto)
- `tools/run_phase4_carry.py`: Skip carry para commodities, scalar auto-calibrado, tabla diagnóstica

---

### Resultados Fase 5: Portfolio Multi-Instrumento + IDM

**Configuración:**
- 10 instrumentos, pesos iguales (10% cada uno)
- IDM auto-calculado de matriz de correlación de returns
- Vol target 12%, buffer 10%, capital $100K
- Dos modos: A (EWMAC only) vs B (EWMAC + Carry, commodities sin carry)
- Two-pass: IDM=1.0 para obtener returns → calcular correlación → IDM real → re-run

**Matriz de correlación (returns diarios, Mode A):**

|  | SP500 | NAS100 | DAX40 | NIK225 | GOLD | SILVER | EURUSD | USDJPY | AUDUSD | GBPUSD |
|--|-------|--------|-------|--------|------|--------|--------|--------|--------|--------|
| SP500 | — | 0.81 | 0.42 | 0.09 | 0.02 | 0.02 | 0.01 | 0.00 | 0.05 | 0.01 |
| NAS100 | 0.81 | — | 0.30 | 0.07 | 0.03 | 0.02 | 0.01 | -0.01 | 0.06 | 0.00 |
| DAX40 | 0.42 | 0.30 | — | 0.21 | 0.04 | 0.06 | 0.02 | 0.04 | 0.05 | 0.01 |
| NIK225 | 0.09 | 0.07 | 0.21 | — | 0.04 | 0.03 | -0.01 | 0.14 | 0.02 | 0.02 |
| GOLD | 0.02 | 0.03 | 0.04 | 0.04 | — | 0.65 | 0.05 | 0.03 | 0.09 | 0.08 |
| SILVER | 0.02 | 0.02 | 0.06 | 0.03 | 0.65 | — | 0.02 | 0.02 | 0.10 | 0.05 |
| EURUSD | 0.01 | 0.01 | 0.02 | -0.01 | 0.05 | 0.02 | — | 0.28 | 0.25 | 0.37 |
| USDJPY | 0.00 | -0.01 | 0.04 | 0.14 | 0.03 | 0.02 | 0.28 | — | 0.08 | 0.08 |
| AUDUSD | 0.05 | 0.06 | 0.05 | 0.02 | 0.09 | 0.10 | 0.25 | 0.08 | — | 0.31 |
| GBPUSD | 0.01 | 0.00 | 0.01 | 0.02 | 0.08 | 0.05 | 0.37 | 0.08 | 0.31 | — |

**Correlaciones por clase de activo:**
- Intra-equity: avg 0.32 (6 pares) — SP500↔NAS100 = 0.81 es alta
- Intra-commodity: avg 0.65 (1 par) — GOLD↔SILVER muy correlados
- Intra-FX: avg 0.23 (6 pares) — FX es la clase más diversificada
- Equity vs commodity: avg 0.03 — prácticamente independientes ✅
- Equity vs FX: avg 0.03 — prácticamente independientes ✅
- Commodity vs FX: avg 0.05 — prácticamente independientes ✅

**IDM calculado:**
- Mode A (EWMAC only): **2.1654** — excelente, confirma diversificación real
- Mode B (EWMAC+Carry): **2.2340**
- Carver target con 10 instrumentos multi-asset: 1.8-2.0. Superamos expectativa.

**Comparación Mode A vs Mode B:**

| Métrica | Mode A (EWMAC) | Mode B (EWMAC+Carry) | Delta |
|---------|----------------|----------------------|-------|
| **Sharpe** | **0.314** | 0.228 | **-0.086** |
| Sortino | 0.382 | 0.281 | -0.101 |
| CAGR % | 3.25 | 2.09 | -1.15 |
| Vol % | 12.4 | 12.2 | -0.3 |
| Max DD % | -28.5 | -28.7 | -0.2 |
| Profit Factor | 1.05 | 1.03 | -0.02 |
| Calmar | 0.114 | 0.073 | -0.041 |

**⚠️ DECISIÓN DEFINITIVA: Carry DESCARTADO.**
Mode A (EWMAC only) supera a Mode B en TODAS las métricas.
La señal carry, incluso correctamente escalada, RESTA valor al portfolio.
No hay ambigüedad: carry se elimina del sistema.

**Contribución por instrumento (Mode A, EWMAC only):**

| Instrumento | PnL Total | % del Total | Clase |
|-------------|-----------|-------------|-------|
| SP500 | +$40,341 | 30.8% | equity |
| NASDAQ100 | +$33,005 | 25.2% | equity |
| GOLD | +$30,812 | 23.5% | commodity |
| NIKKEI225 | +$20,481 | 15.6% | equity |
| USDJPY | +$12,006 | 9.2% | fx |
| DAX40 | +$5,867 | 4.5% | equity |
| EURUSD | +$1,809 | 1.4% | fx |
| SILVER | -$89 | -0.1% | commodity |
| AUDUSD | -$4,705 | -3.6% | fx |
| GBPUSD | -$8,342 | -6.4% | fx |
| **TOTAL** | **+$131,184** | **100%** | |

**Análisis de diversificación (lo que importa):**

| Métrica | Mejor Individual (GOLD) | Portfolio (10 inst) | Mejora |
|---------|------------------------|---------------------|--------|
| Sharpe | 0.47 | 0.31 | -0.16 (peor) |
| Max DD | -41.2% | -28.5% | +12.7pp (mejor) |
| Vol | 13.8% | 12.4% | mejor control |
| CAGR | 5.50% | 3.25% | -2.25pp (peor) |
| Años ganadores | 56% | 59% | +3pp (mejor) |

El portfolio Sharpe (0.31) es MENOR que GOLD individual (0.47).
Esto es esperado: instrumentos negativos (GBPUSD, AUDUSD) arrastran el promedio.
Pero la diversificación funciona donde importa:
- **Max DD: -41% → -28%** (reducción de 13pp)
- **Vol más controlada: 12.4% vs target 12%**
- **Años ganadores: 59% vs 56%**

El criterio de Fase 5 era "IDM calculado, correlaciones OK" → **CUMPLIDO.**
- IDM = 2.17 (excelente)
- Correlaciones inter-clase < 0.05 (prácticamente independientes)
- El portfolio reduce DD significativamente vs instrumento individual

**Observaciones importantes (Axioma 6):**
1. GBPUSD y AUDUSD son los únicos instrumentos claramente negativos.
   Juntos restan $13K (-10% del PnL total).
   En Fase 6 (costes reales), es probable que sean aún peores.
   Candidatos a exclusión si no aportan diversificación neta.
2. SP500 + NASDAQ100 representan 56% del PnL con correlación 0.81 entre sí.
   Riesgo de concentración alto. Si us equity cae, pierde la mayoría del edge.
3. GOLD es el activo estrella (23.5% del PnL, correlación ~0.02 con equity) = diversificador real.
4. FX como clase aporta poco edge neto (+$742 neto), pero baja la correlación global.

**Archivos creados (sesión 2026-03-29):**
- `core/portfolio.py`: Correlación entre instrumentos, IDM, portfolio position sizing, portfolio backtest
- `tools/run_phase5_portfolio.py`: Runner Fase 5 con modos A/B, comparación, heatmap correlaciones

*Ultima edicion: 2026-03-29 (Fase 5 completa. IDM=2.17. Carry descartado definitivamente. Portfolio EWMAC only con 10 instrumentos.) por sesion Copilot*
