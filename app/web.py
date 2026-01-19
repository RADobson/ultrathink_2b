import hmac
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.constants import CATEGORIES

VAULT_ROOT = Path(os.environ.get("VAULT_PATH", "/vault")).resolve()
WEB_USERNAME = os.environ.get("WEB_USERNAME", "admin")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD")
WEB_SECRET = os.environ.get("WEB_SECRET") or secrets.token_hex(32)

if not WEB_PASSWORD:
    raise RuntimeError("WEB_PASSWORD is required for web access")

VAULT_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=WEB_SECRET, same_site="lax")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def _is_authed(request: Request) -> bool:
    return request.session.get("user") == WEB_USERNAME


def _require_login(request: Request) -> Optional[RedirectResponse]:
    if not _is_authed(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _resolve_path(rel_path: str) -> Path:
    rel_path = (rel_path or "").strip().lstrip("/")
    path = (VAULT_ROOT / rel_path).resolve()
    if path == VAULT_ROOT or VAULT_ROOT in path.parents:
        return path
    raise HTTPException(status_code=400, detail="Invalid path")


def _relpath(path: Path) -> str:
    return str(path.relative_to(VAULT_ROOT))


def _default_note_content(path: Path) -> str:
    title = path.stem.replace("-", " ").title()
    category = path.parent.name
    note_type = category.lower() if category in CATEGORIES else "note"
    created = datetime.now().strftime("%Y-%m-%d")
    return (
        "---\n"
        f"type: {note_type}\n"
        "status: active\n"
        f"created: {created}\n"
        "---\n\n"
        f"# {title}\n\n"
    )


def _iter_md_files(root: Path):
    for file_path in root.rglob("*.md"):
        if file_path.is_file():
            yield file_path


@app.get("/login")
def login_page(request: Request):
    if _is_authed(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if hmac.compare_digest(username, WEB_USERNAME) and hmac.compare_digest(password, WEB_PASSWORD):
        request.session["user"] = WEB_USERNAME
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password."},
        status_code=401,
    )


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/")
def index(request: Request, path: str = ""):
    redirect = _require_login(request)
    if redirect:
        return redirect

    dir_path = _resolve_path(path)
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    dirs = []
    files = []
    for entry in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            dirs.append({"name": entry.name, "path": _relpath(entry)})
        elif entry.is_file() and entry.suffix.lower() == ".md":
            files.append({"name": entry.name, "path": _relpath(entry)})

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "path": _relpath(dir_path) if dir_path != VAULT_ROOT else "",
            "dirs": dirs,
            "files": files,
        },
    )


@app.get("/edit")
def edit_page(request: Request, path: str):
    redirect = _require_login(request)
    if redirect:
        return redirect

    file_path = _resolve_path(path)
    if file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Only markdown files are supported")

    if file_path.exists():
        content = file_path.read_text()
        is_new = False
    else:
        content = _default_note_content(file_path)
        is_new = True

    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "path": _relpath(file_path),
            "content": content,
            "is_new": is_new,
        },
    )


@app.post("/edit")
def save_edit(request: Request, path: str = Form(...), content: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect

    path = path.strip()
    if not path.endswith(".md"):
        path += ".md"

    file_path = _resolve_path(path)
    if file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Only markdown files are supported")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return RedirectResponse(url=f"/edit?path={_relpath(file_path)}", status_code=303)


@app.post("/delete")
def delete_file(request: Request, path: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect

    file_path = _resolve_path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Only markdown files are supported")

    parent = file_path.parent
    file_path.unlink()
    return RedirectResponse(url=f"/?path={_relpath(parent)}", status_code=303)


@app.get("/search")
def search(request: Request, q: str = ""):
    redirect = _require_login(request)
    if redirect:
        return redirect

    query = q.strip()
    results = []
    if query:
        q_lower = query.lower()
        for file_path in _iter_md_files(VAULT_ROOT):
            try:
                text = file_path.read_text()
            except Exception:
                continue
            if q_lower in file_path.name.lower() or q_lower in text.lower():
                snippet = ""
                for line in text.splitlines():
                    if q_lower in line.lower():
                        snippet = line.strip()
                        break
                results.append(
                    {
                        "name": file_path.name,
                        "path": _relpath(file_path),
                        "snippet": snippet,
                    }
                )

    return templates.TemplateResponse(
        "search.html",
        {"request": request, "query": query, "results": results},
    )
