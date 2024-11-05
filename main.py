import requests
import os
import time
import logging
from colorama import Fore, Style
import json
import random
from prettytable import PrettyTable
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, NoSuchWindowException, InvalidSessionIdException
from termcolor import colored
import sys

# Load settings from settings.txt
SETTINGS_FILE = 'settings.txt'
settings = {}
try:
    with open(SETTINGS_FILE, 'r') as f:
        for line in f:
            key, value = line.strip().split('=', 1)
            settings[key.strip()] = value.strip()
except FileNotFoundError:
    logger.error(f"Settings file '{SETTINGS_FILE}' not found.")
    sys.exit(1)
except Exception as e:
    logger.error(f"Error reading settings file: {e}")
    sys.exit(1)

TELEGRAM_GROUP_URL = settings.get('TELEGRAM_GROUP_URL', 'https://t.me/cryptoprojectssbt')
BLUM_APP_URL = settings.get('BLUM_APP_URL', 'https://t.me/blum/app?startapp=ref_vNDGLmgnYL')

# Set up logging with colors
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
        # Set time to white
        log_message = log_message.replace(record.asctime, f"{Fore.LIGHTYELLOW_EX}{record.asctime}{Style.RESET_ALL}")
        # Set level name color
        levelname = f"{self.COLORS.get(record.levelno, Fore.WHITE)}{record.levelname}{Style.RESET_ALL}"
        log_message = log_message.replace(record.levelname, levelname)
        # Set message color based on level
        message_color = self.COLORS.get(record.levelno, Fore.WHITE)
        log_message = log_message.replace(record.msg, f"{message_color}{record.msg}{Style.RESET_ALL}")
        return log_message

handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

