FROM python:3.8.10-buster

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

CMD python bcncita/cita.py

