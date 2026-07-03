"""我的任务聚合：指派给我且未完成的项目任务。只读。"""
from sqlalchemy.orm import Session
from app.models.models_project import Project, ProjectTask

_DONE = {"已完成"}


def get_my_tasks(db: Session, user_id):
    rows = (
        db.query(ProjectTask, Project.name, Project.id)
        .join(Project, Project.id == ProjectTask.project_id)
        .filter(ProjectTask.assignee_id == user_id)
        .filter(~ProjectTask.status.in_(_DONE))
        .all()
    )
    out = []
    for task, project_name, project_id in rows:
        out.append({
            "project_id": str(project_id),
            "project_name": project_name,
            "task_id": str(task.id),
            "code": task.code,
            "name": task.name,
            "status": task.status,
            "priority": task.priority,
            "planned_end": task.planned_end.isoformat() if task.planned_end else None,
        })
    return out
