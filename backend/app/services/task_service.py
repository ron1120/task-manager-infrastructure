# Business logic for tasks (used by task routes)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Task, User
from app.schemas import TaskCreate, TaskUpdate


def list_tasks(
    db: Session,
    user: User,
    *,
    completed: bool | None = None,
    search: str | None = None,
) -> list[Task]:
    # Always scoped to the logged-in user (users only see their own tasks)
    query = db.query(Task).filter(Task.user_id == user.id)

    if completed is not None:
        query = query.filter(Task.completed == completed)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
        )

    return query.order_by(Task.created_at.desc()).all()


def get_task(db: Session, user: User, task_id: int) -> Task | None:
    # Must match both task id AND owner — prevents reading others' tasks
    return (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == user.id)
        .first()
    )


def create_task(db: Session, user: User, task_in: TaskCreate) -> Task:
    task = Task(
        title=task_in.title,
        description=task_in.description,
        user_id=user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: Task, task_in: TaskUpdate) -> Task:
    # exclude_unset=True → only apply fields the client actually sent
    updates = task_in.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()


def mark_task_completed(db: Session, task: Task, completed: bool = True) -> Task:
    task.completed = completed
    db.commit()
    db.refresh(task)
    return task
