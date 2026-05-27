# Инструкция по запуску

## Подготовка и установка зависимостей
```bash
# Установка необходимых библиотек
pip install -r requirements.txt

# Инициализация локального удостоверяющего центра в системе
mkcert -install

# Создание серверных сертификатов
mkcert localhost 127.0.0.1

# Выпуск клиентского сертификата для Сервиса А
mkcert -client -cert-file client-cert.pem -key-file client-key.pem client@localhost

# Копирование корневого сертификата для Сервиса Б
cp "$(mkcert -CAROOT)/rootCA.pem" ./rootCA.pem
```

## Создание файла конфигурации
Создать файл .env в корне проекта и прописать ключи:
```bash
VK_CLIENT_ID=ваш_ID_приложения
VK_CLIENT_SECRET=ваш_секретный_ключ
SECRET_KEY=super_secret_string_12345

```
## Одновременный запуск сервисов
Терминал 1: Сервис Б (Data API)
```bash
cd services
uvicorn main_api:app --reload --port 8001 --ssl-keyfile ../localhost+1-key.pem --ssl-certfile ../localhost+1.pem --ssl-ca-certs ../rootCA.pem --ssl-cert-reqs 2
```
Терминал 2: Сервис А (Gateway)
```bash
sudo uvicorn main:app --reload --port 443 --ssl-keyfile localhost+1-key.pem --ssl-certfile localhost+1.pem
```