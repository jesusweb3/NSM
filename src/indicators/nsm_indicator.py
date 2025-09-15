# src/indicators/nsm_indicator.py
from enum import Enum
from typing import Optional, List
from src.indicators.config import NSMConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Signal(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


class NSMIndicator:
    def __init__(self, config: NSMConfig):
        self.config = config
        self.prices: List[float] = []

        self.fast_ema: Optional[float] = None
        self.slow_ema: Optional[float] = None
        self.smoothed_val: Optional[float] = None

        self.macd_history: List[float] = []
        self.normalized_history: List[float] = []
        self.smoothed_history: List[float] = []

        self.alpha_fast = 2.0 / (1.0 + self.config.fast_period)
        self.alpha_slow = 2.0 / (1.0 + self.config.slow_period)
        self.alpha_smooth = 2.0 / (1.0 + self.config.smoothing_period)

        logger.info("NSM индикатор инициализирован")

    def add_candle(self, close_price: float) -> None:
        if close_price <= 0:
            logger.warning(f"Получена некорректная цена: {close_price}")
            return

        self.prices.append(close_price)

        if len(self.prices) < self.config.slow_period:
            return

        if self.fast_ema is None:
            self.fast_ema = close_price
            self.slow_ema = close_price
        else:
            self.fast_ema = self.fast_ema + self.alpha_fast * (close_price - self.fast_ema)
            self.slow_ema = self.slow_ema + self.alpha_slow * (close_price - self.slow_ema)

        macd = self.fast_ema - self.slow_ema
        self.macd_history.append(macd)

        if len(self.macd_history) >= self.config.normalization_period:
            recent_macd = self.macd_history[-self.config.normalization_period:]
            macd_max = max(recent_macd)
            macd_min = min(recent_macd)

            if macd_max != macd_min:
                normalized_val = 2.0 * (macd - macd_min) / (macd_max - macd_min) - 1.0
            else:
                normalized_val = 0.0

            self.normalized_history.append(normalized_val)

            if self.smoothed_val is None:
                self.smoothed_val = normalized_val
            else:
                self.smoothed_val = self.smoothed_val + self.alpha_smooth * (normalized_val - self.smoothed_val)

            self.smoothed_history.append(self.smoothed_val)

    def get_signal(self) -> Signal:
        if len(self.smoothed_history) < 2:
            return Signal.NONE

        current_val = self.smoothed_history[-1]
        previous_val = self.smoothed_history[-2]

        if current_val > previous_val:
            return Signal.LONG
        elif current_val < previous_val:
            return Signal.SHORT
        else:
            return Signal.NONE

    def get_current_value(self) -> Optional[float]:
        if not self.smoothed_history:
            return None
        return self.smoothed_history[-1]

    def is_ready(self) -> bool:
        return len(self.smoothed_history) >= 2

    def get_stats(self) -> dict:
        return {
            "цен_получено": len(self.prices),
            "macd_значений": len(self.macd_history),
            "сглаженных_значений": len(self.smoothed_history),
            "готов_к_сигналам": self.is_ready(),
            "текущее_значение": self.get_current_value()
        }