import asyncio
import logging
import datetime
import json
import os
import socket
from tkinter import messagebox
import aiofiles
from aiofiles import os as aio_os
from async_timeout import timeout
import dotenv
import configargparse
from anyio import sleep, create_task_group, ExceptionGroup
import gui
from socket_manager import open_socket
import tkinter as tk
from tkinter import simpledialog


READING_TIMEOUT = 600
RECONNECT_DELAY = 30
HISTORY_FILENAME = 'history.txt'
CONNECTION_TIMEOUT = 120
PING_DELAY = 3

logger = logging.getLogger('minechat')
watchdog_logger = logging.getLogger('watchdog')


class InvalidToken(Exception):
    pass


def get_datetime_now():
    return datetime.datetime.now().strftime("%d.%m.%y %H:%M:%S")


def sanitize_input(message):
    return message.replace('\n', ' ')


async def register(reader, writer, watchdog_queue, nickname):
    logger.debug('Send empty line to obtain new token')
    writer.write('\n'.encode())
    await writer.drain()
    await handle_chat_reply(reader, watchdog_queue, 'Send empty line to obtain new token')
    writer.write(f'{nickname}\n'.encode())
    await writer.drain()
    logger.debug('Send %s as nickname', nickname)
    reply = await handle_chat_reply(reader, watchdog_queue, 'Get authorize')
    parsed_reply = json.loads(reply)
    chat_token = parsed_reply['account_hash']
    registered_nickname = parsed_reply['nickname']
    logger.debug('Get new token: %s', chat_token)


async def save_messages(filepath, save_msgs_queue):
    async with aiofiles.open(filepath, 'a') as f:
        while True:
            message = await save_msgs_queue.get()
            await f.write(f'{message}\n')


async def read_msgs(host, port, messages_queue, save_msgs_queue, status_updates_queue, watchdog_queue):
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
            watchdog_queue.put_nowait(
                'Connection is alive. Source: New message in chat'
            )
            watchdog_logger.debug('New message in chat')


async def send_msgs(host, port, chat_token, sending_queue, status_updates_queue, watchdog_queue, ask_nickname_queue, send_nickname_queue):
    status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
    async with open_socket(host, port, status_updates_queue, gui.ReadConnectionStateChanged) as s:
        reader, writer = s
        await handle_chat_reply(reader, watchdog_queue, 'Prompt before auth')
        if chat_token:
            ask_nickname_queue.put_nowait('SUCCESS')
            nickname = await authorise(reader, writer, chat_token, watchdog_queue)
        else:
            ask_nickname_queue.put_nowait('ASK_NICKNAME')
            nickname = await send_nickname_queue.get()
            await register(reader, writer, watchdog_queue, nickname)
            ask_nickname_queue.put_nowait('OK')
        if not nickname:
            raise InvalidToken()
        logger.debug('Log in chat as %s', nickname)
        status_updates_queue.put_nowait(gui.NicknameReceived(nickname))
        while True:
            message = await sending_queue.get()
            message = sanitize_input(message)
            if not message == '':
                writer.write(f'{message}\n'.encode())
                await writer.drain()
            writer.write('\n'.encode())
            await writer.drain()
            await handle_chat_reply(
                reader,
                watchdog_queue,
                'Message has been sent'
            )
            logger.debug('Send: %s', message)


async def handle_chat_reply(reader, watchdog_queue, source):
    future = reader.readline()
    line = await asyncio.wait_for(future, READING_TIMEOUT)
    decoded_line = line.decode().rstrip()
    logger.debug('Recieve: %s', decoded_line)
    watchdog_queue.put_nowait(f'Connection is alive. Source: {source}')
    watchdog_logger.debug('Source: %s', source)
    return decoded_line


async def authorise(reader, writer, chat_token, watchdog_queue):
    writer.write(f'{chat_token}\n'.encode())
    await writer.drain()
    authorization_reply = await handle_chat_reply(
        reader,
        watchdog_queue,
        'Authorization done'
    )
    parsed_reply = json.loads(authorization_reply)
    if parsed_reply is None:
        logger.error('Token "%s" is not valid', {chat_token.rstrip()})
        return None
    return parsed_reply['nickname']


async def load_history(filepath, messages_queue):
    if await aio_os.path.exists(filepath):
        async with aiofiles.open(filepath, 'r') as f:
            while True:
                message = await f.readline()
                if not message:
                    break
                messages_queue.put_nowait(message.rstrip())


async def watch_for_connection(watchdog_queue):
    while True:
        try:
            async with timeout(CONNECTION_TIMEOUT) as cm:
                await watchdog_queue.get()
        except asyncio.TimeoutError:
            if cm.expired:
                logger.debug('%ss timeout is elapsed', CONNECTION_TIMEOUT)
                raise ConnectionError()


async def ping(sending_queue):
    while True:
        sending_queue.put_nowait('')
        await sleep(PING_DELAY)


async def handle_connection(host, port_in, port_out, token, messages_queue, save_msgs_queue, sending_queue, status_updates_queue, watchdog_queue, ask_nickname_queue, send_nickname_queue, filepath):
    while True:
        try:
            async with create_task_group() as tg:
                tg.start_soon(
                    read_msgs,
                    host,
                    port_out,
                    messages_queue,
                    save_msgs_queue,
                    status_updates_queue,
                    watchdog_queue
                )
                tg.start_soon(
                    send_msgs,
                    host,
                    port_in,
                    token,
                    sending_queue,
                    status_updates_queue,
                    watchdog_queue,
                    ask_nickname_queue,
                    send_nickname_queue,
                )
                tg.start_soon(save_messages, filepath, save_msgs_queue)
                tg.start_soon(watch_for_connection, watchdog_queue)
                tg.start_soon(ping, sending_queue)
        except (ExceptionGroup, ConnectionError, socket.gaierror):
            logger.debug('Reconnect')
            await sleep(1)


async def main():
    minechat_handler = logging.FileHandler('minechat.log')
    watchdog_handler = logging.FileHandler('watchdog.log')
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    minechat_handler.setFormatter(formatter)
    watchdog_handler.setFormatter(formatter)
    logger.setLevel('DEBUG')
    watchdog_logger.setLevel('DEBUG')
    logger.addHandler(minechat_handler)
    watchdog_logger.addHandler(watchdog_handler)

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
    watchdog_queue = asyncio.Queue()
    ask_nickname_queue = asyncio.Queue()
    send_nickname_queue = asyncio.Queue()

    if options.history:
        history_filename = options.history
    else:
        history_filename = HISTORY_FILENAME
    await load_history(history_filename, messages_queue)

    if not options.token:
        print(gui.input_nickname())
    return
    try:
        async with create_task_group() as tg:
            tg.start_soon(
                gui.draw,
                messages_queue,
                sending_queue,
                status_updates_queue,
                ask_nickname_queue,
                send_nickname_queue,
            )
            tg.start_soon(
                handle_connection,
                options.host,
                options.port_in,
                options.port_out,
                options.token,
                messages_queue,
                save_msgs_queue,
                sending_queue,
                status_updates_queue,
                watchdog_queue,
                ask_nickname_queue,
                send_nickname_queue,
                history_filename
            )
    except InvalidToken:
        messagebox.showerror(
            'Неверный токен',
            'Проверьте токен сервер его не узнал!',
        )


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.debug('Exit on Ctrl-C')
    except gui.TkAppClosed:
        logger.debug('Main window closed. Exit')
