import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger('minechat')


@asynccontextmanager
async def open_socket(host, port):
    reader, writer = await asyncio.open_connection(host, port)
    try:
        logger.debug('Socket has been open')
        yield reader, writer
    finally:
        logger.debug('Closing socket')
        writer.close()
        await writer.wait_closed()
        logger.debug('Socket has been closed')
