import argparse
import base64
import contextlib
import csv
import hashlib
import hmac
import html
import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

import jmcomic  # noqa: E402
from jmcomic import JmMagicConstants  # noqa: E402


ORDER_OPTIONS = {
    "latest": JmMagicConstants.ORDER_BY_LATEST,
    "view": JmMagicConstants.ORDER_BY_VIEW,
    "picture": JmMagicConstants.ORDER_BY_PICTURE,
    "like": JmMagicConstants.ORDER_BY_LIKE,
    "score": JmMagicConstants.ORDER_BY_SCORE,
    "comment": JmMagicConstants.ORDER_BY_COMMENT,
}

TIME_OPTIONS = {
    "all": JmMagicConstants.TIME_ALL,
    "today": JmMagicConstants.TIME_TODAY,
    "week": JmMagicConstants.TIME_WEEK,
    "month": JmMagicConstants.TIME_MONTH,
}

CATEGORY_OPTIONS = {
    "all": JmMagicConstants.CATEGORY_ALL,
    "doujin": JmMagicConstants.CATEGORY_DOUJIN,
    "single": JmMagicConstants.CATEGORY_SINGLE,
    "short": JmMagicConstants.CATEGORY_SHORT,
    "another": JmMagicConstants.CATEGORY_ANOTHER,
    "hanman": JmMagicConstants.CATEGORY_HANMAN,
    "meiman": JmMagicConstants.CATEGORY_MEIMAN,
    "cosplay": JmMagicConstants.CATEGORY_DOUJIN_COSPLAY,
    "3d": JmMagicConstants.CATEGORY_3D,
    "english": JmMagicConstants.CATEGORY_ENGLISH_SITE,
}

