from typing import Dict, Any, List, Optional
from datetime import datetime

DATABASE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "projects": {
        "Name": {"title": {}},
        "Description": {"rich_text": {}},
        "POS_ID": {"rich_text": {}},
    },
    "meetings": {
        "Title": {"title": {}},
        "Date": {"date": {}},
        "Attendees": {"multi_select": {}},
        "POS_ID": {"rich_text": {}},
    },
    "references": {
        "Title": {"title": {}},
        "Authors": {"rich_text": {}},
        "Year": {"number": {"format": "number"}},
        "URL": {"url": {}},
        "Key Takeaways": {"rich_text": {}},
        "POS_ID": {"rich_text": {}},
    },
    "claims": {
        "Statement": {"title": {}},
        "Type": {
            "select": {
                "options": [
                    {"name": "observation", "color": "blue"},
                    {"name": "comparative", "color": "purple"},
                    {"name": "factual", "color": "green"},
                    {"name": "assumption", "color": "yellow"},
                ]
            }
        },
        "Subject": {"rich_text": {}},
        "Metric": {"rich_text": {}},
        "Direction": {
            "select": {
                "options": [
                    {"name": "increase", "color": "green"},
                    {"name": "decrease", "color": "red"},
                    {"name": "better", "color": "green"},
                    {"name": "worse", "color": "red"},
                    {"name": "equal", "color": "gray"},
                ]
            }
        },
        "Dataset": {"rich_text": {}},
        "Value": {"number": {"format": "number"}},
        "Status": {
            "select": {
                "options": [
                    {"name": "supported", "color": "green"},
                    {"name": "unverified", "color": "yellow"},
                    {"name": "contradicted", "color": "red"},
                    {"name": "incomplete", "color": "orange"},
                ]
            }
        },
        "POS_ID": {"rich_text": {}},
    },
    "experiments": {
        "Code": {"title": {}},
        "Hypothesis": {"rich_text": {}},
        "Model": {"rich_text": {}},
        "Dataset": {"rich_text": {}},
        "Status": {
            "select": {
                "options": [
                    {"name": "planned", "color": "gray"},
                    {"name": "running", "color": "blue"},
                    {"name": "completed", "color": "green"},
                    {"name": "aborted", "color": "red"},
                ]
            }
        },
        "Owner": {"rich_text": {}},
        "POS_ID": {"rich_text": {}},
    },
    "decisions": {
        "Decision": {"title": {}},
        "Code": {"rich_text": {}},
        "Rationale": {"rich_text": {}},
        "Status": {
            "select": {
                "options": [
                    {"name": "active", "color": "green"},
                    {"name": "proposed", "color": "blue"},
                    {"name": "superseded", "color": "gray"},
                    {"name": "reverted", "color": "red"},
                    {"name": "modified", "color": "yellow"},
                ]
            }
        },
        "Version": {"number": {"format": "number"}},
        "Decided By": {"rich_text": {}},
        "Decided On": {"date": {}},
        "Origin": {
            "select": {
                "options": [
                    {"name": "human_authored", "color": "blue"},
                    {"name": "system_derived", "color": "gray"},
                    {"name": "ai_inferred", "color": "purple"},
                ]
            }
        },
        "Review Status": {
            "select": {
                "options": [
                    {"name": "approved", "color": "green"},
                    {"name": "unreviewed", "color": "yellow"},
                    {"name": "rejected", "color": "red"},
                ]
            }
        },
        "POS_ID": {"rich_text": {}},
    },
    "tasks": {
        "Task": {"title": {}},
        "Code": {"rich_text": {}},
        "Status": {
            "select": {
                "options": [
                    {"name": "todo", "color": "gray"},
                    {"name": "in_progress", "color": "blue"},
                    {"name": "blocked", "color": "red"},
                    {"name": "done", "color": "green"},
                ]
            }
        },
        "Priority": {
            "select": {
                "options": [
                    {"name": "low", "color": "gray"},
                    {"name": "medium", "color": "yellow"},
                    {"name": "high", "color": "orange"},
                    {"name": "urgent", "color": "red"},
                ]
            }
        },
        "Owner": {"rich_text": {}},
        "Due Date": {"date": {}},
        "Blocked": {"checkbox": {}},
        "Needs Re-evaluation": {"checkbox": {}},
        "POS_ID": {"rich_text": {}},
    },
    "milestones": {
        "Milestone": {"title": {}},
        "Due Date": {"date": {}},
        "Progress": {"number": {"format": "percent"}},
        "POS_ID": {"rich_text": {}},
    },
    "deliverables": {
        "Deliverable": {"title": {}},
        "Type": {"select": {"options": [{"name": "artifact"}, {"name": "apk"}, {"name": "weights"}, {"name": "report"}]}},
        "Status": {
            "select": {
                "options": [
                    {"name": "todo", "color": "gray"},
                    {"name": "in_progress", "color": "blue"},
                    {"name": "completed", "color": "green"},
                ]
            }
        },
        "Due Date": {"date": {}},
        "POS_ID": {"rich_text": {}},
    },
    "reports": {
        "Period": {"title": {}},
        "Published Date": {"date": {}},
        "Summary": {"rich_text": {}},
        "POS_ID": {"rich_text": {}},
    },
    "impact_analyses": {
        "Scenario": {"title": {}},
        "Trigger Decision": {"rich_text": {}},
        "Total Affected": {"number": {"format": "number"}},
        "Summary": {"rich_text": {}},
        "POS_ID": {"rich_text": {}},
    },
}

