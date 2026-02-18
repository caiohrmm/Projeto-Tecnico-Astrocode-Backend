"""Dashboard metrics service for AI chat context."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.models import Client, ClientStatus
from app.losses.models import ClientLoss
from app.sales.models import Sale, SaleStatus
from app.attendances.models import Attendance
from app.visits.models import Visit, VisitStatus
from app.properties.models import Property, PropertyStatus
from app.users.models import User
from app.users.repository import UserRepository
from app.users.role_repository import RoleRepository


def get_dashboard_context_for_chat(db: Session) -> dict[str, Any]:
    """
    Load dashboard metrics for AI chat context.
    Returns a condensed structure suitable for the assistant to interpret.
    """
    now = datetime.utcnow()

    # Clients
    clients = list(db.scalars(select(Client)).all())
    total_clients = len(clients)
    active_leads = len([c for c in clients if c.current_status and c.current_status.value not in ("WON", "LOST", "INACTIVE")])
    won_clients = len([c for c in clients if c.current_status and c.current_status.value == "WON"])
    lost_clients = len([c for c in clients if c.current_status and c.current_status.value == "LOST"])
    clients_by_status = defaultdict(int)
    for c in clients:
        s = c.current_status.value if c.current_status else "NO_STATUS"
        clients_by_status[s] += 1

    # Lead score
    scores = [c.current_lead_score for c in clients if c.current_lead_score is not None]
    avg_lead_score = round(sum(scores) / len(scores)) if scores else 0

    # Sales stats
    sales = list(db.scalars(select(Sale)).all())
    completed_sales = [s for s in sales if s.status == SaleStatus.COMPLETED]
    total_sales_value = sum(float(s.sale_value or 0) for s in completed_sales)
    total_commission = sum(float(s.commission_value or 0) for s in completed_sales)

    # Loss stats
    losses = list(db.scalars(select(ClientLoss)).all())

    # Activity (needed for conversion rate)
    attendances = list(db.scalars(select(Attendance)).all())
    visits = list(db.scalars(select(Visit)).all())
    total_attendances = len(attendances)
    total_visits = len(visits)

    # Conversion rate = vendas concluídas / total de atendimentos
    conversion_rate = round((len(completed_sales) / total_attendances) * 100, 2) if total_attendances > 0 else 0
    loss_rate = round((lost_clients / total_clients) * 100, 2) if total_clients > 0 else 0
    upcoming_visits = len([
        v for v in visits
        if v.scheduled_at and v.scheduled_at >= now
        and v.status in (VisitStatus.SCHEDULED, VisitStatus.CONFIRMED, VisitStatus.IN_PROGRESS)
    ])

    # Properties
    properties = list(db.scalars(select(Property)).all())
    total_properties = len(properties)
    available_properties = len([p for p in properties if p.status == PropertyStatus.PUBLISHED])

    # Funnel
    funnel_stages = [
        ("NEW_LEAD", "Novo Lead"),
        ("CONTACTED", "Contatado"),
        ("QUALIFIED", "Qualificado"),
        ("VISIT_SCHEDULED", "Visita Agendada"),
        ("VISITING", "Em Visita"),
        ("PROPOSAL_SENT", "Proposta Enviada"),
        ("NEGOTIATING", "Negociando"),
        ("WON", "Ganho"),
        ("LOST", "Perdido"),
    ]
    funnel_data = [
        {"stage": label, "count": clients_by_status.get(key, 0), "percentage": round((clients_by_status.get(key, 0) / total_clients) * 100, 2) if total_clients > 0 else 0}
        for key, label in funnel_stages
        if clients_by_status.get(key, 0) > 0
    ]

    # Monthly trends (last 6 months)
    monthly_trends = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        if m <= 0:
            m += 12
            y -= 1
        month_start = datetime(y, m, 1)
        if m == 12:
            month_end = datetime(y + 1, 1, 1)
        else:
            month_end = datetime(y, m + 1, 1)
        month_clients = len([c for c in clients if c.created_at and month_start <= c.created_at < month_end])
        month_sales = len([s for s in completed_sales if s.created_at and month_start <= s.created_at < month_end])
        month_sales_value = sum(float(s.sale_value or 0) for s in completed_sales if s.created_at and month_start <= s.created_at < month_end)
        month_losses = len([l for l in losses if l.lost_at and month_start <= l.lost_at < month_end])
        monthly_trends.append({
            "month": month_start.strftime("%m/%Y"),
            "clients": month_clients,
            "sales": month_sales,
            "revenue": month_sales_value,
            "losses": month_losses,
        })

    # Broker performance
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    corretor_role = role_repo.get_by_name("corretor")
    corretores = user_repo.get_by_role(corretor_role.id) if corretor_role else []
    broker_performance = []
    for broker in corretores:
        broker_sales = [s for s in completed_sales if s.broker_id == broker.id]
        broker_attendances = [a for a in attendances if a.agent_id == broker.id]
        conversion = round((len(broker_sales) / len(broker_attendances)) * 100, 2) if broker_attendances else 0
        broker_performance.append({
            "name": broker.full_name or broker.email or "Corretor",
            "total_sales": len(broker_sales),
            "revenue": sum(float(s.sale_value or 0) for s in broker_sales),
            "commission": sum(float(s.commission_value or 0) for s in broker_sales),
            "conversion_rate": conversion,
        })
    broker_performance.sort(key=lambda x: x["revenue"], reverse=True)

    # Insights
    top_opportunities = [
        {"name": c.name, "score": c.current_lead_score}
        for c in sorted(
            [c for c in clients if c.current_lead_score and c.current_lead_score >= 70 and c.current_status and c.current_status.value not in ("WON", "LOST", "INACTIVE")],
            key=lambda x: x.current_lead_score or 0,
            reverse=True,
        )[:5]
    ]
    seven_days_ago = now - timedelta(days=7)
    at_risk = [
        {"name": c.name, "urgency": c.current_urgency_level.value if c.current_urgency_level else None}
        for c in clients
        if c.last_contact_at and c.last_contact_at < seven_days_ago
        and c.current_urgency_level and c.current_urgency_level.value in ("HIGH", "IMMEDIATE")
        and c.current_status and c.current_status.value not in ("WON", "LOST", "INACTIVE")
    ][:5]
    high_value = [
        {"name": c.name, "budget_max": float(c.current_budget_max) if c.current_budget_max else 0}
        for c in sorted(
            [c for c in clients if c.current_budget_max and float(c.current_budget_max) >= 500000 and c.current_status and c.current_status.value not in ("WON", "LOST", "INACTIVE")],
            key=lambda x: float(x.current_budget_max or 0),
            reverse=True,
        )[:5]
    ]

    return {
        "total_clients": total_clients,
        "active_leads": active_leads,
        "won_clients": won_clients,
        "lost_clients": lost_clients,
        "clients_by_status": dict(clients_by_status),
        "avg_lead_score": avg_lead_score,
        "sales_count": len(completed_sales),
        "sales_total_value": total_sales_value,
        "sales_commission": total_commission,
        "losses_count": len(losses),
        "conversion_rate": conversion_rate,
        "loss_rate": loss_rate,
        "total_attendances": total_attendances,
        "total_visits": total_visits,
        "upcoming_visits": upcoming_visits,
        "total_properties": total_properties,
        "available_properties": available_properties,
        "funnel_data": funnel_data,
        "monthly_trends": monthly_trends,
        "broker_performance": broker_performance,
        "top_opportunities": top_opportunities,
        "at_risk_clients": at_risk,
        "high_value_leads": high_value,
    }
