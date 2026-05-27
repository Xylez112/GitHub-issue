import httpx, asyncio

async def test():
    async with httpx.AsyncClient(timeout=300) as c:
        resp = await c.post("http://localhost:8000/api/analyze", json={
            "issue_url":"https://github.com/fastapi/fastapi/issues/14484",
            "repo_url": "https://github.com/fastapi/fastapi",
        })
        print(f"状态码: {resp.status_code}")
        if resp.status_code != 200:
            print(f"错误: {resp.text[:500]}")
            return
        data = resp.json()
        print(f"Issue: {data['issue_title']}")
        print(f"文件数: {data['total_files_analyzed']}, 片段数: {data['total_snippets_indexed']}")
        print(f"摘要: {data['issue_summary'][:400]}")
        print(f"\n相关片段:")
        for i, s in enumerate(data["relevant_snippets"]):
            print(f"  {i+1}. [{s['kind']}] {s['name']} ({s['file_path']})")

asyncio.run(test())
