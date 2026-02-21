"""Sales routes for CRUD operations."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db import get_db
from app.sales.models import Sale, SaleStatus, SaleType
from app.sales.repository import SaleRepository
from app.sales.schemas import SaleCreate, SaleResponse, SaleStats, SaleUpdate, SaleWithDetails
from app.users.models import User

router = APIRouter(prefix="/sales", tags=["sales"])


def _enrich_sale_response(sale: Sale) -> dict:
    """Enrich sale with related entity names."""
    data = {
        "id": sale.id,
        "client_id": sale.client_id,
        "property_id": sale.property_id,
        "broker_id": sale.broker_id,
        "sale_type": sale.sale_type,
        "status": sale.status,
        "sale_value": sale.sale_value,
        "commission_percentage": sale.commission_percentage,
        "commission_value": sale.commission_value,
        "down_payment": sale.down_payment,
        "payment_method": sale.payment_method,
        "payment_methods": sale.payment_methods,
        "rent_duration_months": sale.rent_duration_months,
        "rent_start_date": sale.rent_start_date,
        "proposal_date": sale.proposal_date,
        "contract_date": sale.contract_date,
        "completion_date": sale.completion_date,
        "notes": sale.notes,
        "ai_analysis": sale.ai_analysis,
        "ai_success_factors": sale.ai_success_factors,
        "created_at": sale.created_at,
        "updated_at": sale.updated_at,
        # Enriched fields
        "client_name": sale.client.name if sale.client else None,
        "property_title": sale.property.title if sale.property else None,
        "broker_name": sale.broker.full_name if sale.broker else None,
    }
    return data


@router.post(
    "/",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar venda/aluguel",
    description="""
Registra uma nova venda ou aluguel.

**Efeitos automáticos:**
- **Cliente:** status atualizado para **WON**.
- **Imóvel:** status atualizado para **SOLD** (venda) ou **RENTED** (aluguel), se property_id informado.
- **Comissão:** valor calculado a partir de commission_percentage e sale_value.
- **Atendimento:** o atendimento ACTIVE do cliente é fechado (status COMPLETED).
- **Timeline:** evento adicionado na timeline do cliente.

Status inicial da venda: PENDING. Requer autenticação.
    """.strip(),
    responses={
        201: {"description": "Venda/aluguel registrado"},
        400: {"description": "Atendimento ativo sem imóvel vinculado"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente ou imóvel não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def create_sale(
    sale_data: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleResponse:
    from app.attendances.repository import AttendanceRepository

    attendance_repo = AttendanceRepository(db)
    active_attendance = attendance_repo.get_active_attendance_by_client(sale_data.client_id)
    if active_attendance and not active_attendance.property_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Para registrar venda, o atendimento ativo do cliente deve ter um imóvel vinculado. Use a página de detalhes do atendimento e o botão 'Alterar imóvel'.",
        )
    sale_repo = SaleRepository(db)
    sale = sale_repo.create(sale_data)
    return SaleResponse(**_enrich_sale_response(sale))


@router.get(
    "/",
    response_model=List[SaleResponse],
    summary="Listar vendas/aluguéis",
    description="""
Lista vendas e aluguéis com paginação e filtros opcionais.

