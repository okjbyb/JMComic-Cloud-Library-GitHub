import base64
import http.client
import json
import os
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote, urlencode

import app


def request(connection, method, path, body=None, headers=None):
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    return response, response.read()


def main():
    root = Path(tempfile.mkdtemp())
    os.environ["JM_DATA_ROOT"] = str(root / "users")
    app.USER_DB = root / "users.db"
    app.init_user_db("admin", "test-password")
    library = app.user_library_dir("admin")
    pdf = library / "管理员书籍.pdf"
    pdf.write_bytes(b"%PDF-1.4 test-content")

    server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    server.admin_username = "admin"
    server.admin_password = "test-password"
    server.session_secret = "test-session-secret"
    server.opds_username = "admin"
    server.opds_password = "test-password"
    server.public_urls = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    response, _ = request(connection, "GET", "/")
    assert response.status == 303 and response.getheader("Location") == "/login"

    form = urlencode({"username": "admin", "password": "test-password"})
    response, _ = request(connection, "POST", "/login", form, {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": str(len(form)),
    })
    assert response.status == 303
    cookie = response.getheader("Set-Cookie").split(";", 1)[0]

    response, body = request(connection, "GET", "/api/library", headers={"Cookie": cookie})
    assert response.status == 200
    books = json.loads(body)["books"]
    assert books[0]["title"] == "管理员书籍"

    response, body = request(connection, "GET", "/files/pdf?path=" + quote(books[0]["path"]), headers={
        "Cookie": cookie,
        "Range": "bytes=0-7",
    })
    assert response.status == 206 and body == b"%PDF-1.4"

    token = base64.b64encode(b"admin:test-password").decode()
    response, body = request(connection, "GET", "/opds", headers={"Authorization": "Basic " + token})
    assert response.status == 200 and "管理员书籍" in body.decode("utf-8")

    register = urlencode({"username": "reader1", "password": "reader-pass-123", "confirm": "reader-pass-123"})
    response, _ = request(connection, "POST", "/register", register, {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": str(len(register)),
    })
    assert response.status == 303
    reader_pdf = app.user_library_dir("reader1") / "用户书籍.pdf"
    reader_pdf.write_bytes(b"%PDF-reader")
    reader_login = urlencode({"username": "reader1", "password": "reader-pass-123"})
    response, _ = request(connection, "POST", "/login", reader_login, {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": str(len(reader_login)),
    })
    reader_cookie = response.getheader("Set-Cookie").split(";", 1)[0]
    response, body = request(connection, "GET", "/api/library", headers={"Cookie": reader_cookie})
    reader_books = json.loads(body)["books"]
    assert [book["title"] for book in reader_books] == ["用户书籍"]

    attack = json.dumps({"paths": ["../../admin/pdf/" + pdf.name]})
    response, body = request(connection, "POST", "/api/library/delete", attack, {
        "Cookie": reader_cookie,
        "Content-Type": "application/json",
        "Content-Length": str(len(attack.encode("utf-8"))),
    })
    assert response.status == 200 and not json.loads(body)["ok"] and pdf.exists()

    marker = app.pdf_marker_path(reader_pdf)
    marker.write_text("{}", encoding="utf-8")
    deletion = json.dumps({"paths": [reader_books[0]["path"]]})
    response, body = request(connection, "POST", "/api/library/delete", deletion, {
        "Cookie": reader_cookie,
        "Content-Type": "application/json",
        "Content-Length": str(len(deletion.encode("utf-8"))),
    })
    result = json.loads(body)
    assert response.status == 200 and result["ok"] and result["deleted"] == 1
    assert not reader_pdf.exists() and not marker.exists()

    change = urlencode({
        "current_password": "reader-pass-123",
        "new_password": "reader-pass-456",
        "confirm": "reader-pass-456",
    })
    response, _ = request(connection, "POST", "/account/password", change, {
        "Cookie": reader_cookie,
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": str(len(change)),
    })
    assert response.status == 200 and app.verify_user("reader1", "reader-pass-456")

    server.shutdown()
    server.server_close()
    print("cloud smoke test ok")


if __name__ == "__main__":
    main()
