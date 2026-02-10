from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_actor, get_introspection_service
from app.schemas.introspection import IntrospectionRequest, IntrospectionResponse
from app.service.introspection import IntrospectionService

router = APIRouter(tags=["introspection"])


@router.post("/introspect", response_model=IntrospectionResponse, status_code=status.HTTP_201_CREATED)
def introspect_table(
    payload: IntrospectionRequest,
    actor: Annotated[str, Depends(get_actor)],
    service: Annotated[IntrospectionService, Depends(get_introspection_service)],
) -> IntrospectionResponse:
    contract, version = service.introspect_table(payload, actor)
    return IntrospectionResponse.model_validate({"contract": contract, "version": version})
