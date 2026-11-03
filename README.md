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

Closing a worklet terminates it, so keep it open for as long as it should run. Once closed, `terminate()` does nothing and `suspend()`, `resume()` and `wakeup()` raise `ValueError`.

## Bare Kit

These bindings are a thin layer over [Bare Kit](https://github.com/holepunchto/bare-kit), whose README covers the [lifecycle](https://github.com/holepunchto/bare-kit#lifecycle), [IPC](https://github.com/holepunchto/bare-kit#ipc), [addons](https://github.com/holepunchto/bare-kit#addons) and [error handling](https://github.com/holepunchto/bare-kit#error-handling) of a worklet. In Python terms:

- If `source` is `None`, `start()` reads `filename` at runtime, so the worklet may be a module next to its `node_modules` rather than a bundle. Python loads Bare Kit as a shared library, so native addons, such as those of `hyperswarm` and `corestore`, work as is.
- `worklet.end()` ends the host side of the IPC, which `Bare.IPC` reads as the end of the stream, and `close()` terminates the worklet.
- An uncaught error in the worklet aborts the process, Python included, so report errors over `Bare.IPC` as described in [error handling](https://github.com/holepunchto/bare-kit#error-handling).

## License

Apache-2.0
