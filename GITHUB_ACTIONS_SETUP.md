# Настройка GitHub Actions для автодеплоя

## 📋 Что нужно сделать

GitHub Actions будет автоматически деплоить на сервер при каждом push в `main`.

---

## 1️⃣ Настроить SSH-ключ на сервере

### На локальной машине (или на сервере):

```bash
# Создать новый SSH-ключ для деплоя
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/edu-portal-deploy

# Это создаст два файла:
# ~/.ssh/edu-portal-deploy (приватный ключ)
# ~/.ssh/edu-portal-deploy.pub (публичный ключ)
```

### На сервере edu.rvnza.ru:

```bash
# Подключиться к серверу
ssh user@edu.rvnza.ru

# Добавить публичный ключ в authorized_keys
nano ~/.ssh/authorized_keys

# Вставить содержимое файла edu-portal-deploy.pub
# Сохранить и выйти (Ctrl+X, Y, Enter)

# Проверить права доступа
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

### Проверить подключение:

```bash
# На локальной машине
ssh -i ~/.ssh/edu-portal-deploy user@edu.rvnza.ru

# Должно подключиться без пароля
```

---

## 2️⃣ Добавить секреты в GitHub

### Открыть настройки репозитория:

1. Перейти на https://github.com/Ranlaurel/edu-portal
2. **Settings** → **Secrets and variables** → **Actions**
3. Нажать **New repository secret**

### Добавить следующие секреты:

#### `DEPLOY_HOST`
```
Значение: edu.rvnza.ru
```
*(или IP-адрес сервера)*

#### `DEPLOY_USER`
```
Значение: username
```
*(имя пользователя на сервере, например: `ubuntu`, `root`, или ваш username)*

#### `DEPLOY_SSH_KEY`
```bash
# Получить содержимое приватного ключа
cat ~/.ssh/edu-portal-deploy

# Скопировать ВЕСЬ вывод, включая:
# -----BEGIN OPENSSH PRIVATE KEY-----
# ...весь ключ...
# -----END OPENSSH PRIVATE KEY-----

# Вставить в поле Value на GitHub
```

#### `DEPLOY_PATH`
```
Значение: /var/www/edu-portal
```
*(полный путь к директории проекта на сервере)*

#### `DEPLOY_PORT` *(опционально)*
```
Значение: 22
```
*(если SSH на нестандартном порту, укажите его)*

---

## 3️⃣ Настроить переменные окружения на сервере

### На сервере edu.rvnza.ru:

```bash
# Открыть файл окружения
nano ~/.bashrc
# или
nano ~/.profile

# Добавить в конец файла:
export EDU_PORTAL_SECRET_KEY="ваш-секретный-ключ-64-символа"
export EDU_PORTAL_PASSWORD="ваш-админ-пароль"
export EDU_PORTAL_LOGIN="admin"

# Сохранить и загрузить
source ~/.bashrc
```

**Сгенерировать SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Для systemd (если используется):

```bash
# Отредактировать unit-файл
sudo nano /etc/systemd/system/edu-portal.service

# Добавить в секцию [Service]:
Environment="EDU_PORTAL_SECRET_KEY=ваш-ключ"
Environment="EDU_PORTAL_PASSWORD=ваш-пароль"
Environment="EDU_PORTAL_LOGIN=admin"

# Перезагрузить конфигурацию
sudo systemctl daemon-reload
sudo systemctl restart edu-portal
```

---

## 4️⃣ Настроить sudo без пароля для restart (опционально)

Если используется `systemctl restart` в workflow:

```bash
# На сервере
sudo visudo

# Добавить в конец:
username ALL=(ALL) NOPASSWD: /bin/systemctl restart edu-portal
username ALL=(ALL) NOPASSWD: /bin/systemctl status edu-portal

# Заменить username на ваше имя пользователя
# Сохранить и выйти
```

**Или убрать `sudo` из workflow** и использовать PM2 вместо systemd.

---

## 5️⃣ Первый деплой

### Вариант A: Push в main (автоматически)

```bash
# На локальной машине
git push origin main

