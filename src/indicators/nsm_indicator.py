# src/indicators/nsm_indicator.py
import numpy as np
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

        self.emaf: Optional[np.float64] = None
        self.emas: Optional[np.float64] = None
        self.val: np.float64 = np.float64(0.0)

        self.macd_history: List[float] = []
        self.val_history: List[float] = []

        self.bar_index = 0
        self.historical_initialization = True
        self.current_trend: Optional[Signal] = None

        self.alphaf = np.float64(2.0) / np.float64(1.0 + max(self.config.fast_period, 1))
        self.alphas = np.float64(2.0) / np.float64(1.0 + max(self.config.slow_period, 1))
        self.alphasm = np.float64(2.0) / np.float64(1.0 + max(self.config.smoothing_period, 1))

        logger.info("NSM индикатор инициализирован.")

    @staticmethod
    def _calculate_sma(prices: List[float], period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        return np.mean(prices[-period:], dtype=np.float64)

    def add_candle(self, close_price: float) -> None:
        if close_price <= 0:
            logger.warning(f"Получена некорректная цена: {close_price}")
            return

        price = np.float64(close_price)
        self.prices.append(float(price))

        if self.bar_index > self.config.slow_period:
            if self.emaf is None:
                sma_fast = self._calculate_sma(self.prices, self.config.fast_period)
                if sma_fast is not None:
                    self.emaf = sma_fast

            if self.emas is None:
                sma_slow = self._calculate_sma(self.prices, self.config.slow_period)
                if sma_slow is not None:
                    self.emas = sma_slow

            if self.emaf is not None and self.emas is not None:
                self.emaf = self.emaf + self.alphaf * (price - self.emaf)
                self.emas = self.emas + self.alphas * (price - self.emas)

                imacd = self.emaf - self.emas
                self.macd_history.append(float(imacd))

                if len(self.macd_history) >= self.config.normalization_period:
                    recent_macd = self.macd_history[-self.config.normalization_period:]
                else:
                    recent_macd = self.macd_history

                if len(recent_macd) > 0:
                    mmax = np.float64(max(recent_macd))
                    mmin = np.float64(min(recent_macd))

                    if mmin != mmax:
                        nval = np.float64(2.0) * (imacd - mmin) / (mmax - mmin) - np.float64(1.0)
                    else:
                        nval = np.float64(0.0)

                    self.val = self.val + self.alphasm * (nval - self.val)
                    self.val_history.append(float(self.val))

        self.bar_index += 1

    def finish_historical_loading(self) -> None:
        self.historical_initialization = False

        if len(self.val_history) >= 2:
            current_val = self.val_history[-1]
            previous_val = self.val_history[-2]

            if current_val > previous_val:
                self.current_trend = Signal.LONG
                logger.info("Текущий тренд: LONG")
            elif current_val < previous_val:
                self.current_trend = Signal.SHORT
                logger.info("Текущий тренд: SHORT")
            else:
                self.current_trend = Signal.NONE
                logger.info("Текущий тренд: NONE")

        logger.info("Историческая инициализация завершена.")

    def get_signal(self) -> Signal:
        if self.historical_initialization:
            return Signal.NONE

        if len(self.val_history) < 2:
            return Signal.NONE

        current_val = self.val_history[-1]
        previous_val = self.val_history[-2]

        if current_val > previous_val:
            new_signal = Signal.LONG
        elif current_val < previous_val:
            new_signal = Signal.SHORT
        else:
            return Signal.NONE

        if new_signal != self.current_trend:
            self.current_trend = new_signal
            return new_signal

        return Signal.NONE

    def get_current_value(self) -> Optional[float]:
        if not self.val_history:
            return None
        return self.val_history[-1]

    def get_current_value_rounded(self) -> Optional[float]:
        value = self.get_current_value()
        if value is None:
            return None
        return round(value, 8)

    def is_ready(self) -> bool:
        return len(self.val_history) >= 2

    def get_stats(self) -> dict:
        return {
            "цен_получено": len(self.prices),
            "bar_index": self.bar_index,
            "macd_значений": len(self.macd_history),
            "val_значений": len(self.val_history),
            "готов_к_сигналам": self.is_ready(),
            "текущее_значение": self.get_current_value(),
            "историческая_инициализация": self.historical_initialization,
            "текущий_тренд": self.current_trend.value if self.current_trend else "None",
            "emaf": round(float(self.emaf), 8) if self.emaf is not None else "Not ready",
            "emas": round(float(self.emas), 8) if self.emas is not None else "Not ready"
        }