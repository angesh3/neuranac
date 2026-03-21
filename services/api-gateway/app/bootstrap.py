"""Bootstrap module - runs on first start to initialize the system"""
import os
import secrets
import stat
import structlog
from sqlalchemy import select, text
from app.database.session import async_session_factory, Base, engine
from app.middleware.auth import hash_password

logger = structlog.get_logger()


async def run_bootstrap():
    """Execute all bootstrap steps idempotently"""
    if not async_session_factory:
        logger.warning("Database not initialized, skipping bootstrap")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Check if already bootstrapped
        from app.models.admin import BootstrapState, Tenant, AdminUser, AdminRole
        result = await session.execute(
            select(BootstrapState).where(BootstrapState.step == "initial_setup")
        )
        if result.scalar_one_or_none():
            logger.info("Bootstrap already completed")
            return

        logger.info("Running first-time bootstrap...")

        # Step 1: Create default tenant
        tenant = Tenant(name="Default", slug="default", status="active")
        session.add(tenant)
        await session.flush()

        # Step 2: Create super-admin role
        admin_role = AdminRole(
            tenant_id=tenant.id,
            name="super-admin",
            description="Full system access",
            permissions=["admin:super"],
            is_builtin=True,
        )
        session.add(admin_role)
        await session.flush()

        # Step 3: Create default admin user
        default_password = secrets.token_urlsafe(16)
        admin_user = AdminUser(
            tenant_id=tenant.id,
            username="admin",
            email="admin@neuranac.local",
            password_hash=hash_password(default_password),
            role_id=admin_role.id,
            role_name="super-admin",
            is_active=True,
        )
        session.add(admin_user)

        # Step 4: Mark bootstrap complete
        bootstrap = BootstrapState(step="initial_setup", completed=True)
        session.add(bootstrap)

        await session.commit()

        # Write initial credentials to a secure one-time file instead of logging
        cred_path = os.environ.get("NEURANAC_INITIAL_CREDS_PATH", "/tmp/neuranac-initial-password")
        try:
            with open(cred_path, "w") as f:
                f.write(f"username=admin\npassword={default_password}\n")
            os.chmod(cred_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
            logger.info("Bootstrap completed — initial credentials written to file",
                        path=cred_path)
        except OSError as exc:
            logger.warning("Could not write credentials file, printing to stdout",
                           error=str(exc))
            print(f"NeuraNAC_INITIAL_PASSWORD={default_password}")

        logger.info("Dashboard: https://localhost:8443")
        logger.info("API Docs: http://localhost:8080/api/docs")
