from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..templating import render

router = APIRouter()


@router.get("/guide")
def guide(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The Features / Guide page: what each feature does, with simple steps. Open to everyone."""
    return render(request, "guide.html", user)
