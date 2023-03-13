import asyncio
import logging
import dotenv
import configargparse
import gui
from socket_manager import open_socket


READING_TIMEOUT = 600
RECONNECT_DELAY = 30
HISTORY_FILENAME = 'history.txt'

logger = logging.getLogger('minechat')


async def read_msgs(host, port, queue):
    async with open_socket(host, port) as s:
        reader, _ = s
        logger.debug('Start listening chat')
        while not reader.at_eof():
            future = reader.readline()
            line = await asyncio.wait_for(future, READING_TIMEOUT)
            queue.put_nowait(line.decode().rstrip())


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

    loop = await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        read_msgs(options.host, options.port_out, messages_queue),
    )


if __name__ == '__main__':
    asyncio.run(main())
