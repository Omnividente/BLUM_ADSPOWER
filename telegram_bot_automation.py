import re
import random
import time
import traceback
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException, StaleElementReferenceException
from utils import setup_logger, get_max_games, stop_event
from browser_manager import BrowserManager
from colorama import Fore, Style 
# Настроим логирование (если не было настроено ранее)
logger = setup_logger()

class TelegramBotAutomation:
    MAX_RETRIES = 3

    def __init__(self, serial_number, settings):
        self.max_games = get_max_games(settings)  # max_games сохраняем в атрибут объекта
        self.remaining_games = None
        self.serial_number = serial_number        
        self.short_account_id = f"#{self.serial_number}"
        self.username = None  # Initialize username as None
        self.balance = 0.0  # Initialize balance as 0.0
        self.browser_manager = BrowserManager(serial_number)
        self.settings = settings        
        self.driver = None
        self.first_game_start = True
        self.is_limited = False  # Attribute to track limitation status
        logger.debug(f"{self.short_account_id}: Initializing automation for account.")

        # Ожидание завершения предыдущей сессии браузера
        if not self.browser_manager.wait_browser_close():
            logger.error(f"{self.short_account_id}: Failed to close previous browser session.")
            raise RuntimeError("Failed to close previous browser session")

        # Запуск браузера
        if not self.browser_manager.start_browser():
            logger.error(f"{self.short_account_id}: Failed to start browser.")
            raise RuntimeError("Failed to start browser")

        # Сохранение экземпляра драйвера
        self.driver = self.browser_manager.driver

        logger.debug(f"{self.short_account_id}: Automation initialization completed successfully.")


    def safe_click(self, element):
        """
        Безопасный клик по элементу.
        """
        try:
            logger.debug(
                f"#{self.serial_number}: Attempting to scroll to element.")
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element)
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(element))
            element.click()
            logger.debug(
                f"#{self.serial_number}: Element clicked successfully.")
        except (WebDriverException, StaleElementReferenceException) as e:
            error_message = str(e).splitlines()[0]
            logger.debug(
                f"#{self.serial_number}: Error during safe click: {error_message}")
            try:
                logger.debug(
                    f"#{self.serial_number}: Attempting JavaScript click as fallback.")
                self.driver.execute_script("arguments[0].click();", element)
                logger.debug(
                    f"#{self.serial_number}: JavaScript click succeeded.")
            except (WebDriverException, StaleElementReferenceException) as e:
                error_message = str(e).splitlines()[0]
                logger.error(
                    f"#{self.serial_number}: JavaScript click failed: {error_message}")
            except Exception as e:
                logger.error(
                    f"#{self.serial_number}: Unexpected error during fallback click: {e}")
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Unexpected error during safe click: {e}")


    def navigate_to_bot(self):
        """
        Очищает кэш браузера, загружает Telegram Web и закрывает лишние окна.
        """
        logger.debug(
            f"#{self.serial_number}: Starting navigation to Telegram web.")
        self.clear_browser_cache_and_reload()

        if stop_event.is_set():  # Проверка перед выполнением долгих операций
            return False

        retries = 0
        while retries < self.MAX_RETRIES and not stop_event.is_set():
            try:
                logger.debug(
                    f"#{self.serial_number}: Attempting to load Telegram web (attempt {retries + 1}).")
                self.driver.get('https://web.telegram.org/k/')

                if stop_event.is_set():  # Проверка после загрузки страницы
                    return False

                logger.debug(
                    f"#{self.serial_number}: Telegram web loaded successfully.")
                logger.debug(f"#{self.serial_number}: Closing extra windows.")
                self.close_extra_windows()

                # Эмуляция ожидания с проверкой stop_event
                sleep_time = random.randint(5, 7)
                logger.debug(
                    f"#{self.serial_number}: Sleeping for {sleep_time} seconds.")
                for _ in range(sleep_time):
                    if stop_event.is_set():
                        logger.debug(
                            f"#{self.serial_number}: Stopping sleep due to stop_event.")
                        return False
                    time.sleep(1)  # Короткий sleep для проверки stop_event

                return True

            except (WebDriverException, TimeoutException) as e:
                error_message = str(e).splitlines()[0]
                logger.warning(
                    f"#{self.serial_number}: Exception in navigating to Telegram bot (attempt {retries + 1}): {error_message}")
                retries += 1

                # Проверка во время ожидания перед повторной попыткой
                for _ in range(5):
                    if stop_event.is_set():
                        logger.debug(
                            f"#{self.serial_number}: Stopping retry sleep due to stop_event.")
                        return False
                    time.sleep(1)

        logger.error(
            f"#{self.serial_number}: Failed to navigate to Telegram web after {self.MAX_RETRIES} attempts.")
        return False

    
    def close_extra_windows(self):
        """
        Закрывает все дополнительные окна, кроме текущего.
        """
        try:
            current_window = self.driver.current_window_handle
            all_windows = self.driver.window_handles

            logger.debug(
                f"#{self.serial_number}: Current window handle: {current_window}")
            logger.debug(
                f"#{self.serial_number}: Total open windows: {len(all_windows)}")

            for window in all_windows:
                if window != current_window:
                    logger.debug(
                        f"#{self.serial_number}: Closing window: {window}")
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    logger.debug(
                        f"#{self.serial_number}: Window {window} closed successfully.")

            # Переключаемся обратно на исходное окно
            self.driver.switch_to.window(current_window)
            logger.debug(
                f"#{self.serial_number}: Switched back to the current window: {current_window}")
        except WebDriverException as e:
            error_message = str(e).splitlines()[0]
            logger.debug(
                f"#{self.serial_number}: Exception while closing extra windows: {error_message}")
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Unexpected error during closing extra windows: {e}")

    
    def send_message(self):
        """
        Отправляет сообщение в указанный Telegram-групповой чат.
        """
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                logger.debug(
                    f"#{self.serial_number}: Attempt {retries + 1} to send message.")

                # Находим область ввода сообщения
                chat_input_area = self.wait_for_element(
                    By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[2]/input[1]'
                )
                if chat_input_area:
                    logger.debug(
                        f"#{self.serial_number}: Chat input area found.")
                    chat_input_area.click()
                    group_url = self.settings.get(
                        'TELEGRAM_GROUP_URL', 'https://t.me/CryptoProjects_sbt'
                    )
                    logger.debug(
                        f"#{self.serial_number}: Typing group URL: {group_url}")
                    chat_input_area.send_keys(group_url)
                else:
                    logger.warning(
                        f"#{self.serial_number}: Chat input area not found.")
                    retries += 1
                    time.sleep(5)
                    continue

                # Находим область поиска
                search_area = self.wait_for_element(
                    By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[1]/div[1]/div[3]/div[2]/div[2]/div[2]/div[1]/div[1]/div[1]/div[2]/ul[1]/a[1]/div[1]'
                )
                if search_area:
                    logger.debug(f"#{self.serial_number}: Search area found.")
                    search_area.click()
                    logger.debug(
                        f"#{self.serial_number}: Group search clicked.")
                else:
                    logger.warning(
                        f"#{self.serial_number}: Search area not found.")
                    retries += 1
                    time.sleep(5)
                    continue

                # Добавляем задержку перед завершением
                sleep_time = random.randint(5, 7)
                logger.debug(
                    f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                time.sleep(sleep_time)
                logger.debug(
                    f"#{self.serial_number}: Message successfully sent to the group.")
                return True
            except (NoSuchElementException, WebDriverException) as e:
                error_message = str(e).splitlines()[0]
                logger.warning(
                    f"#{self.serial_number}: Failed to perform action (attempt {retries + 1}): {error_message}")
                retries += 1
                time.sleep(5)
            except Exception as e:
                logger.error(f"#{self.serial_number}: Unexpected error: {e}")
                break

        logger.error(
            f"#{self.serial_number}: Failed to send message after {self.MAX_RETRIES} attempts.")
        return False

    
    def click_link(self):
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                logger.debug(
                    f"#{self.serial_number}: Attempt {retries + 1} to click link.")

                # Получаем ссылку из настроек
                bot_link = self.settings.get(
                    'BOT_LINK', 'https://t.me/blum/app?startapp=ref_vNDGLmgnYL')
                logger.debug(f"#{self.serial_number}: Bot link: {bot_link}")

                # Поиск элемента ссылки
                link = self.wait_for_element(
                    By.CSS_SELECTOR, f"a[href*='{bot_link}']")
                if link:
                    logger.debug(
                        f"#{self.serial_number}: Link found. Scrolling to the link.")

                    # Скроллинг к ссылке
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", link)
                    # Небольшая задержка для завершения скроллинга
                    time.sleep(1)

                    # Клик по ссылке
                    link.click()
                    logger.debug(
                        f"#{self.serial_number}: Link clicked successfully.")
                    time.sleep(2)

                # Поиск и клик по кнопке запуска
                launch_button = self.wait_for_element(
                    By.CSS_SELECTOR, "button.popup-button.btn.primary.rp", timeout=5)
                if launch_button:
                    logger.debug(
                        f"#{self.serial_number}: Launch button found. Clicking it.")
                    launch_button.click()
                    logger.debug(
                        f"#{self.serial_number}: Launch button clicked.")

                # Проверка iframe
                if self.check_iframe_src():
                    logger.info(
                        f"#{self.serial_number}: App loaded successfully.")

                    # Случайная задержка перед переключением на iframe
                    sleep_time = random.randint(3, 5)
                    logger.debug(
                        f"#{self.serial_number}: Sleeping for {sleep_time} seconds before switching to iframe.")
                    time.sleep(sleep_time)

                    # Переключение на iframe
                    self.switch_to_iframe()
                    logger.debug(
                        f"#{self.serial_number}: Switched to iframe successfully.")
                    return True
                else:
                    logger.warning(
                        f"#{self.serial_number}: Iframe did not load expected content.")
                    raise Exception("Iframe content validation failed.")

            except (NoSuchElementException, WebDriverException, TimeoutException) as e:
                logger.warning(
                    f"#{self.serial_number}: Failed to click link or interact with elements (attempt {retries + 1}): {str(e).splitlines()[0]}")
                retries += 1
                time.sleep(5)
            except Exception as e:
                logger.error(
                    f"#{self.serial_number}: Unexpected error during click_link: {str(e).splitlines()[0]}")
                break

        logger.error(
            f"#{self.serial_number}: All attempts to click link failed after {self.MAX_RETRIES} retries.")
        return False



    def wait_for_element(self, by, value, timeout=10):
        """
        Ожидает, пока элемент станет кликабельным, в течение указанного времени.

        :param by: Метод локатора (например, By.XPATH, By.ID).
        :param value: Значение локатора.
        :param timeout: Время ожидания в секундах (по умолчанию 10).
        :return: Найденный элемент, если он кликабельный, иначе None.
        """
        try:
            logger.debug(
                f"#{self.serial_number}: Waiting for element by {by} with value '{value}' for up to {timeout} seconds.")
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            logger.debug(
                f"#{self.serial_number}: Element found and clickable: {value}")
            return element
        except TimeoutException:
            logger.debug(
                f"#{self.serial_number}: Element not found or not clickable within {timeout} seconds: {value}")
            return None
        except (WebDriverException, StaleElementReferenceException) as e:
            logger.debug(
                f"#{self.serial_number}: Error while waiting for element {value}: {str(e).splitlines()[0]}")
            return None
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Unexpected error while waiting for element: {str(e)}")
            return None

    def clear_browser_cache_and_reload(self):
        """
        Очищает кэш браузера и перезагружает текущую страницу.
        """
        try:
            logger.debug(
                f"#{self.serial_number}: Attempting to clear browser cache.")

            # Очистка кэша через CDP команду
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            logger.debug(
                f"#{self.serial_number}: Browser cache successfully cleared.")

            # Перезагрузка текущей страницы
            logger.debug(f"#{self.serial_number}: Refreshing the page.")
            self.driver.refresh()
            logger.debug(
                f"#{self.serial_number}: Page successfully refreshed.")
        except WebDriverException as e:
            logger.warning(
                f"#{self.serial_number}: WebDriverException while clearing cache or reloading page: {str(e).splitlines()[0]}")
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Unexpected error during cache clearing or page reload: {str(e)}")



    def preparing_account(self):
        attempts = 2  # Maximum number of attempts

        for attempt in range(attempts):
            found = False

            if stop_event.is_set():
                logger.info(f"{self.short_account_id}: Stop event detected. Exiting preparing_account.")
                return

            try:
                # Wait for either the XPath or CSS selector to become clickable
                wait = WebDriverWait(self.driver, 10)
                element = wait.until(
                    EC.any_of(
                        EC.element_to_be_clickable((By.XPATH, "/html[1]/body[1]/div[1]/div[1]/div[1]/div[1]/div[2]/div[2]/div[3]/button[1]")),
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.kit-button.is-large.is-primary.is-fill.btn"))
                    )
                )

                # Click the element
                element.click()
                logger.info(f"{self.short_account_id}: Daily check-in button found and clicked.")

                # Pause after clicking
                sleep_time = random.randint(5, 7)
                for _ in range(sleep_time):  # Проверяем stop_event во время паузы
                    if stop_event.is_set():
                        logger.info(f"{self.short_account_id}: Stop event detected during sleep. Exiting preparing_account.")
                        return
                    time.sleep(1)

                found = True  # Element found and processed
            except TimeoutException:
                logger.debug(f"{self.short_account_id}: Daily check-in button not found within 10 seconds.")
            except WebDriverException as e:
                logger.debug(f"{self.short_account_id}: Failed to interact with the daily check-in button: {str(e)}")

            if found:
                break  # Exit the loop if elements are found and processed

            # If elements are not found, refresh the page
            if attempt < attempts - 1:
                logger.debug(f"{self.short_account_id}: Elements not found, refreshing the page (attempt {attempt + 1}).")
                #Обновляем iframe
                script = """
                    window.location.assign(window.location.origin + window.location.pathname); 
                """
                self.driver.execute_script(script)
                for _ in range(5):  # Проверяем stop_event во время паузы
                    if stop_event.is_set():
                        logger.info(f"{self.short_account_id}: Stop event detected during refresh. Exiting preparing_account.")
                        return
                    time.sleep(1)
            else:
                logger.debug(f"{self.short_account_id}: Elements not found after {attempts} attempts.")

        # Ожидание и клик по навигационной вкладке
        retries = 0
        while retries < self.MAX_RETRIES:
            if stop_event.is_set():
                logger.info(f"{self.short_account_id}: Stop event detected. Exiting preparing_account.")
                return

            try:
                button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#app > div.layout-tabs.tabs > a:nth-child(1)"))
                )
                button.click()
                logger.info(f"{self.short_account_id}: Successfully clicked on the Home tab.")
                break
            except TimeoutException:
                logger.warning(f"{self.short_account_id}: Home tab not found within timeout.")
                break
            except WebDriverException as e:
                logger.warning(f"{self.short_account_id}: Failed to click Home tab (attempt {retries + 1}): {str(e).splitlines()[0]}")
                retries += 1
                for _ in range(5):  # Проверяем stop_event во время паузы
                    if stop_event.is_set():
                        logger.info(f"{self.short_account_id}: Stop event detected during retry. Exiting preparing_account.")
                        return
                    time.sleep(1)

    def check_iframe_src(self):
        iframe_name = "telegram.blum.codes"
        """
        Проверяет, загружен ли правильный iframe по URL в атрибуте src с ожиданием.
        """
        try:
            logger.debug(
                f"#{self.serial_number}: Waiting for iframe to appear...")

            # Ждем появления iframe в течение 20 секунд
            iframe = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            logger.debug(
                f"#{self.serial_number}: Iframe detected. Checking src attribute.")

            iframe_src = iframe.get_attribute("src")

            # Проверяем, соответствует ли src ожидаемому значению
            if iframe_name in iframe_src and "tgWebAppData" in iframe_src:
                logger.debug(
                    f"#{self.serial_number}: Iframe src is valid: {iframe_src}")
                return True
            else:
                logger.warning(
                    f"#{self.serial_number}: Unexpected iframe src: {iframe_src}")
                return False
        except TimeoutException:
            logger.error(
                f"#{self.serial_number}: Iframe not found within the timeout period.")
            return False
        except (WebDriverException, Exception) as e:
            logger.warning(
                f"#{self.serial_number}: Error while checking iframe src: {str(e).splitlines()[0]}")
            return False


    def get_username(self):
        """
        Получает имя пользователя из элемента на странице с поддержкой остановки через stop_event.
        """
        if stop_event.is_set():  # Проверка на остановку перед выполнением
            logger.info(
                f"#{self.serial_number}: Stop event detected. Exiting get_username.")
            return "Unknown"

        try:
            logger.debug(
                f"#{self.serial_number}: Attempting to retrieve username.")

            # Ожидание появления элемента с именем пользователя
            username_block = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#app > div.index-page.page > div > div.profile-with-balance > div.username")
                )
            )

            if stop_event.is_set():  # Проверка после ожидания элемента
                logger.info(
                    f"#{self.serial_number}: Stop event detected after locating username element.")
                return "Unknown"

            logger.debug(f"#{self.serial_number}: Username element located.")

            # Извлечение имени пользователя
            username = username_block.get_attribute("textContent").strip()
            logger.debug(
                f"#{self.serial_number}: Username retrieved: {username}")
            return username

        except TimeoutException:
            logger.debug(
                f"#{self.serial_number}: Timeout while waiting for username element.")
            return "Unknown"
        except (WebDriverException, StaleElementReferenceException) as e:
            error_message = str(e).splitlines()[0]
            logger.warning(
                f"#{self.serial_number}: Exception occurred while retrieving username: {error_message}")
            return "Unknown"
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Unexpected error while retrieving username: {str(e)}")
            return "Unknown"
        
    def get_balance(self):
        """
        Получение текущего баланса пользователя с поддержкой stop_event.
        """
        retries = 0
        while retries < self.MAX_RETRIES:
            if stop_event.is_set():
                logger.info(f"{self.short_account_id}: Stop event detected. Exiting get_balance.")
                return "0"

            try:
                # Ожидаем элементы, содержащие баланс
                logger.debug(f"{self.short_account_id}: Waiting for balance elements.")
                visible_balance_elements = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_all_elements_located(
                        (By.CSS_SELECTOR, "div.profile-with-balance .kit-counter-animation.value .el-char-wrapper .el-char")
                    )
                )

                # Извлекаем текст и собираем в строку
                balance_text = ''.join([element.get_attribute("textContent").strip() for element in visible_balance_elements])
                logger.debug(f"{self.short_account_id}: Raw balance text: {balance_text}")

                # Удаляем запятые из текста
                balance_text = balance_text.replace(',', '')
                logger.debug(f"{self.short_account_id}: Cleaned balance text: {balance_text}")

                # Проверяем, является ли текст валидным числом, и преобразуем в float
                if balance_text.replace('.', '', 1).isdigit():
                    self.balance = float(balance_text)
                else:
                    logger.warning(f"{self.short_account_id}: Invalid balance text: '{balance_text}'")
                    self.balance = 0.0

                # Преобразуем float в строку, убирая `.0`, если число целое
                balance_text = str(int(self.balance)) if self.balance.is_integer() else str(self.balance)

                # Получаем имя пользователя
                if stop_event.is_set():
                    logger.info(f"{self.short_account_id}: Stop event detected. Exiting get_balance.")
                    return "0"

                username = self.get_username()

                # Логируем успешное получение баланса
                logger.info(f"{self.short_account_id}: Balance: {balance_text}, Username: {username}")

                return balance_text

            except (NoSuchElementException, TimeoutException) as e:
                # Логируем предупреждение при неудаче
                if stop_event.is_set():
                    logger.info(f"{self.short_account_id}: Stop event detected during exception handling. Exiting get_balance.")
                    return "0"

                logger.warning(f"{self.short_account_id}: Failed to get balance (attempt {retries + 1}): {str(e).splitlines()[0]}")
                retries += 1
                for _ in range(5):  # Короткие паузы с проверкой stop_event
                    if stop_event.is_set():
                        logger.info(f"{self.short_account_id}: Stop event detected during retry delay. Exiting get_balance.")
                        return "0"
                    time.sleep(1)

            except Exception as e:
                # Логируем ошибку при неожиданном исключении
                logger.error(f"{self.short_account_id}: Unexpected error while getting balance: {str(e)}")
                return "0"

        # Если после всех попыток не удалось получить баланс, возвращаем "0"
        logger.error(f"{self.short_account_id}: Failed to retrieve balance after {self.MAX_RETRIES} retries.")
        return "0"

   


    def get_time(self):
        """
        Получает оставшееся время до следующего действия в формате HH:MM:SS.
        """
        retries = 0
        while retries < self.MAX_RETRIES:
            if stop_event.is_set():
                logger.info(f"{self.short_account_id}: Stop event detected. Exiting get_time.")
                return None

            try:
                # Находим элемент, содержащий текст времени
                time_element = self.driver.find_element(By.CSS_SELECTOR, "div.time-left")
                time_text = time_element.get_attribute("textContent").strip()

                logger.debug(f"{self.short_account_id}: Raw time text: {time_text}")

                # Парсим время из текста
                hours, minutes = 0, 0
                if "h" in time_text or "ч" in time_text:
                    hours_part = time_text.split()[0]
                    hours = int(hours_part[:-1])  # Убираем последний символ (h/ч) и преобразуем в число
                if "m" in time_text or "м" in time_text:
                    minutes_part = time_text.split()[-1]
                    minutes = int(minutes_part[:-1])  # Убираем последний символ (m/м) и преобразуем в число

                # Генерируем случайные секунды
                seconds = random.randint(0, 59)
                formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"

                # Логируем успешное извлечение времени
                logger.info(f"{self.short_account_id}: Start farm will be available after: {formatted_time}")
                return formatted_time

            except NoSuchElementException:
                if stop_event.is_set():
                    logger.info(f"{self.short_account_id}: Stop event detected during NoSuchElementException. Exiting get_time.")
                    return None
                logger.debug(f"{self.short_account_id}: Time element not found (attempt {retries + 1}).")
                retries += 1
                for _ in range(5):  # Короткие паузы с проверкой stop_event
                    if stop_event.is_set():
                        logger.info(f"{self.short_account_id}: Stop event detected during retry delay. Exiting get_time.")
                        return None
                    time.sleep(1)

            except Exception as e:
                if stop_event.is_set():
                    logger.info(f"{self.short_account_id}: Stop event detected during exception handling. Exiting get_time.")
                    return None
                logger.error(f"{self.short_account_id}: Unexpected error while retrieving time: {str(e)}")
                return None

        # Если все попытки извлечения времени не удались
        logger.debug(f"{self.short_account_id}: Failed to retrieve time after {self.MAX_RETRIES} retries.")
        return None







    def farming(self):
        """
        Выполнение действий для farming, включая проверку доступности времени,
        нажатие кнопок и запуск игры.
        """
        actions = [
            (".index-farming-button .kit-button", "Farming button clicked", "No active button found.")
        ]

        for css_selector, success_msg, fail_msg in actions:
            retries = 0
            final_click = False  # Флаг, указывающий, был ли выполнен последний клик

            while retries < self.MAX_RETRIES:
                if stop_event.is_set():
                    logger.info(f"{self.short_account_id}: Stop event detected. Exiting farming loop.")
                    return

                try:
                    # Проверяем доступность времени перед нажатием кнопки
                    formatted_time = self.get_time()
                    if formatted_time:
                        logger.debug(f"{self.short_account_id}: Farming will be available after: {formatted_time}. Skipping button click.")
                        break

                    # Находим и кликаем кнопку
                    button = self.driver.find_element(By.CSS_SELECTOR, css_selector)
                    button.click()
                    logger.info(f"{self.short_account_id}: {success_msg}")
                    final_click = True  # Указываем, что был выполнен финальный клик

                    # Ждем перед проверкой активности кнопки
                    sleep_time = random.randint(3, 4)
                    for _ in range(sleep_time):
                        if stop_event.is_set():
                            logger.info(f"{self.short_account_id}: Stop event detected during sleep. Exiting farming.")
                            return
                        time.sleep(1)

                    # Проверяем время после нажатия
                    formatted_time = self.get_time()
                    if formatted_time:
                        logger.info(f"{self.short_account_id}: Farming paused. Will be available after: {formatted_time}.")
                        break

                    # Проверяем активность кнопки для повторного нажатия
                    try:
                        button = self.driver.find_element(By.CSS_SELECTOR, css_selector)
                        if button.is_enabled():
                            button.click()
                            final_click = True  # Обновляем флаг
                    except NoSuchElementException:
                        break

                except NoSuchElementException:
                    logger.info(f"{self.short_account_id}: {fail_msg}")
                    break
                except WebDriverException as e:
                    logger.warning(f"{self.short_account_id}: Failed farming action (attempt {retries + 1}): {str(e).splitlines()[0]}")
                    retries += 1
                    for _ in range(5):
                        if stop_event.is_set():
                            logger.info(f"{self.short_account_id}: Stop event detected during retry delay. Exiting farming.")
                            return
                        time.sleep(1)

            # Проверка на ошибку, если время так и не появилось после последнего клика
            if final_click and not formatted_time:
                logger.error(f"{self.short_account_id}: Time did not appear after the final click.")

        # Проверяем доступные игры и запускаем auto_start_game
        try:
            if stop_event.is_set():
                logger.info(f"{self.short_account_id}: Stop event detected before checking available games. Exiting farming.")
                return

            available_games = self.get_number_from_element(By.CSS_SELECTOR, ".pass")
            if available_games is None or available_games == 0:
                logger.info(f"{self.short_account_id}: All games completed or unavailable.")
                return

            # Проверяем ограничения на игры
            try:
                self.max_games = self.settings.get("MAX_GAMES", float('inf'))
                if isinstance(self.max_games, str):
                    self.max_games = int(self.max_games) if self.max_games.strip().isdigit() else float('inf')
            except ValueError:
                self.max_games = float('inf')

            if self.max_games == 0:
                logger.info(f"{self.short_account_id}: MAX_GAMES set to 0. Skipping game start.")
                return
            elif self.max_games != float('inf'):
                logger.info(f"{self.short_account_id}: {available_games} games available. Limiting to {self.max_games}.")
            else:
                logger.info(f"{self.short_account_id}: {available_games} games available. No limitation applied.")

            # Запуск игры
            self.auto_start_game()
        except Exception as e:
            logger.error(f"{self.short_account_id}: Error during farming or checking games availability: {str(e)}")

              
    def get_number_from_element(self, by, value):
        """
        Извлечение числа из текста элемента. Если числа нет, возвращается 0.
        """
        retries = 0
        while retries < self.MAX_RETRIES:
            if stop_event.is_set():
                logger.info(f"{self.short_account_id}: Stop event detected. Exiting get_number_from_element.")
                return 0

            try:
                # Логирование попытки найти элемент
                logger.debug(f"{self.short_account_id}: Attempting to locate element using locator: {by}, value: {value}")
                element = self.wait_for_element(by, value)

                if element:
                    # Логирование успешного нахождения элемента
                    logger.debug(f"{self.short_account_id}: Element located successfully.")

                    # Скроллим к элементу, чтобы сделать его видимым
                    logger.debug(f"{self.short_account_id}: Scrolling to element to make it visible.")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

                    # Попытка получить текст из элемента
                    logger.debug(f"{self.short_account_id}: Attempting to extract text from the element.")
                    text = element.get_attribute("textContent").strip() if element.get_attribute("textContent") else element.text.strip()
                    logger.debug(f"{self.short_account_id}: Extracted text: '{text}'")

                    # Используем регулярное выражение для поиска числа
                    logger.debug(f"{self.short_account_id}: Attempting to extract number from the text using regex.")
                    match = re.search(r'\d+', text)  # Исправлено

                    if match:
                        extracted_number = int(match.group())
                        logger.debug(f"{self.short_account_id}: Number extracted successfully: {extracted_number}")
                        return extracted_number
                    else:
                        logger.debug(f"{self.short_account_id}: No number found in the text: '{text}'. Returning 0.")
                        return 0  # Если число не найдено
                else:
                    # Логирование, если элемент не найден
                    logger.debug(f"{self.short_account_id}: Element not found. Returning 0.")
                    return 0
            except Exception as e:
                # Логирование ошибок
                logger.warning(f"{self.short_account_id}: Error while retrieving number from element (attempt {retries + 1}): {str(e)}")
                retries += 1
                for _ in range(5):
                    if stop_event.is_set():
                        logger.info(f"{self.short_account_id}: Stop event detected during retry delay. Exiting get_number_from_element.")
                        return 0
                    time.sleep(1)

        logger.error(f"{self.short_account_id}: Failed to retrieve number after {self.MAX_RETRIES} retries.")
        return 0




    def get_points_and_remaining_games(self):
        """
        Получение поинтов и оставшихся игр.
        """
        try:
            # Ожидаем появления элемента с поинтами
            points_element = self.wait_for_element(
                By.CSS_SELECTOR,
                "#app > div.game-page.page > div > div.content > div.reward > div.value > div.animated-points.visible > div.amount"
            )

            points = None
            if points_element:
                points = points_element.text.strip()
                if points:
                    logger.debug(f"{self.short_account_id}: Points retrieved: {points}")
                else:
                    logger.warning(f"{self.short_account_id}: Points element found but value is empty.")
            else:
                logger.warning(f"{self.short_account_id}: Points element not found.")

            # Ожидаем появления элемента с количеством оставшихся игр
            games_element = self.wait_for_element(
                By.CSS_SELECTOR,
                "#app > div.game-page.page > div > div.buttons > button.kit-button.is-large.is-primary > div.label > span"
            )

            remaining_games_real = None
            if games_element:
                remaining_games_text = games_element.text.strip()
                remaining_games_real = self.extract_number_from_text(remaining_games_text)
                logger.debug(f"{self.short_account_id}: Remaining games retrieved: {remaining_games_real}")
            else:
                logger.debug(f"{self.short_account_id}: Remaining games element not found.")

            return points, remaining_games_real

        except Exception as e:
            logger.error(f"{self.short_account_id}: Error while retrieving points and remaining games: {str(e)}")
            return None, None


    def extract_number_from_text(self, text):
        """
        Извлечение числового значения из текста.

        :param text: Входной текст, из которого необходимо извлечь число.
        :return: Первое найденное числовое значение или 0, если чисел нет.
        """
        try:
            # Проверка на None
            if not text:
                logger.debug(f"{self.short_account_id}: Input text is None or empty. Returning 0.")
                return 0

            # Извлечение чисел из текста
            numbers = re.findall(r'\d+', text)
            if numbers:
                extracted_number = int(numbers[0])
                logger.debug(f"{self.short_account_id}: Extracted number: {extracted_number} from text: '{text}'")
                return extracted_number

            # Логируем случай, когда числа не найдены
            logger.debug(f"{self.short_account_id}: No numbers found in text: '{text}'. Returning 0.")
            return 0
        except Exception as e:
            logger.error(f"{self.short_account_id}: Error while extracting number from text '{text}': {str(e)}")
            return 0

    
    def auto_start_game(self):
        """
        Поиск кнопок 'Play'/'Играть' и выполнение JavaScript, если они найдены.
        """
        try:
            while not stop_event.is_set():
                # Проверяем наличие кнопок 'Play' или 'Играть'
                play_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    "button.kit-button.is-large.is-primary, "
                    "a.play-btn[href='/game'], "
                    "button.kit-button.is-large.is-primary"
                )

                # Логируем количество найденных кнопок
                if play_buttons:
                    logger.debug(f"{self.short_account_id}: Found {len(play_buttons)} potential 'Play' buttons.")

                for btn in play_buttons:
                    if stop_event.is_set():
                        logger.info(f"{self.short_account_id}: Stop event detected. Exiting auto_start_game.")
                        return

                    button_text = btn.text.strip()
                    logger.debug(f"{self.short_account_id}: Checking button text: '{button_text}'")

                    if any(text in button_text for text in ["Play", "Играть"]):
                        if self.first_game_start:
                            logger.info(f"{self.short_account_id}: 'Play' button found. Starting the game.")
                            self.first_game_start = False  # Устанавливаем флаг, чтобы логировать только один раз

                        # Выполняем скрипт для запуска игры
                        self.execute_game_script()
                        logger.debug(f"{self.short_account_id}: Game start script executed.")

                        # Пауза для имитации естественного поведения
                        sleep_time = random.uniform(2, 5)
                        logger.debug(f"{self.short_account_id}: Sleeping for {sleep_time:.2f} seconds.")
                        time.sleep(sleep_time)

                        # Ожидание окончания игры
                        self.wait_for_game_end()
                        logger.debug(f"{self.short_account_id}: Game end detected.")
                        return

                # Если кнопка не найдена на главной странице, пытаемся перезапустить игру
                logger.debug(f"{self.short_account_id}: 'Play' button not found. Restarting game process.")
                self.check_and_restart_game()

                # Прерывание цикла при выполнении задачи или завершении процесса
                if stop_event.is_set():
                    logger.info(f"{self.short_account_id}: Stop event detected. Exiting auto_start_game.")
                    return

        except Exception as e:
            # Логируем ошибки
            logger.error(f"{self.short_account_id}: Error while attempting to start the game: {str(e)}")


    
    def wait_for_game_end(self):
        """
        Ожидание появления данных о поинтах и оставшихся играх после начала игры.
        """
        try:
            while not stop_event.is_set():
                # Ожидаем появления элемента, сигнализирующего об окончании игры
                logger.debug(f"{self.short_account_id}: Waiting for game end data to become visible.")
                try:
                    WebDriverWait(self.driver, 60).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#app > div.game-page.page > div > div.content > div.reward > div.value > div.animated-points.visible > div.amount-hidden"))
                    )
                    # Логируем успешное начало игры
                    if self.first_game_start:
                        logger.info(f"{self.short_account_id}: Game started successfully. Awaiting completion.")
                        self.first_game_start = False  # Устанавливаем флаг, чтобы избежать повторного логирования

                    # Проверяем оставшиеся игры
                    logger.debug(f"{self.short_account_id}: Game end detected. Checking remaining games.")
                    self.check_remaining_games()
                    break

                except TimeoutException:
                    logger.debug(f"{self.short_account_id}: Timeout while waiting for game end data to appear.")
                    break

        except Exception as e:
            logger.error(f"{self.short_account_id}: Error while waiting for the game to end: {str(e)}")


    
    def execute_game_script(self):
        """Выполнение JavaScript кода в браузере через Selenium."""
        try:
            logger.debug(f"{self.short_account_id}: Executing game script in the browser.")

            self.driver.execute_script("""
                // Удерживаем экран активным с помощью Wake Lock API
                let wakeLock = null;

                async function requestWakeLock() {
                    try {
                        wakeLock = await navigator.wakeLock.request('screen');
                        console.log("Wake Lock активирован");
                    } catch (err) {
                        console.error("Не удалось активировать Wake Lock:", err);
                    }
                }

                requestWakeLock();

                window.SETTINGS = window.GAME_SETTINGS || {
                    bombProbability: 0.01,  
                    flowerProbability: 0.95,  
                    iceProbability: 0.10,
                    dogsProbability: 0.99,
                    TrumpProbability: 0.99,
                    HarrisProbability: 0.99,    
                    gameEnded: false,
                    isScriptEnabled: true
                };

                console.log("Текущие настройки при запуске игры:", window.SETTINGS);

                if (window.SETTINGS.isScriptEnabled) {
                    try {
                        const originalArrayPush = Array.prototype.push;
                        Array.prototype.push = function (...items) {
                            items.forEach(item => processGameItem(item));
                            return originalArrayPush.apply(this, items);
                        };

                        function processGameItem(item) {
                            if (!item || !item.asset) return;

                            const { assetType } = item.asset;
                            switch (assetType) {
                                case "CLOVER":
                                    handleFlower(item);
                                    break;
                                case "BOMB":
                                    handleBomb(item);
                                    break;
                                case "FREEZE":
                                    handleFreeze(item);
                                    break;
                                case "DOGS":
                                    handleDogs(item);
                                    break;
                                case "TRUMP":
                                    handleTrump(item);
                                    break;
                                case "HARRIS":
                                    handleHarris(item);
                                    break;
                            }
                        }

                        function handleFlower(item) {
                            if (Math.random() < window.SETTINGS.flowerProbability) {
                                triggerClick(item);
                            }
                        }

                        function handleBomb(item) {
                            if (Math.random() < window.SETTINGS.bombProbability) {
                                triggerClick(item);
                            }
                        }

                        function handleFreeze(item) {
                            if (Math.random() < window.SETTINGS.iceProbability) {
                                triggerClick(item);
                            }
                        }

                        function handleDogs(item) {
                            if (Math.random() < window.SETTINGS.dogsProbability) {
                                triggerClick(item);
                            }
                        }

                        function handleTrump(item) {
                            if (Math.random() < window.SETTINGS.TrumpProbability) {
                                triggerClick(item);
                            }
                        }

                        function handleHarris(item) {
                            if (Math.random() < window.SETTINGS.HarrisProbability) {
                                triggerClick(item);
                            }
                        }

                        function triggerClick(item) {
                            setTimeout(() => {
                                if (typeof item.onClick === 'function') {
                                    item.onClick(item);
                                } else {
                                    console.log("item.onClick не определен.");
                                }
                                item.isExplosion = true;
                                item.addedAt = performance.now();
                            }, calculateDelay());
                        }

                        function calculateDelay() {
                            const min = 500;
                            const max = 1000;
                            return Math.random() * (max - min) + min;
                        }

                        function detectGameEnd() {
                            const rewardElement = document.querySelector('#app > div > div > div.content > div.reward');
                            if (rewardElement && !window.SETTINGS.gameEnded) {
                                window.SETTINGS.gameEnded = true;
                                resetGameData();
                            }
                        }

                        function resetGameData() {
                            window.SETTINGS.gameEnded = false;
                        }

                        function autoStartGame() {
                            const buttons = document.querySelectorAll('button.kit-button.is-large.is-primary, a.play-btn[href="/game"], button.kit-button.is-large.is-primary');
                            buttons.forEach(btn => {
                                if (/Play|Continue|Играть|Продолжить|Вернуться на главную/.test(btn.textContent)) {
                                    setTimeout(() => {
                                        btn.click();
                                        window.SETTINGS.gameEnded = false;
                                    }, calculateDelay());
                                }
                            });
                        }

                        function monitorPlayButton() {
                            autoStartGame();
                        }

                        const mutationObserver = new MutationObserver(mutations => {
                            mutations.forEach(mutation => {
                                if (mutation.type === 'childList') {
                                    detectGameEnd();
                                    mutationObserver.disconnect();
                                }
                            });
                        });

                        const appRoot = document.querySelector('#app');
                        if (appRoot) {
                            mutationObserver.observe(appRoot, { childList: true, subtree: true });
                        }

                        monitorPlayButton();

                        window.updateGameSettings = function(newSettings) {
                            window.SETTINGS = newSettings;
                            console.log("Настройки обновлены:", window.SETTINGS);
                        };

                    } catch (error) {
                        console.error("Ошибка в Blum AutoPlayer:", error);
                    }
                } else {
                    console.log("Скрипт отключен через настройки.");
                }
            """)
        except Exception as e:
            logger.error(f"{self.short_account_id}: Error while executing JavaScript game script: {str(e)}")

        

    def check_remaining_games(self):
        """Проверка оставшихся игр после выполнения JavaScript."""        

        # Установить значение по умолчанию, если self.max_games отсутствует
        if self.max_games is None:
            self.max_games = float('inf')  # Неограниченное количество игр

        points, remaining_games_real = self.get_points_and_remaining_games()

        # Проверяем, что поинты и оставшиеся игры не равны None перед сравнением
        if points is not None:
            logger.info(f"Points earned: {points}")
        else:
            logger.error("Failed to retrieve points.")

        # Если количество оставшихся игр None, трактуем как 0
        if remaining_games_real is None:
            remaining_games_real = 0

        # Проверка, нужно ли ограничивать количество оставшихся игр
        if self.remaining_games is None:  # Для первого вызова
            # Если remaining_games_real больше чем max_games-1, ограничиваем количество игр
            if remaining_games_real > (self.max_games - 1):
                self.remaining_games = self.max_games - 1  # Ограничиваем количество игр
                self.is_limited = True  # Устанавливаем, что ограничение было применено
            else:
                self.remaining_games = remaining_games_real  # Если ограничение не нужно, используем реальное количество игр
                self.is_limited = False  # Ограничение не применено

        # Логируем реальное количество оставшихся игр
        if self.is_limited:  # Если сработало ограничение
            logger.debug(f"Remaining games real: {remaining_games_real}.")
            logger.debug(f"Remaining games after possible limitation: {self.remaining_games}")
        else:
            self.remaining_games = remaining_games_real

        if self.remaining_games == 0:
            logger.info("Remaining games are 0. Ending the process.")
            self.driver.back()  # Используем команду браузера "назад"
            time.sleep(2)  # Задержка для загрузки предыдущей страницы
            self.switch_to_iframe()
        elif self.remaining_games > 0:
            logger.info(f"Remaining games: {self.remaining_games}. Starting again.")
            if self.remaining_games != remaining_games_real:  # Если ограничение было применено
                self.remaining_games -= 1
            self.auto_start_game()  # Повторный запуск игры
        else:
            logger.error("Failed to retrieve the remaining games. Ending the process.")

    def switch_to_iframe(self):
        """
        Switches to the first iframe on the page, if available.
        """
        try:
            # Возвращаемся к основному контенту страницы
            logger.debug(
                f"#{self.serial_number}: Switching to the default content.")
            self.driver.switch_to.default_content()

            # Ищем все iframes на странице
            logger.debug(
                f"#{self.serial_number}: Looking for iframes on the page.")
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.debug(
                f"#{self.serial_number}: Found {len(iframes)} iframes on the page.")

            if iframes:
                # Переключаемся на первый iframe
                self.driver.switch_to.frame(iframes[0])
                logger.debug(
                    f"#{self.serial_number}: Successfully switched to the first iframe.")
                return True
            else:
                logger.warning(
                    f"#{self.serial_number}: No iframes found to switch.")
                return False
        except NoSuchElementException:
            logger.warning(
                f"#{self.serial_number}: No iframe element found on the page.")
            return False
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Unexpected error while switching to iframe: {str(e)}")
            return False


    
    def check_and_restart_game(self):
        """Проверка на главную страницу и запуск игры."""
        try:
            while not stop_event.is_set():
                # Проверяем наличие кнопок 'Play' или 'Играть'
                play_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "button.kit-button.is-large.is-primary, a.play-btn[href='/game'], button.kit-button.is-large.is-primary"
                )

                if not play_buttons:
                    logger.debug(f"{self.short_account_id}: No 'Play' or 'Играть' buttons found on the main page.")
                    return

                for btn in play_buttons:
                    if stop_event.is_set():
                        logger.info(f"{self.short_account_id}: Stop event detected. Exiting check_and_restart_game.")
                        return

                    if any(text in btn.text for text in ["Play", "Играть"]):
                        logger.info(f"{self.short_account_id}: 'Play' button found. Starting the game.")
                        try:
                            self.execute_game_script()  # Используем execute_game_script для корректного запуска
                            time.sleep(random.uniform(2, 5))  # Пауза для имитации естественного поведения
                            self.wait_for_game_end()  # Ожидание завершения игры
                            return
                        except Exception as game_start_error:
                            logger.error(f"{self.short_account_id}: Error while executing game script: {str(game_start_error)}")
                            return  # Прерываем, если произошла ошибка при запуске игры
        except Exception as e:
            logger.error(f"{self.short_account_id}: Error while checking the main page: {str(e)}")
    
    def check_for_continue_button(self):
        """Проверка наличия кнопки с текстом 'Continue' или 'Вернуться на главную' и выполнение клика по ней."""
        try:
            # Находим все кнопки, которые могут содержать текст 'Continue' или 'Вернуться на главную'
            continue_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button.kit-button.is-large.is-primary, a.play-btn[href='/game'], button.kit-button.is-large.is-primary") 
            
            if not continue_buttons:
                logger.info(f"{self.short_account_id}: No 'Continue' or 'Return to Main' button found.")
                return  # Если кнопки не найдены, выходим из функции

            logger.info(f"{self.short_account_id}: Checking for 'Continue' button to proceed.")
            
            for btn in continue_buttons:
                # Проверяем, что кнопка действительно содержит нужный текст
                if any(text in btn.text for text in ["Continue", "Вернуться на главную"]):
                    logger.info(f"{self.short_account_id}: 'Continue' or 'Return to Main' button found. Clicking.")
                    btn.click()  # Кликаем на кнопку для завершения всех игр
                    break  # Прерываем цикл после первого клика
        except Exception as e:
            logger.error(f"{self.short_account_id}: Error while checking for continue button: {str(e)}")
