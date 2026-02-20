"""AI Chat routes for Gemini-powered chat agent."""

import logging
from concurrent.futures import ThreadPoolExecutor
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.ai.chat_service import ChatService
from app.ai.schemas import ChatRequest, ChatResponse
from app.db import get_db
from app.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/chat", tags=["ai-chat"])

# Palavras-chave que indicam pedido de resumo/métricas da dashboard (carrega dashboard mesmo sem include_dashboard no body)
DASHBOARD_MESSAGE_KEYWORDS = (
    "dashboard",
    "métricas da dashboard",
    "resumo da dashboard",
    "métricas",
    "visão geral",
    "resumo executivo",
    "como está a imobiliária",
    "como está o negócio",
    "resuma as principais",
    "resumo das principais",
)


def _message_asks_for_dashboard(message: str) -> bool:
    """Return True if the message clearly asks for dashboard/summary metrics."""
    if not message or not message.strip():
        return False
    lower = message.lower().strip()
    return any(kw in lower for kw in DASHBOARD_MESSAGE_KEYWORDS)

# Thread pool executor for blocking Gemini API calls
_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """Get or create the thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="gemini")
    return _executor


def shutdown_executor():
    """Shutdown the thread pool executor gracefully."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True, timeout=5.0)
        _executor = None


@router.post(
    "/",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ChatResponse:
    """
    Chat with AI agent about CRM system data.
    
    The AI can answer questions about clients, properties, and attendances
    based on data loaded from the database. It will never hallucinate data
    and will explicitly state when information is not available.
    
    Args:
        request: Chat request with message and optional context IDs
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        AI response with answer and optional error
    
    Raises:
        HTTPException: If context IDs are invalid or data cannot be loaded
    """
    try:
        chat_service = ChatService(db)
        
        # Incluir dashboard quando o frontend pedir OU quando a mensagem pedir resumo da dashboard
        include_dashboard = request.include_dashboard or _message_asks_for_dashboard(request.message)
        
        # Load context data if IDs provided or dashboard requested
        context_data = None
        if request.context or include_dashboard:
            context_data = chat_service.load_context(
                client_id=request.context.client_id if request.context else None,
                property_id=request.context.property_id if request.context else None,
                attendance_id=request.context.attendance_id if request.context else None,
                include_dashboard=include_dashboard,
            )
        
        # Run Gemini API call in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        executor = get_executor()
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    chat_service.get_response,
                    request.message,
                    context_data,
                ),
                timeout=35.0,  # Slightly longer than Gemini timeout (30s)
            )
        except asyncio.TimeoutError:
            logger.error("Gemini API call timed out")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI service timeout. Please try again.",
            )
        except asyncio.CancelledError:
            logger.warning("Gemini API call was cancelled")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Request was cancelled. Please try again.",
            )
        
        return ChatResponse(**response)
        
    except ValueError as e:
        logger.error(f"Invalid context ID: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat request: {str(e)}",
        )

