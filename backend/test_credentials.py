import httpx
import asyncio
from app.config import settings

async def verify_notion():
    print("Testing Notion API connection...")
    headers = {
        "Authorization": f"Bearer {settings.NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    page_id = settings.NOTION_PAGE_ID
    async with httpx.AsyncClient() as client:
        # Check parent page access
        url = f"https://api.notion.com/v1/pages/{page_id}"
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            print("[OK] Notion API Connected successfully!")
            print("     Page ID:", data.get("id"))
            print("     URL:", data.get("url"))
            return True
        else:
            print("[WARN] Notion API returned status:", resp.status_code)
            print("       Response:", resp.text)
            return False

async def verify_groq():
    print("\nTesting Groq API connection...")
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        url = "https://api.groq.com/openai/v1/models"
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])[:5]]
            print("[OK] Groq API Connected successfully!")
            print("     Available Models sample:", models)
            return True
        else:
            print("[WARN] Groq API returned status:", resp.status_code)
            print("       Response:", resp.text)
            return False

async def main():
    await verify_notion()
    await verify_groq()

if __name__ == "__main__":
    asyncio.run(main())