def to_rich_text(content: Optional[str]) -> List[Dict[str, Any]]:
    if not content:
        return []
    return [{"type": "text", "text": {"content": str(content)[:2000]}}]

def to_title(content: str) -> List[Dict[str, Any]]:
    return [{"type": "text", "text": {"content": (content or "Untitled")[:2000]}}]

def map_entity_to_notion_properties(
    entity_type: str,
    entity: Any,
    relations: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """Serializes an app database model into Notion page properties."""
    etype = entity_type.lower()
    props: Dict[str, Any] = {}

    if etype == "decisions":
        title_text = f"[{entity.code}] {entity.statement}"
        props["Decision"] = {"title": to_title(title_text)}
        props["Code"] = {"rich_text": to_rich_text(entity.code)}
        props["Rationale"] = {"rich_text": to_rich_text(entity.rationale)}
        props["Status"] = {"select": {"name": entity.status or "active"}}
        props["Version"] = {"number": entity.version or 1}
        props["Decided By"] = {"rich_text": to_rich_text(entity.decided_by)}
        if entity.decided_on:
            props["Decided On"] = {"date": {"start": entity.decided_on.strftime("%Y-%m-%d")}}
        props["Origin"] = {"select": {"name": entity.origin or "human_authored"}}
        props["Review Status"] = {"select": {"name": entity.review_status or "approved"}}
        props["POS_ID"] = {"rich_text": to_rich_text(entity.id)}

    elif etype == "tasks":
        title_text = f"[{entity.code}] {entity.title}"
        props["Task"] = {"title": to_title(title_text)}
        props["Code"] = {"rich_text": to_rich_text(entity.code)}
        props["Status"] = {"select": {"name": entity.status or "todo"}}
        props["Priority"] = {"select": {"name": entity.priority or "medium"}}
        props["Owner"] = {"rich_text": to_rich_text(entity.owner)}
        if entity.due_date:
            props["Due Date"] = {"date": {"start": entity.due_date.strftime("%Y-%m-%d")}}
        props["Blocked"] = {"checkbox": bool(entity.is_blocked)}
        props["Needs Re-evaluation"] = {"checkbox": bool(getattr(entity, "needs_reevaluation", False))}
        props["POS_ID"] = {"rich_text": to_rich_text(entity.id)}

    elif etype == "claims":
        props["Statement"] = {"title": to_title(entity.statement)}
        props["Type"] = {"select": {"name": entity.claim_type or "observation"}}
        props["Subject"] = {"rich_text": to_rich_text(entity.subject)}
        props["Metric"] = {"rich_text": to_rich_text(entity.metric)}
        if entity.direction:
            props["Direction"] = {"select": {"name": entity.direction}}
        props["Dataset"] = {"rich_text": to_rich_text(entity.dataset)}
        if entity.value is not None:
            props["Value"] = {"number": float(entity.value)}
        props["Status"] = {"select": {"name": entity.coverage_status or "unverified"}}
        props["POS_ID"] = {"rich_text": to_rich_text(entity.id)}

    elif etype == "experiments":
        props["Code"] = {"title": to_title(entity.code)}
        props["Hypothesis"] = {"rich_text": to_rich_text(entity.hypothesis)}
        props["Model"] = {"rich_text": to_rich_text(entity.model)}
        props["Dataset"] = {"rich_text": to_rich_text(entity.dataset)}
        props["Status"] = {"select": {"name": entity.status or "completed"}}
        props["Owner"] = {"rich_text": to_rich_text(entity.owner)}
        props["POS_ID"] = {"rich_text": to_rich_text(entity.id)}

    elif etype == "deliverables":
        props["Deliverable"] = {"title": to_title(entity.name)}
        props["Type"] = {"select": {"name": entity.deliverable_type or "artifact"}}
        props["Status"] = {"select": {"name": entity.status or "in_progress"}}
        if entity.due_date:
            props["Due Date"] = {"date": {"start": entity.due_date.strftime("%Y-%m-%d")}}
        props["POS_ID"] = {"rich_text": to_rich_text(entity.id)}

    elif etype == "milestones":
        props["Milestone"] = {"title": to_title(entity.name)}
        if entity.due_date:
            props["Due Date"] = {"date": {"start": entity.due_date.strftime("%Y-%m-%d")}}
        props["Progress"] = {"number": (entity.progress_percentage or 0) / 100.0}
        props["POS_ID"] = {"rich_text": to_rich_text(entity.id)}

    # Attach Relation properties if provided
    if relations:
        for prop_name, target_page_ids in relations.items():
            if target_page_ids:
                props[prop_name] = {
                    "relation": [{"id": pid} for pid in target_page_ids if pid]
                }

    return props

def parse_notion_page_properties(entity_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    """Parses Notion properties dict into normalized app attribute values."""
    parsed: Dict[str, Any] = {}
    from app.notion.hashing import extract_plain_text

    for prop_name, prop_data in properties.items():
        key = prop_name.lower().replace(" ", "_")
        val = extract_plain_text(prop_data)
        parsed[key] = val

    return parsed
