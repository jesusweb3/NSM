# src/indicators/signal_manager.py
import time
from datetime import datetime
from typing import Optional, Callable
from src.indicators.config import NSMConfig
from src.indicators.nsm_indicator import NSMIndicator, Signal
from src.indicators.data_feed import DataFeed
from src.indicators.hist_data_load import HistoricalDataLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SignalManager:
    def __init__(self, config: NSMConfig):
        self.config = config
        self.nsm_indicator = NSMIndicator(config)
        self.data_feed = DataFeed(config)
        self.historical_loader = HistoricalDataLoader(config)
        self.last_signal: Optional[Signal] = None
        self.candles_processed = 0
        self.signals_generated = 0
        self.start_time: Optional[float] = None
        self.ready_callback: Optional[Callable[[], None]] = None

        self.data_feed.set_candle_callback(self.on_new_candle)
        self.data_feed.set_ready_callback(self.on_websocket_ready)

    def set_ready_callback(self, callback: Callable[[], None]) -> None:
        self.ready_callback = callback

    def on_websocket_ready(self) -> None:
        if self.ready_callback:
            self.ready_callback()

    def on_new_candle(self, timestamp: int, close_price: float) -> None:
        try:
            dt = datetime.fromtimestamp(timestamp / 1000)
            logger.debug(f"Обработка свечи: {dt.strftime('%Y-%m-%d %H:%M:%S')}, цена: {close_price}")

            # Добавляем свечу как live данные (не исторические)
            self.nsm_indicator.add_candle(close_price, is_historical=False)
            self.candles_processed += 1

            current_value = self.nsm_indicator.get_current_value_rounded()
            signal_time = dt.strftime('%H:%M:%S')

            # Логируем NSM значение после каждой свечи для сравнения с TradingView
            if current_value is not None:
                logger.info(f"NSM: {current_value:.8f} | Цена: {close_price} | {signal_time}")

            if not self.nsm_indicator.is_ready():
                logger.debug(f"Индикатор еще не готов. Обработано свечей: {self.candles_processed}")
                return

            current_signal = self.nsm_indicator.get_signal()

            if current_signal != Signal.NONE and current_signal != self.last_signal:
                self.signals_generated += 1

                if current_signal == Signal.LONG:
                    logger.info(f"🟢 LONG СИГНАЛ | {signal_time} | Цена: {close_price} | NSM: {current_value:.8f}")
                elif current_signal == Signal.SHORT:
                    logger.info(f"🔴 SHORT СИГНАЛ | {signal_time} | Цена: {close_price} | NSM: {current_value:.8f}")

                self.last_signal = current_signal

            if self.candles_processed % 50 == 0:
                logger.info(
                    f"Статистика: обработано {self.candles_processed} свечей, сгенерировано {self.signals_generated} сигналов")

        except Exception as e:
            logger.error(f"Ошибка при обработке свечи: {e}")

    def start(self) -> None:
        try:
            self.start_time = time.time()

            # Загружаем исторические данные
            logger.info("Загрузка исторических данных...")
            historical_candles = self.historical_loader.load_historical_candles()

            # Инициализируем NSM индикатор историческими данными
            logger.info("Инициализация NSM индикатора историческими данными...")
            for timestamp, close_price in historical_candles:
                self.nsm_indicator.add_candle(close_price, is_historical=True)

            # Завершаем историческую инициализацию
            self.nsm_indicator.finish_historical_loading()

            # Проверяем готовность индикатора
            if self.nsm_indicator.is_ready():
                logger.info(f"NSM индикатор готов к работе. Инициализирован {len(historical_candles)} свечами")
            else:
                logger.warning("NSM индикатор не готов после инициализации историческими данными")

            # Запускаем WebSocket для получения новых данных
            self.data_feed.start()

            logger.info("SignalManager успешно запущен. Ожидание данных...")

        except Exception as e:
            logger.error(f"Ошибка при запуске SignalManager: {e}")
            raise

    def stop(self) -> None:
        if not self.is_running():
            return

        try:
            self.data_feed.stop()

            if self.start_time:
                runtime = time.time() - self.start_time
                logger.info(f"Время работы: {runtime:.1f} секунд")

            logger.info(f"Финальная статистика:")
            logger.info(f"  - Обработано свечей: {self.candles_processed}")
            logger.info(f"  - Сгенерировано сигналов: {self.signals_generated}")

            stats = self.nsm_indicator.get_stats()
            logger.info(f"  - Статистика индикатора: {stats}")

        except Exception as e:
            logger.error(f"Ошибка при остановке SignalManager: {e}")

    def get_status(self) -> dict:
        return {
            "подключен": self.data_feed.is_connected(),
            "индикатор_готов": self.nsm_indicator.is_ready(),
            "обработано_свечей": self.candles_processed,
            "сгенерировано_сигналов": self.signals_generated,
            "последний_сигнал": self.last_signal.value if self.last_signal else "None",
            "текущее_значение_nsm": self.nsm_indicator.get_current_value(),
            "время_работы": time.time() - self.start_time if self.start_time else 0
        }

    def is_running(self) -> bool:
        return self.data_feed.is_connected()