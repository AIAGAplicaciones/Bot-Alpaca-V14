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

1. **Solo logs**: `mode: paper` + ejecutar con `--dry-run`. Calcula y registra,
   no envía nada. Útil para revisar la primera decisión.
2. **Alpaca Paper (dinero falso)** — defecto del deploy: `mode: paper` +
   `ALPACA_PAPER=true` + claves Alpaca. El bot compra de verdad en la cuenta
   paper de Alpaca (sin dinero real).
3. **Real**: `mode: real` + `real_trading_enabled: true` + `ALPACA_PAPER=false`.

El bot se niega a operar con dinero real si está en `mode: paper`. No pasar a
real hasta tener semanas en Alpaca Paper sin errores ni posiciones inesperadas.

## Apagado de emergencia

Cambiar inmediatamente y redeploy:

```yaml
bot:
  real_trading_enabled: false
```

El kill switch ya detiene el bot automáticamente si faltan datos, el broker no
responde, hay posiciones inesperadas, errores de orden o pérdidas que superan
los límites configurados.
