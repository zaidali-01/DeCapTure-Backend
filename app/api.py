from fastapi import APIRouter

from app.modules.Accounts.router import router as accounts_router
from app.modules.Analytics.router import router as analytics_router
from app.modules.Audit.router import router as audit_router
from app.modules.Business.router import router as business_router
from app.modules.CRM.router import router as crm_router
from app.modules.Communications.router import router as communications_router
from app.modules.Employees.router import router as employees_router
from app.modules.Loyalty.router import router as loyalty_router
from app.modules.Marketing.router import router as marketing_router
from app.modules.Notifications.router import router as notifications_router
from app.modules.POS.router import router as pos_router
from app.modules.Suppliers.router import router as suppliers_router
from app.modules.Store.router import router as store_router
from app.modules.Users.router import router as users_router

api_router = APIRouter()

api_router.include_router(users_router)
api_router.include_router(business_router)
api_router.include_router(communications_router)
api_router.include_router(pos_router)
api_router.include_router(marketing_router)
api_router.include_router(analytics_router)
api_router.include_router(accounts_router)
api_router.include_router(crm_router)
api_router.include_router(employees_router)
api_router.include_router(suppliers_router)
api_router.include_router(notifications_router)
api_router.include_router(audit_router)
api_router.include_router(loyalty_router)
api_router.include_router(store_router)
