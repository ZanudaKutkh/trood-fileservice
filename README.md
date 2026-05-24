
Quickstart
----------

Download and start TroodFiles service container:

```bash
    docker pull registry.tools.trood.ru/files:dev
    docker run -d -p 127.0.0.1:8000:8000/tcp \
        --env DJANGO_CONFIGURATION=Development \
        --env AUTH_TYPE=NONE \
        --env DATABASE_URL=sqlite://./db.sqlite3 \
        --name=fileservice registry.tools.trood.ru/files:dev
```

Initiate database structure for created container:

```bash
    docker exec fileservice python manage.py migrate
```

Upload your first File:

```bash
    curl -X POST 'http://127.0.0.1:8000/api/v1.0/files/' \
        -F 'name=My test file' \
        -F 'file=@./test.jpg'
```

Check other API methods on documentation:

```bash
    open http://127.0.0.1:8000/swagger/
```

Environment variables
=====================

General settings
----------------

DATABASE_URL

    Service database connection URL


AUTHENTICATION_TYPE

    Authentication type can be ``NONE`` or ``TROOD``


SERVICE_DOMAIN

    Service identification used in TroodCore ecosystem, default ``FILESERVICE``


SERVICE_AUTH_SECRET

    Random generated string for system token authentication purposes, ``please keep in secret``


FILES_BASE_URL

    Absolute base URL for files links


LANGUAGE_CODE

    Default service language


Debug settings
--------------

DJANGO_CONFIGURATION

    Service mode, cab be ``Production`` or ``Development``.
    ``Development`` mode has additional features enabled:
    - Swagger endpoint at  ``/swagger/``
    

ENABLE_RAVEN

    Boolean flag for ``Sentry`` logging enabled ``False`` by default
    

RAVEN_CONFIG_DSN

    Sentry project DSN URL to log events to
    

RAVEN_CONFIG_RELEASE

    String tag for identify events sent into ``Sentry`` log
    