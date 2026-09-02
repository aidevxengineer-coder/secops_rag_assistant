import asyncio
import websockets


async def test():
    uri = "ws://localhost:8088/ws/test123"
    async with websockets.connect(uri) as ws:
        print("Connected successfully!")
        await ws.send('{"type":"subscribe","trace_id":"abc"}')
        await asyncio.sleep(2)


asyncio.run(test())
