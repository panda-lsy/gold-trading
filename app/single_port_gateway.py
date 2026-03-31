"""Single-port gateway for Dashboard/API/WebSocket/Portal.

Routes:
- /api/*        -> API upstream
- /ws           -> WebSocket upstream
- /portal/*     -> Portal upstream
- /ai_playground.html -> Portal upstream
- everything else -> Dashboard upstream
"""

import argparse
import asyncio
from typing import Dict, Optional
from urllib.parse import urljoin

from aiohttp import ClientSession, WSMsgType, web

HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _strip_hop_headers(headers: Dict[str, str]) -> Dict[str, str]:
    clean = {}
    for k, v in headers.items():
        if k.lower() not in HOP_HEADERS:
            clean[k] = v
    return clean


def _compose_target(base: str, path_qs: str) -> str:
    base = base.rstrip("/") + "/"
    if path_qs.startswith("/"):
        path_qs = path_qs[1:]
    return urljoin(base, path_qs)


class SinglePortGateway:
    def __init__(
        self,
        dashboard_upstream: str,
        api_upstream: str,
        ws_upstream: str,
        portal_upstream: str,
    ):
        self.dashboard_upstream = dashboard_upstream.rstrip("/")
        self.api_upstream = api_upstream.rstrip("/")
        self.ws_upstream = ws_upstream.rstrip("/")
        self.portal_upstream = portal_upstream.rstrip("/")
        self.client: Optional[ClientSession] = None

    async def startup(self, app: web.Application):
        self.client = ClientSession()

    async def cleanup(self, app: web.Application):
        if self.client:
            await self.client.close()

    async def _proxy_http(self, request: web.Request, target_base: str, strip_prefix: str = "") -> web.Response:
        assert self.client is not None

        rel = request.path_qs
        if strip_prefix and request.path.startswith(strip_prefix):
            rel_path = request.path[len(strip_prefix) :]
            if not rel_path.startswith("/"):
                rel_path = "/" + rel_path
            rel = rel_path
            if request.query_string:
                rel += "?" + request.query_string

        target_url = _compose_target(target_base, rel)
        req_headers = _strip_hop_headers(dict(request.headers))
        req_headers.pop("Host", None)

        body = await request.read()
        async with self.client.request(
            method=request.method,
            url=target_url,
            headers=req_headers,
            data=body,
            allow_redirects=False,
        ) as upstream:
            resp_headers = _strip_hop_headers(dict(upstream.headers))
            data = await upstream.read()
            return web.Response(status=upstream.status, headers=resp_headers, body=data)

    async def _proxy_ws(self, request: web.Request) -> web.StreamResponse:
        assert self.client is not None

        suffix = request.path_qs
        if suffix.startswith("/ws"):
            suffix = suffix[3:]
            if not suffix.startswith("/"):
                suffix = "/" + suffix
            if suffix == "/":
                suffix = ""
        target_url = self.ws_upstream + suffix

        ws_server = web.WebSocketResponse()
        await ws_server.prepare(request)

        ws_headers = _strip_hop_headers(dict(request.headers))
        ws_headers.pop("Host", None)

        try:
            ws_client = await self.client.ws_connect(target_url, headers=ws_headers)
        except Exception as exc:
            await ws_server.send_str(f"gateway ws_connect failed: {exc}")
            await ws_server.close()
            return ws_server

        async def client_to_upstream():
            async for msg in ws_server:
                if msg.type == WSMsgType.TEXT:
                    await ws_client.send_str(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    await ws_client.send_bytes(msg.data)
                elif msg.type == WSMsgType.CLOSE:
                    await ws_client.close()
                    break

        async def upstream_to_client():
            async for msg in ws_client:
                if msg.type == WSMsgType.TEXT:
                    await ws_server.send_str(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    await ws_server.send_bytes(msg.data)
                elif msg.type == WSMsgType.CLOSE:
                    await ws_server.close()
                    break

        await asyncio.gather(client_to_upstream(), upstream_to_client(), return_exceptions=True)

        await ws_client.close()
        await ws_server.close()
        return ws_server

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "success": True,
                "service": "single_port_gateway",
                "upstreams": {
                    "dashboard": self.dashboard_upstream,
                    "api": self.api_upstream,
                    "ws": self.ws_upstream,
                    "portal": self.portal_upstream,
                },
            }
        )

    async def api_handler(self, request: web.Request) -> web.Response:
        return await self._proxy_http(request, self.api_upstream, strip_prefix="")

    async def portal_handler(self, request: web.Request) -> web.Response:
        return await self._proxy_http(request, self.portal_upstream, strip_prefix="/portal")

    async def portal_ai_playground(self, request: web.Request) -> web.Response:
        return await self._proxy_http(request, self.portal_upstream, strip_prefix="")

    async def default_handler(self, request: web.Request) -> web.Response:
        return await self._proxy_http(request, self.dashboard_upstream, strip_prefix="")


def build_app(args) -> web.Application:
    gateway = SinglePortGateway(
        dashboard_upstream=args.dashboard_upstream,
        api_upstream=args.api_upstream,
        ws_upstream=args.ws_upstream,
        portal_upstream=args.portal_upstream,
    )

    app = web.Application()
    app.on_startup.append(gateway.startup)
    app.on_cleanup.append(gateway.cleanup)

    app.router.add_get("/gateway/health", gateway.health)
    app.router.add_route("*", "/ws{tail:.*}", gateway._proxy_ws)
    app.router.add_route("*", "/api{tail:.*}", gateway.api_handler)
    app.router.add_route("*", "/portal{tail:.*}", gateway.portal_handler)
    app.router.add_route("*", "/ai_playground.html", gateway.portal_ai_playground)
    app.router.add_route("*", "/{tail:.*}", gateway.default_handler)

    return app


def parse_args():
    parser = argparse.ArgumentParser(description="Single-port gateway for gold-trading")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--dashboard-upstream", default="http://127.0.0.1:5000")
    parser.add_argument("--api-upstream", default="http://127.0.0.1:8080")
    parser.add_argument("--ws-upstream", default="ws://127.0.0.1:8765")
    parser.add_argument("--portal-upstream", default="http://127.0.0.1:8090")
    return parser.parse_args()


def main():
    args = parse_args()
    app = build_app(args)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
