# Runbook operativo

## Antes de cada ejecución real

1. Confirmar que `config.yaml` tiene:
   - `mode: paper` si aún estás probando.
   - `real_trading_enabled: false` salvo activación manual.
2. Confirmar claves de Alpaca Paper en `.env`.
3. Ejecutar:

```bash
python main.py --dry-run --force
```

4. Revisar logs:
   - `logs/signals.jsonl`
   - `logs/portfolio.jsonl`
   - `logs/errors.jsonl`

## Activación real

No activar real hasta cumplir:

- 1 mes paper sin errores.
- 0 órdenes duplicadas.
- 0 operaciones fuera de horario.
- 0 posiciones inesperadas.
- 0 fallos de datos sin bloqueo.

Cambiar solo entonces:

```yaml
mode: real
real_trading_enabled: true
```

## Apagado de emergencia

Cambiar inmediatamente:

```yaml
real_trading_enabled: false
```

Y detener el proceso en Railway/VPS.
