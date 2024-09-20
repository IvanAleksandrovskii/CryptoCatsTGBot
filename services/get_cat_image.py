import asyncio

from core import logger
from core.models import http_helper


async def get_random_cat_image() -> str:
    max_retry = 3
    url = "https://api.thecatapi.com/v1/images/search"
    for retry in range(max_retry):
        client = await http_helper.get_client()
        try:
            response = await client.request('GET', url)
            if response.status == 200:
                data = await response.json()
                return data[0]["url"]
            else:
                raise Exception(f"Unexpected status code: {response.status}")
        except Exception as e:
            logger.error(f"Request error (attempt {retry + 1}/{max_retry}): %s", e)
            if retry < max_retry - 1:
                await asyncio.sleep(1)
        finally:
            await http_helper.release_client(client)

    logger.warning("All attempts failed, using fallback image URL")
    return "https://masterpiecer-images.s3.yandex.net/505cfa23621d11eea5826a0259d7362a:upscaled"
