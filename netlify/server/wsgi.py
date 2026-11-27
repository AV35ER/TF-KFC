import json
import sys
from io import BytesIO
from urllib.parse import unquote_to_bytes, urlsplit

from werkzeug.wrappers import Response

sys.path.insert(0, "/kfc")
from app import app


def handle_request(metadata, payload):
    request = json.loads(metadata)
    url = urlsplit(request["url"])
    body = bytes(payload.to_py())
    environ = {
        "REQUEST_METHOD": request["method"],
        "SCRIPT_NAME": "",
        "PATH_INFO": unquote_to_bytes(url.path).decode("latin-1"),
        "QUERY_STRING": url.query,
        "SERVER_NAME": url.hostname,
        "SERVER_PORT": str(url.port or (443 if url.scheme == "https" else 80)),
        "SERVER_PROTOCOL": "HTTP/1.1",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": url.scheme,
        "wsgi.input": BytesIO(body),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": False,
        "wsgi.multiprocess": True,
        "wsgi.run_once": False,
    }
    for name, value in request["headers"]:
        if name == "content-type":
            environ["CONTENT_TYPE"] = value
        elif name != "content-length":
            environ["HTTP_" + name.upper().replace("-", "_")] = value

    response = Response.from_app(app, environ, buffered=True)
    return response.status_code, response.headers.to_wsgi_list(), response.get_data()