# GitHub Actions автоматически запустит деплой
```

### Вариант B: Ручной запуск

1. Перейти на https://github.com/Ranlaurel/edu-portal/actions
2. Выбрать **Deploy to Production**
3. Нажать **Run workflow** → **Run workflow**

---

## 6️⃣ Проверить статус деплоя

### В GitHub:

1. Перейти на https://github.com/Ranlaurel/edu-portal/actions
2. Открыть последний запущенный workflow
3. Посмотреть логи выполнения

**Успешный деплой выглядит так:**
```
🚀 Starting deployment...
📥 Pulling latest code from GitHub...
🔧 Activating virtual environment...
📦 Installing dependencies...
🗄️ Running database migrations...
✓ Database initialized
📚 Checking content...
✓ Content already loaded (562 topics)
🔒 Setting file permissions...
♻️  Restarting application...
✓ Service restarted via systemd
⏳ Waiting for service to start...
🏥 Running health check...
✅ Deployment successful! Service is responding.

📊 Deployment Summary:
  • Subjects: 15
  • Topics: 562
  • Users: 3

✨ Deployment completed successfully!
```

### На сервере:

```bash
# Проверить логи приложения
sudo journalctl -u edu-portal -n 50

# Или PM2
pm2 logs edu-portal --lines 50

# Проверить что сервис работает
curl http://localhost:8000/login
```

---

## 🔧 Устранение проблем

### Ошибка: "Permission denied (publickey)"

**Решение:**
```bash
# Проверить что ключ добавлен на сервере
ssh user@edu.rvnza.ru
cat ~/.ssh/authorized_keys | grep github-actions

# Проверить права
ls -la ~/.ssh
# authorized_keys должен быть 600
```

### Ошибка: "sudo: no tty present"

**Решение A:** Настроить NOPASSWD для sudo (см. шаг 4)

**Решение B:** Изменить в `.github/workflows/deploy.yml`:
```yaml
# Заменить:
sudo systemctl restart edu-portal

# На:
systemctl --user restart edu-portal
# или
pm2 restart edu-portal
```

### Ошибка: "Database is locked"

**Решение:**
```bash
# На сервере
ps aux | grep python
sudo kill -9 <PID>
sudo systemctl restart edu-portal
```

### Workflow не запускается

**Проверить:**
1. Файл `.github/workflows/deploy.yml` есть в репозитории
2. В GitHub Settings → Actions → General:
   - "Allow all actions and reusable workflows" включено
3. Все секреты добавлены правильно

---

## 📊 Мониторинг деплоев

### Настроить уведомления GitHub:

1. **Settings** → **Notifications**
2. Включить **Actions** notifications
3. Выбрать канал уведомлений (Email / GitHub notifications)

### Просмотр истории деплоев:

https://github.com/Ranlaurel/edu-portal/actions/workflows/deploy.yml

---

## ✅ Чеклист готовности

- [ ] SSH-ключ создан и добавлен на сервер
- [ ] Все секреты добавлены в GitHub:
  - [ ] `DEPLOY_HOST`
  - [ ] `DEPLOY_USER`
  - [ ] `DEPLOY_SSH_KEY`
  - [ ] `DEPLOY_PATH`
- [ ] Переменные окружения настроены на сервере:
  - [ ] `EDU_PORTAL_SECRET_KEY`
  - [ ] `EDU_PORTAL_PASSWORD`
- [ ] sudo настроен (если используется systemd)
- [ ] Workflow файл закоммичен и запушен
- [ ] Первый деплой прошёл успешно

---

## 🎯 Готово!

После настройки каждый push в `main` будет автоматически деплоить на сервер.

**Тестовый коммит:**
```bash
echo "test" >> README.md
git add README.md
git commit -m "Test auto-deploy"
git push origin main

# Проверить в Actions
```
