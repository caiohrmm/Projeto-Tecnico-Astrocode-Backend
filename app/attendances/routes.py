"""Attendance routes for CRUD operations."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.attendances.models import Attendance, AttendanceChannel, AttendanceStatus
from app.attendances.repository import AttendanceRepository
from app.attendances.schemas import AttendanceCreate, AttendanceResponse, AttendanceUpdate
from app.db import get_db
from app.users.models import User
from app.users.repository import UserRepository

router = APIRouter(prefix="/attendances", tags=["attendances"])


def _validate_agent_is_corretor(agent_id: uuid.UUID, db: Session) -> None:
    """
    Validate that agent_id belongs to a user with 'corretor' role.

    Args:
        agent_id: UUID of the agent to validate
        db: Database session

    Raises:
        HTTPException: If agent_id is provided but user doesn't have 'corretor' role
    """
    user_repo = UserRepository(db)
    agent = user_repo.get_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {agent_id} not found",
        )

    # Check if user has 'corretor' role
    role_names = [role.name for role in agent.roles]
    if "corretor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {agent_id} does not have 'corretor' role. Only users with 'corretor' role can be assigned as agents.",
        )


@router.post("/", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
def create_attendance(
    attendance_data: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    """
    Create a new attendance or update an existing active one.

    **Cycle Logic:**
    - If the client has an active attendance with the same objective, the new content
      will be accumulated into the existing attendance (conversation continues).
    - If the objective has changed significantly, the previous active attendance will be
      closed (ABANDONED) and a new attendance cycle will be created.
    - If no objective is provided, it will be auto-detected from the raw_content.

    **Automatic Behaviors:**
    - AI summary is generated automatically for new attendances.
    - If updated_client_status is provided, client status will be updated.
    - If scheduled_visit_at is provided, a visit will be created automatically.
    - Client state is derived from AI signals with anti-flip logic.

    Args:
        attendance_data: Attendance creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created or updated attendance response
    """
    # Validate agent_id must be a corretor
    _validate_agent_is_corretor(attendance_data.agent_id, db)

    attendance_repo = AttendanceRepository(db)
    
    # Track if there was an existing active attendance before creation
    existing_active = attendance_repo.get_active_attendance_by_client(attendance_data.client_id)
    existing_id = existing_active.id if existing_active else None
    
    attendance = attendance_repo.create(attendance_data)
    
    # Determine the action taken
    from app.attendances.schemas import CycleAction, DetectedVisitInfo
    
    if existing_active and existing_active.id != attendance.id:
        # New cycle created, previous one was closed
        cycle_action = CycleAction.NEW_CYCLE_CREATED
        previous_cycle_id = existing_active.id
    elif existing_active and existing_active.id == attendance.id:
        # Existing cycle was updated
        cycle_action = CycleAction.CYCLE_UPDATED
        previous_cycle_id = None
    else:
        # New cycle created (no previous active)
        cycle_action = CycleAction.NEW_CYCLE_CREATED
        previous_cycle_id = None
    
    # Detect visit intent from raw_content using AI
    detected_visit = None
    try:
        from app.ai.service import AISummaryService
        from datetime import datetime
        
        visit_info = AISummaryService.detect_visit_intent(
            raw_content=attendance.raw_content,
            client_id=attendance.client_id,
            property_id=attendance.property_id,
            agent_id=attendance.agent_id,
        )
        
        if visit_info and visit_info.get("detected"):
            detected_visit = DetectedVisitInfo(**visit_info)
            
            # If visit was detected and attendance doesn't have scheduled_visit_at yet, create it
            if detected_visit.scheduled_at and not attendance.scheduled_visit_at:
                try:
                    # Parse the scheduled_at from ISO format
                    scheduled_at = datetime.fromisoformat(detected_visit.scheduled_at.replace('Z', '+00:00'))
                    
                    # Update attendance with scheduled_visit_at
                    attendance.scheduled_visit_at = scheduled_at
                    db.commit()
                    db.refresh(attendance)
                    
                    # Create visit automatically
                    attendance_repo._create_visit_from_attendance(attendance)
                    
                    logger.info(f"Visit automatically created from detected intent: {detected_visit.scheduled_at}")
                except Exception as e:
                    logger.warning(f"Error creating visit from detected intent: {e}", exc_info=True)
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error detecting visit intent: {e}", exc_info=True)
    
    # Detect loss intent from raw_content using AI
    # ⚠️ IMPORTANT: This is ONLY a suggestion. Attendance status remains ACTIVE until user confirms.
    detected_loss = None
    try:
        from app.ai.service import AISummaryService
        from app.attendances.schemas import DetectedLossInfo
        
        # ⚠️ PROTECTION: Only detect if attendance is still ACTIVE (not LOST, COMPLETED, or ABANDONED)
        # This prevents multiple detections and annoying popups
        if attendance.status.value == "ACTIVE":
            loss_info = AISummaryService.detect_loss_intent(
                raw_content=attendance.raw_content,
                client_id=attendance.client_id,
                property_id=attendance.property_id,
                agent_id=attendance.agent_id,
                attendance_status=attendance.status.value,  # Pass current status to skip if LOST
            )
            
            if loss_info and loss_info.get("detected"):
                detected_loss = DetectedLossInfo(**loss_info)
                logger.info(f"Loss intent detected (suggestion only): {detected_loss.loss_reason} at stage {detected_loss.loss_stage}. Attendance remains ACTIVE until user confirms.")
        else:
            logger.debug(f"Skipping loss detection: attendance status is {attendance.status.value} (not ACTIVE)")
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error detecting loss intent: {e}", exc_info=True)
    
    # Create response with cycle action info, detected visit, and detected loss
    # Use model_validate and then add cycle action fields using model_copy
    response = AttendanceResponse.model_validate(attendance)
    response = response.model_copy(update={
        'cycle_action': cycle_action,
        'previous_cycle_id': previous_cycle_id,
        'detected_visit': detected_visit,
        'detected_loss': detected_loss,
    })
    
    return response


@router.get("/", response_model=List[AttendanceResponse])
def list_attendances(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    client_id: uuid.UUID | None = Query(None, description="Filter by client ID"),
    agent_id: uuid.UUID | None = Query(None, description="Filter by agent ID"),
    property_id: uuid.UUID | None = Query(None, description="Filter by property ID"),
    channel: AttendanceChannel | None = Query(None, description="Filter by channel"),
    status: AttendanceStatus | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[AttendanceResponse]:
    """
    List all attendances with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        client_id: Optional filter by client ID
        agent_id: Optional filter by agent ID
        property_id: Optional filter by property ID
        channel: Optional filter by channel
        status: Optional filter by status
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of attendance responses
    """
    attendance_repo = AttendanceRepository(db)
    attendances = attendance_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        agent_id=agent_id,
        property_id=property_id,
        channel=channel,
        status=status,
    )
    
    # Serialize attendances with error handling
    result = []
    for attendance in attendances:
        try:
            result.append(AttendanceResponse.model_validate(attendance))
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error serializing attendance {attendance.id}: {e}", exc_info=True)
            # Continue with other attendances even if one fails
            continue
    
    return result


@router.get("/active/client/{client_id}", response_model=AttendanceResponse)
def get_active_attendance_by_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    """
    Get the active attendance for a specific client.

    This endpoint is useful for checking if a client has an ongoing attendance cycle
    before creating a new one. The system ensures only one ACTIVE attendance per client.

    Args:
        client_id: Client UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Active attendance response

    Raises:
        HTTPException: If no active attendance exists (404)
    """
    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_active_attendance_by_client(client_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active attendance found for client {client_id}",
        )

    return AttendanceResponse.model_validate(attendance)


@router.get("/{attendance_id}", response_model=AttendanceResponse)
def get_attendance(
    attendance_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    """
    Get an attendance by ID.

    Args:
        attendance_id: Attendance UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Attendance response

    Raises:
        HTTPException: If attendance is not found
    """
    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    return AttendanceResponse.model_validate(attendance)


@router.put("/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(
    attendance_id: uuid.UUID,
    attendance_data: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    """
    Update an attendance.

    **Important Notes:**
    - If you update the `objective` field for an ACTIVE attendance, consider whether
      this should trigger a new cycle instead. The system will not automatically
      close and recreate attendances on objective updates (manual control).
    - If `status` is changed to COMPLETED, AI summary will be regenerated automatically.
    - If `raw_content` or other AI-relevant fields are updated for a COMPLETED attendance,
      the AI summary will be regenerated.

    **Automatic Behaviors:**
    - Duration is recalculated automatically if ended_at is updated.
    - If updated_client_status is provided, client status will be updated.
    - If scheduled_visit_at is provided and not already set, a visit will be created.

    Args:
        attendance_id: Attendance UUID
        attendance_data: Attendance update data (only provided fields will be updated)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated attendance response

    Raises:
        HTTPException: If attendance is not found
    """
    # Validate agent_id if being updated
    if attendance_data.agent_id is not None:
        _validate_agent_is_corretor(attendance_data.agent_id, db)

    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    updated_attendance = attendance_repo.update(attendance, attendance_data)
    
    # Detect visit intent if raw_content was updated
    detected_visit = None
    if attendance_data.raw_content is not None:
        try:
            from app.ai.service import AISummaryService
            from app.attendances.schemas import DetectedVisitInfo
            from datetime import datetime
            
            visit_info = AISummaryService.detect_visit_intent(
                raw_content=updated_attendance.raw_content,
                client_id=updated_attendance.client_id,
                property_id=updated_attendance.property_id,
                agent_id=updated_attendance.agent_id,
            )
            
            if visit_info and visit_info.get("detected"):
                detected_visit = DetectedVisitInfo(**visit_info)
                
                # If visit was detected and attendance doesn't have scheduled_visit_at yet, create it
                if detected_visit.scheduled_at and not updated_attendance.scheduled_visit_at:
                    try:
                        # Parse the scheduled_at from ISO format
                        scheduled_at = datetime.fromisoformat(detected_visit.scheduled_at.replace('Z', '+00:00'))
                        
                        # Update attendance with scheduled_visit_at
                        updated_attendance.scheduled_visit_at = scheduled_at
                        db.commit()
                        db.refresh(updated_attendance)
                        
                        # Create visit automatically
                        attendance_repo._create_visit_from_attendance(updated_attendance)
                        
                        logger.info(f"Visit automatically created from detected intent: {detected_visit.scheduled_at}")
                    except Exception as e:
                        logger.warning(f"Error creating visit from detected intent: {e}", exc_info=True)
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error detecting visit intent: {e}", exc_info=True)
    
    # Detect loss intent if raw_content was updated
    # ⚠️ IMPORTANT: This is ONLY a suggestion. Attendance status remains ACTIVE until user confirms.
    detected_loss = None
    if attendance_data.raw_content is not None:
        try:
            from app.ai.service import AISummaryService
            from app.attendances.schemas import DetectedLossInfo
            
            # ⚠️ PROTECTION: Only detect if attendance is still ACTIVE (not LOST, COMPLETED, or ABANDONED)
            # This prevents multiple detections and annoying popups
            if updated_attendance.status.value == "ACTIVE":
                loss_info = AISummaryService.detect_loss_intent(
                    raw_content=updated_attendance.raw_content,
                    client_id=updated_attendance.client_id,
                    property_id=updated_attendance.property_id,
                    agent_id=updated_attendance.agent_id,
                    attendance_status=updated_attendance.status.value,  # Pass current status to skip if LOST
                )
                
                if loss_info and loss_info.get("detected"):
                    detected_loss = DetectedLossInfo(**loss_info)
                    logger.info(f"Loss intent detected (suggestion only): {detected_loss.loss_reason} at stage {detected_loss.loss_stage}. Attendance remains ACTIVE until user confirms.")
            else:
                logger.debug(f"Skipping loss detection: attendance status is {updated_attendance.status.value} (not ACTIVE)")
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error detecting loss intent: {e}", exc_info=True)
    
    response = AttendanceResponse.model_validate(updated_attendance)
    update_dict = {}
    if detected_visit:
        update_dict['detected_visit'] = detected_visit
    if detected_loss:
        update_dict['detected_loss'] = detected_loss
    if update_dict:
        response = response.model_copy(update=update_dict)
    
    return response


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete an attendance.

    Args:
        attendance_id: Attendance UUID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If attendance is not found
    """
    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    attendance_repo.delete(attendance)

