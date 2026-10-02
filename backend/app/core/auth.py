from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import Request, Depends, Header
from pydantic import BaseModel
from app.core.config import settings
from app.core.errors import ProblemException

class UserContext(BaseModel):
    id: str
    email: str
    display_name: str
    is_authenticated: bool = True
    roles_by_project: Dict[str, str] = {}  # project_id -> role
    teams_by_project: Dict[str, List[str]] = {}  # project_id -> list of team_ids

class UserScope(BaseModel):
    user_id: str
    project_id: str
    role: str  # owner, member, reviewer, guest
    team_ids: List[str] = []

    def can_view(self, visibility: str, visibility_team_id: Optional[str] = None, created_by: Optional[str] = None) -> bool:
        """Determines if the user scope has visibility to a resource."""
        if self.role in ("owner", "member"):
            if visibility == "project":
                return True
            if visibility == "team":
                return visibility_team_id in self.team_ids or not visibility_team_id
            if visibility == "private":
                return created_by == self.user_id
            return True
        elif self.role == "reviewer":
            # Reviewer can view project-scoped artifacts
            return visibility == "project" or (visibility == "team" and visibility_team_id in self.team_ids)
        elif self.role == "guest":
            # Guest can ONLY view project-wide artifacts, never team or private
            return visibility == "project"
        return False

# Mock/Demo user generator for fast development & prototype walkthroughs
DEFAULT_DEMO_USER = UserContext(
    id="usr_karan_leafguard",
    email="karan@leafguard.ai",
    display_name="Karan Mehta",
    is_authenticated=True,
    roles_by_project={"*": "owner"},
    teams_by_project={"*": ["team_ml", "team_edge"]},
)

GUEST_DEMO_USER = UserContext(
    id="usr_guest_auditor",
    email="guest@external-audit.com",
    display_name="Auditor Guest",
    is_authenticated=True,
    roles_by_project={"*": "guest"},
    teams_by_project={"*": []},
)

async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_user_role: Optional[str] = Header(None),
) -> UserContext:
    """Extracts user from Authorization header (Bearer token) or provides demo user context."""
    # Fast path: Role override for automated multi-team security tests & demo testing
    if x_user_role == "guest":
        return GUEST_DEMO_USER
    
    if not authorization:
        # In prototype/dev mode, default to lead engineer Karan
        return DEFAULT_DEMO_USER

    token = authorization.replace("Bearer ", "").strip()
    if token == "guest_token":
        return GUEST_DEMO_USER

    # If real JWT token or Supabase Auth token, we would decode here
    return DEFAULT_DEMO_USER

def require_project_role(required_role: str):
    """Dependency ensuring the user possesses the minimum specified project role."""
    ROLE_HIERARCHY = {
        "guest": 0,
        "reviewer": 1,
        "member": 2,
        "owner": 3,
    }

    async def role_checker(
        project_id: str,
        user: UserContext = Depends(get_current_user)
    ) -> UserScope:
        user_role = user.roles_by_project.get(project_id) or user.roles_by_project.get("*", "member")
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)

        if user_level < required_level:
            raise ProblemException(
                status=403,
                title="Forbidden",
                detail=f"Action requires role '{required_role}', but current role is '{user_role}'.",
                problem_type="https://notionary.dev/errors/forbidden",
            )

        team_ids = user.teams_by_project.get(project_id) or user.teams_by_project.get("*", [])
        return UserScope(
            user_id=user.id,
            project_id=project_id,
            role=user_role,
            team_ids=team_ids,
        )

    return role_checker