class BrowserManager:
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
                return True
            else:
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Account {self.serial_number}: Exception in checking browser status: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error in checking browser status: {str(e)}")
            return False

    def wait_browser_close(self):
        if self.check_browser_status():
            logger.info(f"Account {self.serial_number}: Browser already open. Waiting for closure.")          
            start_time = time.time()
            time_out = 900
            while time.time() - start_time < time_out:
                if not self.check_browser_status():                
                    logger.info(f"Account {self.serial_number}: Browser already closed.")
                    return True                                       
                time.sleep(5)
            logger.warning(f"Account {self.serial_number}: The waiting time has expired.")
            return False    
    
    
    def start_browser(self):
        try:           
            if self.check_browser_status():
                logger.info(f"Account {self.serial_number}: Browser already open. Closing the existing browser.")
                self.close_browser()
                time.sleep(5)    
            script_dir = os.path.dirname(os.path.abspath(__file__))
            requestly_extension_path = os.path.join(script_dir, 'blum_unlocker_extension')

            launch_args = json.dumps([f"--load-extension={requestly_extension_path}",  "--disable-notifications"])

            request_url = (
                f'http://local.adspower.net:50325/api/v1/browser/start?'
                f'serial_number={self.serial_number}&ip_tab=1&launch_args={launch_args}'
            )

            response = requests.get(request_url)
            response.raise_for_status()
            data = response.json()
            if data['code'] == 0:
                selenium_address = data['data']['ws']['selenium']
                webdriver_path = data['data']['webdriver']
                chrome_options = Options()
                chrome_options.add_experimental_option("debuggerAddress", selenium_address)

                service = Service(executable_path=webdriver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.set_window_size(600, 720)
                logger.info(f"Account {self.serial_number}: Browser started successfully.")
                return True
            else:
                logger.warning(f"Account {self.serial_number}: Failed to start the browser. Error: {data['msg']}")
                return False
        except (requests.exceptions.RequestException, WebDriverException) as e:
            logger.error(f"Account {self.serial_number}: Exception in starting browser: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error in starting browser: {str(e)}")
            return False

    def close_browser(self):
        try:
            if self.driver:
                try:
                    self.driver.quit()
                    self.driver = None  
                    logger.info(f"Account {self.serial_number}: Browser closed successfully.")
                except (WebDriverException, NoSuchWindowException, InvalidSessionIdException) as e:
                    logger.warning(f"Account {self.serial_number}: Exception occurred, browser should be closed now: {str(e)}")
                except Exception as e:
                    logger.error(f"Account {self.serial_number}: Unexpected error while closing browser: {str(e)}")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: General Exception occurred when trying to close the browser: {str(e)}")
        finally:
            try:
                response = requests.get(
                    'http://local.adspower.net:50325/api/v1/browser/stop',
                    params={'serial_number': self.serial_number}
                )
                response.raise_for_status()
                data = response.json()
                if data['code'] == 0:
                    logger.info(f"Account {self.serial_number}: Browser closed successfully.")
                else:
                    logger.warning(f"Account {self.serial_number}: Exception, browser should be closed now")
            except requests.exceptions.RequestException as e:
                logger.error(f"Account {self.serial_number}: Exception occurred when trying to close the browser: {str(e)}")
            except Exception as e:
                logger.error(f"Account {self.serial_number}: Unexpected error when trying to close the browser: {str(e)}")

class TelegramBotAutomation:    

    def __init__(self, serial_number):
        self.serial_number = serial_number
        self.browser_manager = BrowserManager(serial_number)
        logger.info(f"Initializing automation for account {serial_number}")        
        self.browser_manager.wait_browser_close()
        if not self.browser_manager.start_browser():
            logger.error(f"Account {serial_number}: Failed to start browser, aborting automation.")
            return
        self.driver = self.browser_manager.driver
    
    def get_username(self):
        try:
            username_elements = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "#app > div.index-page.page > div > div.profile-with-balance > div.username"))
            )
            username = ''.join([element.text for element in username_elements])
            return username
        except TimeoutException:
            logger.warning(f"Account {self.serial_number}: Failed to find the username element.")
            return None
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while getting username: {str(e)}")
            return None

    def navigate_to_bot(self):
        try:
            self.driver.get('https://web.telegram.org/k/')
            logger.info(f"Account {self.serial_number}: Navigated to Telegram web.")
        except (WebDriverException, TimeoutException) as e:
            logger.error(f"Account {self.serial_number}: Exception in navigating to Telegram bot: {str(e)}")
            self.browser_manager.close_browser()
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error in navigating to Telegram bot: {str(e)}")
            self.browser_manager.close_browser()
        try:
            current_window = self.driver.current_window_handle
            all_windows = self.driver.window_handles
            for window in all_windows:
                if window != current_window:
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    self.driver.switch_to.window(current_window)
        except NoSuchWindowException as e:
            logger.warning(f"Account {self.serial_number}: Exception while switching windows: {str(e)}")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while switching windows: {str(e)}")

    def send_message(self, message):
        try:
            chat_input_area = self.wait_for_element(By.XPATH, '/html[1]/body[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[2]/input[1]')
            if chat_input_area:
                chat_input_area.click()
                chat_input_area.send_keys(message)

            search_area = self.wait_for_element(By.XPATH, '/html[1]/body[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[3]/div[2]/div[2]/div[2]/div[1]/div[1]/div[1]/div[2]/ul[1]/a[1]/div[1]')
            if search_area:
                search_area.click()
                logger.info(f"Account {self.serial_number}: Group searched.")
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"Account {self.serial_number}: Failed to send message: {str(e)}")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while sending message: {str(e)}")
         
    def click_link(self):
        try:
            link = self.wait_for_element(By.CSS_SELECTOR, f"a[href*='{BLUM_APP_URL}']")
            if link:
                link.click()
        except (TimeoutException, NoSuchElementException, WebDriverException) as e:
            logger.warning(f"Account {self.serial_number}: Error in clicking link or interacting with elements: {str(e)}")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error in clicking link: {str(e)}")
           
        try:
            launch_button = self.wait_for_element(By.CSS_SELECTOR, "button.popup-button.btn.primary.rp", timeout=5)
            if launch_button:
                launch_button.click()
                logger.info(f"Account {self.serial_number}: Launch button clicked.")
        except TimeoutException:
            logger.info(f"Account {self.serial_number}: Launch button not found, proceeding.")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while clicking launch button: {str(e)}")
        logger.info(f"Account {self.serial_number}: BLUM STARTED")
        logger.info(f"Search for available games.")
        sleep_time = random.randint(20, 30)
        logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
        time.sleep(sleep_time)
        if not self.switch_to_iframe():
            logger.info(f"Account {self.serial_number}: No iframes found")
            return
        
        try:
            if WebDriverWait(self.driver, 1800).until(lambda driver: EC.text_to_be_present_in_element((By.XPATH, '/html/body/div[1]/div/div[1]/div/div[2]/div/a'), "Invite for")(driver) or EC.text_to_be_present_in_element((By.XPATH, '/html/body/div[1]/div/div[1]/div/div[2]/div/a'), "Пригласить за")(driver)):
                logger.info(f"All game played")                   
                sleep_time = random.randint(10, 20)
                logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                time.sleep(sleep_time)
            else:
                logger.info(f"Waiting for the end of all games")                         
        except TimeoutException:
            logger.info(f"All game played")
            sleep_time = random.randint(10, 20)
            logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while waiting for game completion: {str(e)}")
            
        try:
            username_elements = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "#app > div.index-page.page > div > div.profile-with-balance > div.username"))
            )
            username = ''.join([element.text for element in username_elements])
            logger.info(f"Account {self.serial_number}: Current username: {username}")
        except TimeoutException:
            logger.warning(f"Account {self.serial_number}: Username element not found after game completion.")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while getting username after game completion: {str(e)}")
        
        try:
            daily_reward_button = WebDriverWait(self.driver, 1).until(
                    EC.element_to_be_clickable((By.XPATH, "/html[1]/body[1]/div[1]/div[1]/div[1]/div[1]/div[2]/div[2]/div[3]/button[1]"))
                )
            daily_reward_button.click()
            logger.info(f"Account {self.serial_number}: Daily reward claimed.")
            time.sleep(2)
        except TimeoutException:
            logger.info(f"Account {self.serial_number}: Daily reward has already been claimed or button not found.")         
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while claiming daily reward: {str(e)}")
           
    def check_claim_button(self):
        if not self.switch_to_iframe():
            logger.info(f"Account {self.serial_number}: No iframes found")
            return 0.0
        
        initial_balance = self.check_balance()
        self.process_buttons()
        final_balance = self.check_balance()

        if final_balance is not None and initial_balance == final_balance and not self.is_farming_active():
            logger.warning(f"Account {self.serial_number}: Balance did not change after claiming tokens.")
        
        return final_balance if final_balance is not None else 0.0

    def switch_to_iframe(self):
        try:
            self.driver.switch_to.default_content()
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                self.driver.switch_to.frame(iframes[0])
                return True
        except NoSuchElementException:
            logger.warning(f"Account {self.serial_number}: No iframe found.")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while switching to iframe: {str(e)}")
        return False

    def process_buttons(self):
        parent_selector = "div.kit-fixed-wrapper.has-layout-tabs"

        button_primary_selector = "button.kit-button.is-large.is-primary.is-fill.button"
        button_done_selector = "button.kit-button.is-large.is-drop.is-fill.button.is-done"
        button_secondary_selector = "button.kit-button.is-large.is-secondary.is-fill.is-centered.button.is-active"

        parent_element = self.wait_for_element(By.CSS_SELECTOR, parent_selector)
        
        if parent_element:
            primary_buttons = parent_element.find_elements(By.CSS_SELECTOR, button_primary_selector)
            done_buttons = parent_element.find_elements(By.CSS_SELECTOR, button_done_selector)
            secondary_buttons = parent_element.find_elements(By.CSS_SELECTOR, button_secondary_selector)
            
            for button in primary_buttons:
                self.process_single_button(button)
            for button in done_buttons:
                self.process_single_button(button)
            for button in secondary_buttons:
                self.process_single_button(button)
        else:
            logger.warning(f"Account {self.serial_number}: Parent element not found.")

    def process_single_button(self, button):
        try:
            button_text = self.get_button_text(button)
            amount_elements = button.find_elements(By.CSS_SELECTOR, "div.amount")
            amount_text = amount_elements[0].text if amount_elements else None

            if "Farming" in button_text or "Фарминг" in button_text:
                self.handle_farming(button)
            elif ("Start farming" in button_text or "Начать фарминг" in button_text) and not amount_text:
                self.start_farming(button)
            elif amount_text:
                self.claim_tokens(button, amount_text)
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while processing button: {str(e)}")

    def get_button_text(self, button):
        try:
            return button.find_element(By.CSS_SELECTOR, ".button-label").text
        except NoSuchElementException:
            try:
                return button.find_element(By.CSS_SELECTOR, ".label").text
            except NoSuchElementException:
                logger.warning(f"Account {self.serial_number}: Button text not found.")
                return ""
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while getting button text: {str(e)}")
            return ""

    def handle_farming(self, button):
        logger.info(f"Account {self.serial_number}: Farming is active. The account is currently farming. Checking timer again.")
        try:
            time_left = self.driver.find_element(By.CSS_SELECTOR, "div.time-left").text
            logger.info(f"Account {self.serial_number}: Remaining time to next claim opportunity: {time_left}")
        except NoSuchElementException:
            logger.warning(f"Account {self.serial_number}: Timer not found after detecting farming status.")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while handling farming: {str(e)}")

    def start_farming(self, button):
        try:
            button.click()
            logger.info(f"Account {self.serial_number}: Clicked on 'Start farming'.")
            sleep_time = random.randint(20, 30)
            logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
            time.sleep(sleep_time)
            self.handle_farming(button)
            if not self.is_farming_active():
                logger.warning(f"Account {self.serial_number}: Farming did not start successfully.")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while starting farming: {str(e)}")

    def claim_tokens(self, button, amount_text):
        try:
            sleep_time = random.randint(5, 15)
            logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
            time.sleep(sleep_time)
            logger.info(f"Account {self.serial_number}: Account has {amount_text} claimable tokens. Trying to claim.")
            
            button.click() 
            logger.info(f"Account {self.serial_number}: Click successful. 10s sleep, waiting for button to update to 'Start Farming'...")
            time.sleep(10)
      
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, ".label"))
                )
                start_farming_button = self.wait_for_element(By.CSS_SELECTOR, ".label")
                if start_farming_button:
                    start_farming_button.click() 
                    logger.info(f"Account {self.serial_number}: Second click successful on 'Start farming'")
                    sleep_time = random.randint(5, 15)
                    logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                    time.sleep(sleep_time)
                    self.process_buttons()
                    self.handle_farming(start_farming_button)
                    if not self.is_farming_active():
                        logger.warning(f"Account {self.serial_number}: Farming did not start successfully.")
            except TimeoutException:
                logger.warning(f"Account {self.serial_number}: Failed to find the 'Start Farming' button after claiming tokens.")
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while claiming tokens: {str(e)}")

    def check_balance(self):
        logger.info(f"Account {self.serial_number}: Trying to get total balance")
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                self.driver.switch_to.frame(iframes[0])

            balance_elements = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "div.profile-with-balance .kit-counter-animation.value .el-char-wrapper .el-char"))
            )
            balance = ''.join([element.text for element in balance_elements])
            logger.info(f"Account {self.serial_number}: Current balance: {balance}")
            sleep_time = random.randint(5, 15)
            logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
            time.sleep(sleep_time)
            return float(balance.replace(',', ''))

        except TimeoutException:
            logger.warning(f"Account {self.serial_number}: Failed to find the balance element.")
            return 0.0
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while checking balance: {str(e)}")
            return 0.0

    def wait_for_element(self, by, value, timeout=10):
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        except TimeoutException:
            logger.warning(f"Account {self.serial_number}: Failed to find the element located by {by} with value {value} within {timeout} seconds.")
            return None
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while waiting for element: {str(e)}")
            return None

    def is_farming_active(self):
        try:
            self.driver.find_element(By.CSS_SELECTOR, "div.time-left")
            return True
        except NoSuchElementException:
            return False
        except Exception as e:
            logger.error(f"Account {self.serial_number}: Unexpected error while checking farming status: {str(e)}")
            return False

