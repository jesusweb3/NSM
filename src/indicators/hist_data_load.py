# src/indicators/hist_data_load.py
import requests
from typing import List, Tuple
from src.indicators.config import NSMConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HistoricalDataLoader:
    def __init__(self, config: NSMConfig):
        self.config = config
        self.base_url = "https://fapi.binance.com"
        self.candles_to_request = 1500

        logger.info("HistoricalDataLoader инициализирован.")

    def load_historical_candles(self) -> List[Tuple[int, float]]:
        """
        Загружает исторические свечи с Binance
        Возвращает список кортежей (timestamp, close_price)
        """
        try:
            params = {
                'symbol': self.config.symbol,
                'interval': self.config.timeframe,
                'limit': self.candles_to_request
            }

            url = f"{self.base_url}/fapi/v1/klines"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            klines_data = response.json()

            if not klines_data:
                raise ValueError("Получен пустой ответ от Binance API")

            historical_candles = []
            for i, kline in enumerate(klines_data):
                if i == len(klines_data) - 1:
                    continue

                timestamp = int(kline[6])
                close_price = float(kline[4])

                if close_price <= 0:
                    logger.warning(f"Некорректная цена в исторических данных: {close_price}")
                    continue

                historical_candles.append((timestamp, close_price))

            last_5_prices = [price for _, price in historical_candles[-5:]]
            last_5_prices.reverse()  # От самой свежей к самой старой
            logger.info(f"Последние 5 исторических цен: {last_5_prices}")

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

    @staticmethod
    def get_required_candles_count() -> int:
        return 1499