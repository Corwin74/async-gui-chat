import asyncio
import aiofiles
import logging
import datetime
import dotenv
import configargparse
import gui
from socket_manager import open_socket


READING_TIMEOUT = 600
RECONNECT_DELAY = 30
HISTORY_FILENAME = 'history.txt'

logger = logging.getLogger('minechat')


def get_datetime_now():
    return datetime.datetime.now().strftime("%d.%m.%y %H:%M:%S")


async def save_messages(filepath, save_msgs_queue):
    async with aiofiles.open(filepath, 'a') as f:
        while True:
            message = await save_msgs_queue.get()
            formatted_date = get_datetime_now()
            await f.write(f'[{formatted_date}] {message}\n')


async def read_msgs(host, port, messages_queue, save_msgs_queue):
    async with open_socket(host, port) as s:
        reader, _ = s
        logger.debug('Start listening chat')
        while not reader.at_eof():
            future = reader.readline()
            line = await asyncio.wait_for(future, READING_TIMEOUT)
            msg = line.decode().rstrip()
            messages_queue.put_nowait(msg)
            save_msgs_queue.put_nowait(msg)


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

    loop = await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        read_msgs(
            options.host,
            options.port_out,
            messages_queue,
            save_msgs_queue,
        ),
        save_messages(HISTORY_FILENAME, save_msgs_queue),
    )
    print(loop)


if __name__ == '__main__':
    asyncio.run(main())
