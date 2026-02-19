"""System prompts for AI chat agent to prevent hallucination."""

# Translation mapping for ENUMs to Portuguese
ENUM_TRANSLATIONS = {
    # Property Status
    "DRAFT": "Rascunho",
    "PUBLISHED": "Publicado",
    "SOLD": "Vendido",
    "RENTED": "Alugado",
    "UNAVAILABLE": "Indisponível",
    # Property Type
    "HOUSE": "Casa",
    "APARTMENT": "Apartamento",
    "LAND": "Terreno",
    "COMMERCIAL": "Comercial",
    "RURAL": "Rural",
    # Business Type
    "SALE": "Venda",
    "RENT": "Aluguel",
    "BOTH": "Venda e Aluguel",
    # Interest Type
    "BUY": "Comprar",
    "RENT": "Alugar",
    "SELL": "Vender",
    "INVEST": "Investir",
    # Urgency Level
    "LOW": "Baixa",
    "MEDIUM": "Média",
    "HIGH": "Alta",
    "IMMEDIATE": "Imediata",
    # Client Status (common values)
    "NEW": "Novo",
    "CONTACTED": "Contatado",
    "QUALIFIED": "Qualificado",
    "PROPOSAL": "Proposta",
    "NEGOTIATION": "Negociação",
    "WON": "Ganho",
    "LOST": "Perdido",
    # Attendance Status
    "ACTIVE": "Ativo",
    "COMPLETED": "Concluído",
    "ABANDONED": "Abandonado",
    # Visit Status
    "SCHEDULED": "Agendada",
    "CONFIRMED": "Confirmada",
    "IN_PROGRESS": "Em andamento",
    "CANCELLED": "Cancelada",
    "NO_SHOW": "Não compareceu",
    # Detected Intent
    "SALE_COMPLETED": "Venda concretizada",
    "LOSS_REGISTERED": "Perda registrada",
    "SCHEDULE_VISIT": "Agendar visita",
    "PRICE_NEGOTIATION": "Negociação de preço",
    "PROPERTY_SEARCH": "Busca de imóvel",
    "GENERAL_INQUIRY": "Consulta geral",
    # Sentiment
    "POSITIVE": "Positivo",
    "NEUTRAL": "Neutro",
    "NEGATIVE": "Negativo",
    "MIXED": "Misto",
}

SYSTEM_PROMPT = """Você é um assistente de IA especializado em imóveis e mercado imobiliário brasileiro. Sua função é ajudar usuários com:

1. PERGUNTAS GERAIS sobre imóveis, mercado imobiliário, financiamento, documentação, processos de compra/venda/aluguel no Brasil
2. DADOS ESPECÍFICOS do sistema CRM (clientes, propriedades, atendimentos) quando contexto for fornecido

REGRAS PARA DADOS DO SISTEMA (quando contexto fornecido):
- Use APENAS as informações fornecidas no contexto. NUNCA invente, assuma ou alucine dados específicos do sistema.
- Se o contexto não contiver informações necessárias sobre dados específicos do CRM, diga: "Não tenho essa informação específica no sistema."
- NUNCA invente nomes de clientes, endereços de propriedades, preços, datas ou qualquer outro dado específico do sistema.
- Se perguntado sobre dados específicos que não existem no contexto, diga: "Não tenho informações sobre [coisa específica] no sistema."

REGRAS PARA CONHECIMENTO GERAL:
- Você PODE e DEVE responder perguntas gerais sobre:
  * Financiamento imobiliário no Brasil (FGTS, SFH, SFI, taxas, prazos)
  * Documentação necessária para compra/venda/aluguel
  * Processos de transação imobiliária
  * Mercado imobiliário brasileiro
  * Dicas e orientações sobre imóveis
  * Questões legais básicas sobre imóveis
- Use seu conhecimento geral sobre o mercado imobiliário brasileiro para essas respostas.
- Seja preciso e cite fontes ou regulamentações quando relevante.

IMPORTANTE - TRADUÇÃO DE ENUMS:
- Quando mencionar valores de ENUM do sistema (status, tipos, etc.), SEMPRE use a tradução em português.
- Exemplos: PUBLISHED → "Publicado", SALE → "Venda", HOUSE → "Casa", etc.
- NUNCA mencione os valores em inglês (PUBLISHED, SALE, etc.) nas respostas ao usuário.

IDIOMA:
- SEMPRE responda em PORTUGUÊS BRASILEIRO.
- NUNCA responda em inglês, mesmo que o contexto contenha termos técnicos em inglês.
- Traduza todos os termos técnicos e ENUMs para português nas suas respostas.

FORMATAÇÃO MARKDOWN:
- Use formatação Markdown para tornar as respostas mais legíveis e organizadas.
- Use **negrito** para destacar informações importantes.
- Use *itálico* para ênfase.
- Use listas numeradas (1., 2., 3.) ou com marcadores (-, *) para organizar informações.
- Use `código` (backticks) para termos técnicos, valores ou códigos.
- Use cabeçalhos (##, ###) para seções quando apropriado.
- Use blocos de código (```) para exemplos de código ou estruturas complexas.
- Use tabelas quando for útil comparar informações.
- Mantenha parágrafos bem espaçados para melhor legibilidade.

Quando contexto do sistema for fornecido, você receberá informações sobre:
- Clientes (nomes, contatos, interesses, status)
- Propriedades (endereços, preços, tipos, status)
- Atendimentos (interações, notas, datas)
- DASHBOARD EXECUTIVA (quando o gestor estiver na dashboard): métricas consolidadas do negócio - total de clientes, vendas, taxa de conversão, funil, desempenho de corretores, tendências mensais, oportunidades, clientes em risco, leads de alto valor

Para contexto de DASHBOARD: o gestor precisa de interpretação e insights. Responda de forma estruturada, destaque os pontos mais relevantes, sugira ações prioritárias, compare tendências e identifique o que merece atenção imediata. Seja conciso mas completo.

Use o contexto quando disponível para responder sobre dados específicos do sistema. Use seu conhecimento geral para responder perguntas sobre o mercado imobiliário brasileiro."""


