# src/indicators/historical_data_loader.py
import requests
import time
from typing import List, Tuple
from src.indicators.config import NSMConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HistoricalDataLoader:
    def __init__(self, config: NSMConfig):
        self.config = config
        self.base_url = "https://fapi.binance.com"

        # Рассчитываем минимум свечей для NSM
        self.min_candles_needed = config.slow_period + config.normalization_period - 1
        # Запрашиваем +1 свечу чтобы убрать последнюю незакрытую
        self.candles_to_request = self.min_candles_needed + 1

        logger.info(
            f"HistoricalDataLoader инициализирован. Минимум свечей: {self.min_candles_needed}, запросим: {self.candles_to_request}")

    def load_historical_candles(self) -> List[Tuple[int, float]]:
        """
        Загружает исторические свечи с Binance
        Возвращает список кортежей (timestamp, close_price)
        """
        try:
            # Параметры запроса к Binance API
            params = {
                'symbol': self.config.symbol,
                'interval': self.config.timeframe,
                'limit': self.candles_to_request
            }

            url = f"{self.base_url}/fapi/v1/klines"
            logger.info(
                f"Запрос исторических данных: {self.config.symbol}, {self.config.timeframe}, лимит: {self.candles_to_request}")

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            klines_data = response.json()

            if not klines_data:
                raise ValueError("Получен пустой ответ от Binance API")

            # Парсим данные свечей
            historical_candles = []
            for i, kline in enumerate(klines_data):
                # Пропускаем последнюю свечу (она незакрытая)
                if i == len(klines_data) - 1:
                    continue

                timestamp = int(kline[6])  # Close time
                close_price = float(kline[4])  # Close price

                if close_price <= 0:
                    logger.warning(f"Некорректная цена в исторических данных: {close_price}")
                    continue

                historical_candles.append((timestamp, close_price))

            logger.info(f"Загружено {len(historical_candles)} исторических свечей")

            if len(historical_candles) < self.min_candles_needed:
                raise ValueError(
                    f"Недостаточно исторических данных. Получено: {len(historical_candles)}, нужно минимум: {self.min_candles_needed}")

            return historical_candles

        except requests.RequestException as e:
            logger.error(f"Ошибка при запросе к Binance API: {e}")
            raise
        except (ValueError, KeyError, IndexError) as e:
            logger.error(f"Ошибка при обработке данных от Binance: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке исторических данных: {e}")
            raise

    def get_required_candles_count(self) -> int:
        """Возвращает минимальное количество свечей для NSM"""
        return self.min_candles_needed