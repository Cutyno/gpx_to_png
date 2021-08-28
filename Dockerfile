FROM python:alpine

RUN apk --no-cache add \
    build-base \
    freetype-dev \
    fribidi-dev \
    harfbuzz-dev \
    jpeg-dev \
    lcms2-dev \
    openjpeg-dev \
    tcl-dev \
    tiff-dev \
    tk-dev \
    zlib-dev \
    && pip install --no-cache-dir \
    pyyaml \
    gpxpy \
    pillow \
    requests \
    flask \
    uwsgi \
    && apk del \
    build-base \
    fribidi-dev \
    lcms2-dev \
    tcl-dev \
    tk-dev

# RUN adduser -u 1000 --disabled-password --no-create-home www-data www-data

# USER www-data:www-data

COPY . /

VOLUME /tmp /metrics

EXPOSE 80

ENTRYPOINT ./start_service.sh