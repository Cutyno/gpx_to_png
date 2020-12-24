FROM python:alpine

RUN apk add \
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
    && pip install \
    pyyaml \
    gpxpy \
    pillow \
    requests \
    flask

COPY . /

VOLUME [ "/tmp" ]

EXPOSE 80

WORKDIR /

ENTRYPOINT [ "python", "api.py" ]