**Filtros:** client_id, property_id, broker_id, sale_type (SALE/RENT), sale_status (PENDING, SIGNED, COMPLETED, CANCELLED). Resposta inclui nomes do cliente, imóvel e corretor.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de vendas/aluguéis"},
        401: {"description": "Não autenticado"},
    },
)
def list_sales(
    skip: int = Query(0, ge=0, description="Registros a pular (paginação)"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros"),
    client_id: uuid.UUID | None = Query(None, description="Filtrar por cliente"),
    property_id: uuid.UUID | None = Query(None, description="Filtrar por imóvel"),
    broker_id: uuid.UUID | None = Query(None, description="Filtrar por corretor"),
    sale_type: SaleType | None = Query(None, description="Filtrar por tipo (SALE ou RENT)"),
    sale_status: SaleStatus | None = Query(None, description="Filtrar por status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[SaleResponse]:
    sale_repo = SaleRepository(db)
    sales = sale_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        property_id=property_id,
        broker_id=broker_id,
        sale_type=sale_type,
        status=sale_status,
    )
    return [SaleResponse(**_enrich_sale_response(sale)) for sale in sales]


@router.get(
    "/stats",
    response_model=SaleStats,
    summary="Estatísticas de vendas",
    description="""
Retorna estatísticas agregadas: total de vendas, valor total, comissão total, contagens por tipo (venda/aluguel) e por status (pendentes/concluídas), médias. Filtros opcionais: broker_id, start_date, end_date.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Estatísticas (SaleStats)"},
        401: {"description": "Não autenticado"},
    },
)
def get_sales_stats(
    broker_id: uuid.UUID | None = Query(None, description="Filtrar por corretor"),
    start_date: datetime | None = Query(None, description="Data inicial"),
    end_date: datetime | None = Query(None, description="Data final"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleStats:
    sale_repo = SaleRepository(db)
    return sale_repo.get_stats(
        broker_id=broker_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/{sale_id}",
    response_model=SaleWithDetails,
    summary="Buscar venda por ID",
    description="Retorna uma venda/aluguel pelo UUID com detalhes completos: dados da venda, nome do cliente/imóvel/corretor, telefone e e-mail do cliente, endereço e cidade do imóvel.",
    responses={
        200: {"description": "Venda com detalhes (SaleWithDetails)"},
        401: {"description": "Não autenticado"},
        404: {"description": "Venda não encontrada"},
    },
)
def get_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleWithDetails:
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    data = _enrich_sale_response(sale)
    
    # Add extra details
    if sale.client:
        data["client_phone"] = sale.client.phone
        data["client_email"] = sale.client.email
    
    if sale.property:
        data["property_address"] = f"{sale.property.street}, {sale.property.number}" if sale.property.street else None
        data["property_city"] = sale.property.city
    
    return SaleWithDetails(**data)


@router.put(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Atualizar venda",
    description="""
Atualização parcial. Transições de status com efeitos automáticos:

- **SIGNED:** define contract_date e adiciona evento na timeline.
- **COMPLETED:** define completion_date e dispara análise de sucesso pela IA (ai_analysis, ai_success_factors).
- **CANCELLED:** reverte status do cliente para LOST e do imóvel para PUBLISHED.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Venda atualizada"},
        401: {"description": "Não autenticado"},
        404: {"description": "Venda não encontrada"},
        422: {"description": "Dados inválidos"},
    },
)
def update_sale(
    sale_id: uuid.UUID,
    sale_data: SaleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleResponse:
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    updated_sale = sale_repo.update(sale, sale_data)
    return SaleResponse(**_enrich_sale_response(updated_sale))


@router.delete(
    "/{sale_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir venda",
    description="""
Remove a venda do sistema. Se a venda não estiver CANCELLED, o status do cliente e do imóvel é revertido (cliente deixa de ser WON; imóvel volta a PUBLISHED). Operação irreversível.

Requer autenticação.
    """.strip(),
    responses={
        204: {"description": "Venda excluída"},
        401: {"description": "Não autenticado"},
        404: {"description": "Venda não encontrada"},
    },
)
def delete_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    sale_repo.delete(sale)


@router.post(
    "/{sale_id}/complete",
    response_model=SaleResponse,
    summary="Concluir venda",
    description="""
Marca a venda como COMPLETED. Atalho que define status COMPLETED, completion_date e dispara a análise de sucesso pela IA (ai_analysis, ai_success_factors).

**Restrição:** não é possível concluir venda já CANCELLED (400).

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Venda concluída"},
        400: {"description": "Venda já cancelada"},
        401: {"description": "Não autenticado"},
        404: {"description": "Venda não encontrada"},
    },
)
def complete_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleResponse:
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    if sale.status == SaleStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete a cancelled sale",
        )
    
    updated_sale = sale_repo.update(sale, SaleUpdate(status=SaleStatus.COMPLETED))
    return SaleResponse(**_enrich_sale_response(updated_sale))


@router.post(
    "/{sale_id}/cancel",
    response_model=SaleResponse,
    summary="Cancelar venda",
    description="""
Marca a venda como CANCELLED. Efeitos: status CANCELLED; cliente volta para **LOST**; imóvel volta para **PUBLISHED**.

**Restrição:** não é possível cancelar venda já COMPLETED (400). Opcionalmente informe **reason** (query) para gravar nas notas.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Venda cancelada"},
        400: {"description": "Venda já concluída"},
        401: {"description": "Não autenticado"},
        404: {"description": "Venda não encontrada"},
    },
)
def cancel_sale(
    sale_id: uuid.UUID,
    reason: str | None = Query(None, description="Motivo do cancelamento (opcional, gravado nas notas)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleResponse:
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    if sale.status == SaleStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed sale",
        )
    
    update_data = SaleUpdate(status=SaleStatus.CANCELLED)
    if reason:
        update_data.notes = f"Cancelado: {reason}"
    
    updated_sale = sale_repo.update(sale, update_data)
    return SaleResponse(**_enrich_sale_response(updated_sale))

