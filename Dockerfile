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
    && apk del \
    build-base \
    freetype-dev \
    fribidi-dev \
    lcms2-dev \
    tcl-dev \
    tk-dev

COPY . /

VOLUME [ "/tmp" ]

EXPOSE 80

WORKDIR /

ENTRYPOINT [ "python", "api.py" ]