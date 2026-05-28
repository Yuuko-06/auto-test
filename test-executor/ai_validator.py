"""
AI 测试结果校验器
"""
import json
import logging
import re

from . import config

logger = logging.getLogger(__name__)

RESULT_VALIDATION_PROMPT = """你是一个API测试结果校验专家。请判断以下测试用例的执行结果是否符合预期。

## 测试用例
{test_case_json}

## 实际响应
状态码: {status_code}
响应体: {response_body}

## 校验规则
1. 实际状态码是否匹配预期状态码
2. 响应体是否包含预期的关键内容或结构特征
3. 异常场景下，错误响应是否合理

## 输出格式
{{
  "passed": true/false,
  "reason": "用中文简要说明判断理由，不超过100字",
  "issues": ["问题描述1", "问题描述2"]
}}
"""


class AIValidator:

    def __init__(self):
        self.provider = config.AI_PROVIDER

    async def validate_batch(self, results: list[dict]) -> list[dict]:
        """批量校验多条测试结果"""
        if not results:
            return []

        validations = []
        for result in results:
            try:
                validation = await self._validate_single(result)
                validations.append(validation)
            except Exception as e:
                logger.error(f"校验失败: {e}")
                validations.append({
                    "passed": False,
                    "reason": f"AI校验异常: {e}",
                    "issues": [],
                })
        return validations

    async def _validate_single(self, result: dict) -> dict:
        """校验单条测试结果"""
        test_case = result.get("test_case", {})
        response_status = result.get("response_status", 0)
        response_body = result.get("response_body", "")

        # 如果实际响应体太大，截断
        body_str = json.dumps(response_body, ensure_ascii=False) if isinstance(response_body, dict) else str(response_body)
        if len(body_str) > 3000:
            body_str = body_str[:3000] + "...(已截断)"

        prompt = RESULT_VALIDATION_PROMPT.format(
            test_case_json=json.dumps(test_case, ensure_ascii=False, indent=2),
            status_code=response_status,
            response_body=body_str,
        )

        raw = await self._call_ai(prompt, max_tokens=1024)
        return self._parse_validation_response(raw)

    async def _call_ai(self, prompt: str, max_tokens: int = 1024) -> str:
        """调用 AI"""
        if self.provider == "claude":
            import anthropic
            kwargs = {"api_key": config.AI_API_KEY, "max_retries": 2}
            if config.AI_BASE_URL:
                kwargs["base_url"] = config.AI_BASE_URL
            client = anthropic.AsyncAnthropic(**kwargs)
            try:
                resp = await client.messages.create(
                    model=config.AI_MODEL,
                    max_tokens=max_tokens,
                    system="你是一个API测试校验专家，只输出JSON格式。",
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp.content[0].text
            finally:
                await client.close()
        else:
            from openai import AsyncOpenAI
            kwargs = {"api_key": config.AI_API_KEY, "max_retries": 2}
            if config.AI_BASE_URL:
                kwargs["base_url"] = config.AI_BASE_URL
            client = AsyncOpenAI(**kwargs)
            try:
                resp = await client.chat.completions.create(
                    model=config.AI_MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个API测试校验专家，只输出JSON格式。"},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.1,
                )
                return resp.choices[0].message.content or ""
            finally:
                await client.close()

    def _parse_validation_response(self, raw: str) -> dict:
        """解析 AI 校验响应"""
        raw = raw.strip()
        # 去掉可能的 markdown 包裹
        md_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
        if md_match:
            raw = md_match.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 尝试匹配 JSON 对象
            obj_match = re.search(r"\{[\s\S]*\}", raw)
            if obj_match:
                try:
                    return json.loads(obj_match.group(0))
                except json.JSONDecodeError:
                    pass
            return {"passed": False, "reason": f"无法解析校验结果: {raw[:200]}", "issues": []}
