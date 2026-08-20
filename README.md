# Учебный портал (6 класс)

FastAPI + SQLite + Jinja2, без фреймворков на фронте. Контент (уроки/тесты) хранится
как markdown/JSON в `content/` и заливается в БД через `pipeline/load_content.py`.

## Запуск

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python pipeline\load_content.py
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Открыть http://localhost:8000

## Структура

```
content/<subject>/topics.json          # предмет → разделы → темы
content/<subject>/<topic-slug>/lesson.md
content/<subject>/<topic-slug>/quiz.json
app/                                    # FastAPI backend + Jinja2 шаблоны
pipeline/load_content.py                # content/ → portal.db (безопасно перезапускать)
```

## Добавить новую тему

1. Добавь запись темы в `content/<subject>/topics.json` (slug, title, order — в нужный раздел).
2. Создай `content/<subject>/<slug>/lesson.md` — простое объяснение + примеры + мини-практика.
3. Создай `content/<subject>/<slug>/quiz.json` — 8-12 вопросов. Форматы вопросов:
   - `single` — один правильный вариант
   - `multiple` — несколько правильных вариантов (чекбоксы)
   - `dropdown` — выбор из выпадающего списка
   - `fill_blank` — вписать ответ (сравнение без учёта регистра/пробелов; можно указать `accepted: [...]` для нескольких верных написаний)
   - `matching` — соединение пар линиями (`pairs: [{left, right}, ...]`)
4. Прогони `pipeline/load_content.py <subject>` — идемпотентно, безопасно перезапускать.

## Что уже готово

- **Весь 6 класс, три предмета**: 55 тем по русскому языку + 56 тем по математике +
  34 темы по английскому языку, каждая — урок + тест (8-10 вопросов, все 5 форматов:
  single/multiple/dropdown/fill_blank/matching). Русский и математика собраны из
  официального списка lesson.edu.ru (`resh_6klass_temy.json`), английский — из
  `english_6klass_temy.json`; все три сжаты и разбиты заново без служебных пунктов
  (диктанты, работа над ошибками, «обобщение и контроль»), но с плотностью, близкой
  к школьной (у английского топиков меньше — под его реальные 3 ч/нед против 5-6 у
  русского/математики). Уроки английского — таблица лексики (англ-рус) + один
  грамматический пункт, объяснённый по-русски; `matching` в тестах — англ. слово ↔
  русский перевод.
- **Расписание на учебный год** (`/schedule`) — 2026/2027 год, ~166 учебных дней,
  темы русского, математики и английского распределены по дням недели
  (`content/schedule.json`, генерируется `pipeline/build_schedule.py`).
- **Биология, география, история, литература — пока только часы в расписании**,
  без уроков/тестов. Расставлены по фиксированным дням недели на стандартном
  количестве часов в год по 6 классу (базисный учебный план): литература 3 ч/нед
  (~102 ч/год, Пн/Ср/Пт), история 2 ч/нед (~68 ч/год, Вт/Чт), биология и география
  по 1 ч/нед (~34 ч/год каждая, Пн и Ср). В расписании считают урок N/всего, но
  ссылок на уроки нет — контента для них ещё не существует (см. `HOUR_ONLY_SUBJECTS`
  в `pipeline/build_schedule.py`, если нужно поменять дни/часы).
- Прогресс по темам (не начато / пройдено / нужно повторить) и % по предмету.
- Порог прохождения теста — 70%, можно пересдать («Пройти ещё раз»).

## Деплой на VPS (edu.rvnza.ru)

Предполагается сервер, уже настроенный аналогично `threads-automation` (nginx +
Python 3.11+ уже стоят). Шаблоны конфигов лежат в `deploy/`.

### 1. Получить код на сервер

Репозиторий: https://github.com/Ranlaurel/edu-portal. Клонируем на сервере через
git — так же будет работать автодеплой (см. ниже), не только первая заливка:

```bash
ssh user@your-server-ip
sudo mkdir -p /var/www/edu-portal && sudo chown $USER:$USER /var/www/edu-portal
git clone https://github.com/Ranlaurel/edu-portal.git /var/www/edu-portal
```