SUB_CATEGORY_OPTIONS = {
    "": None,
    "chinese": JmMagicConstants.SUB_CHINESE,
    "japanese": JmMagicConstants.SUB_JAPANESE,
    "cg": JmMagicConstants.SUB_DOUJIN_CG,
    "youth": JmMagicConstants.SUB_SINGLE_YOUTH,
    "other": JmMagicConstants.SUB_ANOTHER_OTHER,
    "3d": JmMagicConstants.SUB_ANOTHER_3D,
    "cosplay": JmMagicConstants.SUB_ANOTHER_COSPLAY,
}


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JMComic Crawler UI</title>
  <style>
    :root{font-family:"Microsoft YaHei UI",system-ui,sans-serif;color:#172026;background:#f6f7f8}
    body{margin:0}
    header{height:56px;background:#ffffff;border-bottom:1px solid #d7dde2;display:flex;align-items:center;justify-content:space-between;padding:0 18px}
    h1{font-size:18px;margin:0}
    main{display:grid;grid-template-columns:260px 1fr;min-height:calc(100vh - 56px)}
    nav{background:#ffffff;border-right:1px solid #d7dde2;padding:12px}
    nav button{display:block;width:100%;text-align:left;border:0;background:transparent;padding:10px 12px;border-radius:6px;font-size:14px;cursor:pointer}
    nav button.active{background:#0f766e;color:white}
    section{display:none;padding:18px;max-width:1220px}
    section.active{display:block}
    .band{background:#ffffff;border:1px solid #d7dde2;border-radius:6px;padding:14px;margin-bottom:14px}
    .grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
    .grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
    label{display:block;font-size:12px;color:#52616d;margin-bottom:5px}
    input,select,textarea{width:100%;box-sizing:border-box;border:1px solid #b9c3cc;border-radius:5px;padding:8px;background:#fff;font:inherit}
    textarea{min-height:110px;resize:vertical}
    button.primary{background:#0f766e;color:white;border:0;border-radius:5px;padding:9px 14px;cursor:pointer}
    button.secondary{background:#eef2f4;color:#172026;border:1px solid #cbd5dc;border-radius:5px;padding:8px 13px;cursor:pointer}
    .actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
    table{width:100%;border-collapse:collapse;background:white}
    th,td{border-bottom:1px solid #e0e6ea;padding:8px;text-align:left;font-size:13px;vertical-align:top}
    th{background:#f0f3f5;color:#394854}
    tr:hover{background:#f9fbfb}
    .log{height:210px;background:#101417;color:#d8f3dc;border-radius:6px;padding:10px;overflow:auto;font-family:Consolas,monospace;font-size:12px;white-space:pre-wrap}
    .muted{color:#657480;font-size:12px}
    .checks label{font-size:14px;color:#172026;margin:8px 0}
    .checks input{width:auto;margin-right:8px}
    @media(max-width:900px){main{grid-template-columns:1fr}nav{border-right:0;border-bottom:1px solid #d7dde2}.grid,.grid2{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <header><h1>JMComic Crawler UI</h1><span class="muted" id="status">就绪</span></header>
  <main>
    <nav>
      <button class="active" data-tab="download">下载</button>
      <button data-tab="query">详情 / 搜索</button>
      <button data-tab="browse">分类 / 排行</button>
      <button data-tab="favorite">收藏夹</button>
      <button data-tab="option">配置</button>
      <button data-tab="logs">日志</button>
    </nav>
    <div>
      <section id="download" class="active">
        <div class="band">
          <div class="grid2">
            <div><label>下载 ID，空格/换行分隔；章节可写 p123</label><textarea id="downloadIds">123
p456</textarea></div>
            <div class="checks">
              <label><input type="radio" name="mode" value="album" checked>按本子 album 下载</label>
              <label><input type="radio" name="mode" value="photo">按章节 photo 下载</label>
              <label><input type="radio" name="mode" value="mixed">自动识别 p 前缀</label>
              <label><input type="checkbox" id="pluginCover">下载封面</label>
              <label><input type="checkbox" id="pluginZip">完成后合并 ZIP</label>
              <label><input type="checkbox" id="pluginPdf">完成后合并 PDF</label>
              <label><input type="checkbox" id="pluginLong">完成后合并长图 PNG</label>
            </div>
          </div>
          <div class="grid">
            <div><label>下载目录</label><input id="baseDir" value="downloads"></div>
            <div><label>option.yml 路径，可留空用界面配置</label><input id="optionPath"></div>
            <div><label>ZIP/PDF 密码，可留空</label><input id="archivePassword" type="password"></div>
            <div><label>客户端</label><select id="clientImpl"><option value="api">api</option><option value="html">html</option></select></div>
          </div>
          <div class="actions"><button class="primary" onclick="download()">开始下载</button><button class="secondary" onclick="saveOption()">保存配置</button></div>
        </div>
      </section>
      <section id="query">
        <div class="band">
          <div class="grid">
            <div><label>ID 或包含数字的文本</label><input id="detailId"></div>
            <div><label>关键词</label><input id="searchQuery"></div>
            <div><label>页码</label><input id="searchPage" value="1"></div>
            <div><label>范围</label><select id="mainTag"><option value="0">站内</option><option value="1">作品</option><option value="2">作者</option><option value="3">标签</option><option value="4">角色</option></select></div>
          </div>
          <div class="grid">
            <div><label>排序</label><select id="searchOrder"><option value="latest">最新</option><option value="view">观看</option><option value="picture">图片数</option><option value="like">点赞</option><option value="score">评分</option><option value="comment">评论</option></select></div>
            <div><label>时间</label><select id="searchTime"><option value="all">全部</option><option value="today">今日</option><option value="week">本周</option><option value="month">本月</option></select></div>
            <div><label>分类</label><select id="searchCategory"></select></div>
            <div><label>副分类</label><select id="searchSubCategory"></select></div>
          </div>
          <div class="actions"><button class="primary" onclick="detail()">查详情</button><button class="secondary" onclick="cover()">下载封面</button><button class="primary" onclick="search()">搜索</button><button class="secondary" onclick="downloadSelected()">下载选中项</button></div>
        </div>
        <div class="band"><div id="detailOut" class="muted"></div><table id="resultTable"></table></div>
      </section>
      <section id="browse">
        <div class="band">
          <div class="grid">
            <div><label>模式</label><select id="rankMode"><option value="custom">自定义</option><option value="day">日排行</option><option value="week">周排行</option><option value="month">月排行</option></select></div>
            <div><label>页码</label><input id="browsePage" value="1"></div>
            <div><label>时间</label><select id="browseTime"><option value="all">全部</option><option value="today">今日</option><option value="week">本周</option><option value="month">本月</option></select></div>
            <div><label>分类</label><select id="browseCategory"></select></div>
            <div><label>排序</label><select id="browseOrder"><option value="view">观看</option><option value="latest">最新</option><option value="picture">图片数</option><option value="like">点赞</option></select></div>
            <div><label>副分类</label><select id="browseSubCategory"></select></div>
          </div>
          <div class="actions"><button class="primary" onclick="browse()">加载</button><button class="secondary" onclick="downloadSelected('browseTable')">下载选中项</button></div>
        </div>
        <div class="band"><table id="browseTable"></table></div>
      </section>
      <section id="favorite">
        <div class="band">
          <div class="grid">
            <div><label>页码</label><input id="favoritePage" value="1"></div>
            <div><label>文件夹 ID</label><input id="folderId" value="0"></div>
            <div><label>排序</label><select id="favoriteOrder"><option value="latest">最新</option><option value="view">观看</option><option value="like">点赞</option></select></div>
            <div><label>用户名，可留空</label><input id="favoriteUser"></div>
          </div>
          <div class="actions"><button class="primary" onclick="favorites()">加载收藏夹</button><button class="secondary" onclick="exportFavorites()">导出 CSV</button><button class="secondary" onclick="downloadSelected('favoriteTable')">下载选中项</button></div>
        </div>
        <div class="band"><div id="folders" class="muted"></div><table id="favoriteTable"></table></div>
      </section>
      <section id="option">
        <div class="band">
          <div class="grid">
            <div><label>代理：system/null/127.0.0.1:7890</label><input id="proxy" value="system"></div>
            <div><label>图片后缀</label><select id="suffix"><option value="">原格式</option><option>.jpg</option><option>.png</option><option>.webp</option></select></div>
            <div><label>图片线程</label><input id="imageThreads" value="30"></div>
            <div><label>章节线程</label><input id="photoThreads" value=""></div>
            <div><label>目录规则</label><input id="dirRule" value="Bd / Ptitle"></div>
          </div>
          <div class="checks">
            <label><input type="checkbox" id="decodeImage" checked>解码图片</label>
            <label><input type="checkbox" id="downloadCache" checked>跳过已存在文件</label>
          </div>
          <div class="actions"><button class="primary" onclick="previewOption()">刷新配置文本</button><button class="secondary" onclick="saveOption()">保存 option.yml</button></div>
        </div>
        <div class="band"><textarea id="optionText" style="min-height:360px;font-family:Consolas,monospace"></textarea></div>
      </section>
      <section id="logs"><div class="band"><div id="log" class="log"></div></div></section>
    </div>
  </main>
<script>
const cat=[["all","全部"],["doujin","同人"],["single","单本"],["short","短篇"],["another","其他"],["hanman","韩漫"],["meiman","美漫"],["cosplay","Cosplay"],["3d","3D"],["english","英文站"]];
const sub=[["","无"],["chinese","中文"],["japanese","日文"],["cg","CG"],["youth","青年"],["other","其他漫画"],["3d","3D"],["cosplay","Cosplay"]];
for(const id of ["searchCategory","browseCategory"]) document.getElementById(id).innerHTML=cat.map(x=>`<option value="${x[0]}">${x[1]}</option>`).join("");
for(const id of ["searchSubCategory","browseSubCategory"]) document.getElementById(id).innerHTML=sub.map(x=>`<option value="${x[0]}">${x[1]}</option>`).join("");
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll("nav button,section").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.getElementById(b.dataset.tab).classList.add("active")});
function v(id){return document.getElementById(id).value}
function c(id){return document.getElementById(id).checked}
function mode(){return document.querySelector("input[name=mode]:checked").value}
function config(){return {baseDir:v("baseDir"),optionPath:v("optionPath"),clientImpl:v("clientImpl"),proxy:v("proxy"),suffix:v("suffix"),imageThreads:v("imageThreads"),photoThreads:v("photoThreads"),dirRule:v("dirRule"),decodeImage:c("decodeImage"),downloadCache:c("downloadCache"),pluginCover:c("pluginCover"),pluginZip:c("pluginZip"),pluginPdf:c("pluginPdf"),pluginLong:c("pluginLong"),archivePassword:v("archivePassword")}}
async function post(url,data){setStatus("运行中");const r=await fetch(url,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(data)});const j=await r.json();if(!j.ok) alert(j.error||"操作失败");setStatus("就绪");return j}
function setStatus(s){document.getElementById("status").textContent=s}
function table(id,rows){const t=document.getElementById(id);t.innerHTML="<thead><tr><th><input type='checkbox' onchange='toggleAll(this,\""+id+"\")'></th><th>ID</th><th>标题</th><th>标签</th></tr></thead><tbody>"+rows.map(r=>`<tr><td><input type="checkbox" data-id="${r.id}"></td><td>${r.id}</td><td>${esc(r.title)}</td><td>${esc((r.tags||[]).join(", "))}</td></tr>`).join("")+"</tbody>"}
function esc(s){return String(s||"").replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]))}
function toggleAll(x,id){document.querySelectorAll(`#${id} tbody input`).forEach(i=>i.checked=x.checked)}
function selected(id="resultTable"){return [...document.querySelectorAll(`#${id} tbody input:checked`)].map(x=>x.dataset.id)}
async function download(){await post("/api/download",{...config(),ids:v("downloadIds"),mode:mode()})}
async function detail(){let j=await post("/api/detail",{...config(),text:v("detailId")}); if(j.ok) document.getElementById("detailOut").innerHTML="<pre>"+esc(j.detail)+"</pre>"}
async function cover(){await post("/api/cover",{...config(),text:v("detailId")})}
async function search(){let j=await post("/api/search",{...config(),query:v("searchQuery"),page:v("searchPage"),mainTag:v("mainTag"),order:v("searchOrder"),time:v("searchTime"),category:v("searchCategory"),subCategory:v("searchSubCategory")}); if(j.ok)table("resultTable",j.rows)}
async function browse(){let j=await post("/api/browse",{...config(),page:v("browsePage"),mode:v("rankMode"),time:v("browseTime"),category:v("browseCategory"),order:v("browseOrder"),subCategory:v("browseSubCategory")}); if(j.ok)table("browseTable",j.rows)}
async function favorites(){let j=await post("/api/favorites",{...config(),page:v("favoritePage"),folderId:v("folderId"),order:v("favoriteOrder"),username:v("favoriteUser")}); if(j.ok){table("favoriteTable",j.rows);document.getElementById("folders").textContent=(j.folders||[]).map(x=>x.id+":"+x.name).join("  ")}}
async function exportFavorites(){await post("/api/export-favorites",{...config(),page:v("favoritePage"),folderId:v("folderId"),order:v("favoriteOrder"),username:v("favoriteUser")})}
async function downloadSelected(id){let ids=selected(id||"resultTable"); if(!ids.length){alert("请先选中结果");return} await post("/api/download",{...config(),ids:ids.join("\\n"),mode:"album"})}
async function previewOption(){let j=await post("/api/option-text",config()); if(j.ok) document.getElementById("optionText").value=j.text}
async function saveOption(){let j=await post("/api/save-option",config()); if(j.ok){document.getElementById("optionPath").value=j.path; alert("已保存: "+j.path)}}
async function poll(){let r=await fetch("/api/logs");let j=await r.json();document.getElementById("log").textContent=j.text;document.getElementById("log").scrollTop=999999;setTimeout(poll,1200)}
previewOption(); poll();
</script>
</body>
</html>"""

UI_FILE = ROOT / "cloud_ui.html"
if UI_FILE.exists():
    HTML = UI_FILE.read_text(encoding="utf-8")

LOGIN_FILE = ROOT / "login.html"
LOGIN_HTML = LOGIN_FILE.read_text(encoding="utf-8") if LOGIN_FILE.exists() else "Login"
REGISTER_FILE = ROOT / "register.html"
REGISTER_HTML = REGISTER_FILE.read_text(encoding="utf-8") if REGISTER_FILE.exists() else "Register"
ACCOUNT_FILE = ROOT / "account.html"
ACCOUNT_HTML = ACCOUNT_FILE.read_text(encoding="utf-8") if ACCOUNT_FILE.exists() else "Account"

USER_DB = Path(os.getenv("JM_USER_DB", "/data/users.db"))


class AppState:
    def __init__(self):
        self.lock = threading.Lock()
        self.logs = []
        self.library_dir = Path(os.getenv("JM_LIBRARY_DIR", "/data/pdf"))
        self.login_attempts = {}

    def log(self, text):
        with self.lock:
            stamp = datetime.now().strftime("%H:%M:%S")
            self.logs.append(f"[{stamp}] {text}")
            self.logs = self.logs[-700:]

    def text(self):
        with self.lock:
            return "".join(self.logs)

    def set_library_dir(self, path):
        root = Path(path or "downloads").expanduser()
        if not root.is_absolute():
            root = Path.cwd() / root
        with self.lock:
            self.library_dir = root.resolve()

    def get_library_dir(self):
        with self.lock:
            return self.library_dir

    def login_allowed(self, address):
        now = time.time()
        with self.lock:
            attempts = [stamp for stamp in self.login_attempts.get(address, []) if now - stamp < 300]
            self.login_attempts[address] = attempts
            return len(attempts) < 8

    def record_login_failure(self, address):
        with self.lock:
            self.login_attempts.setdefault(address, []).append(time.time())

    def clear_login_failures(self, address):
        with self.lock:
            self.login_attempts.pop(address, None)


STATE = AppState()


def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)


def init_user_db(admin_username, admin_password):
    USER_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(USER_DB) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash BLOB NOT NULL,
                salt BLOB NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        exists = db.execute("SELECT 1 FROM users WHERE username = ?", (admin_username,)).fetchone()
        if not exists:
            salt = secrets.token_bytes(16)
            db.execute(
                "INSERT INTO users(username,password_hash,salt,role,created_at) VALUES(?,?,?,?,?)",
                (admin_username, password_digest(admin_password, salt), salt, "admin", datetime.now().isoformat()),
            )
        db.commit()


def create_user(username, password):
    salt = secrets.token_bytes(16)
    try:
        with sqlite3.connect(USER_DB) as db:
            db.execute(
                "INSERT INTO users(username,password_hash,salt,role,created_at) VALUES(?,?,?,?,?)",
                (username, password_digest(password, salt), salt, "user", datetime.now().isoformat()),
            )
            db.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username, password):
    with sqlite3.connect(USER_DB) as db:
        row = db.execute(
            "SELECT password_hash,salt,active FROM users WHERE username = ?", (username,)
        ).fetchone()
    return bool(row and row[2] and hmac.compare_digest(row[0], password_digest(password, row[1])))


def user_exists(username):
    with sqlite3.connect(USER_DB) as db:
        return db.execute("SELECT 1 FROM users WHERE username = ? AND active = 1", (username,)).fetchone() is not None


def user_role(username):
    with sqlite3.connect(USER_DB) as db:
        row = db.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    return row[0] if row else None


def update_password(username, new_password):
    salt = secrets.token_bytes(16)
    with sqlite3.connect(USER_DB) as db:
        db.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (password_digest(new_password, salt), salt, username),
        )
        db.commit()


def make_session(username, secret, lifetime=86400 * 30):
    expires = int(time.time()) + lifetime
    payload = f"{username}:{expires}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def validate_session(token, secret):
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        token_user, expires, signature = raw.split(":", 2)
        payload = f"{token_user}:{expires}"
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if int(expires) < int(time.time()) or not hmac.compare_digest(signature, expected):
            return None
        return token_user if user_exists(token_user) else None
    except Exception:
        return None


class LogStream(io.TextIOBase):
    def write(self, text):
        if text:
            STATE.log(text)
        return len(text)

    def flush(self):
        return None


def parse_ids(text):
    if isinstance(text, list):
        values = text
    else:
        values = re.split(r"[\s,，;；]+", str(text).strip())
    return list(dict.fromkeys(str(x).strip() for x in values if str(x).strip()))


def run_background(name, func):
    def target():
        STATE.log(f"后台任务开始: {name}\n")
        stream = LogStream()
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                func()
            STATE.log(f"后台任务完成: {name}\n")
        except Exception:
            STATE.log(traceback.format_exc())

    threading.Thread(target=target, name=name, daemon=True).start()


def local_urls(port):
    addresses = []
    with contextlib.suppress(OSError):
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                addresses.append(ip)
    return [f"http://{ip}:{port}/" for ip in dict.fromkeys(addresses)]


OPDS_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".cbz": "application/vnd.comicbook+zip",
    ".epub": "application/epub+zip",
    ".mobi": "application/x-mobipocket-ebook",
    ".azw3": "application/vnd.amazon.ebook",
}


def user_data_dir(username):
    root = Path(os.getenv("JM_DATA_ROOT", "/data/users")) / username
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def user_library_dir(username):
    root = user_data_dir(username) / "pdf"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


PDF_OPTIMIZE_LOCK = threading.Lock()
PDF_OPTIMIZING = set()


def pdf_marker_path(pdf_path):
    return pdf_path.with_name(pdf_path.name + ".optimized.json")


def pdf_is_optimized(pdf_path):
    try:
        data = json.loads(pdf_marker_path(pdf_path).read_text(encoding="utf-8"))
        stat = pdf_path.stat()
        return data.get("size") == stat.st_size and data.get("mtime_ns") == stat.st_mtime_ns
    except (OSError, ValueError, TypeError):
        return False


def mark_pdf_optimized(pdf_path):
    stat = pdf_path.stat()
    pdf_marker_path(pdf_path).write_text(
        json.dumps({"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}),
        encoding="utf-8",
    )


def optimize_pdf(pdf_path):
    """Recompress comic images and linearize a PDF for fast network viewing."""
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf" or pdf_is_optimized(pdf_path):
        return None
    key = str(pdf_path.resolve())
    with PDF_OPTIMIZE_LOCK:
        if key in PDF_OPTIMIZING:
            return None
        PDF_OPTIMIZING.add(key)

    temp_path = pdf_path.with_name(f".{pdf_path.stem}.optimizing.pdf")
    original_size = pdf_path.stat().st_size
    try:
        gs = shutil.which("gs")
        if gs:
            nice = shutil.which("nice")
            command = ([nice, "-n", "15"] if nice else []) + [
                gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/ebook",
                "-dNOPAUSE", "-dQUIET", "-dBATCH", "-dSAFER", "-dFastWebView=true",
                "-dNumRenderingThreads=1", "-dMaxBitmap=32000000",
                "-dBufferSpace=16000000", "-dBandBufferSpace=8000000",
                "-dDetectDuplicateImages=true", "-dCompressFonts=true",
                "-dDownsampleColorImages=true", "-dColorImageResolution=180",
                "-dDownsampleGrayImages=true", "-dGrayImageResolution=180",
                "-dDownsampleMonoImages=true", "-dMonoImageResolution=300",
                "-dAutoFilterColorImages=false", "-dColorImageFilter=/DCTEncode", "-dJPEGQ=82",
                f"-sOutputFile={temp_path}", str(pdf_path),
            ]
            subprocess.run(command, check=True, timeout=3600, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        else:
            import pikepdf
            with pikepdf.open(pdf_path) as pdf:
                pdf.save(temp_path, linearize=True, compress_streams=True)

        if not temp_path.is_file() or temp_path.stat().st_size < 1024:
            raise RuntimeError("PDF optimizer produced an invalid file")
        optimized_size = temp_path.stat().st_size
        os.replace(temp_path, pdf_path)
        mark_pdf_optimized(pdf_path)
        saved = original_size - optimized_size
        percent = (saved / original_size * 100) if original_size else 0
        STATE.log(
            f"PDF optimized: {pdf_path.name} "
            f"{original_size / 1048576:.1f} MB -> {optimized_size / 1048576:.1f} MB ({percent:.1f}% smaller)\n"
        )
        return original_size, optimized_size
    except Exception as exc:
        STATE.log(f"PDF optimization failed for {pdf_path.name}: {exc}\n")
        return None
    finally:
        with contextlib.suppress(OSError):
            temp_path.unlink()
        with PDF_OPTIMIZE_LOCK:
            PDF_OPTIMIZING.discard(key)


def pdf_snapshot(library_dir):
    return {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in Path(library_dir).rglob("*.pdf")
        if path.is_file()
    }


def optimize_changed_pdfs(library_dir, before=None):
    before = before or {}
    for path, signature in pdf_snapshot(library_dir).items():
        if before.get(path) != signature or not pdf_is_optimized(path):
            optimize_pdf(path)


def optimize_existing_pdfs():
    if os.getenv("JM_PDF_OPTIMIZE", "true").lower() != "true":
        return
    users_root = Path(os.getenv("JM_DATA_ROOT", "/data/users"))
    if users_root.exists():
        time.sleep(to_int(os.getenv("JM_PDF_OPTIMIZE_START_DELAY"), 90))
        for library_dir in users_root.glob("*/pdf"):
            optimize_changed_pdfs(library_dir)


def safe_library_path(relative_path="", library_root=None):
    root = Path(library_root or STATE.get_library_dir()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / unquote(relative_path or "")).resolve()
    if os.path.commonpath((str(root), str(target))) != str(root):
        raise ValueError("OPDS path is outside the library")
    return root, target


def opds_feed(relative_path, base_url, library_root=None):
    root, directory = safe_library_path(relative_path, library_root)
    if not directory.is_dir():
        raise FileNotFoundError(relative_path)

    atom = "http://www.w3.org/2005/Atom"
    opds_profile = "application/atom+xml;profile=opds-catalog;kind=acquisition"
    ET.register_namespace("", atom)
    feed = ET.Element(f"{{{atom}}}feed")
    ET.SubElement(feed, f"{{{atom}}}id").text = f"urn:jmcomic:opds:{quote(relative_path or 'root')}"
    ET.SubElement(feed, f"{{{atom}}}title").text = "JMComic Library" if not relative_path else directory.name
    ET.SubElement(feed, f"{{{atom}}}updated").text = datetime.now().astimezone().isoformat(timespec="seconds")
    ET.SubElement(feed, f"{{{atom}}}link", {
        "rel": "self",
        "href": f"{base_url}/opds/catalog?path={quote(relative_path)}",
        "type": opds_profile,
    })
    if directory != root:
        parent_rel = directory.parent.relative_to(root).as_posix()
        ET.SubElement(feed, f"{{{atom}}}link", {
            "rel": "up",
            "href": f"{base_url}/opds/catalog?path={quote(parent_rel)}",
            "type": opds_profile,
        })

    for item in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if item.name.startswith("."):
            continue
        rel = item.relative_to(root).as_posix()
        if item.is_dir():
            entry = ET.SubElement(feed, f"{{{atom}}}entry")
            ET.SubElement(entry, f"{{{atom}}}id").text = f"urn:jmcomic:dir:{quote(rel)}"
            ET.SubElement(entry, f"{{{atom}}}title").text = item.name
            ET.SubElement(entry, f"{{{atom}}}updated").text = datetime.fromtimestamp(
                item.stat().st_mtime
            ).astimezone().isoformat(timespec="seconds")
            ET.SubElement(entry, f"{{{atom}}}link", {
                "rel": "subsection",
                "href": f"{base_url}/opds/catalog?path={quote(rel)}",
                "type": opds_profile,
            })
            continue

        mime_type = OPDS_MIME_TYPES.get(item.suffix.lower())
        if mime_type is None:
            continue
        entry = ET.SubElement(feed, f"{{{atom}}}entry")
        ET.SubElement(entry, f"{{{atom}}}id").text = f"urn:jmcomic:file:{quote(rel)}"
        ET.SubElement(entry, f"{{{atom}}}title").text = item.stem
        ET.SubElement(entry, f"{{{atom}}}updated").text = datetime.fromtimestamp(
            item.stat().st_mtime
        ).astimezone().isoformat(timespec="seconds")
        ET.SubElement(entry, f"{{{atom}}}content", {"type": "text"}).text = f"{item.stat().st_size} bytes"
        ET.SubElement(entry, f"{{{atom}}}link", {
            "rel": "http://opds-spec.org/acquisition",
            "href": f"{base_url}/opds/file?path={quote(rel)}",
            "type": mime_type,
        })

    return ET.tostring(feed, encoding="utf-8", xml_declaration=True)


def to_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def album_id_from_text(text):
    aid = "".join(re.findall(r"\d+", str(text)))
    if not aid:
        raise ValueError("没有找到数字 ID")
    return aid


def build_option_yaml(data, pdf_level="album"):
    base_dir = str(data.get("baseDir") or "downloads").replace("\\", "/")
    proxy = data.get("proxy") or "system"
    if str(proxy).lower() in {"none", "null", ""}:
        proxy = "null"
    hook = "after_photo" if pdf_level == "photo" else "after_album"
    filename_rule = "Pid" if pdf_level == "photo" else "Aname"
    return f"""log: true
client:
  impl: {data.get("clientImpl") or "api"}
  async_impl: async_api
  retry_times: 5
  cache: null
  postman:
    meta_data:
      proxies: {proxy}
      cookies: null

download:
  cache: true
  image:
    decode: true
    suffix: null
  threading:
    image: {to_int(data.get("imageThreads"), 30)}
    photo: {to_int(data.get("photoThreads"), os.cpu_count() or 4)}

dir_rule:
  base_dir: {base_dir}/.pdf-temp
  rule: Bd / Aid / Pindex

plugins:
  valid: raise
  {hook}:
    - plugin: img2pdf
      kwargs:
        pdf_dir: {base_dir}/pdf
        filename_rule: {filename_rule}
        delete_original_file: true
"""


def option_from(data, pdf_level="album"):
    return jmcomic.create_option_by_str(build_option_yaml(data, pdf_level))


def client_from(data):
    return option_from(data).new_jm_client()


def rows_from_page(page):
    return [
        {"id": aid, "title": info.get("name", ""), "tags": info.get("tags", [])}
        for aid, info in page.content
    ]


def album_detail_text(album):
    lines = [
        f"标题: {album.name}",
        f"ID: JM{album.album_id}",
        f"页数: {album.page_count}",
        f"发布: {album.pub_date}",
        f"更新: {album.update_date}",
        f"观看: {album.views}",
        f"点赞: {album.likes}",
        f"评论: {album.comment_count}",
        f"作者: {', '.join(album.authors) if album.authors else '-'}",
        f"标签: {', '.join(album.tags) if album.tags else '-'}",
        "章节:",
    ]
    for pid, index, title in album.episode_list:
        lines.append(f"  {index}. {title} ({pid})")
    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    server_version = "JMComicWebUI/1.0"

    def log_message(self, fmt, *args):
        STATE.log((fmt % args) + "\n")

    def send_bytes(self, body, content_type="application/json; charset=utf-8"):
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def read_json(self):
        length = int(self.headers.get("content-length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def authenticated(self):
        return self.session_user() is not None

    def session_user(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("jm_session")
        return validate_session(morsel.value, self.server.session_secret) if morsel else None

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def serve_login(self, error=""):
        page = LOGIN_HTML.replace("{{ERROR}}", html.escape(error))
        self.send_bytes(page.encode("utf-8"), "text/html; charset=utf-8")

    def serve_register(self, error=""):
        page = REGISTER_HTML.replace("{{ERROR}}", html.escape(error))
        self.send_bytes(page.encode("utf-8"), "text/html; charset=utf-8")

    def serve_account(self, error="", success=""):
        username = self.session_user() or ""
        page = ACCOUNT_HTML.replace("{{ERROR}}", html.escape(error))
        page = page.replace("{{SUCCESS}}", html.escape(success))
        page = page.replace("{{USERNAME}}", html.escape(username))
        page = page.replace("{{ROLE}}", html.escape(user_role(username) or "user"))
        self.send_bytes(page.encode("utf-8"), "text/html; charset=utf-8")

    def handle_login(self):
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        username = form.get("username", [""])[0]
        password = form.get("password", [""])[0]
        address = self.client_address[0]
        if not STATE.login_allowed(address):
            self.serve_login("尝试次数过多，请 5 分钟后再试")
            return
        valid = verify_user(username, password)
        if not valid:
            STATE.record_login_failure(address)
            self.serve_login("用户名或密码错误")
            return
        STATE.clear_login_failures(address)
        token = make_session(username, self.server.session_secret)
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", f"jm_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_register(self):
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        username = form.get("username", [""])[0].strip()
        password = form.get("password", [""])[0]
        confirm = form.get("confirm", [""])[0]
        if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username):
            self.serve_register("用户名需为 3-32 位字母、数字或下划线")
            return
        if len(password) < 10:
            self.serve_register("密码至少需要 10 位")
            return
        if password != confirm:
            self.serve_register("两次输入的密码不一致")
            return
        if not create_user(username, password):
            self.serve_register("用户名已存在")
            return
        self.redirect("/login?registered=1")

    def handle_change_password(self):
        username = self.session_user()
        if not username:
            self.redirect("/login")
            return
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        current = form.get("current_password", [""])[0]
        new_password = form.get("new_password", [""])[0]
        confirm = form.get("confirm", [""])[0]
        if not verify_user(username, current):
            self.serve_account("当前密码错误")
            return
        if len(new_password) < 10:
            self.serve_account("新密码至少需要 10 位")
            return
        if new_password != confirm:
            self.serve_account("两次输入的新密码不一致")
            return
        update_password(username, new_password)
        self.serve_account(success="密码已更新")

    def send_pdf_file(self, relative_path, library_root):
        _, filepath = safe_library_path(relative_path, library_root)
        if not filepath.is_file() or filepath.suffix.lower() != ".pdf":
            self.send_error(404)
            return
        if os.getenv("JM_ACCEL_REDIRECT", "").lower() == "true":
            data_root = Path(os.getenv("JM_DATA_ROOT", "/data/users")).resolve()
            internal_path = filepath.relative_to(data_root).as_posix()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(filepath.name)}")
            self.send_header("X-Accel-Redirect", "/_protected_pdf/" + quote(internal_path, safe="/"))
            self.end_headers()
            return
        size = filepath.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes="):
            start_text, _, end_text = range_header[6:].partition("-")
            start = int(start_text or 0)
            end = min(int(end_text or end), end)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(filepath.name)}")
        self.end_headers()
        with open(filepath, "rb") as file:
            file.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = file.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def opds_authenticated_user(self):
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Basic "):
            return None
        try:
            raw = base64.b64decode(authorization[6:]).decode("utf-8")
            username, password = raw.split(":", 1)
        except Exception:
            return None
        return username if verify_user(username, password) else None

    def require_opds_auth(self):
        username = self.opds_authenticated_user()
        if username:
            return username
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="JMComic OPDS", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("OPDS authentication required".encode("utf-8"))
        return None

    def opds_base_url(self):
        return f"http://{self.headers.get('Host') or f'127.0.0.1:{self.server.server_port}'}"

    def send_opds_file(self, relative_path, library_root):
        _, filepath = safe_library_path(relative_path, library_root)
        if not filepath.is_file() or filepath.suffix.lower() not in OPDS_MIME_TYPES:
            self.send_error(404)
            return
        if os.getenv("JM_ACCEL_REDIRECT", "").lower() == "true":
            data_root = Path(os.getenv("JM_DATA_ROOT", "/data/users")).resolve()
            internal_path = filepath.relative_to(data_root).as_posix()
            self.send_response(200)
            self.send_header("Content-Type", OPDS_MIME_TYPES.get(filepath.suffix.lower(), "application/octet-stream"))
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filepath.name)}")
            self.send_header("X-Accel-Redirect", "/_protected_pdf/" + quote(internal_path, safe="/"))
            self.end_headers()
            return
        stat = filepath.stat()
        self.send_response(200)
        self.send_header("Content-Type", OPDS_MIME_TYPES.get(filepath.suffix.lower()) or
                         mimetypes.guess_type(filepath.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filepath.name)}")
        self.end_headers()
        with open(filepath, "rb") as file:
            while chunk := file.read(1024 * 1024):
                self.wfile.write(chunk)

    def do_GET(self):
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)
        if path == "/login":
            self.serve_login()
        elif path == "/register":
            self.serve_register()
        elif path in {"/opds", "/opds/", "/opds/catalog"}:
            opds_user = self.require_opds_auth()
            if not opds_user:
                return
            relative_path = query.get("path", [""])[0]
            try:
                body = opds_feed(relative_path, self.opds_base_url(), user_library_dir(opds_user))
            except (FileNotFoundError, ValueError):
                self.send_error(404)
                return
            self.send_bytes(body, "application/atom+xml;profile=opds-catalog;kind=acquisition; charset=utf-8")
        elif path == "/opds/file":
            opds_user = self.require_opds_auth()
            if not opds_user:
                return
            self.send_opds_file(query.get("path", [""])[0], user_library_dir(opds_user))
        elif not self.authenticated():
            self.redirect("/login")
        elif path == "/account":
            self.serve_account()
        elif path == "/reader":
            username = self.session_user()
            relative_path = query.get("path", [""])[0]
            _, filepath = safe_library_path(relative_path, user_library_dir(username))
            if not filepath.is_file() or filepath.suffix.lower() != ".pdf":
                self.send_error(404)
                return
            reader = (ROOT / "reader.html").read_text(encoding="utf-8")
            reader = reader.replace("{{TITLE}}", html.escape(filepath.stem))
            reader = reader.replace("{{PDF_URL}}", "/files/pdf?path=" + quote(relative_path))
            self.send_bytes(reader.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/files/pdf":
            self.send_pdf_file(query.get("path", [""])[0], user_library_dir(self.session_user()))
        elif path == "/api/library":
            root = user_library_dir(self.session_user())
            root.mkdir(parents=True, exist_ok=True)
            books = []
            for filepath in root.rglob("*.pdf"):
                if not filepath.is_file():
                    continue
                stat = filepath.stat()
                books.append({
                    "title": filepath.stem,
                    "path": filepath.relative_to(root).as_posix(),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                })
            books.sort(key=lambda item: item["modified"], reverse=True)
            self.send_json({"ok": True, "books": books})
        elif path == "/":
            self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/logs":
            self.send_json({"ok": True, "text": STATE.text()})
        elif path == "/api/info":
            urls = getattr(self.server, "public_urls", [])
            self.send_json({
                "ok": True,
                "urls": urls,
                "opdsUrls": [url.rstrip("/") + "/opds" for url in urls],
                "opdsUsername": self.server.opds_username,
            })
        elif path == "/manifest.webmanifest":
            manifest = {
                "name": "JMComic Crawler UI",
                "short_name": "JMComic",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#f5f7f8",
                "theme_color": "#0f766e",
            }
            self.send_bytes(json.dumps(manifest, ensure_ascii=False).encode("utf-8"),
                            "application/manifest+json; charset=utf-8")
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/login":
            self.handle_login()
            return
        if path == "/register":
            self.handle_register()
            return
        if path == "/account/password":
            self.handle_change_password()
            return
        if path == "/logout":
            self.send_response(303)
            self.send_header("Location", "/login")
            self.send_header("Set-Cookie", "jm_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not self.authenticated():
            self.send_response(401)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "登录已失效"}, ensure_ascii=False).encode("utf-8"))
            return
        try:
            data = self.read_json()
            data["baseDir"] = str(user_data_dir(self.session_user()))
            with contextlib.redirect_stdout(LogStream()), contextlib.redirect_stderr(LogStream()):
                result = self.dispatch(path, data)
            self.send_json({"ok": True, **(result or {})})
        except Exception as exc:
            STATE.log(traceback.format_exc())
            self.send_json({"ok": False, "error": str(exc)})

    def dispatch(self, path, data):
        if path == "/api/library/delete":
            paths = data.get("paths") or []
            if isinstance(paths, str):
                paths = [paths]
            paths = list(dict.fromkeys(str(item) for item in paths if str(item).strip()))
            if not paths:
                raise ValueError("请选择要删除的 PDF")
            if len(paths) > 100:
                raise ValueError("一次最多删除 100 本书")

            root = user_library_dir(self.session_user())
            targets = []
            for relative_path in paths:
                _, target = safe_library_path(relative_path, root)
                if target.suffix.lower() != ".pdf" or not target.is_file():
                    raise ValueError(f"PDF 不存在: {relative_path}")
                with PDF_OPTIMIZE_LOCK:
                    if str(target.resolve()) in PDF_OPTIMIZING:
                        raise ValueError(f"PDF 正在优化，请稍后再删除: {target.name}")
                targets.append(target)

            freed = 0
            for target in targets:
                freed += target.stat().st_size
                target.unlink()
                with contextlib.suppress(OSError):
                    pdf_marker_path(target).unlink()
                parent = target.parent
                while parent != root:
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent
            STATE.log(f"Deleted {len(targets)} PDF(s), freed {freed / 1048576:.1f} MB\n")
            return {"deleted": len(targets), "freed": freed}
        if path == "/api/option-text":
            return {"text": build_option_yaml(data)}
        if path == "/api/save-option":
            path = data.get("optionPath") or str(ROOT / "option-ui.yml")
            Path(path).write_text(build_option_yaml(data), encoding="utf-8")
            STATE.log(f"已保存配置: {path}\n")
            return {"path": path}
        if path == "/api/download":
            ids = parse_ids(data.get("ids", ""))
            if not ids:
                raise ValueError("请输入至少一个下载 ID")
            mode = data.get("mode") or "album"
            album_ids, photo_ids = [], []
            for item in ids:
                low = item.lower()
                if mode == "photo" or low.startswith("p"):
                    photo_ids.append(item[1:] if low.startswith("p") else item)
                elif mode == "mixed" and low.startswith("a"):
                    album_ids.append(item[1:])
                else:
                    album_ids.append(item)
            username = self.session_user()
            def download_task():
                library_dir = user_library_dir(username)
                before = pdf_snapshot(library_dir)
                if album_ids:
                    album_option = option_from(data, "album")
                    jmcomic.download_album(album_ids if len(album_ids) > 1 else album_ids[0], album_option)
                if photo_ids:
                    photo_option = option_from(data, "photo")
                    jmcomic.download_photo(photo_ids if len(photo_ids) > 1 else photo_ids[0], photo_option)
                if os.getenv("JM_PDF_OPTIMIZE", "true").lower() == "true":
                    optimize_changed_pdfs(library_dir, before)

            run_background(f"下载并生成 PDF：{len(ids)} 项", download_task)
            return {"queued": len(ids)}
        if path == "/api/detail":
            album = client_from(data).get_album_detail(album_id_from_text(data.get("text", "")))
            return {"detail": album_detail_text(album)}
        if path == "/api/cover":
            aid = album_id_from_text(data.get("text", ""))
            out = Path(data.get("baseDir") or "downloads") / "covers"
            out.mkdir(parents=True, exist_ok=True)
            save_path = out / f"{aid}.jpg"
            client_from(data).download_album_cover(aid, str(save_path))
            STATE.log(f"封面已保存: {save_path}\n")
            return {"path": str(save_path)}
        if path == "/api/search":
            page = client_from(data).search(
                search_query=data.get("query", ""),
                page=to_int(data.get("page"), 1),
                main_tag=to_int(data.get("mainTag"), 0),
                order_by=ORDER_OPTIONS.get(data.get("order"), JmMagicConstants.ORDER_BY_LATEST),
                time=TIME_OPTIONS.get(data.get("time"), JmMagicConstants.TIME_ALL),
                category=CATEGORY_OPTIONS.get(data.get("category"), JmMagicConstants.CATEGORY_ALL),
                sub_category=SUB_CATEGORY_OPTIONS.get(data.get("subCategory")),
            )
            return {"rows": rows_from_page(page), "total": page.total, "pageCount": page.page_count}
        if path == "/api/browse":
            client = client_from(data)
            page_no = to_int(data.get("page"), 1)
            category = CATEGORY_OPTIONS.get(data.get("category"), JmMagicConstants.CATEGORY_ALL)
            mode = data.get("mode")
            if mode == "day":
                page = client.day_ranking(page_no, category)
            elif mode == "week":
                page = client.week_ranking(page_no, category)
            elif mode == "month":
                page = client.month_ranking(page_no, category)
            else:
                page = client.categories_filter(
                    page=page_no,
                    time=TIME_OPTIONS.get(data.get("time"), JmMagicConstants.TIME_ALL),
                    category=category,
                    order_by=ORDER_OPTIONS.get(data.get("order"), JmMagicConstants.ORDER_BY_VIEW),
                    sub_category=SUB_CATEGORY_OPTIONS.get(data.get("subCategory")),
                )
            return {"rows": rows_from_page(page), "total": page.total, "pageCount": page.page_count}
        if path == "/api/favorites":
            page = client_from(data).favorite_folder(
                page=to_int(data.get("page"), 1),
                order_by=ORDER_OPTIONS.get(data.get("order"), JmMagicConstants.ORDER_BY_LATEST),
                folder_id=data.get("folderId") or "0",
                username=data.get("username") or "",
            )
            folders = [{"id": fid, "name": name} for fid, name in page.iter_folder_id_name()]
            return {"rows": rows_from_page(page), "folders": folders}
        if path == "/api/export-favorites":
            page = client_from(data).favorite_folder(
                page=to_int(data.get("page"), 1),
                order_by=ORDER_OPTIONS.get(data.get("order"), JmMagicConstants.ORDER_BY_LATEST),
                folder_id=data.get("folderId") or "0",
                username=data.get("username") or "",
            )
            out = Path(data.get("baseDir") or "downloads")
            out.mkdir(parents=True, exist_ok=True)
            csv_path = out / "favorites.csv"
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["album_id", "title", "tags"])
                for aid, info in page.content:
                    writer.writerow([aid, info.get("name", ""), " ".join(info.get("tags", []))])
            STATE.log(f"已导出: {csv_path}\n")
            return {"path": str(csv_path)}
        raise ValueError(f"unknown api: {path}")


def free_port(preferred):
    with socket.socket() as s:
        with contextlib.suppress(OSError):
            s.bind(("0.0.0.0", preferred))
            return preferred
    with socket.socket() as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--admin-user", default=os.getenv("JM_ADMIN_USER", "admin"))
    parser.add_argument("--admin-password", default=os.getenv("JM_ADMIN_PASSWORD", "ChangeMe@2026"))
    parser.add_argument("--session-secret", default=os.getenv("JM_SESSION_SECRET", ""))
    parser.add_argument("--opds-user", default=os.getenv("JM_OPDS_USER", ""))
    parser.add_argument("--opds-password", default=os.getenv("JM_OPDS_PASSWORD", ""))
    parser.add_argument("--library-dir", default=os.getenv("JM_LIBRARY_DIR", "/data/pdf"))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    init_user_db(args.admin_user, args.admin_password)
    port = free_port(args.port)
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.admin_username = args.admin_user
    server.admin_password = args.admin_password
    server.session_secret = args.session_secret or secrets.token_urlsafe(48)
    server.opds_username = args.opds_user or args.admin_user
    server.opds_password = args.opds_password or args.admin_password
    STATE.set_library_dir(args.library_dir)
    url = f"http://127.0.0.1:{port}/"
    server.public_urls = [url, *local_urls(port)]
    STATE.log("JMComic Crawler UI 已启动:\n" + "\n".join(server.public_urls) + "\n")
    STATE.log(f"JMComic Crawler UI 已启动: {url}\n")
    run_background("optimize existing PDFs", optimize_existing_pdfs)
    if args.self_test:
        print("self-test ok")
        server.server_close()
        return
    if not args.no_browser:
        webbrowser.open(url)
    print(f"JMComic Crawler UI: {url}")
    print(f"OPDS: {url.rstrip('/')}/opds")
    print(f"OPDS 用户名: {server.opds_username}")
    print(f"OPDS 密码: {server.opds_password}")
    for public_url in server.public_urls[1:]:
        print(f"手机访问: {public_url}")
    print("关闭这个窗口即可退出。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
