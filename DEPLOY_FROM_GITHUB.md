# Деплой на edu.rvnza.ru с GitHub

## 📋 Подготовка (один раз)

### 1. Подключиться к серверу
```bash
ssh user@edu.rvnza.ru
```

### 2. Перейти в директорию проекта
```bash
cd /path/to/edu-portal  # Укажите реальный путь
```

---

## 🚀 Деплой новой версии

### Шаг 1: Получить изменения с GitHub
```bash
git fetch origin
git pull origin main
```

**Ожидаемый вывод:**
```
Updating ed16c3a..b22d389
Fast-forward
 534 files changed, 40177 insertions(+), 91 deletions(-)
```

---

### Шаг 2: Установить/обновить зависимости
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

### Шаг 3: Настроить переменные окружения

**Проверить текущие:**
```bash
echo $EDU_PORTAL_SECRET_KEY
echo $EDU_PORTAL_PASSWORD
```

**Если не установлены, создать:**
```bash
# Сгенерировать SECRET_KEY
export EDU_PORTAL_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Установить пароль админа
export EDU_PORTAL_PASSWORD="ваш-безопасный-пароль"

# Логин админа (опционально, по умолчанию "admin")
export EDU_PORTAL_LOGIN="admin"
```

**Сохранить в ~/.bashrc для постоянства:**
```bash
echo 'export EDU_PORTAL_SECRET_KEY="ваш-сгенерированный-ключ"' >> ~/.bashrc
echo 'export EDU_PORTAL_PASSWORD="ваш-пароль"' >> ~/.bashrc
source ~/.bashrc
```

---

### Шаг 4: Загрузить контент в базу данных

**Бэкап текущей базы (если есть):**
```bash
cp portal.db portal.db.backup.$(date +%Y%m%d-%H%M%S)
```

**Загрузить контент для обоих классов:**
```bash
.venv/bin/python pipeline/load_content.py
```

**Ожидаемый вывод:**
```
Loading content for grade 5...
Loading content for grade 6...
✓ Loaded 15 subjects
✓ Loaded 562 topics
✓ Loaded 2 schedules
```

**Проверить данные:**
```bash
.venv/bin/python -c "
from app.db import SessionLocal
from app.models import Subject, Topic, User
db = SessionLocal()
print(f'Subjects: {db.query(Subject).count()}')
print(f'Topics: {db.query(Topic).count()}')
print(f'Users: {db.query(User).count()}')
db.close()
"
```

**Ожидаемый результат:**
```
Subjects: 15
Topics: 562
Users: 3
```

---

### Шаг 5: Проверить права доступа
```bash
chmod 600 portal.db
chmod 700 .venv
```

---

### Шаг 6: Перезапустить приложение

**Вариант A: systemd**
```bash
sudo systemctl restart edu-portal
sudo systemctl status edu-portal
```

**Вариант B: PM2**
```bash
pm2 restart edu-portal
pm2 logs edu-portal --lines 50
```

**Вариант C: Manual uvicorn**
```bash
# Остановить старый процесс
pkill -f "uvicorn app.main:app"

# Запустить новый
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```

---

## ✅ Проверка деплоя

### 1. Проверить, что сервер запустился
```bash
curl http://localhost:8000/login
```
**Ожидается:** HTML-страница логина (статус 200)

### 2. Проверить логи
```bash
# systemd
journalctl -u edu-portal -n 50

# PM2
pm2 logs edu-portal --lines 50

# Manual
tail -f app.log
```

### 3. Открыть в браузере
Перейти на **https://edu.rvnza.ru**

---

## 🧪 Тестирование после деплоя

### Тест 1: Логин админа
1. Открыть https://edu.rvnza.ru/login
2. Ввести логин: `admin`
3. Ввести пароль: ваш `EDU_PORTAL_PASSWORD`
4. ✅ Должен перенаправить на страницу выбора класса

### Тест 2: Логин Ranlaurel4
1. Логин: `Ranlaurel4`
2. Пароль: `елисей2018`
3. ✅ В навигации должно показать: **Елисей С.**
4. ✅ Дашборд должен показывать прогресс (~18 тем)

### Тест 3: Логин Shvedko1
1. Логин: `Shvedko1`
2. Пароль: `анжелика2017`
3. ✅ В навигации должно показать: **Анжелика Ш.**
4. ✅ Дашборд должен показывать прогресс (~12 тем)

### Тест 4: Выбор класса
1. Выбрать **5 класс**
2. ✅ В списке предметов должно быть 7 предметов:
   - Биология
   - Английский язык
   - География
   - История Древнего мира
   - Литература
   - Математика
   - Русский язык
