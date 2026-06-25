# Runbook operativo

## Estrategia activa

50% SPY / 50% QQQ, rebalanceo solo si algún peso sale de la banda 45%-55%.

## Antes de operar

1. Confirmar en `config.yaml`:
   - `bot.mode: paper` mientras pruebas.
   - `bot.real_trading_enabled: false` salvo activación manual.
2. Configurar variables en Railway (ver `.env.example`).
3. Prueba local:

```bash
python main.py --dry-run
```

4. Revisar logs en `logs/`:
   - `portfolio.jsonl` (decisión y pesos)
   - `orders.jsonl`
   - `rejected.jsonl`
   - `errors.jsonl`

   Y, si hay PostgreSQL, las tablas `portfolio_snapshots`, `bot_orders`,
   `bot_runs`, `known_positions`, `state_kv`.

## Activación gradual

1. **Paper interno** (defecto): `mode: paper`. Solo calcula y registra.
2. **Alpaca Paper** (sin dinero real): `mode: real`, `real_trading_enabled: true`,
   `ALPACA_PAPER=true`.
3. **Real**: lo anterior con `ALPACA_PAPER=false`.

No pasar a real hasta tener semanas de paper sin errores ni posiciones
inesperadas.

## Apagado de emergencia

Cambiar inmediatamente y redeploy:

```yaml
bot:
  real_trading_enabled: false
```

El kill switch ya detiene el bot automáticamente si faltan datos, el broker no
responde, hay posiciones inesperadas, errores de orden o pérdidas que superan
los límites configurados.