Замени `user@your-server-ip` на свои реальные логин/IP сервера. Если каталог
`/var/www/edu-portal` уже существует и должен принадлежать конкретному
пользователю (как на threads-automation) — поправь путь и владельца под свою
конвенцию (и не забудь поправить `WorkingDirectory` в `deploy/edu-portal.service`
и `DEPLOY_PATH` в GitHub-секретах на тот же путь).

### 2. На сервере: окружение и БД

```bash
ssh user@your-server-ip
cd /var/www/edu-portal
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python pipeline/load_content.py
.venv/bin/python pipeline/build_schedule.py
```

`portal.db` создаётся заново на сервере из `content/` — не переноси файл БД с
локальной машины, база пересобирается за секунды.

### 3. systemd — держим процесс живым

```bash
sudo cp deploy/edu-portal.service /etc/systemd/system/edu-portal.service
sudo nano /etc/systemd/system/edu-portal.service   # поправь User/Group/WorkingDirectory под свой сервер
sudo systemctl daemon-reload
sudo systemctl enable --now edu-portal
sudo systemctl status edu-portal                   # должно быть active (running)
```

### 4. nginx — reverse proxy на домен

```bash
sudo cp deploy/nginx-edu-portal.conf /etc/nginx/sites-available/edu-portal
sudo ln -s /etc/nginx/sites-available/edu-portal /etc/nginx/sites-enabled/edu-portal
sudo nginx -t && sudo systemctl reload nginx
```

Убедись, что A-запись `edu.rvnza.ru` в DNS указывает на IP сервера (обычно уже
так, если поддомен настраивался вместе с остальными на этом же VPS).

### 5. HTTPS

```bash
sudo certbot --nginx -d edu.rvnza.ru
```

Certbot сам допишет `listen 443 ssl` в конфиг и настроит автообновление
сертификата.

### 6. Проверка

```bash
curl -I https://edu.rvnza.ru
```

Должен вернуться `200 OK`. Дальше открывай `https://edu.rvnza.ru` в браузере.

### Обновление контента вручную (без автодеплоя)

```bash
ssh user@your-server-ip
cd /var/www/edu-portal
git pull
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python pipeline/load_content.py
.venv/bin/python pipeline/build_schedule.py
sudo systemctl restart edu-portal
```

## Автодеплой через GitHub Actions

После пуша в `main` GitHub Actions сам зайдёт на сервер по SSH и прогонит те же
шаги, что выше — код обновится и сервис перезапустится без ручных команд.
Workflow уже в репозитории: `.github/workflows/deploy.yml`.

### 1. Добавить SSH-ключ на сервер

Уже сгенерирован отдельный ключ только для деплоя (не твой личный). Публичный
ключ — допиши его в `~/.ssh/authorized_keys` того пользователя, под которым
будет заходить Actions:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHE9duSuCoUklnLEF3sqFXuvypExdcojtmEssDn9obFu edu-portal-deploy
```

Приватная часть ключа лежит у меня локально в скретчпаде сессии — не в
репозитории. Попроси показать её содержимое, если нужно вставить в GitHub
Secrets (следующий шаг), или сгенерируй свою пару командой
`ssh-keygen -t ed25519 -f deploy_key -N ""` и используй её вместо этой.

### 2. Добавить секреты в GitHub

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Имя | Значение |
|---|---|
| `SSH_HOST` | IP или домен сервера |
| `SSH_USER` | `root` (или твой пользователь для SSH) |
| `SSH_PRIVATE_KEY` | содержимое приватного ключа целиком (`-----BEGIN...-----END...`) |
| `SSH_PORT` | порт SSH, если не 22 (необязательно) |
| `DEPLOY_PATH` | `/var/www/edu-portal` |

### 3. Проверка

Пушни что-нибудь в `main` (или запусти workflow вручную: Actions →
"Deploy to VPS" → Run workflow) и посмотри вкладку Actions — должен пройти
зелёным.

## Дальше

- Наполнить биологию/географию/историю/литературу настоящим контентом (уроки+тесты)
  так же, как русский и математику — тогда их темы тоже станут кликабельными
  в `/schedule`, как сейчас работает для этих двух предметов.
- Пересдача с новым набором вопросов (сейчас — тот же набор).
- Сверка порядка тем с конкретной школьной программой/учебником, если отличается
  от федерального списка (см. `edu-portal-plan.md`, раздел 7).
- Итоговые тесты по разделам (сейчас есть только финальный тест по всему курсу).
