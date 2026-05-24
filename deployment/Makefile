default: run

build:
	@docker-compose build

test:
	@docker-compose exec fileservice pytest

run: build
	@docker-compose up -d

down:
	@docker-compose down

makemigrations:
	@docker-compose exec python manage.py makemigrations

.PHONY: run default build test down