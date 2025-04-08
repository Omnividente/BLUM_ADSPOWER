// ==UserScript==
// @name         TheOpenCoin Auto Miner
// @namespace    http://tampermonkey.net/
// @version      2.0
// @description  Auto mining script for TheOpenCoin
// @author       You
// @match        https://miniapp.theopencoin.xyz/*
// @grant        none
// ==/UserScript==

(function () {
    "use strict";
  
    let isScriptPaused = false; // Флаг для паузы скрипта
    let isMainLoopRunning = false;
  
    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }
  
    function simulateMouseClick(element) {
      if (!element) return false;
  
      const clickEvents = [
        new MouseEvent("mouseenter", {
          bubbles: true,
          cancelable: true,
          view: window,
        }),
        new MouseEvent("mouseover", {
          bubbles: true,
          cancelable: true,
          view: window,
        }),
        new MouseEvent("mousedown", {
          bubbles: true,
          cancelable: true,
          view: window,
          button: 0,
          buttons: 1,
        }),
        new MouseEvent("mouseup", {
          bubbles: true,
          cancelable: true,
          view: window,
          button: 0,
          buttons: 0,
        }),
        new MouseEvent("click", {
          bubbles: true,
          cancelable: true,
          view: window,
          button: 0,
          buttons: 0,
        }),
      ];
  
      clickEvents.forEach((event) => element.dispatchEvent(event));
      return true;
    }
  
    function clickGotIt() {
      const dialogs = document.querySelectorAll('div[role="dialog"]');
      for (const dialog of dialogs) {
        const titleElement = dialog.querySelector("h2");
        if (titleElement && titleElement.textContent.includes("Mining Started")) {
          const gotItButton = dialog.querySelector("button");
          if (gotItButton && gotItButton.textContent.includes("Got it")) {
            simulateMouseClick(gotItButton);
            return true; // Выходим после успешного выполнения
          }
        }
      }
      console.log("Диалог 'Got it' не найден.");
      return false; // Завершаем выполнение без действия
    }
  
    const solveCaptcha = async () => {
      if (isScriptPaused) {
        console.log("Скрипт на паузе. Прекращаем выполнение.");
        return false; // Прерываем выполнение при активной паузе
      }
  
      console.log("Checking for captcha...");
      let captchaDialog = document.querySelector(
        'div[role="dialog"] p.text-sm.text-muted-foreground'
      );
      if (captchaDialog) {
        const buttons = Array.from(
          captchaDialog.closest('div[role="dialog"]').querySelectorAll("button")
        );
  
        const mineMoreButton = buttons.find((button) =>
          button.textContent.includes("Mine more")
        );
        if (mineMoreButton) {
          console.log(
            "Обнаружена кнопка 'Mine more'. Запускаем clickMineMore..."
          );
          clickMineMore();
          captchaDialog = null; // Устанавливаем captchaDialog как null, чтобы условие if (!captchaDialog) было true
        } else if (
          buttons.find((button) => button.textContent.includes("Got it"))
        ) {
          console.log("Обнаружена кнопка 'Got it'. Запускаем clickGotIt...");
          clickGotIt();
          captchaDialog = null; // Устанавливаем captchaDialog как null, чтобы условие if (!captchaDialog) было true
        } else {
          // Если это не кнопки "Mine more" или "Got it", возвращаем оригинальный captchaDialog
          captchaDialog = document.querySelector(
            'div[role="dialog"] p.text-sm.text-muted-foreground'
          );
        }
      } else {
        console.log("No captcha dialog found");
        return true;
      }
  
      // Проверяем наличие капчи нового образца (canvas)
      const canvas = document.querySelector("canvas");
      if (canvas) {
        console.log(
          "Обнаружена капча нового образца (canvas). Переходим к обработке..."
        );
  
        // Предобработка canvas
        const preprocessCanvas = (canvas) => {
          console.log("Предобработка canvas...");
          const ctx = canvas.getContext("2d", { willReadFrequently: true });
  
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const data = imageData.data;
  
          for (let i = 0; i < data.length; i += 4) {
            const grayscale = (data[i] + data[i + 1] + data[i + 2]) / 3;
            data[i] = data[i + 1] = data[i + 2] = grayscale > 128 ? 255 : 0; // Чёрно-белое изображение
          }
          ctx.putImageData(imageData, 0, 0);
  
          console.log("Предобработка завершена.");
          return canvas; // Возвращаем canvas
        };
        
        // Функция отправки canvas на сервер
        const sendCanvasToServer = async (canvas) => {
          try {
            console.log("Инициализация отправки canvas...");
  
            // Пытаемся извлечь username
            let username = "unknown_user"; // Значение по умолчанию
            try {            
              username = extractUsernameFromLaunchParams() || username;
            } catch (error) {
              console.warn(
                "Не удалось извлечь username. Используется значение по умолчанию:",
                username
              );
            }
            console.log("Username для отправки:", username);
  
            const base64Image = canvas.toDataURL("image/png").split(",")[1];
            console.log(
              "Base64 изображение подготовлено. Длина:",
              base64Image.length
            );
  
            // Отправляем запрос на сервер с username и изображением
            const response = await fetch("http://127.0.0.1:5000/process", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ image: base64Image, username: username }),
            });
  
            if (!response.ok) {
              throw new Error(`Ошибка сервера: ${response.statusText}`);
            }
  
            const result = await response.json();
            console.log("Результат от сервера:", result);
  
            return result;
          } catch (error) {
            console.error("Ошибка при отправке canvas:", error);
            return null; // Возвращаем null в случае ошибки
          }
        };
  
        const preprocessedCanvas = preprocessCanvas(canvas);
        const result = await sendCanvasToServer(preprocessedCanvas);
  
        if (result) {
          if (result.type === "math") {
            console.log(`Математическая капча решена: ${result.result}`);
            await handleCaptchaResult(
              result.result,
              document.querySelector('div[role="dialog"]')
            );
            return true; // Успешная обработка
          } else if (result.type === "stars") {
            console.log(`Капча со звёздами решена: ${result.result}`);
            await handleCaptchaResult(
              result.result,
              document.querySelector('div[role="dialog"]')
            );
            return true; // Успешная обработка
          } else {
            console.log(`Неизвестный тип капчи: ${result.result}`);
            isScriptPaused = true;
            return false; // Неизвестный тип капчи
          }
        } else {
          console.error("Не удалось получить результат с сервера.");
          isScriptPaused = true;
          createPausePopup(
            "Ошибка: сервер не вернул результат. Скрипт поставлен на паузу."
          );
          return false;
        }
      } else {
        // Проверяем наличие капчи старого образца
        if (!captchaDialog) {
          console.log("Капча не найдена.");
          return true; // Капча не найдена
        }
  
        if (isScriptPaused) {
          console.log(
            "Скрипт на паузе. Обработка капчи старого образца прервана."
          );
          return false; // Прерываем выполнение при активной паузе
        }
  
        console.log("Обнаружена капча старого образца.");
        const captchaText = captchaDialog.textContent;
  
        const mathMatch = captchaText.match(/(\d+)\s*\+\s*(\d+)\s*=\s*\?/);
        const stars = captchaDialog.querySelectorAll("svg");
  
        let result = 0;
        if (mathMatch) {
          const num1 = parseInt(mathMatch[1], 10);
          const num2 = parseInt(mathMatch[2], 10);
          result = num1 + num2;
          console.log(
            `Решение математической капчи: ${num1} + ${num2} = ${result}`
          );
        } else if (stars.length > 0) {
          result = stars.length;
          console.log(`Решение капчи со звёздами: ${result} звёзд найдено`);
        } else {
          console.log("Тип капчи не распознан.");
          return false; // Не удалось распознать капчу
        }
  
        if (isScriptPaused) {
          console.log("Скрипт на паузе. Передача результата капчи прервана.");
          return false; // Прерываем выполнение при активной паузе
        }
  
        await handleCaptchaResult(result, captchaDialog);
        if (isScriptPaused) {
          console.log("Скрипт на паузе. Прекращаем выполнение.");
          return false; // Прерываем выполнение при активной паузе
        } else {
          return true; // Успешная обработка
        }
      }
    };
  
    const waitForCaptchaDialogClose = async () => {
      console.log("Ожидаем закрытия окна капчи...");
      const maxAttempts = 10; // Максимальное количество проверок
      const interval = 1000; // Интервал в миллисекундах между проверками
  
      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        let captchaDialog = document.querySelector('div[role="dialog"]');
  
        if (captchaDialog) {
          // Проверяем, есть ли кнопки с текстом "Mine more" или "Got it"
          const hasExcludedButtons = Array.from(
            captchaDialog.querySelectorAll("button")
          ).some(
            (button) =>
              button.textContent.includes("Mine more") ||
              button.textContent.includes("Got it")
          );
  
          if (hasExcludedButtons) {
            console.log(
              "Обнаружено другое окно (Mine more или Got it). Считаем капчу закрытой."
            );
            return true; // Считаем, что окно капчи закрыто, если это другое окно
          }
  
          console.log("Окно капчи всё ещё открыто. Ожидаем...");
        } else {
          console.log("Окно капчи полностью отсутствует. Считаем, что закрыто.");
          return true; // Окно полностью исчезло
        }
  
        // Ждём заданный интервал перед повторной проверкой
        await new Promise((resolve) => setTimeout(resolve, interval));
      }
  
      console.error("Окно капчи не закрылось в течение ожидаемого времени.");
      return false; // Возвращаем false, если окно не закрылось
    };
  
    const handleCaptchaResult = async (result, captchaDialog) => {
      if (isScriptPaused) {
        console.log(
          "Скрипт на паузе. Прекращаем выполнение handleCaptchaResult."
        );
        return false; // Явно возвращаем false для обработки
      }
  
      if (!captchaDialog) {
        console.error("Диалог капчи не найден.");
        isScriptPaused = true;
        createPausePopup(
          "Ошибка: диалог капчи не найден. Скрипт поставлен на паузу."
        );
        return false;
      }
  
      const input = captchaDialog.querySelector(
        'input[placeholder="result"][type="number"]'
      );
      const verifyButton = Array.from(
        captchaDialog.closest('div[role="dialog"]').querySelectorAll("button")
      ).find((button) => button.textContent.includes("Verify"));
  
      if (!input || !verifyButton) {
        console.error("Кнопка верификации или поле ввода не найдены.");
        isScriptPaused = true;
        createPausePopup(
          "Ошибка: кнопка или поле ввода не найдены. Скрипт поставлен на паузу."
        );
        return false;
      }
  
      console.log("Подтверждаем решение капчи...");
  
      if (isScriptPaused) {
        console.log(
          "Скрипт на паузе. Прекращаем выполнение перед вводом значения."
        );
        return false;
      }
  
      input.focus();
  
      // Устанавливаем значение на 1 больше, чтобы инициировать проверку
      input.value = (result + 1).toString();
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
  
      console.log(`Первоначальное значение установлено: ${result + 1}`);
      await new Promise((resolve) => setTimeout(resolve, 2000));
  
      if (isScriptPaused) {
        console.log(
          "Скрипт на паузе. Прекращаем выполнение перед симуляцией ввода."
        );
        return false;
      }
  
      // Симулируем нажатие стрелки вниз для установки точного значения
      await simulateKeyPress(input, "ArrowDown");
      await new Promise((resolve) => setTimeout(resolve, 1000));
  
      if (isScriptPaused) {
        console.log(
          "Скрипт на паузе. Прекращаем выполнение перед проверкой значения."
        );
        return false;
      }
      await sleep(500);
      let finalValue = parseInt(input.value, 10);
      console.log(`Финальное значение после нажатия вниз: ${finalValue}`);
      await sleep(2000);
  
      if (isScriptPaused) {
        console.log(
          "Скрипт на паузе. Прекращаем выполнение перед повторной проверкой."
        );
        return false;
      }
  
      // Проверяем результат
      if (finalValue !== result) {
        console.warn(
          `Несоответствие значения. Ожидалось: ${result}, Получено: ${finalValue}`
        );
        console.log("Повторная настройка значения...");
        input.value = (result + 1).toString();
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
  
        await simulateKeyPress(input, "ArrowDown");
        await new Promise((resolve) => setTimeout(resolve, 1000));
  
        finalValue = parseInt(input.value, 10);
        if (finalValue !== result) {
          console.error(
            `Повторная попытка не удалась. Ожидалось: ${result}, Получено: ${finalValue}`
          );
          isScriptPaused = true;
          createPausePopup("Капча не была решена. Скрипт поставлен на паузу.");
          return false;
        }
      }
  
      if (isScriptPaused) {
        console.log(
          "Скрипт на паузе. Прекращаем выполнение перед кликом по кнопке."
        );
        return false;
      } else {
        await sleep(2000);
        console.log("Финальное значение совпадает с ожидаемым.");
        verifyButton.click();
        await sleep(2000);
        console.log("Капча подтверждена.");
        return true; // Возвращаем true при успешном завершении
      }
    };
  
    // Функция для симуляции нажатий клавиш
    async function simulateKeyPress(input, key) {
      console.log(`Simulating key press: ${key}`);
  
      input.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: key,
          code: key,
          keyCode: key === "ArrowUp" ? 38 : 40,
          which: key === "ArrowUp" ? 38 : 40,
          bubbles: true,
          cancelable: true,
        })
      );
  
      if (key === "ArrowUp") {
        input.stepUp();
      } else {
        input.stepDown();
      }
  
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(
        new KeyboardEvent("keyup", {
          key: key,
          code: key,
          keyCode: key === "ArrowUp" ? 38 : 40,
          which: key === "ArrowUp" ? 38 : 40,
          bubbles: true,
          cancelable: true,
        })
      );
  
      await sleep(100); // Пауза между нажатиями
    }
  
    function clickMineMore() {
      const buttons = document.querySelectorAll("button");
      for (const button of buttons) {
        if (button.textContent.includes("Mine more")) {
          simulateMouseClick(button);
          return true;
        }
      }
      return false;
    }
  
    function clickMine() {
      const mineButton = document.querySelector("button.button_type_default");
      if (
        mineButton &&
        mineButton.textContent.includes("MINE") &&
        !mineButton.disabled
      ) {
        simulateMouseClick(mineButton);
        return true;
      }
      return false;
    }
  
    function createPausePopup(message) {
      const popup = document.createElement("div");
      popup.style.position = "fixed";
      popup.style.top = "5%";
      popup.style.left = "50%";
      popup.style.transform = "translate(-50%, 0)";
      popup.style.padding = "20px";
      popup.style.backgroundColor = "#fff";
      popup.style.border = "2px solid #000";
      popup.style.borderRadius = "10px";
      popup.style.boxShadow = "0 4px 6px rgba(0, 0, 0, 0.1)";
      popup.style.zIndex = "99999";
      popup.style.textAlign = "center";
      popup.style.pointerEvents = "auto";
      popup.style.userSelect = "none";
      popup.style.width = "400px";
  
      popup.innerHTML = `
                    <div class="flex flex-col space-y-1.5 text-center sm:text-left">
                        <h2 id="radix-:attention:" class="text-lg font-semibold leading-none tracking-tight" 
                            style="margin-bottom: 10px; font-size: 18px; color: #000;">
                            Внимание
                        </h2>
                    </div>
                    <p style="margin-bottom: 10px; font-size: 14px; color: #333; line-height: 1.5;">${message}</p>
                    <button id="resumeScriptButton" style="
                        padding: 10px 20px;
                        font-size: 14px;
                        font-weight: bold;
                        text-transform: uppercase;
                        background-color: #fff;
                        color: #000;
                        border: 2px solid #000;
                        border-radius: 5px;
                        cursor: pointer;
                        transition: background-color 0.3s, color 0.3s;
                        z-index: 100000;
                    ">Продолжить</button>
                `;
  
      document.body.appendChild(popup);
  
      // Добавляем событие на кнопку
      const button = document.getElementById("resumeScriptButton");
      button.addEventListener("click", () => {
        popup.remove(); // Убираем всплывающее окно
        isScriptPaused = false; // Снимаем паузу
        console.log("Script resumed.");
      });
  
      // Стилизация эффекта при наведении
      button.addEventListener("mouseout", () => {
        button.style.backgroundColor = "#fff";
        button.style.color = "#000";
      });
      button.addEventListener("mouseover", () => {
        button.style.backgroundColor = "#000";
        button.style.color = "#fff";
      });
    }
  
    const extractUsernameFromLaunchParams = () => {
      const launchParams = sessionStorage.getItem("tapps/launchParams");
      if (!launchParams) {
        console.error("LaunchParams not found in sessionStorage.");
        return null;
      }
  
      console.log("LaunchParams found in sessionStorage:", launchParams);
  
      // Используем URLSearchParams для извлечения параметров
      const params = new URLSearchParams(launchParams);
  
      // Декодируем параметр "user" из tgWebAppData
      const tgWebAppData = params.get("tgWebAppData");
      if (!tgWebAppData) {
        console.error("tgWebAppData not found in LaunchParams.");
        return null;
      }
  
      const dataParams = new URLSearchParams(tgWebAppData);
      const userData = dataParams.get("user");
      if (!userData) {
        console.error("User data not found in tgWebAppData.");
        return null;
      }
  
      // Преобразуем строку JSON в объект
      const user = JSON.parse(decodeURIComponent(userData));
  
      // Извлекаем имя пользователя
      const username = user.username;
      console.log("Username extracted:", username);
  
      return username;
    };
  
    async function mainLoop() {
      if (isScriptPaused) {
        console.log("Скрипт на паузе");
        return;
      }
  
      console.log("Запуск mainLoop...");
  
      if (clickGotIt()) {
        console.log("Обработан диалог 'Got it'.");
        await sleep(1000);
        return;
      }
  
      if (clickMineMore()) {
        await sleep(1000);
        return;
      }
  
      if (await solveCaptcha()) {
        console.log("Капча успешно решена.");
        const captchaClosed = await waitForCaptchaDialogClose();
        if (!captchaClosed) {
          console.error(
            "Не удалось закрыть окно капчи. Останавливаем выполнение."
          );
          isScriptPaused = true;
          createPausePopup("Окно капчи не закрылось. Скрипт поставлен на паузу.");
          return;
        }
        console.log("Капча закрыта, продолжаем...");
      } else {
        console.error("Ошибка решения капчи.");
        isScriptPaused = true;
        return;
      }
  
      if (clickMine()) {
        console.log("Начата добыча.");
        return;
      }
  
      console.log("mainLoop завершён без действий.");
    }
  
    console.log("Starting TheOpenCoin Auto Miner...");
    setInterval(async () => {
      if (!isScriptPaused && !isMainLoopRunning) {
        isMainLoopRunning = true;
        try {
          await mainLoop(); // Ждём завершения mainLoop
        } catch (error) {
          console.error("Ошибка в mainLoop:", error);
        } finally {
          isMainLoopRunning = false; // Сбрасываем флаг после завершения
        }
      }
    }, 5000);
  })();
  