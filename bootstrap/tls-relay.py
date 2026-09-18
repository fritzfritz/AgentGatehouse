#!/usr/bin/env python3
"""Opaque loopback TCP -> verified gateway TLS relay; no HTTP policy or credentials.

Uses only Ubuntu's preinstalled Python library so bootstrap needs no open egress.
"""
import argparse
import asyncio
import ssl


async def relay(reader, writer, host, port, context):
    upstream = None
    tasks = []
    try:
        remote_reader, upstream = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=context, server_hostname=host), 15
        )

        async def copy(source, target):
            while data := await source.read(65536):
                target.write(data)
                await target.drain()

        tasks = [asyncio.create_task(copy(reader, upstream)), asyncio.create_task(copy(remote_reader, writer))]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except (OSError, asyncio.TimeoutError):
        # Never dump traffic, exception payloads or proxy credentials to logs.
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for stream in (writer, upstream):
            if stream is not None:
                stream.close()
                try:
                    await stream.wait_closed()
                except OSError:
                    pass


async def serve(args):
    context = ssl.create_default_context(cafile=args.ca)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    server = await asyncio.start_server(
        lambda r, w: relay(r, w, args.host, args.port, context), "127.0.0.1", args.listen_port
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="10.82.2.4")
    parser.add_argument("--port", type=int, default=14443)
    parser.add_argument("--listen-port", type=int, default=14322)
    parser.add_argument("--ca", default="/etc/agentgatehouse/transport.crt")
    asyncio.run(serve(parser.parse_args()))
