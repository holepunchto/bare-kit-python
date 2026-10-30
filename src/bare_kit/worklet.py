import asyncio
import ctypes
import itertools
import os
from collections import deque
from contextlib import suppress

from ._native import (
    ERROR,
    READ_BUFFER_SIZE,
    READABLE,
    WOULD_BLOCK,
    WRITABLE,
    ExitCallback,
    PollCallback,
    WorkletOptions,
    library,
)


class BareKitError(Exception):
    """A call into Bare Kit failed with ``status``."""

    def __init__(self, status):
        super().__init__(f"Bare Kit failed with status {status}")
        self.status = status


def _check(status):
    if status != 0:
        raise BareKitError(status)


def optimize_for_memory(enabled):
    """Trade performance for memory. Must be configured before starting the
    first worklet."""
    library().bare_worklet_optimize_for_memory(enabled)


def teardown():
    """Tear down the state shared by the worklets of the process.

    Every worklet must have been closed first. Must be called at most once,
    after which starting a worklet fails. A process that runs worklets for as
    long as it lives need not call it.
    """
    library().bare_worklet_teardown()


# Bare Kit calls back from threads of its own, possibly after the worklet that a
# callback is for has been released, so the callbacks are shared and look the
# worklet up by key.
_worklets = {}
_keys = itertools.count(1)


@ExitCallback
def _on_exit(code, data):
    worklet = _worklets.get(data)

    if worklet is not None:
        worklet._call_soon(worklet._on_exit, code)


@PollCallback
def _on_poll(poll, events):
    # Polls are level-triggered, so the poll is stopped until the loop has
    # handled the events and starts it again.
    library().bare_ipc_poll_stop(poll)

    worklet = _worklets.get(library().bare_ipc_poll_get_data(poll))

    if worklet is not None:
        worklet._call_soon(worklet._on_poll)


async def start(filename, *args, source=None, memory_limit=0):
    """Start ``filename`` in a worklet with an IPC connection to it and return
    its ``Worklet``.

    ``args`` are passed to the worklet as ``Bare.argv``. ``source`` is the
    source of the module, read from ``filename`` if ``None``. ``memory_limit``
    is the memory limit of each JavaScript heap in bytes, or 0 to infer it from
    the amount of physical memory of the device.
    """
    worklet = Worklet(asyncio.get_running_loop(), memory_limit)

    try:
        worklet._start(filename, args, source)
    except BaseException:
        worklet._destroy()
        raise

    return worklet


