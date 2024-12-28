import re
import random
import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException, StaleElementReferenceException
from utils import get_max_games, stop_event
from urllib.parse import unquote, parse_qs
from browser_manager import BrowserManager
from colorama import Fore, Style
import logging
# Настроим логирование (если не было настроено ранее)
logger = logging.getLogger("application_logger")


class TelegramBotAutomation:
    MAX_RETRIES = 3

    def __init__(self, serial_number, settings):
        # max_games сохраняем в атрибут объекта
        self.max_games = get_max_games(settings)
        self.remaining_games = None
        self.serial_number = serial_number
        self.username = None  # Initialize username as None
        self.balance = 0.0  # Initialize balance as 0.0
        self.browser_manager = BrowserManager(serial_number)
        self.settings = settings
        self.driver = None
        self.first_game_start = True
        self.logged_farm_time = False
        self.is_limited = False  # Attribute to track limitation status
        logger.debug(
            f"#{self.serial_number}: Initializing automation for account.")

        # Ожидание завершения предыдущей сессии браузера
        if not self.browser_manager.wait_browser_close():
            logger.error(
                f"#{self.serial_number}: Failed to close previous browser session.")
            raise RuntimeError("Failed to close previous browser session")

        # Запуск браузера
        if not self.browser_manager.start_browser():
            logger.error(f"#{self.serial_number}: Failed to start browser.")
            raise RuntimeError("Failed to start browser")

        # Сохранение экземпляра драйвера
        self.driver = self.browser_manager.driver

        logger.debug(
            f"#{self.serial_number}: Automation initialization completed successfully.")

    def wait_for_page_load(self, timeout=30):
        """
        Ожидание полной загрузки страницы с помощью проверки document.readyState.

        :param driver: WebDriver Selenium.
        :param timeout: Максимальное время ожидания.
        """
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.execute_script(
                "return document.readyState") == "complete"
        )

    def claim_daily_reward(self):
        """
        Проверяет наличие кнопки для ежедневного вознаграждения "Собрать".
        Если кнопка доступна, нажимает её и проверяет появление времени до следующего нажатия.
        """
        if stop_event.is_set():
            logger.debug(
                f"#{self.serial_number}: Stop event detected. Exiting claim_daily_reward.")
            return

        self.wait_for_page_load()

        try:
            logger.debug(
                f"#{self.serial_number}: Checking for the daily reward button.")

            # Ограничиваем поиск областью блока 'pages-index-daily-reward reward'
            reward_container = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.pages-index-daily-reward.reward"))
            )
            logger.debug(f"#{self.serial_number}: Found reward container.")

            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                if stop_event.is_set():
                    logger.debug(
                        f"#{self.serial_number}: Stop event detected during retries. Exiting.")
                    return

                try:
                    # Ожидание кнопки "Собрать" внутри reward_container
                    reward_button = WebDriverWait(reward_container, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "button.kit-pill-claim.reset"))
                    )
                    logger.debug(
                        f"#{self.serial_number}: Daily reward button found. Checking button state.")

                    # Проверяем классы кнопки
                    button_classes = reward_button.get_attribute("class")
                    logger.debug(
                        f"#{self.serial_number}: Button classes: {button_classes}")

                    # Определяем состояние кнопки
                    if "is-state-claimed" in button_classes:
                        logger.info(
                            f"#{self.serial_number}: Daily check-in already claimed.")
                        break
                    elif "is-state-claim" in button_classes:
                        logger.debug(
                            f"#{self.serial_number}: Daily check-in button is available. Attempting to click.")
                        self.safe_click(reward_button)
                        logger.info(
                            f"#{self.serial_number}: Daily check-in clicked successfully.")
                        break
                    else:
                        logger.warning(
                            f"#{self.serial_number}: Reward button state is unknown.")
                        break

                except StaleElementReferenceException:
                    retry_count += 1
                    logger.warning(
                        f"#{self.serial_number}: Stale element reference detected. Retrying {retry_count}/{max_retries}."
                    )
                    reward_container = WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div.pages-index-daily-reward.reward"))
                    )
                except TimeoutException:
                    logger.warning(
                        f"#{self.serial_number}: Daily reward button not found within timeout.")
                    break

            # Проверяем, что появилось время до следующего нажатия
            next_claim_element = reward_container.find_element(
                By.CSS_SELECTOR, "div.subtitle")
            next_claim_text = next_claim_element.text.strip()
            logger.debug(
                f"#{self.serial_number}: Raw text for next claim: {next_claim_text}")

            # Парсим интервал времени
            time_pattern = r"(\d+\s*[hH]\s*\d+\s*[mM])"
            match = re.search(time_pattern, next_claim_text)

            formatted_text = (
                f"Next check-in available in: {match.group(1)}" if match else f"Next check-in available: {next_claim_text}"
            )
            logger.info(f"#{self.serial_number}: {formatted_text}")

            # Проверяем количество чекинов внутри reward_container
            total_checkins_element = reward_container.find_element(
                By.CSS_SELECTOR, "div.title")
            total_checkins_full_text = total_checkins_element.text.strip()

            # Извлекаем количество дней
            checkin_days_pattern = r"(\d+)-days"
            match_days = re.search(checkin_days_pattern,
                                   total_checkins_full_text)
            total_checkins = match_days.group(
                1) if match_days else total_checkins_full_text

            logger.info(
                f"#{self.serial_number}: Total check-ins: {total_checkins}")

        except TimeoutException:
            logger.warning(
                f"#{self.serial_number}: Daily reward button or container not found within timeout.")
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Unexpected error in claim_daily_reward: {str(e).splitlines()[0]}")

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
                    # Короткий sleep для проверки stop_event
                    stop_event.wait(1)

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
                    stop_event.wait(1)

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
                    stop_event.wait(5)
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
                    stop_event.wait(5)
                    continue

                # Добавляем задержку перед завершением
                sleep_time = random.randint(5, 7)
                logger.debug(
                    f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                stop_event.wait(sleep_time)
                logger.debug(
                    f"#{self.serial_number}: Message successfully sent to the group.")
                return True
            except (NoSuchElementException, WebDriverException) as e:
                error_message = str(e).splitlines()[0]
                logger.warning(
                    f"#{self.serial_number}: Failed to perform action (attempt {retries + 1}): {error_message}")
                retries += 1
                stop_event.wait(5)
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
                    stop_event.wait(1)

                    # Клик по ссылке
                    link.click()
                    logger.debug(
                        f"#{self.serial_number}: Link clicked successfully.")
                    stop_event.wait(2)

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
                    stop_event.wait(sleep_time)

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
                stop_event.wait(5)
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
        """
        Подготавливает аккаунт, проверяя и кликая на нужные элементы.
        Возвращает True, если выполнение успешно, иначе False.
        """
        retries = 0
        while retries < self.MAX_RETRIES:
            if stop_event.is_set():
                logger.debug(
                    f"#{self.serial_number}: Stop event detected. Exiting preparing_account.")
                return False  # Завершаем с неуспешным результатом

            try:
                # Ищем и кликаем на кнопку "Home tab"
                button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "#app > div.layout-tabs.tabs > a:nth-child(1)"))
                )
                button.click()
                logger.debug(
                    f"#{self.serial_number}: Successfully clicked on the Home tab.")
                return True  # Успешное выполнение
            except TimeoutException:
                retries += 1
                logger.warning(
                    f"#{self.serial_number}: Home tab not found within timeout (attempt {retries}/{self.MAX_RETRIES}).")
                if retries >= self.MAX_RETRIES:
                    logger.error(
                        f"#{self.serial_number}: Maximum retries reached. Aborting Home tab click.")
                    return False  # Превышение количества попыток
            except WebDriverException as e:
                retries += 1
                logger.warning(
                    f"#{self.serial_number}: Failed to click Home tab (attempt {retries}/{self.MAX_RETRIES}): {str(e).splitlines()[0]}")
                if retries >= self.MAX_RETRIES:
                    logger.error(
                        f"#{self.serial_number}: Maximum retries reached. Aborting Home tab click.")
                    return False  # Превышение количества попыток
            finally:
                if retries < self.MAX_RETRIES:
                    # Проверяем stop_event во время паузы между попытками
                    for _ in range(5):
                        if stop_event.is_set():
                            logger.debug(
                                f"#{self.serial_number}: Stop event detected during retry. Exiting preparing_account.")
                            return False
                        stop_event.wait(1)

        return False  # На случай, если цикл завершится без успешного клика

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
        Извлечение имени пользователя из sessionStorage.
        """
        if stop_event.is_set():
            logger.debug(
                f"#{self.serial_number}: Stop event detected. Exiting get_username.")
            return None

        try:
            # Извлекаем __telegram__initParams из sessionStorage
            logger.debug(
                f"#{self.serial_number}: Attempting to retrieve '__telegram__initParams' from sessionStorage.")
            init_params = self.driver.execute_script(
                "return sessionStorage.getItem('__telegram__initParams');"
            )
            if not init_params:
                raise Exception("InitParams not found in sessionStorage.")

            # Преобразуем данные JSON в Python-объект
            init_data = json.loads(init_params)
            logger.debug(
                f"#{self.serial_number}: InitParams successfully retrieved.")

            # Получаем tgWebAppData
            tg_web_app_data = init_data.get("tgWebAppData")
            if not tg_web_app_data:
                raise Exception("tgWebAppData not found in InitParams.")

            # Декодируем tgWebAppData
            decoded_data = unquote(tg_web_app_data)
            logger.debug(
                f"#{self.serial_number}: Decoded tgWebAppData: {decoded_data}")

            # Парсим строку параметров
            parsed_data = parse_qs(decoded_data)
            logger.debug(
                f"#{self.serial_number}: Parsed tgWebAppData: {parsed_data}")

            # Извлекаем параметр 'user' и преобразуем в JSON
            user_data = parsed_data.get("user", [None])[0]
            if not user_data:
                raise Exception("User data not found in tgWebAppData.")

            # Парсим JSON и извлекаем username
            user_info = json.loads(user_data)
            username = user_info.get("username")
            logger.debug(
                f"#{self.serial_number}: Username successfully extracted: {username}")

            return username

        except Exception as e:
            # Логируем ошибку без громоздкого Stacktrace
            error_message = str(e).splitlines()[0]
            logger.debug(
                f"#{self.serial_number}: Error extracting Telegram username: {error_message}")
            return None

    def get_balance(self):
        """
        Получение текущего баланса пользователя с обновленным селектором.
        """
        retries = 0
        while retries < self.MAX_RETRIES:
            if stop_event.is_set():
                logger.debug(
                    f"#{self.serial_number}: Stop event detected. Exiting get_balance.")
                return "0"

            try:
                # Ожидание контейнеров с балансами
                logger.debug(
                    f"#{self.serial_number}: Waiting for wallet asset container.")
                wallet_assets = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_all_elements_located(
                        (By.CSS_SELECTOR, "div.pages-wallet-asset")
                    )
                )

                # Извлечение данных из каждого контейнера
                balances = {}
                for asset in wallet_assets:
                    if stop_event.is_set():
                        logger.debug(
                            f"#{self.serial_number}: Stop event detected during balance processing. Exiting.")
                        return "0"
                    try:
                        name_element = asset.find_element(
                            By.CSS_SELECTOR, "div.name")
                        balance_element = asset.find_element(
                            By.CSS_SELECTOR, "div.balance")

                        # Получение текста
                        name = name_element.text.strip()
                        balance_text = balance_element.text.strip()

                        # Удаление запятых и единиц измерения
                        balance_cleaned = balance_text.split()[
                            0].replace(',', '')

                        # Проверка валидности значения
                        if balance_cleaned.replace('.', '', 1).isdigit():
                            balance_value = float(balance_cleaned)
                            balances[name] = balance_value
                        else:
                            logger.warning(
                                f"#{self.serial_number}: Invalid balance text for {name}: '{balance_text}'")
                    except Exception as e:
                        logger.debug(
                            f"#{self.serial_number}: Error processing wallet asset: {str(e).splitlines()[0]}")

                logger.debug(
                    f"#{self.serial_number}: Extracted balances: {balances}")

                # Если найдены "Blum points"
                if "Blum points" in balances:
                    return str(balances["Blum points"])
                else:
                    logger.warning(
                        f"#{self.serial_number}: Blum points not found in balances.")
                    return "0"

            except (NoSuchElementException, TimeoutException) as e:
                if stop_event.is_set():
                    logger.debug(
                        f"#{self.serial_number}: Stop event detected during exception handling. Exiting get_balance.")
                    return "0"

                logger.warning(
                    f"#{self.serial_number}: Failed to get balance (attempt {retries + 1}): {str(e).splitlines()[0]}")
                retries += 1
                for _ in range(5):
                    if stop_event.is_set():
                        logger.debug(
                            f"#{self.serial_number}: Stop event detected during retry delay. Exiting get_balance.")
                        return "0"
                    stop_event.wait(1)

            except Exception as e:
                logger.error(
                    f"#{self.serial_number}: Unexpected error while getting balance: {str(e).splitlines()[0]}")
                return "0"

        logger.error(
            f"#{self.serial_number}: Failed to retrieve balance after {self.MAX_RETRIES} retries.")
        return "0"

    def get_time(self):
        """
        Получает оставшееся время до следующего действия на основе процента выполнения.
        """
        retries = 0
        total_time_minutes = 8 * 60  # 8 часов в минутах

        while retries < self.MAX_RETRIES:
            if stop_event.is_set():
                logger.debug(
                    f"#{self.serial_number}: Stop event detected. Exiting get_time.")
                return None

            try:
                # Ожидание родительского контейнера с классом 'pages-index-points'
                logger.debug(
                    f"#{self.serial_number}: Searching for farming container.")
                farming_container = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.pages-index-points"))
                )
                logger.debug(
                    f"#{self.serial_number}: Farming container found.")

                # Поиск кнопки внутри контейнера
                farming_button = farming_container.find_element(
                    By.CSS_SELECTOR, "button.kit-pill.farming"
                )
                logger.debug(f"#{self.serial_number}: Farming button found.")

                # Получение стиля кнопки и извлечение процента прогресса
                style_attribute = farming_button.get_attribute("style")
                logger.debug(
                    f"#{self.serial_number}: Farming button style: {style_attribute}")

                # Извлечение процента выполнения
                percentage_pattern = r"background-position-x:\s*(-?\d+\.?\d*)%"
                match = re.search(percentage_pattern, style_attribute)

                if match:
                    progress_percentage = float(match.group(1))
                    logger.debug(
                        f"#{self.serial_number}: Farming progress percentage: {progress_percentage}%")

                    # Вычисление оставшегося времени
                    progress_fraction = max(
                        0, min(1, abs(progress_percentage / 100)))
                    remaining_time_minutes = total_time_minutes * \
                        (1 - progress_fraction)

                    # Форматирование времени в HH:MM:SS
                    hours = int(remaining_time_minutes // 60)
                    minutes = int(remaining_time_minutes % 60)
                    seconds = random.randint(0, 59)
                    formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"

                    logger.debug(
                        f"#{self.serial_number}: Calculated remaining time: {formatted_time}")

                    if not self.logged_farm_time:
                        logger.info(
                            f"#{self.serial_number}: Farming available after: {formatted_time}")
                        self.logged_farm_time = True

                    return formatted_time
                else:
                    logger.warning(
                        f"#{self.serial_number}: Farming progress percentage not found.")
                    return None

            except (NoSuchElementException, TimeoutException) as e:
                retries += 1
                logger.debug(
                    f"#{self.serial_number}: Element not found or timeout (attempt {retries}/{self.MAX_RETRIES})."
                )
                stop_event.wait(1)

            except Exception as e:
                error_message = str(e).splitlines()[0]
                logger.error(
                    f"#{self.serial_number}: Unexpected error in get_time: {error_message}")
                return None

        logger.debug(
            f"#{self.serial_number}: Failed to retrieve time after {self.MAX_RETRIES} retries.")
        return None

    def farming(self):
        """
        Выполнение действий для farming: нажатие кнопки, если её состояние позволяет.
        """
        try:
            if stop_event.is_set():
                logger.debug(
                    f"#{self.serial_number}: Stop event detected. Exiting farming.")
                return

            logger.debug(f"#{self.serial_number}: Starting farming process.")

            # Ожидание готовности страницы
            self.wait_for_page_load()
            time.sleep(3)  # Пауза для стабилизации страницы

            # Ищем родительский контейнер 'pages-index-points'
            farming_container = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.pages-index-points"))
            )
            logger.debug(f"#{self.serial_number}: Farming container found.")

            # Ищем блок 'pages-wallet-asset-farming-slot' внутри farming_container
            farming_slots = farming_container.find_elements(
                By.CSS_SELECTOR, "div.pages-wallet-asset-farming-slot"
            )
            if not farming_slots:
                logger.warning(
                    f"#{self.serial_number}: No farming slots found.")
                return

            logger.debug(
                f"#{self.serial_number}: Found {len(farming_slots)} farming slot(s). Checking buttons.")

            for slot in farming_slots:
                if stop_event.is_set():
                    logger.debug(
                        f"#{self.serial_number}: Stop event detected during slot processing. Exiting.")
                    return

                try:
                    # Ищем кнопку внутри текущего слота
                    farming_button = slot.find_element(
                        By.CSS_SELECTOR, "button.kit-pill-claim.reset")
                    logger.debug(
                        f"#{self.serial_number}: Farming button found in slot.")

                    # Получаем классы кнопки
                    button_classes = farming_button.get_attribute("class")
                    logger.debug(
                        f"#{self.serial_number}: Initial farming button classes: {button_classes}")

                    if "is-state-claim is-type-default" in button_classes or "is-state-claim is-type-dark" in button_classes:
                        # Первый клик
                        logger.debug(
                            f"#{self.serial_number}: Attempting first click on farming button.")
                        self.safe_click(farming_button)
                        logger.info(
                            f"#{self.serial_number}: First click on farming button performed.")

                        # Ожидание изменения состояния кнопки
                        for _ in range(5):  # Повторяем до 5 раз
                            if stop_event.is_set():
                                logger.debug(
                                    f"#{self.serial_number}: Stop event detected during button state check. Exiting.")
                                return

                            time.sleep(2)
                            try:
                                farming_button = slot.find_element(
                                    By.CSS_SELECTOR, "button.kit-pill-claim.reset")
                                button_classes = farming_button.get_attribute(
                                    "class")
                                logger.debug(
                                    f"#{self.serial_number}: Farming button classes after first click: {button_classes}")

                                if "is-state-claim is-type-dark" in button_classes:
                                    # Второй клик
                                    logger.debug(
                                        f"#{self.serial_number}: Attempting second click on farming button.")
                                    self.safe_click(farming_button)
                                    logger.info(
                                        f"#{self.serial_number}: Second click on farming button performed.")
                                    break
                                elif "farming" in button_classes:
                                    logger.info(
                                        f"#{self.serial_number}: Farming button successfully changed to 'farming' state.")
                                    return
                            except StaleElementReferenceException:
                                logger.debug(
                                    f"#{self.serial_number}: Farming button reference stale. Retrying...")
                                continue

                        # Проверяем статус после второго клика
                        if stop_event.is_set():
                            logger.debug(
                                f"#{self.serial_number}: Stop event detected before final state check. Exiting.")
                            return

                        time.sleep(2)
                        button_classes = farming_button.get_attribute("class")
                        if "farming" in button_classes:
                            logger.info(
                                f"#{self.serial_number}: Farming button successfully changed to 'farming' state.")
                        else:
                            logger.warning(
                                f"#{self.serial_number}: Farming button did not reach 'farming' state.")
                    elif "farming" in button_classes:
                        logger.info(
                            f"#{self.serial_number}: Farming button is already in 'farming' state.")
                    else:
                        logger.warning(
                            f"#{self.serial_number}: Farming button is in an unexpected state.")

                    # Прерываем цикл после успешной обработки слота
                    break

                except NoSuchElementException:
                    logger.debug(
                        f"#{self.serial_number}: No clickable farming button in this slot. Skipping.")
                    continue
                except StaleElementReferenceException:
                    logger.debug(
                        f"#{self.serial_number}: Farming button reference stale. Retrying slot.")
                    continue
                except Exception as e:
                    logger.warning(
                        f"#{self.serial_number}: Error while interacting with button: {str(e).splitlines()[0]}")
                    continue
            # Проверяем доступные игры и запускаем auto_start_game
            try:
                # Проверяем наличие стоп-события
                if stop_event.is_set():
                    logger.debug(
                        f"#{self.serial_number}: Stop event detected before checking available games. Exiting farming.")
                    return

                # Ищем родительский контейнер с информацией об играх
                game_container = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.pages-index-game"))
                )
                logger.debug(f"#{self.serial_number}: Game container found.")

                # Извлекаем количество оставшихся игр
                balance_element = game_container.find_element(
                    By.CSS_SELECTOR, "div.balance"
                )
                balance_text = balance_element.text.strip()
                available_games = self.extract_number_from_text(balance_text)

                if available_games == 0:
                    logger.info(
                        f"#{self.serial_number}: All games completed or unavailable.")
                    return

                # Проверяем ограничения на игры
                try:
                    self.max_games = self.settings.get(
                        "MAX_GAMES", float('inf'))
                    if isinstance(self.max_games, str):
                        self.max_games = int(
                            self.max_games) if self.max_games.strip().isdigit() else float('inf')
                except ValueError:
                    self.max_games = float('inf')

                if self.max_games == 0:
                    logger.info(
                        f"#{self.serial_number}: MAX_GAMES set to 0. Skipping game start.")
                    return
                elif self.max_games != float('inf'):
                    logger.info(
                        f"#{self.serial_number}: {available_games} games available. Limiting to {self.max_games}.")
                else:
                    logger.info(
                        f"#{self.serial_number}: {available_games} games available. No limitation applied.")

                # Находим кнопку "Играть"
                play_button = game_container.find_element(
                    By.CSS_SELECTOR, "button.kit-pill.reset.is-type-white"
                )

                # Проверяем наличие и кликаем на кнопку "Играть"
                if play_button:
                    logger.debug(
                        f"#{self.serial_number}: Clicking the play button to start the game.")

                    self.auto_start_game()

                else:
                    logger.warning(
                        f"#{self.serial_number}: Play button not found or not clickable.")

            except TimeoutException:
                logger.warning(
                    f"#{self.serial_number}: Game container not found within timeout.")
            except Exception as e:
                logger.error(
                    f"#{self.serial_number}: Error during farming or checking games availability: {str(e).splitlines()[0]}")
        except TimeoutException:
            logger.warning(
                f"#{self.serial_number}: Farming container not found within timeout.")
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Critical error during farming process: {str(e).splitlines()[0]}")

    def get_number_from_element(self, by, value):
        """
        Извлечение числа из текста элемента. Если числа нет, возвращается 0.
        """
        retries = 0
        while retries < self.MAX_RETRIES:
            if stop_event.is_set():
                logger.debug(
                    f"#{self.serial_number}: Stop event detected. Exiting get_number_from_element.")
                return 0

            try:
                logger.debug(
                    f"#{self.serial_number}: Attempting to locate element using locator: {by}, value: {value}.")
                element = self.wait_for_element(by, value)

                if element:
                    logger.debug(
                        f"#{self.serial_number}: Element located successfully. Scrolling into view.")
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", element)

                    # Извлекаем текст из элемента
                    text = element.get_attribute("textContent") or element.text
                    text = text.strip()
                    logger.debug(
                        f"#{self.serial_number}: Extracted text: '{text}'.")

                    # Используем регулярное выражение для поиска числа
                    match = re.search(r'\d+', text)
                    if match:
                        extracted_number = int(match.group())
                        logger.debug(
                            f"#{self.serial_number}: Number extracted successfully: {extracted_number}.")
                        return extracted_number
                    else:
                        logger.debug(
                            f"#{self.serial_number}: No number found in the text: '{text}'. Returning 0.")
                        return 0
                else:
                    logger.debug(
                        f"#{self.serial_number}: Element not found. Returning 0.")
                    return 0
            except Exception as e:
                logger.warning(
                    f"#{self.serial_number}: Error while retrieving number (attempt {retries + 1}): {str(e).splitlines()[0]}")
                retries += 1
                for _ in range(5):
                    if stop_event.is_set():
                        logger.debug(
                            f"#{self.serial_number}: Stop event detected during retry delay. Exiting get_number_from_element.")
                        return 0
                    stop_event.wait(1)

        logger.error(
            f"#{self.serial_number}: Failed to retrieve number after {self.MAX_RETRIES} retries.")
        return 0

    def get_points_and_remaining_games(self):
        """
        Получение поинтов и оставшихся игр.
        """
        try:
            if stop_event.is_set():
                logger.debug(
                    f"#{self.serial_number}: Stop event detected. Exiting get_points_and_remaining_games.")
                return None, None

            # Ожидаем появления элемента с поинтами
            points_element = self.wait_for_element(
                By.CSS_SELECTOR,
                "#app > div.game-page.page > div > div.content > div.reward > div.value > div.animated-points.visible > div.amount"
            )
            points = None
            if points_element:
                points = points_element.text.strip()
                if points:
                    logger.debug(
                        f"#{self.serial_number}: Points retrieved: {points}")
                else:
                    logger.warning(
                        f"#{self.serial_number}: Points element found but value is empty.")
            else:
                logger.debug(
                    f"#{self.serial_number}: Points element not found.")

            # Проверяем stop_event перед извлечением оставшихся игр
            if stop_event.is_set():
                logger.debug(
                    f"#{self.serial_number}: Stop event detected before retrieving remaining games. Exiting.")
                return points, None

            # Ожидаем появления элемента с количеством оставшихся игр
            games_element = self.wait_for_element(
                By.CSS_SELECTOR,
                "#app > div.game-page.page > div > div.buttons > button.kit-button.is-large.is-primary > div.label > span"
            )
            remaining_games_real = None
            if games_element:
                remaining_games_text = games_element.text.strip()
                remaining_games_real = self.extract_number_from_text(
                    remaining_games_text)
                logger.debug(
                    f"#{self.serial_number}: Remaining games retrieved: {remaining_games_real}")
            else:
                logger.debug(
                    f"#{self.serial_number}: Remaining games element not found.")

            return points, remaining_games_real

        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Error while retrieving points and remaining games: {str(e).splitlines()[0]}")
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
                logger.debug(
                    f"#{self.serial_number}: Input text is None or empty. Returning 0.")
                return 0

            # Извлечение чисел из текста
            numbers = re.findall(r'\d+', text)
            if numbers:
                extracted_number = int(numbers[0])
                logger.debug(
                    f"#{self.serial_number}: Extracted number: {extracted_number} from text: '{text}'")
                return extracted_number

            # Логируем случай, когда числа не найдены
            logger.debug(
                f"#{self.serial_number}: No numbers found in text: '{text}'. Returning 0.")
            return 0
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Error while extracting number from text '{text}': {str(e)}")
            return 0

    def auto_start_game(self):
        """
        Поиск кнопок 'Play'/'Играть' и выполнение JavaScript, если они найдены.
        Ограничение на количество попыток для предотвращения зависания.
        """
        max_attempts = 3  # Максимальное количество попыток
        attempt = 0

        while not stop_event.is_set() and attempt < max_attempts:
            try:
                logger.debug(
                    f"#{self.serial_number}: Attempt {attempt + 1} of {max_attempts}: Searching for 'Play' buttons.")

                # Проверяем наличие кнопок 'Play' или 'Играть'
                play_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "button.kit-button.is-large.is-primary, "
                    "a.play-btn[href='/game'], "
                    "button.kit-button.is-large.is-primary, "
                    "button.kit-pill.reset.is-type-white"  # Новый селектор для кнопки
                )

                if play_buttons:
                    logger.debug(
                        f"#{self.serial_number}: Found {len(play_buttons)} potential 'Play' buttons.")
                    for btn in play_buttons:
                        button_text = btn.text.strip()
                        logger.debug(
                            f"#{self.serial_number}: Checking button text: '{button_text}'")

                        if any(text in button_text for text in ["Play", "Играть"]):
                            logger.debug(
                                f"#{self.serial_number}: 'Play' button found. Attempting to start the game.")

                            # Выполняем скрипт для запуска игры
                            self.execute_game_script()
                            logger.debug(
                                f"#{self.serial_number}: Game start script executed.")

                            # Пауза для имитации естественного поведения
                            sleep_time = random.uniform(2, 5)
                            logger.debug(
                                f"#{self.serial_number}: Sleeping for {sleep_time:.2f} seconds.")
                            stop_event.wait(sleep_time)

                            # Ожидание завершения игры
                            self.wait_for_game_end()
                            logger.debug(
                                f"#{self.serial_number}: Game process completed.")
                            return
                    else:
                        logger.debug(
                            f"#{self.serial_number}: No valid 'Play' button text found. Retrying...")

                else:
                    logger.debug(
                        f"#{self.serial_number}: No 'Play' buttons found. Retrying...")

                attempt += 1
                stop_event.wait(2)  # Задержка перед повторной попыткой

            except Exception as e:
                logger.error(
                    f"#{self.serial_number}: Error in auto_start_game: {str(e)}")
                break

        logger.error(
            f"#{self.serial_number}: Max attempts reached or stop event triggered. Exiting auto_start_game.")

    def wait_for_game_end(self):
        """
        Ожидание появления данных о поинтах и оставшихся играх после начала игры.
        """
        try:
            while not stop_event.is_set():
                # Логируем успешное начало игры
                if self.first_game_start:
                    logger.info(
                        f"#{self.serial_number}: Game started successfully. Awaiting completion.")
                    # Устанавливаем флаг, чтобы избежать повторного логирования
                    self.first_game_start = False
                # Ожидаем появления элемента, сигнализирующего об окончании игры
                logger.debug(
                    f"#{self.serial_number}: Waiting for game end data to become visible.")
                try:
                    WebDriverWait(self.driver, 60).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "#app > div.game-page.page > div > div.content > div.reward > div.value > div.animated-points.visible > div.amount-hidden"))
                    )

                    # Проверяем оставшиеся игры
                    logger.debug(
                        f"#{self.serial_number}: Game end detected. Checking remaining games.")
                    self.check_remaining_games()
                    break

                except TimeoutException:
                    logger.debug(
                        f"#{self.serial_number}: Timeout while waiting for game end data to appear.")
                    break

        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Error while waiting for the game to end: {str(e)}")

    def execute_game_script(self):
        """Выполнение JavaScript кода в браузере через Selenium."""
        try:
            logger.debug(
                f"#{self.serial_number}: Executing game script in the browser.")

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
                    flowerProbability: 0.99,  
                    iceProbability: 0.80,
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
                            const buttons = document.querySelectorAll('button.kit-button.is-large.is-primary, a.play-btn[href="/game"], button.kit-button.is-large.is-primary, button.kit-pill.reset.is-type-white');
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
            logger.error(
                f"#{self.serial_number}: Error while executing JavaScript game script: {str(e)}")

    def check_remaining_games(self):
        """Проверка оставшихся игр после выполнения JavaScript."""

        # Установить значение по умолчанию, если self.max_games отсутствует
        if self.max_games is None:
            self.max_games = float('inf')  # Неограниченное количество игр

        points, remaining_games_real = self.get_points_and_remaining_games()

        # Проверяем, что поинты и оставшиеся игры не равны None перед сравнением
        if points is not None:
            logger.info(f"#{self.serial_number}: Points earned: {points}")
        else:
            logger.error(f"#{self.serial_number}: Failed to retrieve points.")

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
                # Если ограничение не нужно, используем реальное количество игр
                self.remaining_games = remaining_games_real
                self.is_limited = False  # Ограничение не применено

        # Логируем реальное количество оставшихся игр
        if self.is_limited:  # Если сработало ограничение
            logger.debug(
                f"#{self.serial_number}: Remaining games real: {remaining_games_real}.")
            logger.debug(
                f"#{self.serial_number}: Remaining games after possible limitation: {self.remaining_games}")
        else:
            self.remaining_games = remaining_games_real

        if self.remaining_games == 0:
            logger.info(
                f"#{self.serial_number}: Remaining games are 0. Ending the process.")
            self.driver.back()  # Используем команду браузера "назад"
            stop_event.wait(2)  # Задержка для загрузки предыдущей страницы
            self.switch_to_iframe()
        elif self.remaining_games > 0:
            logger.info(
                f"#{self.serial_number}: Remaining games: {self.remaining_games}. Starting again.")
            if self.remaining_games != remaining_games_real:  # Если ограничение было применено
                self.remaining_games -= 1
            self.auto_start_game()  # Повторный запуск игры
        else:
            logger.error(
                f"#{self.serial_number}: Failed to retrieve the remaining games. Ending the process.")

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
        start_time = time.time()
        timeout = 60 * 3  # 3 минут
        try:
            while not stop_event.is_set():
                if time.time() - start_time > timeout:
                    logger.error(
                        f"#{self.serial_number}: Timeout reached. Exiting loop.")
                    break
                # Проверяем наличие кнопок 'Play' или 'Играть'
                play_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "button.kit-button.is-large.is-primary, a.play-btn[href='/game'], button.kit-button.is-large.is-primary"
                )

                if not play_buttons:
                    logger.debug(
                        f"#{self.serial_number}: No 'Play' or 'Играть' buttons found on the main page.")
                    return

                for btn in play_buttons:
                    if stop_event.is_set():
                        logger.debug(
                            f"#{self.serial_number}: Stop event detected. Exiting check_and_restart_game.")
                        return

                    if any(text in btn.text for text in ["Play", "Играть"]):
                        logger.info(
                            f"#{self.serial_number}: 'Play' button found. Starting the game.")
                        try:
                            self.execute_game_script()  # Используем execute_game_script для корректного запуска
                            # Пауза для имитации естественного поведения
                            stop_event.wait(random.uniform(2, 5))
                            self.wait_for_game_end()  # Ожидание завершения игры
                            return
                        except Exception as game_start_error:
                            logger.error(
                                f"#{self.serial_number}: Error while executing game script: {str(game_start_error)}")
                            return  # Прерываем, если произошла ошибка при запуске игры
        except StaleElementReferenceException:
            logger.debug(f"#{self.serial_number}: Stale element detected.")
            return
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Error while checking the main page: {str(e)}")

    def check_for_continue_button(self):
        """Проверка наличия кнопки с текстом 'Continue' или 'Вернуться на главную' и выполнение клика по ней."""
        try:
            # Находим все кнопки, которые могут содержать текст 'Continue' или 'Вернуться на главную'
            continue_buttons = self.driver.find_elements(
                By.CSS_SELECTOR, "button.kit-button.is-large.is-primary, a.play-btn[href='/game'], button.kit-button.is-large.is-primary")

            if not continue_buttons:
                logger.info(
                    f"#{self.serial_number}: No 'Continue' or 'Return to Main' button found.")
                return  # Если кнопки не найдены, выходим из функции

            logger.info(
                f"#{self.serial_number}: Checking for 'Continue' button to proceed.")

            for btn in continue_buttons:
                # Проверяем, что кнопка действительно содержит нужный текст
                if any(text in btn.text for text in ["Continue", "Вернуться на главную"]):
                    logger.info(
                        f"#{self.serial_number}: 'Continue' or 'Return to Main' button found. Clicking.")
                    btn.click()  # Кликаем на кнопку для завершения всех игр
                    break  # Прерываем цикл после первого клика
        except Exception as e:
            logger.error(
                f"#{self.serial_number}: Error while checking for continue button: {str(e)}")
