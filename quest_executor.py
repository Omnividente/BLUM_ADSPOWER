import json
import time
from selenium.webdriver.common.by import By
from utils import setup_logger, is_debug_enabled

logger = setup_logger()  # Используем логгер

class QuestExecutor:
    def __init__(self, driver, account):
        self.driver = driver
        self.short_account_id = f"#{account}"
        self.token = None
        self.cached_answers = None
        self.cached_tasks = None
        self.last_task_fetch_time = 0

    def make_request(self, url, method="GET", headers=None, body=None):
        try:
            return self.driver.execute_script(
                """
                const url = arguments[0];
                const method = arguments[1];
                const headers = arguments[2];
                const body = arguments[3];
                return fetch(url, {
                    method: method,
                    headers: headers,
                    body: body ? JSON.stringify(body) : null,
                }).then(res => res.json());
                """,
                url, method, headers or {}, body
            )
        except Exception as e:
            logger.error(f"Error making {method} request to {url}: {e}")
            raise

    def authorize(self):
        logger.debug(f"{self.short_account_id}: Starting authorization process...")
        init_params = self.driver.execute_script(
            "return sessionStorage.getItem('__telegram__initParams');"
        )
        if not init_params:
            raise Exception("InitParams not found in sessionStorage.")
        
        init_data = json.loads(init_params)
        tg_web_app_data = init_data.get("tgWebAppData")
        if not tg_web_app_data:
            raise Exception("tgWebAppData not found in InitParams.")

        auth_url = "https://user-domain.blum.codes/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP"
        payload = {"query": tg_web_app_data}
        response = self.make_request(auth_url, method="POST", headers={"Content-Type": "application/json"}, body=payload)

        self.token = response.get("token", {}).get("access")
        if not self.token:
            raise Exception("Authorization failed. Token not found.")
        
        logger.debug(f"{self.short_account_id}: Authorization successful.")

    def fetch_tasks(self, force_update=False):
        current_time = time.time()
        if not force_update and self.cached_tasks and (current_time - self.last_task_fetch_time) < 10:
            return self.cached_tasks

        tasks_url = "https://earn-domain.blum.codes/api/v1/tasks"
        headers = {"Authorization": f"Bearer {self.token}"}
        tasks = self.make_request(tasks_url, headers=headers)        
        self.cached_tasks = tasks
        self.last_task_fetch_time = current_time
        return tasks

    def fetch_answers(self):
        """
        Загружает ответы из внешнего JSON.
        """
        logger.debug(f"{self.short_account_id}: Fetching answers from external JSON file...")
        answer_url = f"https://omnividente.github.io/QUIZ/answer.json?timestamp={int(time.time())}"
        headers = {"User-Agent": "Marin Kitagawa"}

        try:
            answers = self.make_request(answer_url, headers=headers)
            if not answers:
                raise Exception("Failed to fetch answers. Response is empty.")
            self.cached_answers = answers
            logger.debug(f"{self.short_account_id}: Answers successfully fetched and cached.")
        except Exception as e:
            logger.error(f"{self.short_account_id}: Error while fetching answers: {e}")
            raise

    def extract_tasks(self, data):
        """
        Итеративно извлекает все задачи из данных, включая вложенные структуры.
        """
        result = []
        stack = data if isinstance(data, list) else [data]
        seen_ids = set()

        while stack:
            item = stack.pop()

            # Проверка уникальности задачи
            task_id = item.get("id")
            if task_id and task_id not in seen_ids:
                seen_ids.add(task_id)

                # Исключаем задачи со статусом FINISHED
                if item.get("status") != "FINISHED":
                    # Обрабатываем задачи с нужным статусом и типом
                    if item.get("type") in ["PROGRESS_TARGET", "ONCHAIN_TRANSACTION", "GROUP", "INTERNAL"]:
                        if item.get("status") == "READY_TO_CLAIM":
                            result.append(item)
                    else:
                        result.append(item)

            # Добавляем вложенные задачи из известных ключей
            for key in ["tasks", "subSections", "subTasks"]:
                if key in item and isinstance(item[key], list):
                    stack.extend(item[key])

            # Проверяем любые вложенные структуры
            for value in item.values():
                if isinstance(value, list) and all(isinstance(sub_item, dict) for sub_item in value):
                    stack.extend(value)

        return result




    def wait_for_task_status(self, task_id, expected_status, timeout=60, interval=5):
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_status = self.get_task_status(task_id)
            if current_status in expected_status:
                return current_status
            time.sleep(interval)
        return None

    def get_task_status(self, task_id):
        tasks = self.fetch_tasks(force_update=True)
        all_tasks = self.extract_tasks(tasks)        
        for task in all_tasks:
            if task.get("id") == task_id:
                return task.get("status")
        return None

    def process_task_by_status(self, task):
        task_title = task.get("title", "Unnamed Task")
        task_id = task.get("id", "Unknown ID")
        status = task.get("status")

        logger.debug(f"{self.short_account_id}: Processing task '{task_title}' (ID: {task_id}, Status: {status})")

        if status == "NOT_STARTED":
            logger.info(f"{self.short_account_id}: Starting task '{task_title}'.")
            new_status = self.start_task(task)
            logger.debug(f"{self.short_account_id}: Task '{task_title}' started, new status: {new_status}.")
        elif status == "READY_FOR_VERIFY":
            logger.info(f"{self.short_account_id}: Verifying task '{task_title}'.")
            new_status = self.verify_task(task)
            logger.debug(f"{self.short_account_id}: Task '{task_title}' verified, new status: {new_status}.")
        elif status == "READY_FOR_CLAIM":
            logger.info(f"{self.short_account_id}: Claiming task '{task_title}'.")
            new_status = self.claim_task(task)
            logger.debug(f"{self.short_account_id}: Task '{task_title}' claimed, new status: {new_status}.")
        else:
            logger.debug(f"{self.short_account_id}: Task '{task_title}' has an unexpected status: {status}")


    def start_task(self, task):
        task_id = task.get("id")
        start_url = f"https://earn-domain.blum.codes/api/v1/tasks/{task_id}/start"
        response = self.make_request(start_url, method="POST", headers={"Authorization": f"Bearer {self.token}"})
        return response.get("status")

    def verify_task(self, task):
        task_id = task.get("id")
        verify_url = f"https://earn-domain.blum.codes/api/v1/tasks/{task_id}/validate"
        keyword = self.cached_answers.get(task_id)

        if not keyword:
            logger.warning(f"{self.short_account_id}: No keyword found for task {task.get('title', 'Unnamed Task')}. Skipping verification.")
            return

        logger.info(f"{self.short_account_id}: Verifying task '{task.get('title')}' with keyword: '{keyword}'")
        response = self.make_request(verify_url, method="POST", headers={
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }, body={"keyword": keyword})
        return response.get("status")

    def claim_task(self, task):
        task_id = task.get("id")
        task_title = task.get("title", "Unnamed Task")
        claim_url = f"https://earn-domain.blum.codes/api/v1/tasks/{task_id}/claim"
        response = self.make_request(claim_url, method="POST", headers={"Authorization": f"Bearer {self.token}"})
        status = response.get("status")
        if status == "FINISHED":
            logger.info(f"{self.short_account_id}: Successfully claimed task '{task_title}'.")
        return status

    def process_tasks(self):
        tasks = self.fetch_tasks()
        all_tasks = self.extract_tasks(tasks)
        for task in all_tasks:
            self.process_task_by_status(task)

        # Повторная обработка задач с нужными статусами
        self.process_ready_for_claim()
        if self.process_ready_for_verify():
            self.process_ready_for_claim()  # Проверяем READY_FOR_CLAIM после VERIFY

    def process_ready_for_claim(self):
        logger.debug(f"{self.short_account_id}: Checking for tasks READY_FOR_CLAIM...")
        tasks = self.fetch_tasks()
        all_tasks = self.extract_tasks(tasks)
        for task in all_tasks:
            if task.get("status") == "READY_FOR_CLAIM":
                self.claim_task(task)

    def process_ready_for_verify(self):
        logger.debug(f"{self.short_account_id}: Checking for tasks READY_FOR_VERIFY...")
        tasks = self.fetch_tasks()
        all_tasks = self.extract_tasks(tasks)
        any_verified = False
        for task in all_tasks:
            if task.get("status") == "READY_FOR_VERIFY":
                self.verify_task(task)
                any_verified = True
        return any_verified

    def execute_all_tasks(self):
        try:
            self.authorize()
            self.fetch_answers()
            self.process_tasks()
        except Exception as e:
            logger.error(f"{self.short_account_id}: An error occurred: {e}")
