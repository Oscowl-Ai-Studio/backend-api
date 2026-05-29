import time
from sqlalchemy.orm import Session
from app.models import User, Workspace, WorkspaceStatus
from app.main import provision_workspace

# --- Helper Functions ---
def create_user(db: Session, username: str, email: str, password_hash: str):
    db_user = User(username=username, email=email, hashed_password=password_hash)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_workspace_lifecycle(db: Session, name: str, description: str, owner_id: int):
    """Creates a workspace and simulates container startup state transition."""
    db_workspace = Workspace(name=name, description=description, owner_id=owner_id)
    db.add(db_workspace)
    db.commit()
    db.refresh(db_workspace)
    
    assert db_workspace.status == WorkspaceStatus.CREATING
    
    time.sleep(0.05)
    
    db_workspace.status = WorkspaceStatus.RUNNING
    db.commit()
    db.refresh(db_workspace)
    
    return db_workspace


# --- Pytest Tests ---

def test_workspace_lifecycle(db_session):
    """Verifies user creation and workspace life-cycle states."""
    user = create_user(
        db=db_session, 
        username="sunsung_dev", 
        email="sunsung@example.com", 
        password_hash="secret123"
    )

    workspace = create_workspace_lifecycle(
        db=db_session,
        name="Main Workspace",
        description="Testing layout setups",
        owner_id=user.id
    )

    assert workspace.id is not None
    assert workspace.status == WorkspaceStatus.RUNNING
    assert workspace.status.value == "running"  


def test_provision_workspace_background_stub(db_session):
    """Verifies that the provision_workspace function changes status from creating to running."""
    # 1. Arrange: Setup user and initial workspace state
    user = create_user(
        db=db_session, 
        username="async_test_user", 
        email="async@test.com", 
        password_hash="abc"
    )

    workspace = Workspace(name="Async Pod Tracker", description="Testing thread updates", owner_id=user.id)
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    
    # Store the ID safely before closing session references
    workspace_id = workspace.id
    assert workspace.status == WorkspaceStatus.CREATING

    # Expel the workspace tracking from the test session context 
    # so provision_workspace can fetch it fresh without collision errors
    db_session.expunge(workspace)

    # 2. Act: Execute the background provisioning handler manually using our clean factory pattern
    provision_workspace(workspace_id=workspace_id, db_session_factory=lambda: db_session)

    # 3. Assert: Fetch it back fresh from the DB to check its updated status
    updated_workspace = db_session.query(Workspace).filter(Workspace.id == workspace_id).first()
    assert updated_workspace.status == WorkspaceStatus.RUNNING
    assert updated_workspace.status.value == "running"               # Check user's workspace collection