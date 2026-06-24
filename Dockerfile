FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей (убрали проблемный пакет)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование списка библиотек и их установка
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всех файлов проекта в контейнер
COPY . .

# Открытие порта для Streamlit
EXPOSE 8501

# Проверка работоспособности
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Команда запуска дашборда
ENTRYPOINT ["streamlit", "run", "app_climate_analysis.py", "--server.port=8501", "--server.address=0.0.0.0"]
