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

## Writing the worklet

### Using npm modules

The worklet doesn't have to be a bundle. Point `start()` at a plain JavaScript file next to a `package.json` and the worklet resolves `node_modules` from disk, including native addons such as those used by `hyperswarm` and `corestore`:

```
app.js
package.json   # { "type": "module", "dependencies": { "hyperswarm": "..." } }
main.py        # start(Path(__file__).parent / "app.js")
```

Run `npm install` next to `app.js`, then start it from Python as usual. Module types work as in Node.js: use `"type": "module"` or an `.mjs` file for `import` and top-level `await`. Code passed with `source=` and no such filename is CommonJS.

### Handling errors

An uncaught exception or unhandled promise rejection in the worklet aborts the whole process, Python included, without printing an error. This includes syntax errors in the module. Catch errors in the worklet and report them over `Bare.IPC` instead, so that Python can raise them:

```js
function fail(err) {
  Bare.IPC.end(JSON.stringify({ error: err.message }) + '\n')
}

Bare.on('uncaughtException', fail)
Bare.on('unhandledRejection', fail)
```

### Shutting down

`worklet.end()` ends the data written to the worklet, which `Bare.IPC` sees as an `end` event. Handle it by releasing whatever keeps the worklet running, such as sockets, timers and swarms, and then ending `Bare.IPC` in turn, so that the worklet exits:

```js
Bare.IPC.on('data', (data) => {
  // Handle messages from Python
})

Bare.IPC.on('end', async () => {
  await swarm.destroy()
  Bare.IPC.end()
})
```

Set up these listeners before the first `await` of the module. A listener added after an `await` that takes long, such as waiting for peers, is only added once it settles, and Python ending the connection goes unseen until then. `end` is also only emitted once the stream is flowing, so listen for `data` too, or call `Bare.IPC.resume()`.

Putting it together, a worklet using Hyperswarm looks like this:

```js
import Hyperswarm from 'hyperswarm'

const swarm = new Hyperswarm()

function fail(err) {
  Bare.IPC.end(JSON.stringify({ error: err.message }) + '\n')
}

Bare.on('uncaughtException', fail)
Bare.on('unhandledRejection', fail)

Bare.IPC.on('data', (data) => {
  // Handle messages from Python
})

Bare.IPC.on('end', async () => {
  await swarm.destroy()
  Bare.IPC.end()
})

// Only now do the slow work
swarm.join(topic)
await swarm.flush()
```

## License

Apache-2.0