def read_accounts_from_file():
    try:
        with open('accounts.txt', 'r') as file:
            return [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        logger.error("accounts.txt file not found.")
        return []
    except Exception as e:
        logger.error(f"Unexpected error while reading accounts file: {str(e)}")
        return []

def write_accounts_to_file(accounts):
    try:
        with open('accounts.txt', 'w') as file:
            for account in accounts:
                file.write(f"{account}\n")
    except IOError as e:
        logger.error(f"Failed to write accounts to file: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while writing accounts to file: {str(e)}")

def process_accounts():
    os.system('cls' if os.name == 'nt' else 'clear')
    last_processed_account = None
    last_balance = 0.0
    last_username = None

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        account_balances = []

        accounts = read_accounts_from_file()
        if not accounts:
            logger.error("No accounts to process. Exiting.")
            break
        random.shuffle(accounts)
        write_accounts_to_file(accounts)

        for account in accounts:
            retry_count = 0
            success = False
            balance = 0.0

            while retry_count < 3 and not success:
                bot = TelegramBotAutomation(account)
                try:
                    bot.navigate_to_bot()
                    bot.send_message(TELEGRAM_GROUP_URL)
                    bot.click_link()
                   
                    balance = bot.check_claim_button()
                    username = bot.get_username()
                    logger.info(f"Account {account}: Processing completed successfully.")
                    success = True  
                except Exception as e:
                    logger.warning(f"Account {account}: Error occurred on attempt {retry_count + 1}: {e}")
                    retry_count += 1  
                finally:                    
                    logger.info("-------------END-----------")
                    bot.browser_manager.close_browser()
                    logger.info("-------------END-----------")
                    sleep_time = random.randint(5, 15)
                    logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                    time.sleep(sleep_time)
                
                if retry_count >= 3:
                    logger.warning(f"Account {account}: Failed after 3 attempts.")
                    balance = 0.0

            if not success:
                logger.warning(f"Account {account}: Moving to next account after 3 failed attempts.")
                balance = 0.0        
           
            account_balances.append((account, username, balance))

        retry_accounts = []
        for account, username, balance in account_balances:
            if balance == 0.0:
                retry_accounts.append(account)

        retry_results = []
        for account in retry_accounts:
            retry_count = 0
            success = False
            while retry_count < 3 and not success:
                bot = TelegramBotAutomation(account)
                try:
                    bot.navigate_to_bot()
                    bot.send_message(TELEGRAM_GROUP_URL)
                    bot.click_link()
                    balance = bot.check_claim_button()
                    username = bot.get_username()
                    logger.info(f"Account {account}: Retry processing completed successfully.")
                    success = True
                except Exception as e:
                    logger.warning(f"Account {account}: Retry error on attempt {retry_count + 1}: {e}")
                    retry_count += 1
                finally:
                    logger.info("-------------END-----------")
                    bot.browser_manager.close_browser()
                    logger.info("-------------END-----------")
                    sleep_time = random.randint(5, 15)
                    logger.info(f"{Fore.LIGHTBLACK_EX}Sleeping for {sleep_time} seconds.{Style.RESET_ALL}")
                    time.sleep(sleep_time)
                
                if retry_count >= 3:
                    logger.warning(f"Account {account}: Retry failed after 3 attempts.")
                    balance = 0.0
            retry_results.append((account, username, balance, "Success" if success and balance > 0 else "Error"))

        if account_balances:
            last_processed_account, last_username, last_balance = account_balances[-1]

        table = PrettyTable()
        table.field_names = ["ID", "Username", "Balance"]

        total_balance = 0.0
        for serial_number, username, balance in account_balances:
            row = [serial_number, username if username else 'N/A', balance]
            if balance == 0.0:
                table.add_row([colored(cell, 'red') for cell in row])
            else:
                table.add_row([colored(cell, 'cyan') for cell in row])
            total_balance += balance

        logger.info("\n" + colored(str(table), 'cyan'))

        logger.info(f"Total Balance: {colored(f'{total_balance:,.2f}', 'magenta')}")

        retry_table = PrettyTable()
        retry_table.field_names = ["ID", "Username", "Balance", "Retry Status"]
        for serial_number, username, balance, status in retry_results:
            retry_table.add_row([serial_number, username if username else 'N/A', balance, status])

        logger.info("\n" + colored(str(retry_table), 'yellow'))

        logger.info("All accounts processed. Waiting 8 hours before restarting.")

        for hour in range(8):
            logger.info(f"Waiting... {8 - hour} hours left till restart.")
            time.sleep(60 * 60)  

        account_balances = [(last_processed_account, last_username, last_balance)]
        logger.info("Shuffling accounts for the next cycle.")

 
if __name__ == "__main__":
    try:
        process_accounts()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        sys.exit(1)
