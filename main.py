# main.py
import signal
import sys
import time
from typing import Optional
from src.indicators.config import load_config
from src.indicators.signal_manager import SignalManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Глобальная переменная для SignalManager
signal_manager: Optional[SignalManager] = None


def signal_handler(_signum, _frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info("Получен сигнал завершения работы")
    global signal_manager
    if signal_manager:
        signal_manager.stop()
    sys.exit(0)


def on_bot_ready():
    """Callback когда бот полностью готов к работе"""
    logger.info("Бот успешно запущен.")


def main():
    global signal_manager

    try:
        logger.info("=== ЗАПУСК NSM ===")

        # Загрузка конфигурации
        config = load_config()

        # Создание и запуск SignalManager
        signal_manager = SignalManager(config)
        signal_manager.set_ready_callback(on_bot_ready)

        # Установка обработчиков сигналов для корректного завершения
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Запуск системы
        signal_manager.start()

        # Главный цикл
        try:
            while True:
                time.sleep(1)

                # Проверяем статус каждые 60 секунд
                if int(time.time()) % 60 == 0:
                    status = signal_manager.get_status()
                    if not status["подключен"]:
                        logger.warning("Потеряно соединение с источником данных")

        except KeyboardInterrupt:
            logger.info("Получена команда остановки от пользователя")

    except SystemExit:
        # Это нормальный выход из-за проблем с конфигурацией
        pass
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        if signal_manager:
            signal_manager.stop()
        logger.info("Бот успешно остановлен.")


if __name__ == "__main__":
    main()