FROM registry.redhat.io/ubi8/python-311

WORKDIR /app
COPY . /app

USER root

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir uvicorn -r requirements.txt

USER 1001

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=8000"]
