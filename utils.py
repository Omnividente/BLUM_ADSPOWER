import logging
from colorama import Fore, Style, init
import sys

# Инициализация colorama для Windows
init(autoreset=True)

# Глобальная переменная для логгера
logger = None
# Функция для настройки логирования
# Класс для форматирования логов
# Класс для форматирования логов
# Класс для форматирования логов
class CustomFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record):
        record.asctime = self.formatTime(record, self.datefmt).split('.')[0]
        log_message = super().format(record)
        # Устанавливаем цвет времени
        log_message = log_message.replace(record.asctime, f"{Fore.LIGHTYELLOW_EX}{record.asctime}{Style.RESET_ALL}")
        # Устанавливаем цвет уровня логирования
        levelname = f"{self.COLORS.get(record.levelno, Fore.WHITE)}{record.levelname}{Style.RESET_ALL}"
        log_message = log_message.replace(record.levelname, levelname)
        # Устанавливаем цвет сообщения в зависимости от уровня
        message_color = self.COLORS.get(record.levelno, Fore.WHITE)
        log_message = log_message.replace(record.msg, f"{message_color}{record.msg}{Style.RESET_ALL}")
        return log_message

# Функция для настройки логирования
def setup_logger():
    global logger
    if logger is None:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)  # Установите уровень логирования на DEBUG или INFO

        # Настроим обработчик для вывода логов в консоль
        handler = logging.StreamHandler()
        handler.setFormatter(CustomFormatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)

    return logger

# Настроим логирование (если не было настроено ранее)
logger = setup_logger()

balances = []

def read_accounts_from_file():
    try:
        with open('accounts.txt', 'r') as file:
            accounts = [line.strip() for line in file.readlines()]
            logger.debug(f"Successfully read {len(accounts)} accounts from file.")
            return accounts
    except FileNotFoundError:
        logger.error("accounts.txt file not found.")
        return []
    except Exception as e:
        logger.exception(f"Unexpected error while reading accounts file: {str(e)}")
        return []

def write_accounts_to_file(accounts):
    try:
        with open('accounts.txt', 'w') as file:
            for account in accounts:
                file.write(f"{account}\n")
        logger.debug("Accounts written to file successfully.")
    except IOError as e:
        logger.error(f"Failed to write accounts to file: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error while writing accounts to file: {str(e)}")

def reset_balances():
    global balances
    balances = []
    logger.debug("Balances reset successfully.")

def load_settings():
    settings = {}
    try:
        with open('settings.txt', 'r') as f:
            for line in f:
                key, value = line.strip().split('=', 1)
                settings[key.strip()] = value.strip()
    except FileNotFoundError:
        logger.error("Settings file 'settings.txt' not found.")
    except Exception as e:
        logger.error(f"Error reading settings file: {e}")
    return settings


def get_max_games(settings):
    """Возвращаем максимальное количество игр из настроек."""
    # Приводим ключи в нижний регистр и ищем max_games независимо от регистра
    settings = {k.lower(): v for k, v in settings.items()}  # Приводим все ключи в нижний регистр
    max_games = settings.get('max_games', None)
    
    # Если значение max_games задано, проверяем, является ли оно числом
    if max_games and max_games.isdigit():
        return int(max_games)
    else:
        if max_games:
            logger.warning(f"Invalid value for max_games: {max_games}. Using all available games.")
        return None  # Если max_games не задано или указано некорректно, не ограничиваем количество игр

