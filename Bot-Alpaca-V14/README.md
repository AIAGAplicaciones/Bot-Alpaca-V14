# ETF Momentum Rotation Bot

Bot de rotación mensual de ETFs por momentum, preparado para **paper trading con Alpaca** y con modo real desactivado por defecto.

## Estrategia

Cada mes, después del cierre del último día bursátil:

1. Descarga datos diarios de los ETFs.
2. Calcula:
   - SMA200 diaria.
   - Retorno 3 meses, usando 63 sesiones.
   - Retorno 6 meses, usando 126 sesiones.
   - Momentum score = 0.6 × retorno 6M + 0.4 × retorno 3M.
3. Descarta ETFs con:
   - cierre <= SMA200;
   - momentum <= 0;
   - datos incompletos.
4. Selecciona los 2 mejores ETFs por momentum.
5. Vende los ETFs actuales que ya no estén en el top 2.
6. Compra los nuevos ETFs hasta 200 EUR por ETF.
7. Si no hay ETFs válidos, queda en cash por defecto.

## Universo inicial

- SPY
- QQQ
- XLK
- XLV
- XLE
- GLD
- TLT

Activo defensivo opcional:

- SHY

## Seguridad por defecto

El bot viene configurado así:

```yaml
mode: paper
real_trading_enabled: false
capital_per_etf_eur: 200
max_positions: 2
max_total_exposure_eur: 400
allow_margin: false
allow_short: false
allow_leverage: false
```

Aunque conectes claves de Alpaca, no enviará órdenes reales salvo que cambies explícitamente:

```yaml
mode: real
real_trading_enabled: true
```

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` con tus claves de Alpaca Paper Trading.

## Ejecución de prueba

```bash
python main.py --dry-run
```

## Ejecución normal en paper

```bash
python main.py
```

## Backtest simplificado

```bash
python backtest/backtest_monthly_rotation.py
```

## Variables de entorno

Ver `.env.example`.

## Aviso

Esto no es asesoramiento financiero. El bot puede perder dinero. Antes de operar en real, valida:

- señales;
- órdenes;
- logs;
- límites de exposición;
- costes reales;
- fiscalidad;
- funcionamiento con cuenta paper.