class Worklet:
    """A Bare runtime running on a thread of its own, connected to its
    ``Bare.IPC``.

    Iterating it with ``async for`` yields the data the worklet writes to
    ``Bare.IPC`` until the connection ends, and leaving ``async with`` closes
    it. Use ``start()`` to start one.
    """

    def __init__(self, loop, memory_limit):
        lib = library()

        self._loop = loop
        self._key = next(_keys)
        self._handle = ctypes.c_void_p()
        self._ipc = ctypes.c_void_p()
        self._poll = ctypes.c_void_p()
        self._buffer = ctypes.create_string_buffer(READ_BUFFER_SIZE)
        self._exited = loop.create_future()
        self._started = False
        self._closed = False

        self._events = 0
        self._chunks = deque()
        self._buffered = 0
        self._eof = False
        self._reader = None
        self._writes = deque()
        self._ending = False
        self._ended = False
        self._disconnected = False

        options = WorkletOptions(version=0, memory_limit=memory_limit)

        _check(
            lib.bare_worklet_create(ctypes.byref(options), ctypes.byref(self._handle))
        )

        try:
            _check(lib.bare_ipc_create(self._handle, ctypes.byref(self._ipc)))
            _check(lib.bare_ipc_poll_create(self._ipc, ctypes.byref(self._poll)))
        except BaseException:
            self._destroy()
            raise

        lib.bare_ipc_poll_set_data(self._poll, self._key)
        lib.bare_worklet_on_exit(self._handle, _on_exit, self._key)

        _worklets[self._key] = self

    def _start(self, filename, args, source):
        argv = [os.fsencode(arg) for arg in args]

        _check(
            library().bare_worklet_start(
                self._handle,
                os.fsencode(filename),
                source,
                0 if source is None else len(source),
                len(argv),
                (ctypes.c_char_p * (len(argv) + 1))(*argv, None),
            )
        )

        self._started = True
        self._update()

    @property
    def exit_code(self):
        """The exit code of the worklet, or ``None`` while it is running."""
        return self._exited.result() if self._exited.done() else None

    async def read(self, n=65536):
        """Read up to ``n`` bytes from the worklet, or ``b""`` once it has
        ended its end of the connection."""
        while not self._chunks and not self._eof:
            self._reader = self._loop.create_future()

            try:
                await self._reader
            finally:
                self._reader = None

        if not self._chunks:
            self._close_ipc()
            return b""

        chunk = self._chunks.popleft()

        if len(chunk) > n:
            self._chunks.appendleft(chunk[n:])
            chunk = chunk[:n]

        self._buffered -= len(chunk)
        self._update()

        return chunk

    def __aiter__(self):
        return self._chunks_until_eof()

    async def _chunks_until_eof(self):
        while chunk := await self.read():
            yield chunk

    async def write(self, data):
        """Write ``data`` to the worklet and wait for it to drain.

        Data written once the connection has ended or closed, such as while the
        worklet exits, is dropped, as its exit already accounts for it.
        """
        if self._ending or not data:
            return

        written = self._loop.create_future()

        self._writes.append([bytes(data), 0, written])
        self._flush()
        self._update()

        await written

    def end(self):
        """End the data written to the worklet once the pending writes drain,
        after which ``Bare.IPC`` reads end-of-stream while reading continues."""
        if self._ending:
            return

        self._ending = True
        self._flush()
        self._update()

    def suspend(self, linger=-1):
        """Suspend the worklet, emitting ``suspend`` on ``Bare``.

        ``linger`` is how long in milliseconds the worklet may keep running
        before it goes idle, or -1 for as long as the platform allows.
        """
        library().bare_worklet_suspend(self._handle, linger)

    def resume(self):
        """Resume a suspended worklet, emitting ``resume`` on ``Bare``."""
        library().bare_worklet_resume(self._handle)

    def wakeup(self, deadline=-1):
        """Wake up a suspended worklet, emitting ``wakeup`` on ``Bare``.

        ``deadline`` is how long in milliseconds the worklet may run before it
        goes idle again, or -1 for as long as the platform allows.
        """
        library().bare_worklet_wakeup(self._handle, deadline)

    def terminate(self):
        """Ask the worklet to exit unless it has already exited."""
        library().bare_worklet_terminate(self._handle)

    async def wait(self):
        """Wait for the worklet to exit and return its exit code."""
        return await asyncio.shield(self._exited)

    async def close(self):
        """Close the connection, terminating the worklet if it is still
        running, and wait for it to exit."""
        if self._closed:
            return

        self._close_ipc()
        self.terminate()

        await self.wait()

        self._destroy()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    def _call_soon(self, callback, *args):
        # The loop may have been closed while a worklet was left running.
        with suppress(RuntimeError):
            self._loop.call_soon_threadsafe(callback, *args)

    def _on_exit(self, code):
        if not self._exited.done():
            self._exited.set_result(code)

    def _on_poll(self):
        if self._closed:
            return

        self._events = 0
        self._drain()
        self._flush()
        self._update()

    def _drain(self):
        lib = library()

        while not self._eof and self._buffered < READ_BUFFER_SIZE:
            read = lib.bare_ipc_read(self._ipc, self._buffer, READ_BUFFER_SIZE)

            if read > 0:
                self._chunks.append(ctypes.string_at(self._buffer, read))
                self._buffered += read
            else:
                if read == 0:
                    self._eof = True

                break

        if self._reader is not None and not self._reader.done():
            if self._chunks or self._eof:
                self._reader.set_result(None)

    def _flush(self):
        lib = library()

        while self._writes:
            write = self._writes[0]
            data, offset, written = write

            result = lib.bare_ipc_write(
                self._ipc,
                ctypes.cast(data, ctypes.c_void_p).value + offset,
                len(data) - offset,
            )

            if result == WOULD_BLOCK:
                break

            if result == ERROR:
                self._drop_writes()
                break

            write[1] = offset = offset + result

            if offset == len(data):
                self._writes.popleft()

                if not written.done():
                    written.set_result(None)

        if self._ending and not self._writes and not self._ended:
            self._ended = True
            lib.bare_ipc_end(self._ipc)

    def _drop_writes(self):
        while self._writes:
            _, _, written = self._writes.popleft()

            if not written.done():
                written.set_result(None)

    def _update(self):
        if self._closed or not self._started:
            return

        events = 0

        if not self._eof and self._buffered < READ_BUFFER_SIZE:
            events |= READABLE

        if self._writes:
            events |= WRITABLE

        if events == self._events:
            return

        self._events = events

        if events:
            library().bare_ipc_poll_start(self._poll, events, _on_poll)
        else:
            library().bare_ipc_poll_stop(self._poll)

    def _close_ipc(self):
        """Close the connection, which the worklet waits for before it exits
        once it has ended its side."""
        if self._ipc and not self._disconnected:
            self._disconnected = True
            library().bare_ipc_close(self._ipc)

        self._ending = self._ended = True
        self._eof = True
        self._drop_writes()

        if self._reader is not None and not self._reader.done():
            self._reader.set_result(None)

    def _destroy(self):
        lib = library()

        self._closed = True
        self._close_ipc()

        _worklets.pop(self._key, None)

        if self._poll:
            lib.bare_ipc_poll_destroy(self._poll)

        if self._ipc:
            lib.bare_ipc_destroy(self._ipc)

        if self._handle:
            lib.bare_worklet_destroy(self._handle)
