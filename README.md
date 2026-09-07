# «Краски осени» — регистрация участников

Django-сайт регистрации на семейный праздник 19 сентября. Публично показываются заполненность и составы игровых команд, чтобы участники могли записываться к друзьям и знакомым.

## Возможности

- три взаимоисключающие категории: участник «Большой игры», болельщик и конкурс «Счастье в пирогах»;
- 10 игровых команд, максимум 10 активных участников в каждой;
- контактные поля исходной Google-формы: ФИО, предприятие/подразделение и телефон;
- сведения о сопровождающем взрослом или детях;
- для игровой категории: команда, взрослый/ребёнок и возраст ребёнка;
- серверная проверка возраста: детская категория — младше 14 лет;
- защита от регистрации в заполненную команду;
- адаптивная публичная страница с актуальными составами;
- панель модератора `/moderator/`: составы, статистика, отмена и восстановление;
- панель администратора `/admin/`: полный CRUD команд, регистраций и пользователей;
- CSRF, защищённая авторизация и production-настройки через окружение.

## Локальный запуск

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Открыть локально: `http://127.0.0.1:8000/`.

Рабочая публикация: `https://gofaraway.mooo.com/autumn/`.

## Роли

1. Создайте администратора через `createsuperuser`.
2. В `/admin/auth/user/add/` создайте модератора.
3. В карточке пользователя включите `Статус персонала` (`is_staff`). Суперпользователя не включайте.
4. Модератор входит через `/login/` и работает в `/moderator/`.

## Production

Задайте переменные из `.env.example`, затем:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8010
```

Nginx должен проксировать выбранный домен на `127.0.0.1:8010`. Секреты и учётные данные в репозиторий не добавляются.

## Проверки

```bash
.venv/bin/python manage.py test
DJANGO_DEBUG=0 DJANGO_SECRET_KEY=test-secret-change-me DJANGO_ALLOWED_HOSTS=example.org .venv/bin/python manage.py check --deploy
```

Фото: SimonP, «Confederation Park autumn», Wikimedia Commons.
