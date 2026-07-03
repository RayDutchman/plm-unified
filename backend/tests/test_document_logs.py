"""图文档操作记录相关测试。"""
from app.crud import get_logs
from app.models import OperationLog


def test_get_logs_supports_multiple_target_types(db):
    """get_logs 应支持传入 target_type 列表同时过滤多种类型。"""
    from app.models import Workspace, User
    from app.core.security import get_password_hash
    ws = Workspace(name="w")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    u = User(workspace_id=ws.id, username="admin", password_hash=get_password_hash("x"), real_name="A", role="admin")
    db.add(u)
    db.commit()

    log1 = OperationLog(user_id=u.id, username="admin", action="创建图文档", target_type="document", target_id="doc-1")
    log2 = OperationLog(user_id=u.id, username="admin", action="上传附件", target_type="document_att", target_id="doc-1")
    log3 = OperationLog(user_id=u.id, username="admin", action="更新图文档", target_type="document", target_id="doc-2")
    db.add_all([log1, log2, log3])
    db.commit()

    items, total = get_logs(db, target_type=["document", "document_att"], target_id="doc-1")
    assert total == 2
    actions = {log.action for log in items}
    assert actions == {"创建图文档", "上传附件"}

    # 旧参数类型兼容性断言
    items, total = get_logs(db, target_type="document", target_id="doc-1")
    assert total == 1
    assert items[0].action == "创建图文档"

    items, total = get_logs(db, target_id="doc-1")
    assert total == 2
