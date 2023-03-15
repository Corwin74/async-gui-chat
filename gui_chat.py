import asyncio
import logging
import datetime
import json
import os
from tkinter import messagebox
import aiofiles
from aiofiles import os as aio_os
import dotenv
import configargparse
import gui
from socket_manager import open_socket


READING_TIMEOUT = 600
RECONNECT_DELAY = 30
HISTORY_FILENAME = 'history.txt'

logger = logging.getLogger('minechat')


class InvalidToken(Exception):
    pass


def get_datetime_now():
    return datetime.datetime.now().strftime("%d.%m.%y %H:%M:%S")


async def save_messages(filepath, save_msgs_queue):
    async with aiofiles.open(filepath, 'a') as f:
        while True:
            message = await save_msgs_queue.get()
            await f.write(f'{message}\n')


async def read_msgs(host, port, messages_queue, save_msgs_queue, status_updates_queue):
    async with open_socket(host, port, status_updates_queue, gui.SendingConnectionStateChanged) as s:
        reader, _ = s
        logger.debug('Start listening chat')
        while not reader.at_eof():
            future = reader.readline()
            line = await asyncio.wait_for(future, READING_TIMEOUT)
            message = line.decode().rstrip()
            formatted_date = get_datetime_now()
            message = f'[{formatted_date}] {message}'
            messages_queue.put_nowait(message)
            save_msgs_queue.put_nowait(message)


async def send_msgs(host, port, sending_queue, messages_queue, status_updates_queue):
    status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
    async with open_socket(host, port, status_updates_queue, gui.ReadConnectionStateChanged) as s:
        reader, writer = s
        await handle_chat_reply(reader)
        chat_token = os.getenv('MINECHAT_TOKEN')
        nickname = await authorise(reader, writer, chat_token)
        if not nickname:
            raise InvalidToken()
        logger.debug('Log in chat as %s', nickname)
        status_updates_queue.put_nowait(gui.NicknameReceived(nickname))
        while True:
            message = await sending_queue.get()
            formatted_date = get_datetime_now()
            message = f'[{formatted_date}] {nickname}: {message}'
            messages_queue.put_nowait(message)


async def handle_chat_reply(reader, echo=None):
    future = reader.readline()
    line = await asyncio.wait_for(future, READING_TIMEOUT)
    formatted_date = get_datetime_now()
    decoded_line = line.decode().rstrip()
    logger.debug('Recieve: %s', decoded_line)
    if echo:
        print(f'[{formatted_date}] {decoded_line}')
    return decoded_line


async def authorise(reader, writer, chat_token):
    writer.write(f'{chat_token}\n'.encode())
    await writer.drain()
    authorization_reply = await handle_chat_reply(reader)
    logger.debug('Authorization reply: %s', authorization_reply)
    parsed_reply = json.loads(authorization_reply)
    if parsed_reply is None:
        print(f'[{get_datetime_now()}] Неизвестный токен: '
              f'"{chat_token.rstrip()}". '
              'Проверьте его или зарегистрируйте заново.')
        logger.error('Token "%s" is not valid', {chat_token.rstrip()})
        return None
    await handle_chat_reply(reader)
    return parsed_reply['nickname']


async def load_history(filepath, messages_queue):
    if await aio_os.path.exists(filepath):
        async with aiofiles.open(filepath, 'r') as f:
            while True:
                message = await f.readline()
                if not message:
                    break
                messages_queue.put_nowait(message.rstrip())


async def main():
    logging.basicConfig(
        filename='listen_minechat.log',
        filemode='w',
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    dotenv.load_dotenv()
    parser = configargparse.ArgParser()
    parser.add(
        '-host',
        required=True,
        help='host to connection',
        env_var='HOST',
    )
    parser.add(
        '-port_out',
        required=True,
        help='port to connection',
        env_var='PORT_OUT',
    )
    parser.add(
        '-port_in',
        required=True,
        help='port to connection',
        env_var='PORT_IN',
    )
    parser.add(
        '-history',
        required=False,
        help='history filename',
        env_var='MINECHAT_HISTORY',
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-token',
        required=False,
        help='Access token',
        env_var='MINECHAT_TOKEN',
    )
    group.add_argument(
        '-user',
        required=False,
        help='New user to registration',
    )

    options = parser.parse_args()
    logger.debug(
        'Host: %s, port_in: %s, port_out: %s',
        options.host,
        options.port_in,
        options.port_out,
    )

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    save_msgs_queue = asyncio.Queue()

    if options.history:
        history_filename = options.history
    else:
        history_filename = HISTORY_FILENAME
    await load_history(history_filename, messages_queue)

    try:
        await asyncio.gather(
            gui.draw(messages_queue, sending_queue, status_updates_queue),
            read_msgs(
                options.host,
                options.port_out,
                messages_queue,
                save_msgs_queue,
                status_updates_queue,
            ),
            save_messages(history_filename, save_msgs_queue),
            send_msgs(
                options.host,
                options.port_in,
                sending_queue,
                messages_queue,
                status_updates_queue,
            ),
        )
    except InvalidToken:
        messagebox.showerror(
            'Неверный токен',
            'Проверьте токен сервер его не узнал!',
        )


if __name__ == '__main__':
    asyncio.run(main())
