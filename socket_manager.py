import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger('minechat')


@asynccontextmanager
async def open_socket(host, port, status_updates_queue, connection):
    status_updates_queue.put_nowait(connection.INITIATED)
    reader, writer = await asyncio.open_connection(host, port)
    try:
        status_updates_queue.put_nowait(connection.ESTABLISHED)
        logger.debug('Socket has been open')
        yield reader, writer
    finally:
        logger.debug('Closing socket')
        writer.close()
        await writer.wait_closed()
        logger.debug('Socket has been closed')
        status_updates_queue.put_nowait(connection.CLOSED)
