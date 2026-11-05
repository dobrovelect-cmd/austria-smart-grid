FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install the Python dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Fail the image build early if the dataframe/Arrow stack is incompatible.
RUN python -c "import numpy, pandas, pyarrow, streamlit; print('Dependency check:', 'numpy', numpy.__version__, 'pandas', pandas.__version__, 'pyarrow', pyarrow.__version__, 'streamlit', streamlit.__version__)"

# The dashboard uses the committed CSV snapshot and does not fetch data at startup.
COPY app_climate_analysis.py ./
COPY substations_climate_base.csv ./

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)" || exit 1

CMD ["streamlit", "run", "app_climate_analysis.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
