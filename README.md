# Клиент для подпольного чата

Баба Зина ведёт двойную жизнь. Днём она печёт пирожки, гуляет с внуками и вяжет на спицах, а ночью – виртуозно строит в Майнкрафт фермы и курятники. Детство в деревне – это вам не кусь кошачий.  

На днях по Майнкрафт-сообществу прошла радостная новость: несколько умельцев создали чат для обмена кодами. Анонимный, история сообщений не сохраняется, войти и выйти можно в любой момент. Идеальное место для читеров.  

## Как запустить

Для запуска потребуется Python версии не ниже 3.6  
Установите зависимости. Рекомендуется использовать виртуальное окружение.  
```sh
pip install -r requirements.txt
```
Запуск клиента:  
```sh
python minechat.py
```
Обязательные аргументы, должны присутствовать либо в командной строке (имеют приоритет), либо в файле `.env`:
- `-host`   
  Указывается адрес или доменное имя сервера с чатом  
-  `port_in`   
Порт для подключения к чату на отправку сообщений  
- `-port_out`  
Порт для подключения к чату на прослушку  

Необязательные аргументы:  
- `-history`  
  Задается имя файла, в который сохраняется переписка в чате. По умолчанию `history.txt`
  В `.env` файл параметр имеет имя: `MINECHAT_HISTORY`
  
Файл настроек `.env`
```ini
HOST=minechat.secret_lair.org
PORT_OUT=5000
PORT_IN=5050
MINECHAT_HISTORY=chat2.txt
```

Необязательные аргументы:

 - `-token`    
Токен для авторизации в чате  
 - `-user`  
Имя нового пользователя для регистрации в чате. Будет зарегистрирован новый пользователь, полученный токен доступа будет сохранен в файл `.env`. Существующий токен будет перезаписан. В командной сроке может быть указано либо имя пользователя, либо токен доступа. Если ни токен доступа, ни имя пользователя не указано, то клиент сначала попытается использовать токен из файла `.env`, а при его отсутствии произведет регистрацию нового пользователя, для чего запросит его имя.

Формат файла `.env`
```ini
HOST=minechat.secret_lair.org
PORT=5050
MINECHAT_TOKEN='jdj-djdjd-jdjdj'  
```
# Цели проекта  
Код написан в учебных целях — это урок в курсе по Python и веб-разработке на сайте [Devman](https://dvmn.org).
