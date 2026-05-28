"""测试分批生成 + 增加 max_tokens"""
import sqlite3, json, asyncio, os, re
from dotenv import load_dotenv
load_dotenv(".env")
from openai import AsyncOpenAI

# 1. 读取端点数据（只用前5个来测试）
conn = sqlite3.connect('./data/scanner.db')
rows = conn.execute(
    'SELECT id, method, path, summary, tags, parameters, request_body, responses '
    'FROM api_endpoints ORDER BY rowid LIMIT 5'
).fetchall()
endpoints = []
for r in rows:
    ep = {
        'endpoint_id': r[0], 'method': r[1], 'path': r[2],
        'summary': r[3] or '', 'tags': json.loads(r[4]) if r[4] else [],
        'parameters': json.loads(r[5]) if r[5] else [],
        'request_body_schema': json.loads(r[6]) if r[6] else None,
        'response_schemas': json.loads(r[7]) if r[7] else {}
    }
    endpoints.append(ep)
conn.close()
print(f"测试 {len(endpoints)} 个端点")

# 2. Prompt 模板（与 ai-planner 一致）
PROMPT_TEMPLATE = """你是一个专业的API测试工程师。请根据以下接口信息，为每个接口生成全面的测试用例。

## 接口信息
{endpoints_json}

## 要求
1. 为每个接口生成 3-5 条测试用例，覆盖 NORMAL/ABNORMAL/BOUNDARY 三种类型
2. 每条用例必须严格包含以下字段（字段名不可改动）：
   - endpoint_id: 对应的接口ID（字符串）
   - case_type: "NORMAL" / "ABNORMAL" / "BOUNDARY"
   - title: 中文用例标题（字符串，不超过30字）
   - description: 测试目的说明（字符串，不超过50字）
   - priority: "HIGH" / "MEDIUM" / "LOW"
   - request_params: {"query": {}, "headers": {}, "body": {}}
   - expected_status: 预期HTTP状态码（整数）
   - expected_body: {"type": "...", "description": "..."}
3. 输出纯 JSON 数组，不要 markdown 代码块
4. 边界测试中的长字符串值：直接用简短的代表性文本（如 "a"*10 写成 "aaaaaaaaaa"），不要用代码表达式
5. 每个字符串值尽量简短（不超过50字符），避免超出输出限制"""


async def main():
    client = AsyncOpenAI(
        api_key=os.environ['AI_API_KEY'],
        base_url=os.environ['AI_BASE_URL']
    )

    prompt = PROMPT_TEMPLATE.replace(
        '{endpoints_json}',
        json.dumps(endpoints, ensure_ascii=False, indent=2)
    )

    print(f"Prompt: {len(prompt)} 字符")
    print("调用 DeepSeek (max_tokens=16384)...")

    resp = await client.chat.completions.create(
        model='deepseek-chat',
        messages=[
            {'role': 'system', 'content': '你是API测试工程师，严格按JSON格式输出。'},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=16384,  # 加大
        temperature=0.3
    )
    raw = resp.choices[0].message.content or ''
    print(f"响应: {len(raw)} 字符")
    print(f"finish_reason: {resp.choices[0].finish_reason}")

    # 保存
    with open('ai_raw_response.txt', 'w', encoding='utf-8') as f:
        f.write(raw)

    # 解析
    clean = raw.strip()
    md = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean)
    if md:
        clean = md.group(1).strip()

    try:
        data = json.loads(clean)
        print(f"解析成功! {len(data)} 条用例")
        for c in data[:5]:
            print(f"  [{c.get('case_type', '?')}] {c.get('title', '?')[:60]}")
    except json.JSONDecodeError as e:
        print(f"解析失败(位置 {e.pos}): {e}")
        print(f"  上下文: ...{clean[max(0,e.pos-40):e.pos+40]}...")
        # 检查是否被截断
        if 'finish_reason' in dir(resp.choices[0]):
            print(f"  finish_reason: {resp.choices[0].finish_reason}")
        if not clean.endswith(']'):
            print("  响应末尾不是 ] - 可能被截断")

    await client.close()

asyncio.run(main())
