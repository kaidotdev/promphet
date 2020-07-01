# syntax=docker/dockerfile:experimental

FROM python:3.8.2-alpine3.11

ENV deps "musl-dev gcc g++ freetype-dev"

RUN apk update && apk upgrade

RUN apk add --no-cache $deps

COPY requirements.txt /build/requirements.txt

RUN pip install -r /build/requirements.txt

COPY app.py /opt/promphet/app.py

RUN echo 'promphet:x:60000:60000::/nonexistent:/usr/sbin/nologin' >> /etc/passwd
RUN echo 'promphet:x:60000:' >> /etc/group
RUN chown -R promphet:promphet /opt/promphet
USER promphet

ENTRYPOINT ["python", "/opt/promphet/app.py"]
