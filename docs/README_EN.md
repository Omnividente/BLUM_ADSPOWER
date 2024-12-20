
# Telegram Bot Automation for BLUM

This bot is a fork of the repository [Marcelkoo](https://github.com/Marcelkoo/blum-adspower-clicker).

The script automatically launches browsers via AdsPower, plays games, checks in, and collects bonuses.

![Example of bot usage](https://github.com/user-attachments/assets/47cb404e-f8f9-4833-bb70-f7d640c160d7)

## Table of Contents
- [Features](#features)
- [Required Extension](#required-extension)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Support](#support)

## Features
- Automatic browser launches via AdsPower.
- Game actions: check-ins, game launches, and bonus collection.
- Supports multiple accounts and flexible data sources (settings.txt, accounts.txt, API).
- Script updates and automatic update handling.

## Required Extension

***You must install an extension in AdsPower for the bot to work.***

1. Go to AdsPower: `Extensions -> Upload Extensions`.
2. Select the `BLUM-UNLOCKER` archive from the script folder.
3. Install the extension.

---

## Installation

1. Ensure the account is logged into [web.telegram.org](https://web.telegram.org/).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuration

| **Setting**             | **Description**                                                                                                        | **Example**                                     |
|-------------------------|-------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------|
| **TELEGRAM_GROUP_URL**  | Link to your channel or chat where the bot will look for your referral link to start.                                   | `https://t.me/CryptoProjects_sbt`              |
| **BOT_LINK**            | Referral link.                                                                                                         | `https://t.me/blum/app?startapp=ref_example`    |
| **MAX_GAMES**           | Maximum number of games per session (0 - disabled, empty value plays all available games).                             | `10`                                            |
| **ACCOUNTS**            | Account numbers to process (list of numbers and ranges).                                                              | `1,2,5-7`                                       |
| **REPOSITORY_URL**      | Repository URL for update checking.                                                                                    | `https://github.com/Omnividente/blum_adspower` |
| **UPDATE_INTERVAL**     | Update check interval in seconds.                                                                                      | `10800`                                         |
| **AUTO_UPDATE**         | (true/false) Enable or disable automatic updates.                                                                      | `true`                                          |
| **FILES_TO_UPDATE**     | List of files to check for updates. Defaults to `remote_files_for_update` in the repository.                           | `main.py, utils.py`                             |

---

## Usage

Run the script:
```bash
cd path/to/script
python main.py
```

Run options:
```
usage: main.py [-h] [--debug] [--account ACCOUNT] [--visible {0,1}]
Run the script with optional debug logging.
options:
  -h, --help         Show this help message and exit
  --debug            Enable debug logging
  --account ACCOUNT  Force processing a specific account
  --visible {0,1}    Set visible mode (1 for visible, 0 for headless)
```

---

## Support

For any questions or issues, contact [here](https://t.me/cryptoprojectssbt).

## Working with Accounts

The script processes accounts from three sources in the following order of priority:

1. **`accounts` parameter in the `settings.txt` file:**
   - Format: a list of accounts separated by commas, with support for ranges.
   - Example: `accounts=1, 2, 5-7, 10`.

2. **`accounts.txt` file:**
   - One account per line.
   - Used if the `accounts` parameter is missing or empty.

3. **Profiles from the local AdsPower API:**
   - Used if both of the above sources are missing or empty.
   - Processes all available profiles.