3. Переключиться на **6 класс**
4. ✅ В списке предметов должно быть 8 предметов

### Тест 5: Расписание
1. Перейти на `/schedule`
2. ✅ Должно показывать 166 дней
3. ✅ На мобильном (сузить окно) расписание скроллится горизонтально

### Тест 6: Консоль браузера
1. Открыть DevTools (F12)
2. ✅ Не должно быть красных ошибок в Console

---

## 🐛 Решение проблем

### Проблема: "Database is locked"
```bash
ps aux | grep python
kill -9 <PID>
sudo systemctl restart edu-portal
```

### Проблема: "Неверный логин или пароль" для админа
```bash
# Проверить переменные окружения
echo $EDU_PORTAL_PASSWORD

# Если не установлен, установить и перезапустить
export EDU_PORTAL_PASSWORD="новый-пароль"
sudo systemctl restart edu-portal
```

### Проблема: Пустой дашборд у пользователей
```bash
# Проверить, что прогресс загружен
.venv/bin/python -c "
from app.db import SessionLocal
from app.models import UserProgress
db = SessionLocal()
print(f'Progress records: {db.query(UserProgress).count()}')
db.close()
"

# Если 0, создать тестовый прогресс
.venv/bin/python scripts/create_test_progress.py
sudo systemctl restart edu-portal
```

### Проблема: Имена не отображаются в навигации
```bash
# Проверить миграцию
.venv/bin/python -c "
from app.db import SessionLocal, engine
from sqlalchemy import text
db = SessionLocal()
cols = [r[1] for r in db.execute(text('PRAGMA table_info(users)'))]
print('Columns:', cols)
print('display_name exists:', 'display_name' in cols)
db.close()
"

# Если display_name отсутствует
.venv/bin/python -c "
from app.db import SessionLocal, engine
from sqlalchemy import text
db = SessionLocal()
db.execute(text('ALTER TABLE users ADD COLUMN display_name VARCHAR'))
db.commit()
db.close()
print('Migration applied')
"
sudo systemctl restart edu-portal
```

### Проблема: Старый CSS в браузере
```bash
# CSS уже имеет версионирование (?v=2)
# Просто очистить кеш браузера: Ctrl+Shift+R
```

---

## 📊 Мониторинг

### Проверить размер базы данных
```bash
du -h portal.db
# Должно быть ~15-20 MB с полным контентом
```

### Проверить использование CPU/Memory
```bash
top -p $(pgrep -f "uvicorn app.main:app")
```

### Проверить открытые порты
```bash
netstat -tulpn | grep 8000
# Должен слушать 0.0.0.0:8000
```

---

## 🔄 Откат (если что-то пошло не так)

### Вариант 1: Откатить код
```bash
git log --oneline -5
git reset --hard ed16c3a  # предыдущий коммит
sudo systemctl restart edu-portal
```

### Вариант 2: Восстановить базу данных
```bash
ls portal.db.backup.*
cp portal.db.backup.YYYYMMDD-HHMMSS portal.db
sudo systemctl restart edu-portal
```

---

## 📝 Что изменилось в этом деплое

**Коммиты:**
- `c3b284d`: Multi-user support + grade separation
- `b22d389`: Documentation

**Новые файлы:**
- 515 контентных файлов для 5 класса
- 2 расписания (schedule-5.json, schedule-6.json)
- Скрипты: add_user.py, create_test_progress.py
- Тесты: tests/test_core.py

**Изменённые таблицы:**
- `users`: добавлена колонка `display_name`
- `user_progress`: добавлен `ForeignKey` на `users.id`
- `attempts`: добавлен `ForeignKey` на `users.id`

**Пользователи:**
- admin (из ENV)
- Ranlaurel4 (Елисей С.)
- Shvedko1 (Анжелика Ш.)

---

## ✅ Критерии успешного деплоя

- [ ] Код успешно загружен с GitHub
- [ ] База данных содержит 15 предметов и 562 темы
- [ ] Все 3 пользователя могут войти
- [ ] Имена отображаются в навигации
- [ ] Оба класса (5 и 6) работают
- [ ] Дашборды показывают корректный прогресс
- [ ] Нет ошибок в логах
- [ ] Нет ошибок в консоли браузера
- [ ] Мобильная версия работает корректно

---

## 📞 Контакты

При возникновении проблем проверьте:
1. Логи сервера
2. `DEPLOYMENT.md` — детальный чеклист
3. `CODE_REVIEW.md` — технические детали

**GitHub репозиторий:** https://github.com/Ranlaurel/edu-portal
