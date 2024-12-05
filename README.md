Данный бот является форком репозиатория [Marcelkoo](https://github.com/Marcelkoo/blum-adspower-clicker).

# Автоматизация Телеграм Бота для BLUM

Этот скрипт автоматически запускает браузеры через Adspower и раз в 8 часов проходит по всем аккаунтам BLUM, проверяет баланс и нажимает на кнопку для старта нового фарма.

![image](https://github.com/Marcelkoo/blum-adspower-clicker/assets/107651246/89f3a2b0-8bc6-4108-b237-20ca09ba4066)

## Содержание

- [Обязательное расширение](#обязательное-расширение)
- [Что нужно для работы](#что-нужно-для-работы)
- [Установка](#установка)
- [Настройка](#настройка)
- [Использование](#использование)
- [Поддержка](#поддержка)

## Обязательное расширение

***Чтобы у вас работал софт, вам нужно установить расширение в AdsPower.*** 
В папке с софтом есть архив BLUM-UNLOCKER - это и есть само расширение. Нам надо его поставить в адс. Переходим в AdsPower:
1. Extensions -> Upload Extensions
2. Upload File -> Installation package: Upload Extension (Выбираем скачанный архив BLUM-UNLOCKER, указываем любое название для Extension Name и нажимаем OK).
3. Profit, теперь блюм можно открывать с пк в веб версии тг.

## Что нужно для работы
- ***ОЧЕНЬ ВАЖНО:*** Скачайте и установите расширение в Adspower. Если у вас есть Requestly, оно не подойдет, т.к. блокирует переход на новую вкладку. blum_unlocker_extension папка должна быть внутри папки с main.py.
- Установленный браузер Adspower.
- Вход в веб-версию Телеграма в Adspower ([https://web.telegram.org/](https://web.telegram.org/)).
- **Важно:** Первый вход в BLUM по реферальной ссылке должен быть выполнен вручную. Также можно прокликать бонусы (подписка на канал, YouTube и т.д.), так как бот эти действия не выполняет.
--------
- Моя  реферальная ссылка для BLUM: [https://t.me/blum/app?startapp=ref_vNDGLmgnYL](https://t.me/blum/app?startapp=ref_vNDGLmgnYL)
- Моя реферальная ссылка для Adspower: [https://share.adspower.net/omnividente](https://share.adspower.net/omnividente) и купон код omnividente для -5% скидки

## Установка

1. Заполните файл `accounts.txt` серийными номерами аккаунтов Adspower. Каждый серийный номер должен быть на отдельной строке. Повторяю, аккаунт обязательно должен быть залогинен в web.telegram.org

![image](https://github.com/Marcelkoo/blum-adspower-clicker/assets/107651246/262d4387-f298-4c95-b4f7-1c96f6949b34)

2. Установите необходимые зависимости:
    ```
    pip install -r requirements.txt
    ```
## Настройка
    TELEGRAM_GROUP_URL=
    BOT_LINK=
    MAX_GAMES=
(Settings.txt)

TELEGRAM_GROUP_URL= Ссылка на ваш канал или чат, где бот будет искать вашу реферальную ссылку для запуска

BOT_LINK= Реферальная ссылка

MAX_GAMES= Максимальное количество игр за один проход

## Использование

1. Запустите скрипт:
    ```
    cd путь в папку со скриптом
    python main.py
    ```

## Поддержка

По всем вопросам и ошибкам пишите [сюда](https://t.me/cryptoprojectssbt).
