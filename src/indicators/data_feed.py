# src/indicators/data_feed.py
import json
import threading
import time
from typing import Callable, Optional
import websocket
from src.indicators.config import NSMConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DataFeed:
    def __init__(self, config: NSMConfig):
        self.config = config
        self.ws: Optional[websocket.WebSocketApp] = None
        self.candle_callback: Optional[Callable[[int, float], None]] = None
        self.ready_callback: Optional[Callable[[], None]] = None
        self.is_running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5

        symbol_lower = config.symbol.lower()
        timeframe = config.timeframe
        self.stream_url = f"wss://fstream.binance.com/ws/{symbol_lower}@kline_{timeframe}"

    def set_candle_callback(self, callback: Callable[[int, float], None]) -> None:
        self.candle_callback = callback
        logger.info("DataFeed инициализирован, Callback функция для обработки свечей установлена")

    def set_ready_callback(self, callback: Callable[[], None]) -> None:
        self.ready_callback = callback

    def on_message(self, _ws, message: str) -> None:
        try:
            data = json.loads(message)

            if 'k' not in data:
                return

            kline_data = data['k']

            if not kline_data.get('x', False):
                return

            timestamp = int(kline_data['T'])
            close_price = float(kline_data['c'])

            if close_price <= 0:
                logger.warning(f"Получена некорректная цена закрытия: {close_price}")
                return

            logger.debug(f"Получена новая свеча: timestamp={timestamp}, close={close_price}")

            if self.candle_callback:
                self.candle_callback(timestamp, close_price)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Ошибка обработки сообщения WebSocket: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обработке сообщения: {e}")

    @staticmethod
    def on_error(_ws, error) -> None:
        logger.error(f"Ошибка WebSocket: {error}")

    def on_close(self, _ws, close_status_code, close_msg) -> None:
        logger.warning(f"WebSocket соединение закрыто: код={close_status_code}, сообщение={close_msg}")

        if self.is_running and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            logger.info(f"Попытка переподключения #{self.reconnect_attempts}/{self.max_reconnect_attempts}")
            time.sleep(self.reconnect_delay)
            self._connect()
        elif self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Достигнуто максимальное количество попыток переподключения")
            self.is_running = False

    def on_open(self, _ws) -> None:
        logger.info(f"WebSocket соединение установлено с {self.stream_url}")
        self.reconnect_attempts = 0

        if self.ready_callback:
            self.ready_callback()

    def _connect(self) -> None:
        try:
            self.ws = websocket.WebSocketApp(
                self.stream_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )

            logger.info("Запуск WebSocket соединения...")
            self.ws.run_forever()

        except Exception as e:
            logger.error(f"Ошибка при создании WebSocket соединения: {e}")

    def start(self) -> None:
        if self.is_running:
            logger.warning("DataFeed уже запущен")
            return

        if not self.candle_callback:
            logger.error("Callback функция не установлена")
            return

        self.is_running = True
        self.reconnect_attempts = 0

        ws_thread = threading.Thread(target=self._connect, daemon=True)
        ws_thread.start()

    def stop(self) -> None:
        if not self.is_running:
            logger.warning("DataFeed уже остановлен")
            return

        self.is_running = False

        if self.ws:
            self.ws.close()

    def is_connected(self) -> bool:
        return self.ws is not None and self.is_running