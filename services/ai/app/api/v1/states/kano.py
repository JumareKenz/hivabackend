from app.api.v1.kb_factory import build_kb_router

router = build_kb_router(kb_id="kano", prefix="/states/kano", tag="state:kano")


