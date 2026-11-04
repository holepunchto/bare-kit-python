import asyncio
from pathlib import Path

import pytest

from bare_kit import start

FIXTURES = Path(__file__).parent / "fixtures"


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 10))


def test_echoes_ipc_data():
    async def body():
        async with await start(FIXTURES / "echo.js") as worklet:
            await worklet.write(b"Hello world")
            return await worklet.read()

    assert run(body()) == b"Hello world"


def test_ends_ipc_data():
    async def body():
        async with await start(FIXTURES / "collect.js") as worklet:
            await worklet.write(b"Hello ")
            await worklet.write(b"world")
            worklet.end()

            with pytest.raises(BrokenPipeError):
                await worklet.write(b"!")

            return b"".join([chunk async for chunk in worklet]), await worklet.wait()

    assert run(body()) == (b"Hello world", 0)


def test_passes_arguments():
    async def body():
        async with await start(FIXTURES / "argv.js", "foo", "bar") as worklet:
            return b"".join([chunk async for chunk in worklet])

    assert run(body()) == b'["foo","bar"]'


def test_runs_source():
    async def body():
        source = b"Bare.IPC.end('Hello world')"

        async with await start("/app.js", source=source) as worklet:
            return b"".join([chunk async for chunk in worklet])

    assert run(body()) == b"Hello world"


def test_reports_the_exit_code():
    async def body():
        async with await start(FIXTURES / "exit.js") as worklet:
            return await worklet.wait(), await worklet.read(), worklet.exit_code

    assert run(body()) == (3, b"", 3)


def test_terminates():
    async def body():
        async with await start(FIXTURES / "sleep.js") as worklet:
            worklet.terminate()
            await worklet.wait()
            return await worklet.read()

    assert run(body()) == b""


def test_suspends_and_resumes():
    async def body():
        async with await start(FIXTURES / "lifecycle.js") as worklet:
            events = []

            async for chunk in worklet:
                events.append(chunk)

                if chunk == b"ready":
                    worklet.suspend(0)
                elif chunk == b"suspend":
                    worklet.resume()
                else:
                    break

            return events

    assert run(body()) == [b"ready", b"suspend", b"resume"]


def test_rejects_writes_once_closed():
    async def body():
        worklet = await start(FIXTURES / "echo.js")
        await worklet.close()

        with pytest.raises(BrokenPipeError):
            await worklet.write(b"Hello world")

    run(body())


def test_rejects_writes_once_the_worklet_has_exited():
    async def body():
        async with await start(FIXTURES / "exit.js") as worklet:
            await worklet.wait()

            with pytest.raises(BrokenPipeError):
                await worklet.write(b"Hello world")

    run(body())


def test_ignores_terminate_once_closed_and_rejects_other_calls():
    async def body():
        worklet = await start(FIXTURES / "echo.js")
        await worklet.close()
        worklet.terminate()

        with pytest.raises(ValueError):
            worklet.suspend()

    run(body())


def test_streams_large_data():
    data = bytes(range(256)) * 4096

    async def body():
        async with await start(FIXTURES / "collect.js") as worklet:
            await worklet.write(data)
            worklet.end()
            return b"".join([chunk async for chunk in worklet])

    assert run(body()) == data
