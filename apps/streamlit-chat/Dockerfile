FROM python:3.11

RUN apt update && apt install --yes netcat-openbsd

ADD requirements.txt /tmp

RUN pip install -r /tmp/requirements.txt