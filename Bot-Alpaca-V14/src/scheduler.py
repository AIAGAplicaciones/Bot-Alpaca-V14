from __future__ import annotations

from datetime import datetime

import pandas as pd


def is_last_trading_day_of_month(latest_date: pd.Timestamp | datetime) -> bool:
    date = pd.Timestamp(latest_date).normalize()
    next_business_day = date + pd.offsets.BDay(1)
    return date.month != next_business_day.month
