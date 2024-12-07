import requests
import time
import os
from selenium import webdriver
from requests.exceptions import RequestException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from utils import setup_logger

# Настроим логирование (если не было настроено ранее)
logger = setup_logger() 

class BrowserManager:
    MAX_RETRIES = 3

    def __init__(self, serial_number):
        self.serial_number = serial_number
        self.driver = None
    
    def check_browser_status(self):
        try:
            response = requests.get(
                'http://local.adspower.net:50325/api/v1/browser/active',
                params={'serial_number': self.serial_number}
            )
            response.raise_for_status()
            data = response.json()
            if data['code'] == 0 and data['data']['status'] == 'Active':
                #logger.info(f"Account {self.serial_number}: Browser is already active.")
                return True
            else:
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Account {self.serial_number}: Failed to check browser status due to network issue: {str(e)}")
            return False
        except Exception as e:
            logger.exception(f"Account {self.serial_number}: Unexpected exception while checking browser status: {str(e)}")
            return False
            
    def wait_browser_close(self):
        if self.check_browser_status():
            logger.info(f"Account {self.serial_number}: Browser already open. Waiting for closure.")          
            start_time = time.time()
            timeout = 900
            while time.time() - start_time < timeout:
                if not self.check_browser_status():
                    logger.info(f"Account {self.serial_number}: Browser already closed.")
                    return True
                time.sleep(5)
            logger.warning(f"Account {self.serial_number}: Waiting time for browser closure has expired.")
            return False
        return True
            
    def start_browser(self):
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                if self.check_browser_status():
                    logger.info(f"Account {self.serial_number}: Browser already open. Closing the existing browser.")
                    self.close_browser()
                    time.sleep(5)

                request_url = (
                    f'http://local.adspower.net:50325/api/v1/browser/start?'
                    f'serial_number={self.serial_number}&ip_tab=0&headless=1'
                )

                response = requests.get(request_url)
                response.raise_for_status()
                data = response.json()
                if data['code'] == 0:
                    selenium_address = data['data']['ws']['selenium']
                    webdriver_path = data['data']['webdriver']
                    chrome_options = Options()
                    # Отключение всех запросов
                    chrome_options.add_argument("--disable-notifications")  # Уведомления
                    chrome_options.add_argument("--disable-popup-blocking")  # Всплывающие окна
                    chrome_options.add_argument("--disable-geolocation")  # Запросы местоположения
                    chrome_options.add_argument("--disable-translate")  # Запросы переводчика
                    chrome_options.add_argument("--disable-infobars")  # Информационные панели
                    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Обнаружение автоматизации
                    chrome_options.add_argument("--no-sandbox")  # Отключение песочницы (для стабильности)
                    chrome_options.add_argument("--disable-gpu")  # Отключение GPU
                    chrome_options.add_argument("--disable-background-timer-throttling")  # Отключение задержки таймеров
                    chrome_options.add_argument("--disable-renderer-backgrounding")  # Отключение рендера для фона
                    chrome_options.add_argument("--disable-backgrounding-occluded-windows")  # Отключение оптимизации для скрытых окон
                    #extension_dir = os.path.abspath('./Telegram_app_unlocker')  # Путь к папке с расширением
                    #chrome_options.add_argument(f'--load-extension={extension_dir}')  # Загрузка расширения для работы BLUM в браузере
                    chrome_options.add_experimental_option("debuggerAddress", selenium_address)

                    service = Service(executable_path=webdriver_path)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.driver.set_window_size(600, 720)
                    logger.info(f"Account {self.serial_number}: Browser started successfully.")
                    return True
                else:
                    logger.warning(f"Account {self.serial_number}: Failed to start the browser. Error: {data['msg']}")
                    retries += 1
                    time.sleep(5)  # Wait before retrying
            except requests.exceptions.RequestException as e:
                logger.error(f"Account {self.serial_number}: Network issue when starting browser: {str(e)}")
                retries += 1
                time.sleep(5)
            except WebDriverException as e:
                logger.warning(f"Account {self.serial_number}: WebDriverException occurred: {str(e)}")
                retries += 1
                time.sleep(5)
            except Exception as e:
                logger.exception(f"Account {self.serial_number}: Unexpected exception in starting browser: {str(e)}")
                retries += 1
                time.sleep(5)
        
        logger.error(f"Account {self.serial_number}: Failed to start browser after {self.MAX_RETRIES} retries.")
        return False

    
    def close_browser(self):
        """
        Закрывает браузер с использованием API и WebDriver, с приоритетом на API.
        """
        # Флаг для предотвращения повторного закрытия
        if getattr(self, "browser_closed", False):
            logger.info(f"Account {self.serial_number}: Browser already closed. Skipping.")
            return False

        self.browser_closed = True  # Устанавливаем флаг перед попыткой закрытия

        # Попытка остановить браузер через API
        try:
            response = requests.get(
                'http://local.adspower.net:50325/api/v1/browser/stop',
                params={'serial_number': self.serial_number},
                timeout=25  # Тайм-аут для API-запроса
            )
            response.raise_for_status()
            data = response.json()

            if data.get('code') == 0:
                logger.info(f"Account {self.serial_number}: Browser stopped via API successfully.")
                return True
            else:
                logger.warning(f"Account {self.serial_number}: API stop returned unexpected code: {data.get('code')}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Account {self.serial_number}: Network issue while stopping browser via API: {str(e)}")
        except Exception as e:
            logger.exception(f"Account {self.serial_number}: Unexpected error during API stop: {str(e)}")

        # Если API не сработал, пробуем стандартное закрытие через WebDriver
        try:
            if self.driver:
                self.driver.close()
                self.driver.quit()
                logger.info(f"Account {self.serial_number}: Browser closed successfully via WebDriver.")
        except WebDriverException as e:
            logger.warning(f"Account {self.serial_number}: WebDriverException while closing browser: {str(e)}")
        except Exception as e:
            logger.exception(f"Account {self.serial_number}: General exception while closing browser via WebDriver: {str(e)}")
        finally:
            self.driver = None  # Обнуляем драйвер

        return False


