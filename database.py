import uuid
from contextvars import ContextVar

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from models import TenantAwareModel

# Geçerli isteğin org_id'sini thread-safe şekilde tutacak değişken
current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar("current_tenant_id", default=None)

@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(execute_state: ORMExecuteState):
    """
    Bu fonksiyon, veritabanına giden HER SORGUDAN (SELECT, UPDATE, DELETE)
    önce araya girer. Eğer sorgulanan tablo TenantAwareModel'den türemişse,
    otomatik olarak 'WHERE org_id = current_tenant_id' koşulunu ekler.
    """
    # Sadece okuma (SELECT) veya silme/güncelleme işlemleri için araya gir
    if execute_state.is_select or execute_state.is_update or execute_state.is_delete:
        
        # Context'ten mevcut kiracının ID'sini al
        tenant_id = current_tenant_id.get()
        
        if tenant_id:
            # Tüm sorgulara otomatik filter uygula
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(
                    TenantAwareModel,
                    lambda cls: cls.org_id == tenant_id,
                    include_aliases=True
                )
            )