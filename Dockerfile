# Базовый образ
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

# Установка зависимостей
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копирование исходных файлов в контейнер
COPY ./ /app

# Открытие портов
EXPOSE 8023

# Запуск сервера
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
