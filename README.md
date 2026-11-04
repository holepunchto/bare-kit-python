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

Iterating a worklet yields the data that it writes to `Bare.IPC` until it ends its side. As `Bare.IPC` keeps the worklet alive, `end()` ends the data sent to it so that it may exit on its own, and `wait()` returns its exit code. Reading to the end closes the connection, so that the worklet may exit. Writes raise `BrokenPipeError` once the data sent has ended, the connection has closed, or the worklet has closed its side. Closing a worklet terminates it and waits for it to exit, so keep it open for as long as it should run. Once closed, `terminate()` does nothing and `suspend()`, `resume()` and `wakeup()` raise `ValueError`.

These bindings are a thin layer over [Bare Kit](https://github.com/holepunchto/bare-kit), whose README covers the [lifecycle](https://github.com/holepunchto/bare-kit#lifecycle), [IPC](https://github.com/holepunchto/bare-kit#ipc), [suspension](https://github.com/holepunchto/bare-kit#suspension), [addons](https://github.com/holepunchto/bare-kit#addons), and [error handling](https://github.com/holepunchto/bare-kit#error-handling) of a worklet. In Python terms:

- If `source` is `None`, `start()` reads `filename` at runtime, so the worklet may be a module next to its `node_modules` rather than a bundle.
- Python loads Bare Kit as a shared library, so native addons resolve the symbols of Bare from it as is.
- Bare Kit calls back on threads of its own, which the bindings hand to the event loop that called `start()`, so use the worklet from that loop.
- An uncaught error in the worklet aborts the process, Python included, so report errors over `Bare.IPC` as described in [error handling](https://github.com/holepunchto/bare-kit#error-handling).

## Platforms

The package supports Linux, macOS, and Windows on arm64 and x64, and its wheels include Bare Kit for the platform they are for.

## License

Apache-2.0
