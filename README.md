# SPY/QQQ Threshold Rebalance Bot

Bot de cartera fija **50% SPY / 50% QQQ** con rebalanceo por umbral, preparado
para **paper trading con Alpaca** y con modo real desactivado por defecto.

Esta estrategia sustituye a la antigua rotación por momentum, que tras
backtests largos (2011-2026) no superaba a una cartera simple 50/50.

## Estrategia

Cada vez que el bot se ejecuta:

1. Descarga el precio actual de SPY y QQQ desde Alpaca.
2. Lee las posiciones actuales (Alpaca es la fuente de verdad).
3. Calcula el peso de cada ETF sobre el valor total.
4. Decide:
   - si no hay posiciones, crea la cartera inicial 50/50;
   - si ambos pesos están dentro de **45%-55%**, no hace nada;
   - si alguno se sale de ese rango, rebalancea de vuelta a 50/50.
5. Registra todo (logs JSONL y, si hay `DATABASE_URL`, PostgreSQL).

No usa momentum, SMA200, ranking ni ETFs defensivos (GLD/TLT/SHY).

## Configuración por defecto (segura)

```yaml
bot:
  mode: paper
  real_trading_enabled: false
portfolio:
  target_weights: { SPY: 0.50, QQQ: 0.50 }
rebalance:
  threshold_absolute_weight: 0.05   # banda 45%-55%
  min_trade_value_eur: 10
capital:
  total_target_exposure_eur: 400
```

El bot **no envía órdenes** salvo que se active explícitamente:

```yaml
bot:
  mode: real
  real_trading_enabled: true
```

Progresión recomendada: `paper` (solo calcula y registra) → Alpaca Paper
(`mode: real` + `ALPACA_PAPER=true`, sin dinero real) → real
(`ALPACA_PAPER=false`).

## Variables de entorno (Railway)

Ver [.env.example](.env.example): `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`ALPACA_PAPER`, `EURUSD_RATE`, `DATABASE_URL` (opcional).

## Ejecución

```bash
python main.py            # ejecución normal (deploy)
python main.py --dry-run  # calcula y registra sin enviar órdenes
```

## Tests

```bash
pytest tests/
```

## Backtest

```bash
python backtest/backtest_spy_qqq.py
```

## Aviso

Esto no es asesoramiento financiero. El bot puede perder dinero. Valida en
paper antes de operar en real.
