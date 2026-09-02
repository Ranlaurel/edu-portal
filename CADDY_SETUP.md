# Настройка Caddy для edu.rvnza.ru

Приложение работает на `localhost:8000`, но недоступно через HTTPS из-за отсутствия конфигурации в Caddy.

## Решение

Добавьте в `/etc/caddy/Caddyfile`:

```
edu.rvnza.ru {
    reverse_proxy localhost:8000
    encode gzip
}
```

Затем перезагрузите Caddy:

```bash
sudo systemctl reload caddy
```

## Проверка

```bash
curl https://edu.rvnza.ru/login
```

Должен вернуть HTML страницы логина без навигации.
