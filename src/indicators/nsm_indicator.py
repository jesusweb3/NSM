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

        # Для правильного расчета EMA
        self.fast_ema_values: List[float] = []
        self.slow_ema_values: List[float] = []

        # NSM компоненты
        self.macd_history: List[float] = []
        self.smoothed_history: List[float] = []
        self.smoothed_val: float = 0.0

        # Для отслеживания состояния
        self.historical_initialization = True
        self.current_trend: Optional[Signal] = None  # Текущее состояние тренда

        # Коэффициенты точно как в TradingView
        self.alpha_fast = 2.0 / (1.0 + max(self.config.fast_period, 1))
        self.alpha_slow = 2.0 / (1.0 + max(self.config.slow_period, 1))
        self.alpha_smooth = 2.0 / (1.0 + max(self.config.smoothing_period, 1))

        logger.info("NSM индикатор инициализирован")

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """Точно такой же расчет EMA как в рабочем MACD коде"""
        prices_array = np.array(prices, dtype=np.float64)
        n = len(prices_array)
        if n < period:
            return [np.nan] * n

        ema = np.full(n, np.nan, dtype=np.float64)
        alpha = np.float64(2.0) / np.float64(period + 1.0)

        first_idx = period - 1
        window = prices_array[0:period]
        if np.any(np.isnan(window)):
            return ema.tolist()

        ema[first_idx] = np.mean(window, dtype=np.float64)
        for i in range(first_idx + 1, n):
            if not np.isnan(prices_array[i]) and not np.isnan(ema[i - 1]):
                ema[i] = alpha * prices_array[i] + (np.float64(1.0) - alpha) * ema[i - 1]

        return ema.tolist()

    def add_candle(self, close_price: float, is_historical: bool = False) -> None:
        if close_price <= 0:
            logger.warning(f"Получена некорректная цена: {close_price}")
            return

        self.prices.append(close_price)

        # Пересчитываем EMA для всего массива (как в рабочем коде)
        self.fast_ema_values = self.calculate_ema(self.prices, self.config.fast_period)
        self.slow_ema_values = self.calculate_ema(self.prices, self.config.slow_period)

        # Проверяем, есть ли валидные EMA значения
        current_fast = self.fast_ema_values[-1]
        current_slow = self.slow_ema_values[-1]

        if np.isnan(current_fast) or np.isnan(current_slow):
            return

        # Вычисляем MACD
        macd_value = current_fast - current_slow
        self.macd_history.append(macd_value)

        # Нормализация: берем последние normalization_period значений
        if len(self.macd_history) >= self.config.normalization_period:
            recent_macd = self.macd_history[-self.config.normalization_period:]
        else:
            recent_macd = self.macd_history

        if len(recent_macd) > 0:
            mmax = max(recent_macd)
            mmin = min(recent_macd)

            # Нормализация как в TradingView
            if mmin != mmax:
                nval = 2.0 * (macd_value - mmin) / (mmax - mmin) - 1.0
            else:
                nval = 0.0

            # Сглаживание как в TradingView: val := val[1] + alphasm*(nval-val[1])
            self.smoothed_val = self.smoothed_val + self.alpha_smooth * (nval - self.smoothed_val)
            self.smoothed_history.append(self.smoothed_val)

    def finish_historical_loading(self) -> None:
        """Анализирует историю и определяет текущий тренд"""
        self.historical_initialization = False

        # Определяем текущий тренд по последним значениям истории
        if len(self.smoothed_history) >= 2:
            current_val = self.smoothed_history[-1]
            previous_val = self.smoothed_history[-2]

            if current_val > previous_val:
                self.current_trend = Signal.LONG
                logger.info("Текущий тренд: LONG (рост)")
            elif current_val < previous_val:
                self.current_trend = Signal.SHORT
                logger.info("Текущий тренд: SHORT (падение)")
            else:
                self.current_trend = Signal.NONE
                logger.info("Текущий тренд: боковое движение")

        logger.info("Историческая инициализация завершена. Готов к live сигналам.")

    def get_signal(self) -> Signal:
        # Во время исторической инициализации не генерируем сигналы
        if self.historical_initialization:
            return Signal.NONE

        if len(self.smoothed_history) < 2:
            return Signal.NONE

        current_val = self.smoothed_history[-1]
        previous_val = self.smoothed_history[-2]

        # Определяем направление
        if current_val > previous_val:
            new_signal = Signal.LONG
        elif current_val < previous_val:
            new_signal = Signal.SHORT
        else:
            return Signal.NONE

        # Генерируем сигнал только при смене тренда
        if new_signal != self.current_trend:
            self.current_trend = new_signal
            return new_signal

        return Signal.NONE

    def get_current_value(self) -> Optional[float]:
        if not self.smoothed_history:
            return None
        return self.smoothed_history[-1]

    def get_current_value_rounded(self) -> Optional[float]:
        """Возвращает NSM значение с точностью до 8 знаков как в TradingView"""
        value = self.get_current_value()
        if value is None:
            return None
        return round(value, 8)

    def is_ready(self) -> bool:
        return len(self.smoothed_history) >= 2

    def get_stats(self) -> dict:
        return {
            "цен_получено": len(self.prices),
            "macd_значений": len(self.macd_history),
            "сглаженных_значений": len(self.smoothed_history),
            "готов_к_сигналам": self.is_ready(),
            "текущее_значение": self.get_current_value(),
            "историческая_инициализация": self.historical_initialization,
            "текущий_тренд": self.current_trend.value if self.current_trend else "None",
            "fast_ema_готов": len(self.fast_ema_values) > 0 and not np.isnan(
                self.fast_ema_values[-1]) if self.fast_ema_values else False,
            "slow_ema_готов": len(self.slow_ema_values) > 0 and not np.isnan(
                self.slow_ema_values[-1]) if self.slow_ema_values else False
        }