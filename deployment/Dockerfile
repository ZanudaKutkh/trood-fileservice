FROM python:3.8-bullseye

ENV APPDIR=/home/src
ENV PYTHONPATH=$PYTHONPATH:$APPDIR

RUN mkdir -p $APPDIR
WORKDIR $APPDIR

# Установка системных зависимостей
RUN apt-get update -y && \
    apt-get install -y \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    antiword \
    unrtf \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-rus \
    libjpeg-dev \
    swig \
    build-essential \
    libxt-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    gcc \
    cargo \
    libcairo2 \
    libgif-dev \
    ghostscript

COPY ./requirements.txt $APPDIR/
RUN pip install --upgrade pip
RUN pip install -r $APPDIR/requirements.txt

COPY ./file_service $APPDIR/file_service
COPY ./plugins $APPDIR/plugins
COPY ./manage.py $APPDIR/
COPY ./pytest.ini $APPDIR/
COPY ./docs/_static/swagger.yml $APPDIR/static/
COPY ./VERSION $APPDIR/

EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--reload", "--access-logfile", "-", "file_service.wsgi:application"]
