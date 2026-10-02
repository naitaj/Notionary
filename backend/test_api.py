import asyncio
import httpx

async def main():
    print("Testing Notionary Backend APIs...")
    # Test importing app and endpoints
    from app.main import app as fastapi_app
    from app.database import engine, Base
    import app.models.entities

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Database tables verified")

    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Root
        res = await ac.get("/")
        assert res.status_code == 200, res.text
        print("[OK] Root endpoint:", res.json())

        # 2. Seed Demo
        res = await ac.post("/api/v1/seed/demo")
        assert res.status_code == 200, res.text
        seed_data = res.json()
        print("[OK] Seed Demo:", seed_data)
        project_id = seed_data["project_id"]

        # 3. Health
        res = await ac.get(f"/api/v1/projects/{project_id}/health")
        assert res.status_code == 200, res.text
        print("[OK] Project Health:", res.json())

        # 4. Decisions & Lineage
        res = await ac.get(f"/api/v1/decisions?project_id={project_id}")
        assert res.status_code == 200, res.text
        decisions = res.json()
        assert len(decisions) > 0
        d_id = decisions[0]["id"]
        print(f"[OK] Decisions count: {len(decisions)}")

        res = await ac.get(f"/api/v1/decisions/{d_id}/lineage")
        assert res.status_code == 200, res.text
        lineage = res.json()
        print(f"[OK] Lineage for {decisions[0]['code']}: {len(lineage['upstream_evidence'])} upstream, {len(lineage['downstream_work'])} downstream")

        # 5. Impact Analysis
        res = await ac.post("/api/v1/impact/analyze", json={
            "project_id": project_id,
            "decision_id": d_id,
            "scenario": "what_if",
            "proposed_change": "Switch to EfficientNet",
        })
        assert res.status_code == 200, res.text
        impact = res.json()
        print(f"[OK] Impact analysis: {impact['total_affected']} affected items")

        # 6. Cited Q&A
        res = await ac.post("/api/v1/ai/query", json={
            "project_id": project_id,
            "query": "Why was Model B chosen over Model A?",
        })
        assert res.status_code == 200, res.text
        qa = res.json()
        print(f"[OK] Cited Q&A: {len(qa['citations'])} citations returned")

    print("\nSUCCESS: All Notionary Backend Endpoints Passed Successfully!")

if __name__ == "__main__":
    asyncio.run(main())
