# bare-kit-python

Python bindings for [Bare Kit](https://github.com/holepunchto/bare-kit), which runs Bare in a thread of its own within the application, known as a worklet, with an IPC to it exposed as `Bare.IPC` inside the worklet.

```
pip install bare-kit
```

## Usage

```python
import asyncio
from pathlib import Path

from bare_kit import start


async def main():
    async with await start(Path(__file__).parent / "app.bundle") as worklet:
        await worklet.write(b"Hello world")

        async for data in worklet:
            print(data.decode())


asyncio.run(main())
```

Where `app.bundle` is a Bare bundle using `Bare.IPC`:

```js
Bare.IPC.on('data', (data) => Bare.IPC.end(data))
```

Closing a worklet terminates it, so keep it open for as long as it should run.

## License

Apache-2.0
