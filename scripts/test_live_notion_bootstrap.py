import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.config import settings
from app.database import AsyncSessionLocal
from app.models.entities import Project
from app.notion.client import NotionClient
from app.notion.bootstrap import bootstrap_workspace
from sqlalchemy import select

async def main():
    print("=== NOTION LIVE BOOTSTRAP TEST ===")
    print("API Key Prefix:", settings.NOTION_API_KEY[:10] if settings.NOTION_API_KEY else "EMPTY")
    parent_id = settings.NOTION_PARENT_PAGE_ID or "3ed84a36d2bf806984ccf09e561038c2"
    print("Target Parent Page ID:", parent_id)

    client = NotionClient(api_key=settings.NOTION_API_KEY)
    print("Client is_mock:", client.is_mock)

    # 1. Verify Parent Page
    try:
        page = await client.get_page(parent_id)
        print("Successfully accessed parent page!")
        print("Page URL:", page.get("url"))
        print("Page ID:", page.get("id"))
    except Exception as e:
        print("Error accessing parent page:", str(e))
        return

    # 2. Get or create LeafGuard Project
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Project).where(Project.name.like("%LeafGuard%")))
        project = res.scalars().first()
        if not project:
            project = Project(
                name="LeafGuard: Edge Crop Disease Detector",
                description="On-device deep learning system for offline crop disease diagnosis in rural farms.",
                notion_parent_id=parent_id
            )
            db.add(project)
            await db.commit()
            await db.refresh(project)
        else:
            project.notion_parent_id = parent_id
            await db.commit()
            await db.refresh(project)

        print(f"Target Project: {project.name} (ID: {project.id})")

        # 3. Run bootstrap
        print("Bootstrapping canonical databases into Notion workspace...")
        created_map = await bootstrap_workspace(
            db=db,
            project_id=project.id,
            parent_page_id=parent_id,
            client=client
        )

        print("\n=== BOOTSTRAP COMPLETED SUCCESSFULLY! ===")
        for etype, db_id in created_map.items():
            print(f"  • {etype.replace('_', ' ').title():<22} -> Notion DB ID: {db_id}")

if __name__ == "__main__":
    asyncio.run(main())