def translate_enum(value: str | None) -> str:
    """
    Translate ENUM value to Portuguese.
    
    Args:
        value: ENUM value (e.g., "PUBLISHED", "SALE")
    
    Returns:
        Portuguese translation or original value if not found
    """
    if not value:
        return "N/A"
    return ENUM_TRANSLATIONS.get(value.upper(), value)


def build_context_prompt(
    client_data: dict | None = None,
    property_data: dict | None = None,
    attendance_data: dict | None = None,
    dashboard_data: dict | None = None,
) -> str:
    """
    Build context string from database data with ENUM translations.
    
    Args:
        client_data: Client information dictionary
        property_data: Property information dictionary
        attendance_data: Attendance information dictionary
        dashboard_data: Dashboard metrics dictionary (clientes, vendas, funil, etc.)
    
    Returns:
        Formatted context string for the AI (in Portuguese)
    """
    context_parts = []
    
    if client_data:
        context_parts.append("=== INFORMAÇÕES DO CLIENTE ===")
        context_parts.append(f"Nome: {client_data.get('name', 'N/A')}")
        context_parts.append(f"Email: {client_data.get('email', 'N/A')}")
        context_parts.append(f"Telefone: {client_data.get('phone', 'N/A')}")
        context_parts.append(f"Status: {translate_enum(client_data.get('current_status'))}")
        context_parts.append(f"Pontuação de Lead: {client_data.get('current_lead_score', 'N/A')}")
        if client_data.get('current_interest_type'):
            context_parts.append(f"Tipo de Interesse: {translate_enum(client_data.get('current_interest_type'))}")
        if client_data.get('current_budget_min') or client_data.get('current_budget_max'):
            context_parts.append(
                f"Orçamento: R$ {client_data.get('current_budget_min', 'N/A')} - "
                f"R$ {client_data.get('current_budget_max', 'N/A')}"
            )
        if client_data.get('current_city_interest'):
            context_parts.append(f"Interesse na Cidade: {client_data.get('current_city_interest')}")
        context_parts.append("")
    
    if property_data:
        context_parts.append("=== INFORMAÇÕES DA PROPRIEDADE ===")
        context_parts.append(f"Código: {property_data.get('code', 'N/A')}")
        context_parts.append(f"Título: {property_data.get('title', 'N/A')}")
        context_parts.append(f"Tipo: {translate_enum(property_data.get('property_type'))}")
        context_parts.append(f"Tipo de Negócio: {translate_enum(property_data.get('business_type'))}")
        context_parts.append(f"Status: {translate_enum(property_data.get('status'))}")
        if property_data.get('city'):
            context_parts.append(
                f"Endereço: {property_data.get('street', '')} {property_data.get('number', '')}, "
                f"{property_data.get('neighborhood', '')}, {property_data.get('city', '')}, "
                f"{property_data.get('state', '')}"
            )
        if property_data.get('price'):
            context_parts.append(f"Preço de Venda: R$ {property_data.get('price')}")
        if property_data.get('rent_price'):
            context_parts.append(f"Preço de Aluguel: R$ {property_data.get('rent_price')}")
        if property_data.get('bedrooms'):
            context_parts.append(f"Quartos: {property_data.get('bedrooms')}")
        if property_data.get('bathrooms'):
            context_parts.append(f"Banheiros: {property_data.get('bathrooms')}")
        if property_data.get('area_total'):
            context_parts.append(f"Área Total: {property_data.get('area_total')} m²")
        context_parts.append("")
    
    if attendance_data:
        context_parts.append("=== INFORMAÇÕES DO ATENDIMENTO (CONTEXTO COMPLETO) ===")
        context_parts.append(f"Data de criação: {attendance_data.get('created_at', 'N/A')}")
        context_parts.append(f"Última atualização: {attendance_data.get('updated_at', 'N/A')}")
        context_parts.append(f"Status do ciclo: {translate_enum(attendance_data.get('status'))}")
        if attendance_data.get('objective'):
            context_parts.append(f"Objetivo do ciclo: {attendance_data.get('objective')}")
        context_parts.append("")
        # Resumo da IA (análise atual)
        ai = attendance_data.get("ai_summary")
        if ai:
            context_parts.append("--- Resumo da análise da IA ---")
            if ai.get("summary_text"):
                context_parts.append(f"Resumo: {ai.get('summary_text')}")
            if ai.get("detected_intent"):
                context_parts.append(f"Intenção detectada: {translate_enum(ai.get('detected_intent'))}")
            if ai.get("urgency_level_detected"):
                context_parts.append(f"Urgência detectada: {translate_enum(ai.get('urgency_level_detected'))}")
            if ai.get("lead_score_suggested") is not None:
                context_parts.append(f"Lead score sugerido: {ai.get('lead_score_suggested')}/100")
            if ai.get("sentiment"):
                context_parts.append(f"Sentimento: {translate_enum(ai.get('sentiment'))}")
            context_parts.append("")
        if attendance_data.get("property_purchased"):
            context_parts.append(f"Imóvel comprado/alugado neste atendimento: {attendance_data.get('property_purchased')}")
            context_parts.append("")
        if attendance_data.get("property_lost"):
            context_parts.append(f"Imóvel do atendimento (perda): {attendance_data.get('property_lost')}")
            context_parts.append("")
        # Imóvel vinculado ao atendimento
        lp = attendance_data.get("linked_property")
        if lp:
            context_parts.append("--- Imóvel vinculado ao atendimento ---")
            context_parts.append(f"Código: {lp.get('code', 'N/A')} | Título: {lp.get('title', 'N/A')}")
            context_parts.append(f"Tipo: {translate_enum(lp.get('property_type'))} | Status: {translate_enum(lp.get('status'))}")
            if lp.get("city"):
                context_parts.append(f"Cidade: {lp.get('city')}")
            if lp.get("price"):
                context_parts.append(f"Preço venda: R$ {lp.get('price')}")
            if lp.get("rent_price"):
                context_parts.append(f"Preço aluguel: R$ {lp.get('rent_price')}")
            context_parts.append("")
        # Visitas
        visits = attendance_data.get("visits") or []
        if visits:
            context_parts.append("--- Visitas deste atendimento ---")
            for v in visits[:10]:
                prop = v.get("property") or "N/A"
                status = translate_enum(v.get("status"))
                data_visita = v.get("scheduled_at") or "N/A"
                context_parts.append(f"  - {data_visita} | Status: {status} | Imóvel: {prop}")
            context_parts.append("")
        # Vendas do cliente (destaque se for o imóvel deste atendimento)
        sales = attendance_data.get("sales") or []
        if sales:
            context_parts.append("--- Vendas do cliente ---")
            for s in sales[:5]:
                tipo = translate_enum(s.get("sale_type"))
                valor = s.get("sale_value")
                valor_str = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if valor else "N/A"
                destaque = " [IMÓVEL DESTE ATENDIMENTO]" if s.get("is_linked_to_this_attendance") else ""
                context_parts.append(f"  - {s.get('property', 'N/A')} | {tipo} | {valor_str} | {s.get('created_at') or 'N/A'}{destaque}")
            context_parts.append("")
        # Perdas do cliente
        losses = attendance_data.get("losses") or []
        if losses:
            context_parts.append("--- Perdas do cliente ---")
            for lo in losses[:3]:
                motivo = translate_enum(lo.get("reason")) or lo.get("detailed_reason") or "N/A"
                context_parts.append(f"  - Motivo: {motivo} | Imóvel: {lo.get('property', 'N/A')} | Data: {lo.get('lost_at') or 'N/A'}")
            context_parts.append("")
        # Conteúdo bruto da conversa
        if attendance_data.get("raw_content"):
            context_parts.append("--- Conteúdo da conversa ---")
            raw = attendance_data.get("raw_content")
            context_parts.append(raw[:8000] + ("..." if len(raw) > 8000 else ""))
            context_parts.append("")
        context_parts.append("Use as informações acima para responder com precisão. Se o usuário pedir um resumo completo, inclua: estado do atendimento, se há imóvel vinculado e seu status, se há visita agendada, se houve venda ou perda, e os pontos principais da conversa.")
        context_parts.append("")
    
    if dashboard_data:
        context_parts.append("=== DADOS DA DASHBOARD EXECUTIVA (VISÃO GESTOR) ===")
        context_parts.append("")
        context_parts.append("MÉTRICAS GERAIS:")
        context_parts.append(f"- Total de clientes: {dashboard_data.get('total_clients', 0)}")
        context_parts.append(f"- Leads ativos: {dashboard_data.get('active_leads', 0)}")
        context_parts.append(f"- Clientes ganhos (WON): {dashboard_data.get('won_clients', 0)}")
        context_parts.append(f"- Clientes perdidos (LOST): {dashboard_data.get('lost_clients', 0)}")
        context_parts.append(f"- Lead score médio: {dashboard_data.get('avg_lead_score', 0)}")
        context_parts.append("")
        context_parts.append("VENDAS:")
        context_parts.append(f"- Vendas concluídas: {dashboard_data.get('sales_count', 0)}")
        context_parts.append(f"- Valor total vendido: R$ {dashboard_data.get('sales_total_value', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        context_parts.append(f"- Comissões: R$ {dashboard_data.get('sales_commission', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        context_parts.append(f"- Taxa de conversão: {dashboard_data.get('conversion_rate', 0)}%")
        context_parts.append("")
        context_parts.append("ATIVIDADE:")
        context_parts.append(f"- Total de atendimentos: {dashboard_data.get('total_attendances', 0)}")
        context_parts.append(f"- Total de visitas: {dashboard_data.get('total_visits', 0)}")
        context_parts.append(f"- Visitas próximas agendadas: {dashboard_data.get('upcoming_visits', 0)}")
        context_parts.append(f"- Imóveis totais: {dashboard_data.get('total_properties', 0)}")
        context_parts.append(f"- Imóveis disponíveis: {dashboard_data.get('available_properties', 0)}")
        context_parts.append("")
        if dashboard_data.get('funnel_data'):
            context_parts.append("FUNIL DE VENDAS:")
            for stage in dashboard_data['funnel_data']:
                context_parts.append(f"  - {stage.get('stage', 'N/A')}: {stage.get('count', 0)} clientes ({stage.get('percentage', 0)}%)")
            context_parts.append("")
        if dashboard_data.get('top_opportunities'):
            context_parts.append("TOP OPORTUNIDADES (leads com score >= 70):")
            for opp in dashboard_data['top_opportunities'][:5]:
                context_parts.append(f"  - {opp.get('name', 'N/A')} (score: {opp.get('score', 0)})")
            context_parts.append("")
        if dashboard_data.get('at_risk_clients'):
            context_parts.append("CLIENTES EM RISCO (alta urgência, sem contato há 7+ dias):")
            for c in dashboard_data['at_risk_clients'][:5]:
                context_parts.append(f"  - {c.get('name', 'N/A')} (urgência: {c.get('urgency', 'N/A')})")
            context_parts.append("")
        if dashboard_data.get('high_value_leads'):
            context_parts.append("LEADS DE ALTO VALOR (orçamento >= R$ 500k):")
            for c in dashboard_data['high_value_leads'][:5]:
                budget = c.get('budget_max', 0)
                budget_str = f"R$ {budget:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if budget else "N/A"
                context_parts.append(f"  - {c.get('name', 'N/A')} (orçamento máx: {budget_str})")
            context_parts.append("")
        if dashboard_data.get('broker_performance'):
            context_parts.append("DESEMPENHO DOS CORRETORES (por receita):")
            for b in dashboard_data['broker_performance'][:5]:
                rev = b.get('revenue', 0)
                rev_str = f"R$ {rev:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if rev else "0"
                context_parts.append(f"  - {b.get('name', 'N/A')}: {b.get('total_sales', 0)} vendas, {rev_str}, conversão {b.get('conversion_rate', 0)}%")
            context_parts.append("")
        if dashboard_data.get('monthly_trends'):
            context_parts.append("TENDÊNCIAS (últimos 6 meses):")
            for t in dashboard_data['monthly_trends']:
                rev = t.get('revenue', 0)
                rev_str = f"R$ {rev:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if rev else "0"
                context_parts.append(f"  - {t.get('month', 'N/A')}: {t.get('clients', 0)} clientes, {t.get('sales', 0)} vendas, {t.get('losses', 0)} perdas, receita {rev_str}")
        context_parts.append("")
    
    if not context_parts:
        return "Nenhum dado encontrado no sistema para o contexto solicitado."
    
    return "\n".join(context_parts)

