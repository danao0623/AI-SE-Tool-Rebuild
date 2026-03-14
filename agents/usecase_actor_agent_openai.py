from __future__ import annotations
from typing import Dict, List, Any
import aiohttp

# ✅ 改成完整匯入 MODEL_NAME，一起用
from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME


class UseCaseActorAgent:
    """
    和 AI 溝通，產生 / 重生 Actor 與 UseCase 的 Agent。
    ✨ 全部採用「純文字格式」，避免 JSON 解析錯誤。
    （這版已改成 OpenAI chat/completions）
    """

    # ============================================================
    #  一次產生 Actors + UseCases（第一次使用）
    # ============================================================
    @staticmethod
    async def generate_actors_and_usecases(
        project_info: Dict[str, Any],
    ) -> Dict[str, Any]:

        project_name = project_info.get("name", "未命名專案")
        project_desc = project_info.get("description", "")

        prompt = f"""
你是一名專業的系統分析師，正在為一個系統建立「使用者角色(Actors)」與「使用案例(Use Cases)」。

系統名稱：{project_name}
系統描述：
{project_desc}

請你嚴格遵守以下規則：
1. 一定要設計「剛好 5 個」系統角色（不可以少於 5 個，也不可以多於 5 個）。
2. 針對每一個 Actor，「各自設計剛好 3 個」使用案例，總共要 15 個。
3. 在 [USE_CASES] 區段中，每一行一定要標出主要角色名稱，而且每個角色名稱要「剛好出現 3 次」。
4. summary 約 30~50 個中文字，且是一句完整句子，以「。」結尾。

回覆格式（純文字）：

[ACTORS]
角色名稱1 | 角色說明1
角色名稱2 | 角色說明2
...

[USE_CASES]
使用案例名稱1 | 主要角色名稱1 | 使用案例中文概述（30~50 字，句號結尾）
使用案例名稱2 | 主要角色名稱2 | 使用案例中文概述
...

請在輸出前自我檢查：
- [ACTORS] 區段剛好 5 行角色。
- [USE_CASES] 區段剛好 15 行使用案例。
- 每一個角色在 [USE_CASES] 的第二欄位中剛好出現 3 次。
"""

        # 🟣 OpenAI chat/completions 的 payload
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一名專業的系統分析師，請嚴格依照格式輸出純文字。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL, headers=HEADERS, json=payload, timeout=120
            ) as resp:
                if resp.status != 200:
                    print("❌ generate_actors_and_usecases API error:", resp.status)
                    print(await resp.text())
                    return {}

                data = await resp.json()

        # 🔁 OpenAI 回傳內容
        raw_text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        print("\n🧾 generate_actors_and_usecases 原始回應：")
        print(raw_text)

        actors, use_cases = [], []
        section = None

        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("```"):
                continue

            upper = line.upper()
            if upper.startswith("[ACTORS]"):
                section = "actors"
                continue
            if upper.startswith("[USE_CASES]"):
                section = "use_cases"
                continue
            if section is None:
                continue

            parts = [p.strip() for p in line.split("|")]

            # ---- Actors ----
            if section == "actors":
                if len(parts) >= 1:
                    name = parts[0].lstrip("：:-— ")
                    desc = parts[1].lstrip("：:-— ") if len(parts) >= 2 else ""
                    if name and name not in ("名稱", "角色名稱"):
                        actors.append({"name": name, "description": desc})

            # ---- UseCases ----
            if section == "use_cases":
                if len(parts) >= 3:
                    name = parts[0].lstrip("：:-— ")
                    primary = parts[1].lstrip("：:-— ")
                    summary = "|".join(parts[2:]).lstrip("：:-— ").strip()
                    if name and primary:
                        use_cases.append(
                            {
                                "name": name,
                                "primary_actor": primary,
                                "summary": summary,
                            }
                        )

        print("\n✅ generate_actors_and_usecases 解析結果：")
        print("Actors:", actors)
        print("UseCases:", use_cases)

        if not actors:
            return {}

        return {
            "project_name": project_name,
            "actors": actors,
            "use_cases": use_cases,
        }

    # ============================================================
    #   單一 UseCase 重生（實戰版：>=15字即可，自動補句號）
    # ============================================================
    @staticmethod
    async def regenerate_single_usecase(
        project_info: Dict[str, Any],
        actor_name: str,
        old_usecase: Dict[str, Any],
    ) -> Dict[str, Any]:

        project_name = project_info.get("name", "未命名專案")
        project_desc = project_info.get("description", "")
        old_name = old_usecase.get("name") or old_usecase.get("使用案例名稱", "")
        old_summary = old_usecase.get("summary") or old_usecase.get("概述", "")

        # ---- Prompt ----
        base_prompt = f"""
系統名稱：{project_name}
系統描述：
{project_desc}

角色「{actor_name}」的舊使用案例：
- 名稱：{old_name}
- 概述：{old_summary}

請為角色「{actor_name}」重新產生一個新的使用案例：
- 名稱與內容不可完全相同
- 建議 summary 30~50 字，但不強制
- 請寫成一句完整中文句子，最好以「。」結尾

❗回覆格式（純文字）：
使用案例名稱 | 中文概述
"""

        async def call_api() -> str:
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一名專業的系統分析師，請依照指定格式輸出。",
                    },
                    {"role": "user", "content": base_prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 512,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL, headers=HEADERS, json=payload, timeout=90
                ) as resp:
                    if resp.status != 200:
                        print("❌ regenerate_single_usecase API 錯誤:", resp.status)
                        print(await resp.text())
                        return ""

                    data = await resp.json()

            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

        def parse(text: str) -> Dict[str, str] | None:
            print("\n🔁 regenerate_single_usecase 原始回應：")
            print(text)

            lines = [l.strip() for l in text.splitlines() if l.strip()]
            flat = " ".join(lines)

            if "|" not in flat:
                return None

            left, right = flat.split("|", 1)
            name = left.strip().lstrip("：:-— ")
            summary = right.strip().lstrip("：:-— ")

            if not name or not summary:
                return None

            # ---- 驗收邏輯（寬鬆版）----
            # 只要 >= 15 字就接受（避免一直被拒絕）
            if len(summary) < 15:
                print(f"⚠ summary 太短：{summary}")
                return None

            # 句尾若沒有標點 → 自動補「。」
            if not summary.endswith(("。", "！", "？")):
                summary += "。"

            return {"name": name, "summary": summary}

        # ---- 最多兩次重試 ----
        for attempt in range(2):
            text = await call_api()
            parsed = parse(text)

            if parsed:
                return {
                    "name": parsed["name"],
                    "summary": parsed["summary"],
                    "primary_actor": actor_name,
                }

            print(f"🔄 第 {attempt+1} 次重生不合格，準備重試…")

        print("❌ 最終仍不合格，本次重生放棄")
        return {}

    # ============================================================
    #   重生 Actor + 多個 UseCases（完整純文字版）
    # ============================================================
    @staticmethod
    async def regenerate_actor_with_usecases(
        project_info: Dict[str, Any],
        old_actor: Dict[str, Any],
        old_usecases_for_actor: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        project_name = project_info.get("name", "")
        project_desc = project_info.get("description", "")

        actor_name = old_actor.get("name", "")
        actor_desc = old_actor.get("description", "")

        uc_text = "\n".join(
            [f"- {u.get('name')}：{u.get('summary')}" for u in old_usecases_for_actor]
        )

        prompt = f"""
你是一名資深系統分析師，協助重新設計角色與使用案例：

系統名稱：{project_name}
描述：{project_desc}

舊角色：
- 名稱：{actor_name}
- 說明：{actor_desc}

舊使用案例：
{uc_text}

請你重新產生：
1. 一個新的角色名稱 + 說明
2. 三個新的使用案例（每個 summary 約 30~50 字，句號結尾）

❗回覆格式（純文字）：

[ACTOR]
新角色名稱 | 新角色說明

[USE_CASES]
案例1 | 概述（30~50 字）
案例2 | 概述
案例3 | 概述
"""

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一名專業的系統分析師，請嚴格依照指定格式輸出。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 2048,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL, headers=HEADERS, json=payload, timeout=120
            ) as resp:
                if resp.status != 200:
                    print("❌ regenerate_actor_with_usecases API 錯誤:", resp.status)
                    print(await resp.text())
                    return {}

                data = await resp.json()

        raw = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        print("\n♻ regenerate_actor_with_usecases 原始回應：")
        print(raw)

        section = None
        new_actor_name, new_actor_desc = "", ""
        new_usecases = []

        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("```"):
                continue

            upper = line.upper()
            if upper.startswith("[ACTOR]"):
                section = "actor"
                continue
            if upper.startswith("[USE_CASES]"):
                section = "use_cases"
                continue
            if section is None:
                continue

            parts = [p.strip() for p in line.split("|")]

            if section == "actor":
                if len(parts) >= 1:
                    new_actor_name = parts[0].lstrip("：:-— ")
                    new_actor_desc = (
                        parts[1].lstrip("：:-— ") if len(parts) >= 2 else ""
                    )
                continue

            if section == "use_cases":
                if len(parts) >= 2:
                    uc_name = parts[0].lstrip("：:-— ")
                    summary = "|".join(parts[1:]).strip().lstrip("：:-— ")
                    if uc_name:
                        # 自動補句號
                        if not summary.endswith(("。", "！", "？")):
                            summary += "。"
                        new_usecases.append(
                            {
                                "name": uc_name,
                                "summary": summary,
                                "primary_actor": new_actor_name,
                            }
                        )

        if not new_actor_name:
            return {}

        return {
            "actor": {"name": new_actor_name, "description": new_actor_desc},
            "use_cases": new_usecases,
        }
