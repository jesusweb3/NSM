# src/indicators/config.py
import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NSMConfig:
    fast_period: int
    slow_period: int
    smoothing_period: int
    normalization_period: int
    timeframe: str
    symbol: str
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None
    binance_testnet: bool = True


def load_config() -> NSMConfig:
    load_dotenv()

    required_vars = {
        'NSM_FAST_PERIOD': 'Быстрый период NSM не установлен в .env файле',
        'NSM_SLOW_PERIOD': 'Медленный период NSM не установлен в .env файле',
        'NSM_SMOOTHING_PERIOD': 'Период сглаживания NSM не установлен в .env файле',
        'NSM_NORMALIZATION_PERIOD': 'Период нормализации NSM не установлен в .env файле',
        'TIMEFRAME': 'Таймфрейм не установлен в .env файле',
        'SYMBOL': 'Символ торговой пары не установлен в .env файле'
    }

    missing_vars = []
    for var, message in required_vars.items():
        if os.getenv(var) is None:
            missing_vars.append(message)

    if missing_vars:
        logger.error("Отсутствуют обязательные переменные окружения:")
        for msg in missing_vars:
            logger.error(f"  - {msg}")
        raise SystemExit(1)

    try:
        fast_period = int(os.getenv('NSM_FAST_PERIOD'))
        slow_period = int(os.getenv('NSM_SLOW_PERIOD'))
        smoothing_period = int(os.getenv('NSM_SMOOTHING_PERIOD'))
        normalization_period = int(os.getenv('NSM_NORMALIZATION_PERIOD'))
    except ValueError as e:
        logger.error(f"Некорректное числовое значение в .env файле: {e}")
        raise SystemExit(1)

    timeframe = os.getenv('TIMEFRAME')
    symbol = os.getenv('SYMBOL')

    binance_api_key = os.getenv('BINANCE_API_KEY')
    binance_secret_key = os.getenv('BINANCE_SECRET_KEY')
    binance_testnet_str = os.getenv('BINANCE_TESTNET')
    binance_testnet = binance_testnet_str.lower() == 'true' if binance_testnet_str else True

    if fast_period >= slow_period:
        logger.error("Быстрый период должен быть меньше медленного периода")
        raise SystemExit(1)

    if any(period <= 0 for period in [fast_period, slow_period, smoothing_period, normalization_period]):
        logger.error("Все периоды должны быть положительными числами")
        raise SystemExit(1)

    logger.info(
        f"Конфигурация успешно загружена - {symbol}, {timeframe}, {fast_period}/{slow_period}/{smoothing_period}/{normalization_period}")

    return NSMConfig(
        fast_period=fast_period,
        slow_period=slow_period,
        smoothing_period=smoothing_period,
        normalization_period=normalization_period,
        timeframe=timeframe,
        symbol=symbol,
        binance_api_key=binance_api_key,
        binance_secret_key=binance_secret_key,
        binance_testnet=binance_testnet
    )