from __future__ import annotations

import asyncio
import ast
import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from nicegui import app

from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME
from utils.json_cleaner import clean_json_text

from controllers.object_controller import ObjectController
from controllers.attribute_controller import AttributeController
from controllers.method_controller import MethodController
from controllers.usecase_controller import UsecaseController
from controllers.event_list_controller import EventListController
from controllers.event_controller import EventController

from controllers.blueprint_state_controller import BlueprintStateController
from controllers.project_controller import ProjectController


# =========================================================
# Data model
# =========================================================
@dataclass
class CodeAgentInput:
    project_id: int
    project_name: str
    project_description: str
    tech_stack: Dict[str, Any]
    package_name: str
    mode: str  # "cover" | "patch"
    patch_instruction: str = ""
    existing_files: Optional[List[Dict[str, str]]] = None


# =========================================================
# Core helpers (shared)
# =========================================================
def _compact_tech_stack(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ tech_stack 一律從 Project 欄位組裝（你的 projects 表才有這些欄位）
    - frontend_language / platform / library
    - backend_language / platform / library
    - architecture
    """
    tech_stack = {
        "frontend_language": project.get("frontend_language"),
        "frontend_platform": project.get("frontend_platform"),
        "frontend_library": project.get("frontend_library"),
        "backend_language": project.get("backend_language"),
        "backend_platform": project.get("backend_platform"),
        "backend_library": project.get("backend_library"),
        "architecture": project.get("architecture"),
        # 你原本 prompt 會用 database；你目前是把 architecture 當 DB/架構來源也 OK
        "database": project.get("database") or project.get("architecture"),
    }
    return {k: v for k, v in tech_stack.items() if v is not None and str(v).strip() != ""}


def _normalize_lang(x: Any) -> str:
    s = (str(x or "")).strip().lower()
    if s in ("py", "python3", "python-async"):
        return "python"
    if s in ("node", "nodejs", "javascript", "js", "typescript", "ts"):
        return "node"
    if s in ("golang",):
        return "go"
    return s or "python"


def _is_safe_path(path: str) -> bool:
    if not path or path.startswith("/") or ".." in path:
        return False
    path = path.replace("\\", "/").strip()
    if path.startswith("/"):
        return False
    if "//" in path:
        return False
    return True


def _safe_json_load(text: str) -> Dict[str, Any]:
    text = clean_json_text(text)
    return json.loads(text)


async def _repair_to_valid_json(original_text: str) -> Dict[str, Any]:
    fixer_prompt = f"""
你是一個 JSON 修復器。請把下面文字改寫成「合法 JSON」，只能輸出 JSON 本體（不可加入任何解釋）。
輸出必須包含 key "files"，且每個 content 必須是合法 JSON 字串（換行用 \\n）。

【待修復文字開始】
{original_text}
【待修復文字結束】
"""
    payload_fix = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是嚴格的 JSON 修復器，只輸出 JSON。"},
            {"role": "user", "content": fixer_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "max_tokens": 4096,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=HEADERS, json=payload_fix, timeout=120) as resp:
            data = await resp.json()

    text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    return _safe_json_load(text)


def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    d: Dict[str, Any] = {}
    for k in dir(obj):
        if k.startswith("_"):
            continue
        if k in ("metadata", "registry", "sa_instance_state"):
            continue
        try:
            v = getattr(obj, k)
        except Exception:
            continue
        if callable(v):
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            d[k] = v
    return d


def _jpg_bytes_to_data_url(jpg_bytes: bytes) -> str:
    b64 = base64.b64encode(jpg_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _merge_project_preferring_db(base: Dict[str, Any], db: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ 以 DB(Project) 為 single source of truth：
    - db 的非空欄位覆蓋 base（base 可能來自 app.storage 或 project_meta）
    """
    merged = dict(base or {})
    for k, v in (db or {}).items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        merged[k] = v
    return merged


# =========================================================
# Controller compatibility helpers (shared)
# =========================================================
async def _safe_list_by_object_ids(controller_cls: Any, project_id: int, object_ids: List[int]) -> List[Any]:
    if not object_ids:
        return []

    fn = getattr(controller_cls, "list_by_object_ids", None)
    if callable(fn):
        return await fn(object_ids)

    fn = getattr(controller_cls, "list_by_object_id", None)
    if callable(fn):
        tasks = [fn(int(oid)) for oid in object_ids]
        res = await asyncio.gather(*tasks, return_exceptions=True)
        out: List[Any] = []
        for r in res:
            if isinstance(r, Exception):
                continue
            if isinstance(r, list):
                out.extend(r)
            elif r is not None:
                out.append(r)
        return out

    fn = getattr(controller_cls, "list", None)
    if callable(fn):
        ok_object_id = True
        try:
            tasks = [fn(object_id=int(oid)) for oid in object_ids]  # type: ignore
        except TypeError:
            ok_object_id = False

        if ok_object_id:
            res = await asyncio.gather(*tasks, return_exceptions=True)  # type: ignore
            out: List[Any] = []
            for r in res:
                if isinstance(r, Exception):
                    continue
                if isinstance(r, list):
                    out.extend(r)
                elif r is not None:
                    out.append(r)
            return out

        rows: List[Any] = []
        try:
            rows = await fn(project_id=project_id)  # type: ignore
        except TypeError:
            try:
                rows = await fn()  # type: ignore
            except Exception:
                rows = []

        want = set(int(x) for x in object_ids)
        out = []
        for row in rows or []:
            oid = getattr(row, "object_id", None)
            if oid is None:
                continue
            try:
                if int(oid) in want:
                    out.append(row)
            except Exception:
                continue
        return out

    return []


async def _safe_list_event_lists_by_usecase_ids(project_id: int, usecase_ids: List[int]) -> List[Any]:
    if not usecase_ids:
        return []

    fn = getattr(EventListController, "list_by_use_case_ids", None)
    if callable(fn):
        return await fn(usecase_ids)

    fn = getattr(EventListController, "list", None)
    if callable(fn):
        ok_param = True
        try:
            tasks = [fn(use_case_id=int(uid)) for uid in usecase_ids]  # type: ignore
        except TypeError:
            ok_param = False

        if ok_param:
            res = await asyncio.gather(*tasks, return_exceptions=True)
            out: List[Any] = []
            for r in res:
                if isinstance(r, Exception):
                    continue
                if isinstance(r, list):
                    out.extend(r)
                elif r is not None:
                    out.append(r)
            return out

        rows: List[Any] = []
        try:
            rows = await fn(project_id=project_id)  # type: ignore
        except TypeError:
            try:
                rows = await fn()  # type: ignore
            except Exception:
                rows = []

        want = set(int(x) for x in usecase_ids)
        out = []
        for row in rows or []:
            uid = getattr(row, "use_case_id", None)
            if uid is None:
                continue
            try:
                if int(uid) in want:
                    out.append(row)
            except Exception:
                continue
        return out

    return []


async def _safe_list_events_by_event_list_ids(event_list_ids: List[int]) -> List[Any]:
    if not event_list_ids:
        return []

    fn = getattr(EventController, "list_by_event_list_ids", None)
    if callable(fn):
        return await fn(event_list_ids)

    fn = getattr(EventController, "list", None)
    if callable(fn):
        ok_param = True
        try:
            tasks = [fn(event_list_id=int(eid)) for eid in event_list_ids]  # type: ignore
        except TypeError:
            ok_param = False

        if ok_param:
            res = await asyncio.gather(*tasks, return_exceptions=True)
            out: List[Any] = []
            for r in res:
                if isinstance(r, Exception):
                    continue
                if isinstance(r, list):
                    out.extend(r)
                elif r is not None:
                    out.append(r)
            return out

        try:
            rows = await fn()  # type: ignore
        except Exception:
            rows = []

        want = set(int(x) for x in event_list_ids)
        out = []
        for row in rows or []:
            eid = getattr(row, "event_list_id", None)
            if eid is None:
                continue
            try:
                if int(eid) in want:
                    out.append(row)
            except Exception:
                continue
        return out

    return []


async def _collect_blueprint_context(project_id: int, limit: int = 6) -> List[Dict[str, Any]]:
    rows: List[Any] = []
    fn_list = getattr(BlueprintStateController, "list", None)
    if callable(fn_list):
        try:
            rows = await fn_list(project_id=int(project_id))  # type: ignore
        except TypeError:
            try:
                rows = await fn_list()  # type: ignore
            except Exception:
                rows = []
    else:
        rows = []

    if not rows:
        return []

    out: List[Dict[str, Any]] = []
    for it in (rows or []):
        try:
            pid = int(getattr(it, "project_id", -1))
        except Exception:
            pid = -1
        if pid != int(project_id):
            continue

        payload_json = getattr(it, "payload_json", "") or ""
        if isinstance(payload_json, str) and len(payload_json) > 12000:
            payload_json = payload_json[:12000] + "\n...[TRUNCATED]..."

        canvas = getattr(it, "canvas_jpg", None)
        data_url = None
        if isinstance(canvas, (bytes, bytearray)) and len(canvas) > 0:
            data_url = _jpg_bytes_to_data_url(bytes(canvas))

        out.append(
            {
                "id": getattr(it, "id", None),
                "screen_name": getattr(it, "screen_name", "") or "",
                "boundary_id": getattr(it, "boundary_id", None),
                "payload_json": payload_json,
                "has_canvas_jpg": bool(data_url),
                "canvas_data_url": data_url,
            }
        )

    return out[: max(0, int(limit))]


# =========================================================
# Engines
# =========================================================
class BaseEngine:
    async def generate(self, inp: CodeAgentInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class PythonEnterpriseEngine(BaseEngine):
    """
    你現有的 OpenAI 企業級 Python 生成流程（保留 blueprint + 多模態 + AST 驗證）
    """

    @staticmethod
    def _is_valid_python(code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    @staticmethod
    def _contains_forbidden_patterns(code: str) -> bool:
        forbidden_patterns = [
            r"\bpass\b",
            r"\bTODO\b",
            r"\bFlask\b",
            r"\bDjango\b",
            r"from\s+flask\b",
            r"import\s+flask\b",
            r"from\s+django\b",
            r"import\s+django\b",
            r"_store\s*=\s*\{\}",
            r"_user_store\s*=\s*\{\}",
            r"\bin[- ]memory\b",
            r"\bsqlite3\b",
        ]
        for pat in forbidden_patterns:
            if re.search(pat, code):
                return True
        return False

    @classmethod
    def _validate_main_py(cls, code: str) -> bool:
        must = [
            "from nicegui import ui",
            "ui.run",
        ]
        return all(m in code for m in must) and (not cls._contains_forbidden_patterns(code)) and cls._is_valid_python(code)

    @classmethod
    def _validate_minimum_set(cls, files: List[Dict[str, str]]) -> bool:
        has_main = any(f.get("path") == "main.py" for f in files)
        has_view = any((f.get("path") or "").startswith("views/") for f in files)
        has_controller = any((f.get("path") or "").startswith("controllers/") for f in files)
        has_flow = any((f.get("path") or "").startswith("flow_controllers/") for f in files)
        has_db = any((f.get("path") or "") == "controllers/db.py" for f in files)
        return has_main and has_view and has_controller and has_flow and has_db

    async def generate(self, inp: CodeAgentInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        bce_objects = ctx.get("bce_objects", [])
        event_data = ctx.get("event_data", {})
        blueprint_states = ctx.get("blueprint_states", [])
        counts = ctx.get("counts", {})

        prompt = f"""
你是一位企業級 Python 全端架構師與資深軟體工程師。

⚠️ 這不是示範專案：你必須輸出「可實際執行」且符合專案技術棧的程式碼。
⚠️ 嚴禁玩具骨架：不得用 pass 或 TODO 當作主要邏輯。

========================
【專案真實資料（必須遵守、不可臆測）】
========================
- 專案名稱：{inp.project_name}
- 專案說明：{inp.project_description}
- 技術棧設定：{json.dumps(inp.tech_stack, ensure_ascii=False)}
- package_name（參考用）：{inp.package_name}

- object_count = {counts.get("object_count", 0)}
- usecase_count = {counts.get("usecase_count", 0)}
- event_list_count = {counts.get("event_list_count", 0)}
- event_count = {counts.get("event_count", 0)}
- blueprint_count = {counts.get("blueprint_count", 0)}
- blueprint_canvas_count = {counts.get("blueprint_canvas_count", 0)}

【BCE Objects JSON（含 attributes、methods）】
{json.dumps(bce_objects, ensure_ascii=False)}

【UseCase + EventLists + Events（含三段式事件）】
{json.dumps(event_data, ensure_ascii=False)}

【Blueprint States（payload_json + has_canvas_jpg）】
{json.dumps([
    {k: b.get(k) for k in ("id", "screen_name", "boundary_id", "payload_json", "has_canvas_jpg")}
    for b in (blueprint_states or [])
], ensure_ascii=False)}

========================
【硬性技術規範（不可違反）】
========================
1) 必須使用 NiceGUI：
   - from nicegui import ui
   - views 必須用 ui.* 畫出畫面（不可只有 class 空殼）

2) 必須使用 async/await（controller、flow 至少核心操作要 async）

3) main.py 必須：
   - import NiceGUI ui
   - 註冊所有 UseCase 對應頁面
   - 最後必須呼叫 ui.run(...)

4) 嚴禁：
   - Flask / Django
   - 同步 SQLAlchemy（不得寫 create_engine / sessionmaker 同步模式）
   - sqlite3 直連
   - 假資料（不得用 dict/list 當作資料來源）
   - TODO / pass 作為主要邏輯
   - 臆測不存在欄位或自行改名（欄位必須對齊 BCE JSON / blueprint payload_json）

========================
【DB 強制規則（必須遵守，否則視為生成失敗）】
========================
- 你必須生成 controllers/db.py（不可省略）
- controllers/db.py 必須使用 async SQLAlchemy（sqlite+aiosqlite）：
  - create_async_engine("sqlite+aiosqlite:///./app.db")
  - async_sessionmaker
  - 提供 init_db() 做 create_all
  - 提供 get_session() 或 async context manager 讓 controller 使用 AsyncSession
- 任何涉及 data_table/data_fields 的功能：
  - controller 必須透過 AsyncSession 查詢/更新資料表
  - 禁止使用 dict/list 模擬資料庫

========================
【Blueprint 強制規則（必須遵守，違反視為生成失敗）】
========================
你同時收到：
1) Blueprint payload_json（元件 type/name/props/layout/data_table/data_fields）
2) Blueprint canvas_jpg（多張圖片）

【優先權（不可顛倒）】
A) payload_json 是「唯一權威 UI 規格」：你必須 100% 遵守元件清單與 layout(x,y,w,h)。
B) canvas 圖片只允許用於「微調」：字體大小、padding、間距、顏色等，不得推翻 payload_json 的元件/座標/大小/資料綁定。

【你必須做的事】
1) view 必須以 payload_json.components 為準建立元件：
   - Label / Input / Button / Table / Radio / Checkbox / Select / Image
2) view 版面必須採用「絕對定位」還原（1:1）：
   - 建立一個 ui.element('div') 當畫布容器，style: position: relative;
   - 需要 canvas 尺寸時：若 payload_json 無 canvas 寬高，先用「最大 x+w / y+h」推算 width/height
   - 每個元件外層包一個 ui.element('div') style:
       position:absolute; left:{{x}}px; top:{{y}}px; width:{{w}}px; height:{{h}}px;
3) 資料綁定必須落地：
   - 若 component.data_table 與 component.data_fields 有值：
     - controller 必須使用 async SQLAlchemy 查詢/更新對應 models.<table> 的欄位（欄位名必須對齊 data_fields）
4) JPG（圖片）僅供視覺微調參考，不得主導結構與座標。

========================
【架構與輸出限制（必須符合你系統白名單）】
========================
只允許輸出以下相對路徑（不可用 / 開頭，不可包含 ..）：
- models/...
- controllers/...
- views/...
- flow_controllers/...
- main.py
- README.md
- __init__.py（可選）

⚠️ 注意：path 不要加 "{inp.package_name}/" 前綴；直接用 "views/xxx_view.py" 這種格式。

========================
【生成要求（每個 UseCase 都要有）】
========================
對每個 UseCase 都生成三個檔案（命名要有語意）：
- controllers/<usecase>_controller.py
- flow_controllers/<usecase>_flow.py
- views/<usecase>_view.py

另外必須生成：
- controllers/db.py（必須存在）

規則：
- Controller：提供 async 的 list/add/update/delete
- Flow：負責串接 view 與 controller（不得包含 ui.*；不得直接 DB）
- View：NiceGUI 畫面，必須至少呈現：
  - UseCase 名稱/描述
  - 與 blueprint payload_json 對齊的元件
  - 呼叫 flow 的按鈕或操作入口
  - 版面以 payload_json 的 layout 還原（絕對定位 1:1）

========================
【輸出格式（只允許 JSON）】
========================
只能輸出 JSON，不得包含任何解釋文字。

格式：
{{
  "files": [
    {{
      "path": "views/example_view.py",
      "content": "完整可執行程式碼（換行用 \\n）"
    }}
  ]
}}
"""

        user_content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for b in (blueprint_states or []):
            url = b.get("canvas_data_url")
            if not url:
                continue
            user_content.append({"type": "image_url", "image_url": {"url": url}})

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "只輸出合法 JSON，不得包含說明文字。"},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        allowed_prefixes = ("models/", "controllers/", "views/", "flow_controllers/")
        allowed_files = ("main.py", "README.md", "__init__.py")

        for _ in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(API_URL, headers=HEADERS, json=payload, timeout=120) as resp:
                        if resp.status != 200:
                            await asyncio.sleep(1.0)
                            continue
                        data = await resp.json()

                text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

                try:
                    obj = _safe_json_load(text)
                except Exception:
                    obj = await _repair_to_valid_json(text)

                files = obj.get("files", [])
                if not isinstance(files, list):
                    continue

                fixed: List[Dict[str, str]] = []
                for f in files:
                    if not isinstance(f, dict):
                        continue
                    p = (f.get("path") or "").strip().replace("\\", "/").lstrip("/")
                    c = str(f.get("content") or "")
                    if not _is_safe_path(p):
                        continue
                    if not (p.startswith(allowed_prefixes) or p in allowed_files or p.endswith("/__init__.py")):
                        continue
                    if p.startswith("other/"):
                        continue
                    fixed.append({"path": p, "content": c})

                # Enterprise validation
                main_candidates = [f for f in fixed if f.get("path") == "main.py"]
                if not main_candidates:
                    continue
                if not self._validate_main_py(main_candidates[0].get("content", "")):
                    continue

                validated: List[Dict[str, str]] = []
                for f in fixed:
                    path = f.get("path", "")
                    content = f.get("content", "")

                    if path.endswith(".md") or path.endswith("__init__.py"):
                        if self._contains_forbidden_patterns(content):
                            continue
                        validated.append(f)
                        continue

                    if not self._is_valid_python(content):
                        continue
                    if self._contains_forbidden_patterns(content):
                        continue
                    if path.startswith("views/") and "from nicegui import ui" not in content:
                        continue

                    validated.append(f)

                if not self._validate_minimum_set(validated):
                    continue

                return {"files": validated}

            except Exception:
                await asyncio.sleep(1.0)

        return {"files": [], "error": "openai_failed_python_enterprise"}


class GenericMultiLangEngine(BaseEngine):
    """
    泛用多語言引擎：保留「多語言可生成」特性，但不做 Python 專屬 AST / NiceGUI / async SQLAlchemy 強制。
    目標：讓非 Python 技術棧也能產出一組「可編譯/可跑的雛形」。
    """

    @staticmethod
    def _infer_ext(lang: str) -> str:
        lang = _normalize_lang(lang)
        if lang in ("python",):
            return ".py"
        if lang in ("node", "javascript"):
            return ".js"
        if lang in ("typescript", "ts"):
            return ".ts"
        if lang in ("go",):
            return ".go"
        if lang in ("java",):
            return ".java"
        if lang in ("csharp", "c#", "cs"):
            return ".cs"
        return ".txt"

    @staticmethod
    def _folder_by_object_type(obj_type: str) -> str:
        t = (obj_type or "").strip().lower()
        if t == "boundary":
            return "views"
        if t == "control":
            return "controllers"
        if t == "entity":
            return "models"
        return "models"

    @staticmethod
    def _split_first_line_ext(text: str) -> Tuple[Optional[str], str]:
        lines = (text or "").strip().splitlines()
        if not lines:
            return None, ""
        first = lines[0].strip()
        if first.startswith(".") and len(first) <= 8:
            return first, "\n".join(lines[1:]).strip()
        return None, "\n".join(lines).strip()

    async def generate(self, inp: CodeAgentInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        db = inp.tech_stack.get("database") or inp.tech_stack.get("architecture") or ""

        bce_objects = ctx.get("bce_objects", [])
        event_data = ctx.get("event_data", {})
        blueprint_states = ctx.get("blueprint_states", [])

        prompt = f"""
你是一位資深全端工程師。請根據下列「真實專案資料」產出可運行的程式碼檔案集合。

【專案名稱】{inp.project_name}
【專案說明】{inp.project_description}
【技術棧】{json.dumps(inp.tech_stack, ensure_ascii=False)}
【資料庫】{db}

【BCE Objects（含 attributes、methods）】
{json.dumps(bce_objects, ensure_ascii=False)}

【UseCase + EventLists + Events（三段式事件）】
{json.dumps(event_data, ensure_ascii=False)}

【Blueprint payload_json（僅供 UI 參考）】
{json.dumps([
    {k: b.get(k) for k in ("screen_name", "boundary_id", "payload_json")}
    for b in (blueprint_states or [])
], ensure_ascii=False)}

========================
【輸出規則】
========================
1) 只輸出合法 JSON
2) 格式必須是：
{{
  "files": [
    {{"path":"...","content":"..."}}
  ]
}}
3) path 必須是相對路徑，且只能在：
- models/
- controllers/
- views/
- flow_controllers/
- main.* (依技術棧)
- README.md

4) 你必須產出一個可啟動的入口檔：
- 若是 Node/TS：main.js / main.ts（可用 node 執行或 ts-node）
- 若是 Go：main.go（可 go run）
- 若是 Java：Main.java（可編譯執行）
- 若是 Python：main.py

5) 每個 UseCase 至少要有：
- controllers/<usecase>_controller.(對應語言副檔名)
- views/<usecase>_view.(對應語言副檔名 或 html/tsx 視框架)
- flow_controllers/<usecase>_flow.(對應語言副檔名)

6) 若技術棧沒有指定前端框架，views 可以用最小可跑的方式
7) 禁止輸出解釋文字，只能輸出 JSON。
"""

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "只輸出合法 JSON，不得包含說明文字。"},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        allowed_prefixes = ("models/", "controllers/", "views/", "flow_controllers/")
        allowed_files = ("README.md",)
        allowed_main = ("main.py", "main.js", "main.ts", "main.go", "Main.java", "main.java")

        for _ in range(2):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(API_URL, headers=HEADERS, json=payload, timeout=120) as resp:
                        if resp.status != 200:
                            await asyncio.sleep(1.0)
                            continue
                        data = await resp.json()

                text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                try:
                    obj = _safe_json_load(text)
                except Exception:
                    obj = await _repair_to_valid_json(text)

                files = obj.get("files", [])
                if not isinstance(files, list):
                    continue

                fixed: List[Dict[str, str]] = []
                for f in files:
                    if not isinstance(f, dict):
                        continue
                    p = (f.get("path") or "").strip().replace("\\", "/").lstrip("/")
                    c = str(f.get("content") or "")
                    if not _is_safe_path(p):
                        continue
                    if not (p.startswith(allowed_prefixes) or p in allowed_files or p in allowed_main):
                        continue
                    fixed.append({"path": p, "content": c})

                if not any(ff.get("path") in allowed_main for ff in fixed):
                    continue

                return {"files": fixed}

            except Exception:
                await asyncio.sleep(1.0)

        return {"files": [], "error": "openai_failed_generic_multilang"}


# =========================================================
# One Agent, Multi Engines
# =========================================================
class CodeAgentOpenAI:
    """
    一個 AGENT，多個 Engine：
    - PythonEnterpriseEngine：強一致性、可執行保證（你的新版）
    - GenericMultiLangEngine：泛用多語言（你的上版精神）
    """

    def __init__(self) -> None:
        self.python_engine = PythonEnterpriseEngine()
        self.generic_engine = GenericMultiLangEngine()

    # ---------------------------------------------------------
    # Context Collector (shared)
    # ---------------------------------------------------------
    @classmethod
    async def _collect_context(cls, project_id: int) -> Dict[str, Any]:
        objects = await ObjectController.list(project_id=project_id)
        object_ids = [int(o.id) for o in (objects or []) if getattr(o, "id", None) is not None]

        attrs = await _safe_list_by_object_ids(AttributeController, project_id, object_ids)
        meths = await _safe_list_by_object_ids(MethodController, project_id, object_ids)

        usecases = await UsecaseController.list(project_id=project_id)
        usecase_ids = [int(u.id) for u in (usecases or []) if getattr(u, "id", None) is not None]

        event_lists = await _safe_list_event_lists_by_usecase_ids(project_id, usecase_ids)
        event_list_ids = [int(el.id) for el in (event_lists or []) if getattr(el, "id", None) is not None]

        events = await _safe_list_events_by_event_list_ids(event_list_ids)

        blueprint_states = await _collect_blueprint_context(project_id, limit=6)

        attrs_by_obj: Dict[int, List[Dict[str, Any]]] = {}
        for a in (attrs or []):
            oid = getattr(a, "object_id", None)
            if oid is None:
                continue
            try:
                attrs_by_obj.setdefault(int(oid), []).append(_to_dict(a))
            except Exception:
                continue

        meths_by_obj: Dict[int, List[Dict[str, Any]]] = {}
        for m in (meths or []):
            oid = getattr(m, "object_id", None)
            if oid is None:
                continue
            try:
                meths_by_obj.setdefault(int(oid), []).append(_to_dict(m))
            except Exception:
                continue

        bce_objects: List[Dict[str, Any]] = []
        for o in (objects or []):
            od = _to_dict(o)
            oid = getattr(o, "id", None)
            if oid is not None:
                try:
                    od["attributes"] = attrs_by_obj.get(int(oid), [])
                    od["methods"] = meths_by_obj.get(int(oid), [])
                except Exception:
                    od["attributes"] = []
                    od["methods"] = []
            bce_objects.append(od)

        event_data = {
            "usecases": [_to_dict(u) for u in (usecases or [])],
            "event_lists": [_to_dict(el) for el in (event_lists or [])],
            "events": [_to_dict(e) for e in (events or [])],
        }

        counts = {
            "object_count": len(bce_objects),
            "usecase_count": len(event_data["usecases"]),
            "event_list_count": len(event_data["event_lists"]),
            "event_count": len(event_data["events"]),
            "blueprint_count": len(blueprint_states or []),
            "blueprint_canvas_count": len([b for b in (blueprint_states or []) if b.get("canvas_data_url")]),
        }

        return {
            "bce_objects": bce_objects,
            "event_data": event_data,
            "blueprint_states": blueprint_states,
            "counts": counts,
        }

    # ---------------------------------------------------------
    # Engine selector
    # ---------------------------------------------------------
    def _select_engine(self, tech_stack: Dict[str, Any]) -> BaseEngine:
        backend_lang = _normalize_lang(tech_stack.get("backend_language"))
        if backend_lang == "python":
            return self.python_engine
        return self.generic_engine

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    @classmethod
    async def generate_files_for_current_project(
        cls,
        project_id: Optional[int] = None,
        project_meta: Optional[Dict[str, Any]] = None,
        package_name: str = "generated_app",
        mode: str = "cover",
        patch_instruction: str = "",
        existing_files: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        ✅ 一個入口，依 tech_stack 自動挑 engine
        ✅ DB(Project) 為 single source of truth（projects 才有前後端欄位）
        """
        agent = cls()

        # 先用傳入 project_meta / storage 拿到 project_id
        project: Dict[str, Any] = (project_meta or {}) if isinstance(project_meta, dict) else {}

        if project_id is None:
            project = project or (app.storage.user.get("current_project") or {})
            if not project.get("id"):
                return {"files": [], "error": "no_project"}
            project_id = int(project["id"])
        else:
            if not project:
                cur = app.storage.user.get("current_project") or {}
                project = {
                    "id": int(project_id),
                    "name": cur.get("name", ""),
                    "description": cur.get("description", ""),
                }
            project["id"] = int(project_id)

        # ✅ 關鍵：從 DB 讀 Project，補齊/覆蓋 tech stack 欄位
        try:
            db_row = await ProjectController.get(int(project_id))
        except Exception:
            db_row = None

        if db_row is not None:
            db_project = _to_dict(db_row)
            project = _merge_project_preferring_db(project, db_project)

        # ✅ tech_stack 一定從 Project 欄位組裝
        inp = CodeAgentInput(
            project_id=int(project_id),
            project_name=(project.get("name", "") or ""),
            project_description=(project.get("description", "") or ""),
            tech_stack=_compact_tech_stack(project),
            package_name=(package_name or "generated_app").strip() or "generated_app",
            mode=mode or "cover",
            patch_instruction=patch_instruction or "",
            existing_files=existing_files,
        )

        # Collect context once
        ctx = await agent._collect_context(inp.project_id)

        # Select engine
        engine = agent._select_engine(inp.tech_stack)

        # Generate
        return await engine.generate(inp, ctx)