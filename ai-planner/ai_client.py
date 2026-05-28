"""
AI 调用客户端 — 统一封装 OpenAI 和 Anthropic SDK
"""
import json
import logging
import re

from . import config

logger = logging.getLogger(__name__)

# ---- Prompt 模板 ----
# 注意：使用 .replace() 而非 .format()，所以 {endpoints_json} 是唯一替换点，其余 {} 均为字面量

CASE_GENERATION_PROMPT = """你是一个专业的API测试工程师。请根据以下接口信息，为每个接口生成测试用例。

## 接口信息
{endpoints_json}

## 要求
1. 为每个接口生成 2-3 条测试用例，覆盖 NORMAL/ABNORMAL/BOUNDARY
2. 每条用例字段（字段名不可改动）：
   - endpoint_id, case_type, title, description, priority
   - request_params: {"query": {}, "headers": {}, "body": {}}
   - expected_status: 整数
   - expected_body: {"type": "...", "description": "..."}
3. 纯 JSON 数组输出，不要 markdown 包裹
4. 所有值必须是字面量，禁止代码表达式。字符串值尽量简短（不超过30字符）
5. 控制输出长度，确保 JSON 完整闭合，最后一个用例后面不要有逗号

## 输出示例
[{"endpoint_id":"ep1","case_type":"NORMAL","title":"正常查询","description":"合法参数查询","priority":"HIGH","request_params":{"query":{"page":1},"headers":{},"body":{}},"expected_status":200,"expected_body":{"type":"array","description":"返回列表"}}]
"""


class AIClient:
    """统一 AI 调用接口"""

    def __init__(self):
        self.provider = config.AI_PROVIDER

    async def generate_test_cases(self, endpoints: list[dict]) -> list[dict]:
        """分批生成测试用例（每批最多5个接口），合并结果"""
        BATCH_SIZE = 5
        all_cases = []

        for i in range(0, len(endpoints), BATCH_SIZE):
            batch = endpoints[i:i + BATCH_SIZE]
            batch_json = json.dumps(batch, ensure_ascii=False, indent=2)
            prompt = CASE_GENERATION_PROMPT.replace("{endpoints_json}", batch_json)

            logger.info(
                f"调用 AI 生成测试用例，批次 {i // BATCH_SIZE + 1}/{(len(endpoints) - 1) // BATCH_SIZE + 1}，"
                f"接口数: {len(batch)}"
            )
            raw_response = await self._call_ai(prompt, max_tokens=16384)
            cases = self._parse_json_response(raw_response)
            all_cases.extend(cases)
            logger.info(f"  本批生成 {len(cases)} 条用例")

        return all_cases

    async def _call_ai(self, prompt: str, max_tokens: int = 4096) -> str:
        """根据配置调用对应的 AI 提供商"""
        if self.provider == "claude":
            return await self._call_claude(prompt, max_tokens)
        else:
            return await self._call_openai(prompt, max_tokens)

    async def _call_openai(self, prompt: str, max_tokens: int) -> str:
        """调用 OpenAI 兼容 API"""
        from openai import AsyncOpenAI

        kwargs = {"api_key": config.AI_API_KEY, "max_retries": 2}
        if config.AI_BASE_URL:
            kwargs["base_url"] = config.AI_BASE_URL

        client = AsyncOpenAI(**kwargs)
        try:
            resp = await client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的API测试工程师，只输出JSON格式数据。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return resp.choices[0].message.content or ""
        finally:
            await client.close()

    async def _call_claude(self, prompt: str, max_tokens: int) -> str:
        """调用 Anthropic Claude API"""
        import anthropic

        kwargs = {"api_key": config.AI_API_KEY, "max_retries": 2}
        if config.AI_BASE_URL:
            kwargs["base_url"] = config.AI_BASE_URL

        client = anthropic.AsyncAnthropic(**kwargs)
        try:
            resp = await client.messages.create(
                model=config.AI_MODEL,
                max_tokens=max_tokens,
                system="你是一个专业的API测试工程师，只输出JSON格式数据。",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        finally:
            await client.close()

    def _parse_json_response(self, raw: str) -> list[dict]:
        """从 AI 返回值中提取 JSON 数组"""
        raw = raw.strip()

        # 去掉可能的 markdown 代码块包裹
        md_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
        if md_match:
            raw = md_match.group(1).strip()

        # 修复常见的非标准 JSON 表达式
        raw = self._repair_json(raw)

        # 尝试直接解析
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "test_cases" in data:
                return data["test_cases"]
            for val in data.values():
                if isinstance(val, list):
                    return val
        except json.JSONDecodeError:
            pass

        # 尝试找 JSON 数组
        array_match = re.search(r"\[[\s\S]*\]", raw)
        if array_match:
            try:
                return json.loads(array_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(f"无法解析 AI 响应为 JSON 数组，原始响应:\n{raw[:1500]}")
        raise ValueError(f"AI 返回的测试用例格式无法解析，原始响应前500字符: {raw[:500]}")

    def _repair_json(self, raw: str) -> str:
        """修复 AI 响应中常见的非标准 JSON 表达式和被截断的响应"""
        # 修复 "xxx".repeat(N) → 重复字符串
        def _replace_repeat(m: re.Match) -> str:
            s = m.group(1)
            n = int(m.group(2))
            n = min(n, 100)
            return json.dumps(s * n)
        raw = re.sub(r'"([^"]*)"\s*\.\s*repeat\s*\(\s*(\d+)\s*\)', _replace_repeat, raw)

        # 修复 Array(N).fill(x) → JSON 数组
        def _replace_array_fill(m: re.Match) -> str:
            n = min(int(m.group(1)), 20)
            val = m.group(2).strip().strip('"').strip("'")
            return json.dumps([val] * n)
        raw = re.sub(
            r'Array\s*\(\s*(\d+)\s*\)\s*\.\s*fill\s*\(\s*([^)]+)\s*\)',
            _replace_array_fill, raw,
        )

        # 修复被截断的响应：尝试补全未闭合的字符串和括号
        raw = self._repair_truncated(raw)

        return raw

    def _repair_truncated(self, raw: str) -> str:
        """尝试修复被 token 限制截断的 JSON"""
        if not raw:
            return raw

        # 去掉末尾不完整的片段（如 "name": "aaaa... 没有闭合引号）
        # 找到最后一个完整的 JSON 值
        # 简单策略：找到最后一个 ], 截断到这里并补 ]
        last_bracket = raw.rfind(']')
        last_brace = raw.rfind('}')
        last_quote = raw.rfind('"')

        # 如果最后是未闭合的字符串（引号后没有逗号或括号）
        if last_quote > last_bracket and last_quote > last_brace:
            # 尝试在最后一个完整的对象后截断
            # 找最后一个 "} 后跟 , 或 ] 的位置
            complete_end = -1
            for m in re.finditer(r'\}"\s*[,\)\]]', raw):
                complete_end = m.start() + 1

            if complete_end > 0 and complete_end < len(raw) - 10:
                truncated = raw[:complete_end + 1]
                # 确保以 ] 结尾
                truncated = truncated.rstrip().rstrip(',')
                if not truncated.endswith(']'):
                    truncated += '\n]'
                logger.warning(f"响应被截断，已修复：{len(raw)} -> {len(truncated)} 字符")
                return truncated

        # 如果末尾不是 ]，尝试补全
        raw_stripped = raw.rstrip()
        if not raw_stripped.endswith(']'):
            # 找到最后一个完整的 }，截断并补 ]
            last_complete = raw_stripped.rstrip().rstrip(',')
            if not last_complete.endswith(']'):
                last_complete += '\n]'
            return last_complete

        return raw
