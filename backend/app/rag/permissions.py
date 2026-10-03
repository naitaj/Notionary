from typing import Optional, List, Any
from sqlalchemy import or_, and_
from app.core.auth import UserScope

def get_visibility_filter(scope: UserScope, model_class: Any):
    """
    Plan §4.1: Permission filter first.
    Constructs an SQLAlchemy binary expression representing the visibility predicate
    for the given UserScope and entity model (which uses CommonColumnsMixin).
    
    Rules (Plan §0.3, §4.1, §8.7):
    - owner / member:
        * visibility == 'project'
        * visibility == 'team' AND (visibility_team_id IS NULL OR visibility_team_id IN scope.team_ids)
        * visibility == 'private' AND created_by == scope.user_id
    - reviewer:
        * visibility == 'project'
        * visibility == 'team' AND visibility_team_id IN scope.team_ids
    - guest:
        * ONLY visibility == 'project' (NEVER team or private content)
    """
    if scope.role in ("owner", "member"):
        clauses = [model_class.visibility == "project"]
        if scope.team_ids:
            clauses.append(
                and_(
                    model_class.visibility == "team",
                    or_(
                        model_class.visibility_team_id.is_(None),
                        model_class.visibility_team_id.in_(scope.team_ids),
                    ),
                )
            )
        else:
            clauses.append(
                and_(
                    model_class.visibility == "team",
                    model_class.visibility_team_id.is_(None),
                )
            )
        clauses.append(
            and_(
                model_class.visibility == "private",
                model_class.created_by == scope.user_id,
            )
        )
        return or_(*clauses)
    elif scope.role == "reviewer":
        clauses = [model_class.visibility == "project"]
        if scope.team_ids:
            clauses.append(
                and_(
                    model_class.visibility == "team",
                    model_class.visibility_team_id.in_(scope.team_ids),
                )
            )
        return or_(*clauses)
    elif scope.role == "guest":
        # Guest can strictly ONLY see project-wide items
        return model_class.visibility == "project"
    else:
        # Default strict fallback: only public project visibility
        return model_class.visibility == "project"

def filter_query_by_scope(stmt: Any, scope: UserScope, model_class: Any) -> Any:
    """Applies the visibility predicate filter directly to an SQLAlchemy select statement."""
    flt = get_visibility_filter(scope, model_class)
    return stmt.where(flt)
