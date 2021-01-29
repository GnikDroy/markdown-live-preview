from argparse import ArgumentParser, Namespace
from datetime import datetime
from hashlib import sha1
from os import R_OK, access
from socket import getfqdn
from pathlib import Path
from sys import stderr
from typing import AsyncIterator
from webbrowser import open as open_w

from .reconciliate import reconciliate
from .render import render
from .server import Payload, build
from .stream import stream
from .watch import watch

_TOP_LV = Path(__file__)


def parse_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument("markdown")

    location = parser.add_argument_group()
    location.add_argument("-p", "--port", type=int, default=8080)
    location.add_argument("-o", "--open", action="store_true")

    behaviour = parser.add_argument_group()
    behaviour.add_argument("--nf", "--no-follow", dest="follow", action="store_false")
    behaviour.add_argument("--nb", "--no-browser", dest="browser", action="store_false")

    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    path = Path(args.markdown)

    if not access(path, R_OK):
        print(f"cannot read -- {path}", file=stderr)
        exit(1)


    watch_f = stream if args.read_stdin else watch

    cached, markdown = None, ""
    sha = ""

    async def gen_payload() -> AsyncIterator[Payload]:
        while True:
            payload = Payload(
                follow=args.follow, title=path.name, sha=sha, markdown=markdown
            )
            yield payload

    async def gen_update() -> AsyncIterator[None]:
        nonlocal markdown, cached, sha
        async for md in watch_f(path):
            xhtml = render(md)
            cached, markdown = reconciliate(cached, xhtml)
            sha = sha1(markdown.encode()).hexdigest()
            yield
            time = datetime.now().strftime("%H:%M:%S")
            print(f"🦑 -- {time}")

    serve = build(
        localhost=not args.open,
        port=args.port,
        root=_TOP_LV / "js",
        payloads=gen_payload(),
        updates=gen_update(),
    )

    async def post() -> None:
        host = getfqdn() if args.open else "localhost"
        uri = f"http://{host}:{args.port}"
        if args.browser:
            open_w(uri)
        print(f"SERVING -- {uri}")

    await serve(post)
