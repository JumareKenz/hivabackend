from app.api.v1.kb_factory import build_kb_router

router = build_kb_router(kb_id="kaduna", prefix="/states/kaduna", tag="state:kaduna")


