FROM python:3.9.0-alpine3.12

LABEL maintainer="bardin.petr@gmail.com"
LABEL version="0.1"

RUN mkdir /app
WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "main.py"]

