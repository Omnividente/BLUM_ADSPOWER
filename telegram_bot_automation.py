import random
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from utils import setup_logger, load_settings, get_max_games
from browser_manager import BrowserManager
from colorama import Fore, Style 
# Настроим логирование (если не было настроено ранее)
logger = setup_logger()
# Загружаем настройки
settings = load_settings()
# Получаем максимальное количество игр из настроек (один раз при инициализации)
max_games = get_max_games(settings)  # max_games сохраняем в атрибут объекта
remaining_games = None

class TelegramBotAutomation:
    MAX_RETRIES = 3

    def __init__(self, serial_number, settings):
        self.serial_number = serial_number
        self.username = None  # Initialize username as None
        self.balance = 0.0  # Initialize balance as 0.0
        self.browser_manager = BrowserManager(serial_number)
        self.settings = settings        
        self.driver = None
        self.first_game_start = True
        self.is_limited = False  #Атрибут для отслеживания ограничения

        logger.debug(f"Initializing automation for account {serial_number}")

        # Ожидание завершения предыдущей сессии браузера
        if not self.browser_manager.wait_browser_close():
            logger.error(f"Account {serial_number}: Failed to close previous browser session.")
            raise RuntimeError("Failed to close previous browser session")

        # Запуск браузера
        if not self.browser_manager.start_browser():
            logger.error(f"Account {serial_number}: Failed to start browser.")
            raise RuntimeError("Failed to start browser")

        # Сохранение экземпляра драйвера
        self.driver = self.browser_manager.driver

    def safe_click(self, element):
        """
        Безопасный клик по элементу.
        """
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(element))
            element.click()
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", element)
            except Exception:
                pass



    def navigate_to_bot(self):
        self.clear_browser_cache_and_reload()
        time.sleep(5)
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                self.driver.get('https://web.telegram.org/k/')
                logger.debug(f"Account {self.serial_number}: Navigated to Telegram web.")
                self.close_extra_windows()
                sleep_time = random.randint(5, 7)
                logger.debug(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                time.sleep(sleep_time)
                return True
            except (WebDriverException, TimeoutException) as e:
                logger.warning(f"Account {self.serial_number}: Exception in navigating to Telegram bot (attempt {retries + 1}): {str(e)}")
                retries += 1
                time.sleep(5)
        return False
    
    def close_extra_windows(self):
        try:
            current_window = self.driver.current_window_handle
            all_windows = self.driver.window_handles
            for window in all_windows:
                if window != current_window:
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    self.driver.switch_to.window(current_window)
        except WebDriverException as e:
            logger.warning(f"Account {self.serial_number}: Exception while closing extra windows: {str(e)}")
    
    def send_message(self):
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                chat_input_area = self.wait_for_element(By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[2]/input[1]')
                if chat_input_area:
                    chat_input_area.click()
                    group_url = self.settings.get('TELEGRAM_GROUP_URL', 'https://t.me/CryptoProjects_sbt')
                    chat_input_area.send_keys(group_url)
                
                search_area = self.wait_for_element(By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[1]/div[1]/div[3]/div[2]/div[2]/div[2]/div[1]/div[1]/div[1]/div[2]/ul[1]/a[1]/div[1]')
                if search_area:
                    search_area.click()
                    logger.debug(f"Account {self.serial_number}: Group searched.")
                sleep_time = random.randint(5, 7)
                logger.debug(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                time.sleep(sleep_time)
                return True
            except (NoSuchElementException, WebDriverException) as e:
                logger.warning(f"Account {self.serial_number}: Failed to perform action (attempt {retries + 1}): {str(e)}")
                retries += 1
                time.sleep(5)
        return False

    def click_link(self):
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                # Получаем ссылку из настроек
                bot_link = self.settings.get('BOT_LINK', 'https://t.me/blum/app?startapp=ref_vNDGLmgnYL')

                # Поиск элемента ссылки
                link = self.wait_for_element(By.CSS_SELECTOR, f"a[href*='{bot_link}']")
                if link:
                    # Скроллинг к ссылке
                    self.driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", link)
                    time.sleep(1)  # Небольшая задержка для завершения скроллинга
                    
                    # Клик по ссылке
                    link.click()
                    time.sleep(2)

                # Поиск и клик по кнопке запуска
                launch_button = self.wait_for_element(By.CSS_SELECTOR, "button.popup-button.btn.primary.rp", timeout=5)
                if launch_button:
                    launch_button.click()
                    logger.info(f"Account {self.serial_number}: Launch button clicked.")
                
                # Лог успешного запуска
                logger.info(f"Account {self.serial_number}: BLUM STARTED")

                # Случайная задержка перед переключением на iframe
                sleep_time = random.randint(15, 20)
                logger.debug(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                time.sleep(sleep_time)

                # Переключение на iframe
                self.switch_to_iframe()
                return True
            
            except (NoSuchElementException, WebDriverException, TimeoutException) as e:
                logger.warning(f"Account {self.serial_number}: Failed to click link or interact with elements (attempt {retries + 1}): {str(e)}")
                retries += 1
                time.sleep(5)

        # Возвращаем False, если все попытки завершились неудачно
        return False


    def wait_for_element(self, by, value, timeout=10):
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        except TimeoutException:
            #logger.warning(f"Account {self.serial_number}: Failed to find the element located by {by} with value {value} within {timeout} seconds.")
            return None
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while waiting for element: {str(e)}")
            return None
    def clear_browser_cache_and_reload(self):
        """
        Очищает кэш браузера и перезагружает текущую страницу.
        """
        try:
            # Очистка кэша
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            logger.debug(f"Account {self.serial_number}: Browser cache cleared.")
            
            # Перезагрузка текущей страницы
            self.driver.refresh()
            logger.debug(f"Account {self.serial_number}: Page refreshed after clearing cache.")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Failed to clear browser cache or reload page: {e}")


    def preparing_account(self):
        actions = [
            ("/html[1]/body[1]/div[1]/div[1]/div[1]/div[1]/div[2]/div[2]/div[3]/button[1]", "Daily сheck-in claimed")
        ]
        for xpath, success_msg in actions:
            retries = 0
            while retries < self.MAX_RETRIES:
                try:
                    # Пытаемся найти и нажать кнопку
                    element = self.driver.find_element(By.XPATH, xpath)
                    element.click()
                    logger.debug(f"Account {self.serial_number}: {success_msg}")
                    # Пауза после нажатия
                    sleep_time = random.randint(5, 7)
                    logger.debug(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                    time.sleep(sleep_time)
                    break  # Выходим из цикла, если действие выполнено успешно
                except NoSuchElementException:
                    # Игнорируем, если элемент не найден, и переходим к следующему действию
                    break
                except WebDriverException as e:
                    # Логируем ошибку только при WebDriverException
                    logger.warning(f"Account {self.serial_number}: Failed action (attempt {retries + 1}): {str(e).splitlines()[0]}")
                    retries += 1
                    time.sleep(5)

        # Добавляем ожидание кнопки сheck-in
        try:
            logger.debug("Waiting for the presence of the button with the specified selector.")
            button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.kit-button.is-large.is-primary.is-fill.btn"))
            )
            if button.is_enabled():
                logger.info(f"Account {self.serial_number}: Daily сheck-in claimed.")
                button.click()
                time.sleep(random.uniform(1, 2))  # Небольшая пауза после клика
            else:
                logger.debug(f"Account {self.serial_number}: Button is present but not enabled.")
        except TimeoutException:
            logger.debug(f"Account {self.serial_number}: Button with selector not found within 10 seconds.")
        except WebDriverException as e:
            logger.debug(f"Account {self.serial_number}: Failed to interact with the button: {str(e)}")

        
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                # Ожидаем, пока элемент станет кликабельным
                button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#app > div.layout-tabs.tabs > a:nth-child(1)"))
                )
                button.click()
                # logger.info(f"Account {self.serial_number}: Successfully clicked on the navigation tab.")
                break  # Выходим из цикла после успешного нажатия
            except NoSuchElementException:
                logger.warning(f"Account {self.serial_number}: Home tab not found.")
                break  # Выходим из цикла, если элемент не найден
            except WebDriverException as e:
                logger.warning(f"Account {self.serial_number}: Failed to click Home tab (attempt {retries + 1}): {str(e).splitlines()[0]}")
                retries += 1
                time.sleep(5)




    def switch_to_iframe(self):
        """
        This method switches to the first iframe on the page, if available.
        """
        try:
            # Возвращаемся к основному контенту страницы
            self.driver.switch_to.default_content()
            
            # Ищем все iframes на странице
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                # Переключаемся на первый iframe
                self.driver.switch_to.frame(iframes[0])
                #logger.info(f"Account {self.serial_number}: Switched to iframe.")
                return True
            else:
                logger.warning(f"Account {self.serial_number}: No iframe found to switch.")
                return False
        except NoSuchElementException:
            logger.warning(f"Account {self.serial_number}: No iframe found.")
            return False
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while switching to iframe: {str(e)}")
            return False




    def get_username(self):
        # Получение имени пользователя
        username_block = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#app > div.index-page.page > div > div.profile-with-balance > div.username"))  # Укажите точный XPATH для username
        )
        username = username_block.get_attribute("textContent").strip()
        #logger.info(f"Account {self.serial_number}: Current username: {username}")
        return username
    
    def get_balance(self):
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                

                # Поиск всех чисел в балансе
                visible_balance_elements = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "div.profile-with-balance .kit-counter-animation.value .el-char-wrapper .el-char"))
                )

                # Сбор текста чисел и объединение в строку
                balance_text = ''.join([element.get_attribute("textContent").strip() for element in visible_balance_elements])
                logger.debug(f"Account {self.serial_number}: Raw balance text: {balance_text}")

                # Удаление запятых
                balance_text = balance_text.replace(',', '')
                logger.debug(f"Account {self.serial_number}: Cleaned balance text: {balance_text}")

                # Преобразование в float
                if balance_text.replace('.', '', 1).isdigit():
                    self.balance = float(balance_text)
                else:
                    logger.warning(f"Account {self.serial_number}: Balance text is invalid: '{balance_text}'")
                    self.balance = 0.0

                # Преобразование float к строке, удаление .0
                if self.balance.is_integer():
                    balance_text = str(int(self.balance))  # Удаляет .0
                self.get_username()
                
                # Логирование
                
                logger.info(f"Account {self.serial_number}: Current balance: {balance_text}")

                # Обновление таблицы
                return balance_text

            except (NoSuchElementException, TimeoutException) as e:
                logger.warning(f"Account {self.serial_number}: Failed to get balance or username (attempt {retries + 1}): {str(e).splitlines()[0]}")
                retries += 1
                time.sleep(5)

        # Возврат 0 в случае неудачи
        return "0"    


    def get_time(self):
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                # Находим элемент с временем
                time_element = self.driver.find_element(By.CSS_SELECTOR, "div.time-left")
                time_text = time_element.get_attribute("textContent").strip()

                # Преобразуем текст в удобный формат
                hours, minutes = 0, 0
                if "h" in time_text or "ч" in time_text:
                    hours_part = time_text.split()[0]
                    hours = int(hours_part[:-1])  # Убираем последний символ (h/ч) и преобразуем в число
                if "m" in time_text or "м" in time_text:
                    minutes_part = time_text.split()[-1]
                    minutes = int(minutes_part[:-1])  # Убираем последний символ (m/м) и преобразуем в число

                # Генерируем случайные секунды
                seconds = random.randint(0, 59)

                formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"  # Форматируем в HH:MM:SS

                # Логируем только успешное обнаружение времени
                logger.info(f"Account {self.serial_number}: Start farm will be available after: {formatted_time}")
                return formatted_time
            except NoSuchElementException:
                # Если элемент не найден, просто увеличиваем счетчик попыток
                retries += 1
                time.sleep(5)
            except TimeoutException:
                # Если происходит таймаут, увеличиваем счетчик попыток
                retries += 1
                time.sleep(5)

        # Если время так и не было получено
        return None  # Возвращаем None для обработки в вызывающей функции



    def farming(self):
        actions = [
            (".label", "Farming button clicked", "No active button found.")
        ]

        for css_selector, success_msg, fail_msg in actions:
            retries = 0
            while retries < self.MAX_RETRIES:
                try:
                    # Проверяем, доступно ли время перед нажатием
                    formatted_time = self.get_time()
                    if formatted_time:
                        logger.debug(f"Account {self.serial_number}: Skipping button click as farming will be available after: {formatted_time}")
                        break

                    # Находим кнопку
                    button = self.driver.find_element(By.CSS_SELECTOR, css_selector)

                    # Кликаем по кнопке
                    button.click()
                    logger.info(f"Account {self.serial_number}: {success_msg}")
                    
                    # Ждем перед проверкой активности кнопки
                    sleep_time = random.randint(3, 4)
                    time.sleep(sleep_time)

                    # Проверяем, доступно ли время после нажатия
                    formatted_time = self.get_time()
                    if formatted_time:
                        logger.info(f"Account {self.serial_number}: Stopping further actions as farming will be available after: {formatted_time}")
                        break

                    # Проверяем, осталась ли кнопка активной, и повторяем нажатие
                    try:
                        button = self.driver.find_element(By.CSS_SELECTOR, css_selector)
                        if button.is_enabled():
                            button.click()
                    except NoSuchElementException:
                        break

                    break  # Успешное выполнение
                except NoSuchElementException:
                    logger.info(f"Account {self.serial_number}: {fail_msg}")
                    break
                except WebDriverException as e:
                    logger.warning(f"Account {self.serial_number}: Failed action (attempt {retries + 1}): {str(e).splitlines()[0]}")
                    retries += 1
                    time.sleep(5)

        # Вызов auto_start_game после завершения действий farming
        try:
            # Проверяем количество доступных игр
            try:
                available_games = self.get_number_from_element(By.CSS_SELECTOR, ".pass")
                if available_games is None or available_games == 0:  # Если не удалось получить число или оно равно 0
                    available_games = 0
            except Exception as e:
                logger.debug(f"Account {self.serial_number}: Failed to retrieve available games due to error: {str(e)}")
                available_games = 0  # Если произошла ошибка, считаем игры равными 0

            if available_games == 0:
                logger.info(f"Account {self.serial_number}: All games completed or unavailable.")
                return  # Пропускаем запуск игры

            # Проверяем max_games
            if max_games == 0:
                logger.info(f"Account {self.serial_number}: MAX_GAMES is set to 0. Skipping game start.")
                return  # Пропускаем запуск игры
            elif max_games is not None and max_games != float('inf'):
                logger.info(f"Account {self.serial_number}: {available_games} games available.")
                logger.info(f"Account {self.serial_number}: Limiting to {max_games} games in settings.")
            else:
                logger.info(f"Account {self.serial_number}: {available_games} games available. No limitation applied.")

            # Запуск игры
            self.auto_start_game()

        except Exception as e:
            logger.error(f"Account {self.serial_number}: Error while checking games availability: {str(e)}")
              
    def get_number_from_element(self, by, value):
        """
        Извлечение числа из текста элемента. Если числа нет, возвращается 0.
        """
        try:
            logger.debug(f"Attempting to locate element using locator: {by}, value: {value}")
            element = self.wait_for_element(by, value)
            
            if element:
                logger.debug("Element located successfully.")
                
                # Скроллим к элементу, чтобы сделать его видимым
                logger.debug("Scrolling to element to make it visible.")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                
                # Попытка получить текст из разных источников
                logger.debug("Attempting to extract text from the element.")
                text = element.get_attribute("textContent").strip() if element.get_attribute("textContent") else element.text.strip()
                logger.debug(f"Extracted text: {text}")
                
                # Используем регулярное выражение для поиска числа
                logger.debug("Attempting to extract number from the text using regex.")
                
                match = re.search(r'\d+', text)
                
                if match:
                    extracted_number = int(match.group())
                    logger.debug(f"Number extracted successfully: {extracted_number}")
                    return extracted_number  # Возвращаем найденное число
                else:
                    logger.debug(f"No number found in the text: {text}. Returning 0.")
                    return 0  # Число не найдено
            else:
                logger.debug("Element not found. Returning 0.")
                return 0
        except Exception as e:
            logger.debug(f"Error while retrieving number from element: {str(e)}")
            return 0



    def get_points_and_remaining_games(self):
        """Получение поинтов и оставшихся игр."""
        try:
            # Ожидаем, пока появится элемент с поинтами
            points_element = self.wait_for_element(By.CSS_SELECTOR, "#app > div.game-page.page > div > div.content > div.reward > div.value > div.animated-points.visible > div.amount")

            
            if points_element:
                points = points_element.text.strip()
              
                # Если поинты пустые, пробуем другую попытку или логируем предупреждение
                if not points:
                    logger.warning(f"Account {self.serial_number}: Получены пустые поинты.")
            else:
                points = None
                logger.warning(f"Account {self.serial_number}: Элемент с поинтами не найден.")
            
            # Ожидаем, пока появится элемент с количеством оставшихся игр
            games_element = self.wait_for_element(By.CSS_SELECTOR, "#app > div.game-page.page > div > div.buttons > button.kit-button.is-large.is-primary > div.label > span")
            if games_element:
                remaining_games_text = games_element.text.strip()
                remaining_games_real = self.extract_number_from_text(remaining_games_text)
            else:
                remaining_games_real = None
            
            return points, remaining_games_real

        except Exception as e:
            logger.error(f"Account {self.serial_number}: Ошибка при получении информации: {str(e)}")
            return None, None

    def extract_number_from_text(self, text):
        """Извлечение числового значения из текста."""
        # Проверка на None и извлечение чисел
        if text is None:
            return 0  # Возвращаем 0, если текста нет
        
        numbers = re.findall(r'\d+', text)
        if numbers:
            return int(numbers[0])
        return 0  # Если цифр нет, возвращаем 0
    
    def auto_start_game(self):        
        """Поиск кнопок 'Play'/'Играть' и выполнение JavaScript, если они найдены."""
        try:
            # Проверяем, есть ли на странице кнопка 'Play' или 'Играть'
            play_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button.kit-button.is-large.is-primary, a.play-btn[href='/game'], button.kit-button.is-large.is-primary")
            for btn in play_buttons:
                if any(text in btn.text for text in ["Play", "Играть"]):
                    if self.first_game_start:
                        logger.info(f"Account {self.serial_number}: 'Play' button found. Starting the game.")
                        self.first_game_start = False  # Устанавливаем флаг, чтобы логировать только один раз
                    self.execute_game_script()  # Используем execute_game_script для корректного запуска игры                    
                    time.sleep(random.uniform(2, 5))  # Пауза для имитации естественного поведения
                    self.wait_for_game_end()  # Ожидание окончания игры
                    
                    return

            # Если на главной странице кнопка не найдена, перезапускаем игру
            self.check_and_restart_game()

        except Exception as e:
            # В случае любой ошибки в блоке auto_start_game просто пропускаем этот блок
            logger.error(f"Account {self.serial_number}: Error while attempting to start the game: {str(e)}")
            # После ошибки просто продолжаем выполнение, не прерывая программу
            pass

    
    def wait_for_game_end(self):
        """Ожидание появления данных о поинтах и оставшихся играх после начала игры."""
        try:
            # Ожидаем, пока появится информация о поинтах и оставшихся играх
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#app > div.game-page.page > div > div.content > div.reward > div.value > div.animated-points.visible > div.amount-hidden"))
            )

            # Если это первый раз, выводим лог о старте игры
            if self.first_game_start:
                logger.debug(f"Account {self.serial_number}: Game started, waiting for completion.")
                self.first_game_start = False  # Устанавливаем флаг, чтобы логировать только один раз

            # После появления данных запускаем проверку количества оставшихся игр
            self.check_remaining_games()  # Проверка количества оставшихся игр

        except Exception as e:
            logger.error(f"Account {self.serial_number}: Error while waiting for the game to end: {str(e)}")

    
    def execute_game_script(self):
        """Выполнение вашего JavaScript кода в браузере через Selenium."""
        logger.debug(f"Account {self.serial_number}: Game started, waiting for completion.")
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
                        autoStartGame(); // Выполнить одно действие
                    }

                    const mutationObserver = new MutationObserver(mutations => {
                        mutations.forEach(mutation => {
                            if (mutation.type === 'childList') {
                                detectGameEnd();
                                mutationObserver.disconnect(); // Остановить наблюдатель после первого срабатывания
                            }
                        });
                    });

                    const appRoot = document.querySelector('#app');
                    if (appRoot) {
                        mutationObserver.observe(appRoot, { childList: true, subtree: true });
                    }

                    monitorPlayButton(); // Выполним один раз

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
        

    def check_remaining_games(self):
        """Проверка оставшихся игр после выполнения JavaScript."""
        global max_games, remaining_games

        # Установить значение по умолчанию, если max_games отсутствует
        if max_games is None:
            max_games = float('inf')  # Неограниченное количество игр

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
        if remaining_games is None:  # Для первого вызова
            # Если remaining_games_real больше чем max_games-1, ограничиваем количество игр
            if remaining_games_real > (max_games - 1):
                remaining_games = max_games - 1  # Ограничиваем количество игр
                self.is_limited = True
            else:
                remaining_games = remaining_games_real  # Если ограничение не нужно, используем реальное количество игр
                self.is_limited = False

        # Логируем реальное количество оставшихся игр
        
        if self.is_limited:  # Если сработало ограничение
            logger.info(f"Remaining games real: {remaining_games_real}.")
            logger.info(f"Remaining games after possible limitation: {remaining_games }")
        else:
            remaining_games = remaining_games_real

        if remaining_games == 0:
            logger.info("Remaining games are 0. Ending the process.")
            #if self.is_limited:  # Если сработало ограничение
            self.driver.back()  # Используем команду браузера "назад"
            time.sleep(2)  # Задержка для загрузки предыдущей страницы
            self.switch_to_iframe()
            #else:
                #self.check_for_continue_button()  # Проверяем, нужно ли продолжить
        elif remaining_games > 0:
            logger.info(f"Remaining games: {remaining_games }. Starting again.")
            if remaining_games != remaining_games_real:  # Если ограничение было применено
                remaining_games -= 1
            self.auto_start_game()  # Повторный запуск игры
        else:
            logger.error("Failed to retrieve the remaining games. Ending the process.")



    
    def check_and_restart_game(self):
        """Проверка на главную страницу и запуск игры."""
        try:
            # Проверяем, есть ли на странице кнопка 'Play' или 'Играть'
            play_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button.kit-button.is-large.is-primary, a.play-btn[href='/game'], button.kit-button.is-large.is-primary")
            for btn in play_buttons:
                if any(text in btn.text for text in ["Play", "Играть"]):
                    logger.info(f"Account {self.serial_number}: 'Play' button found. Starting the game.")
                    self.execute_game_script()  # Используем execute_game_script для корректного запуска
                    time.sleep(random.uniform(2, 5))  # Пауза для имитации естественного поведения
                    self.wait_for_game_end()  # Ожидание начала игры
                    return
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Error while checking the main page: {str(e)}")
    
    def check_for_continue_button(self):
        """Проверка наличия кнопки с текстом 'Continue' или 'Вернуться на главную' и выполнение клика по ней."""
        try:
            # Находим все кнопки, которые могут содержать текст 'Continue' или 'Вернуться на главную'
            continue_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button.kit-button.is-large.is-primary, a.play-btn[href='/game'], button.kit-button.is-large.is-primary") 
            logger.info(f"Account {self.serial_number}: Finish all games.")
            for btn in continue_buttons:                               
                    btn.click()  # Кликаем на кнопку для завершения всех игр
                    break  # Прерываем цикл после первого клика        
        except Exception as e:
            # Обрабатываем исключения, но не прерываем выполнение
            pass