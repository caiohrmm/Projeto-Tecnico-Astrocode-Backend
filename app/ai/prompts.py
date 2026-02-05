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
    # Attendance Channel
    "WHATSAPP": "WhatsApp",
    "PHONE": "Telefone",
    "EMAIL": "E-mail",
    "SITE": "Site",
    "IN_PERSON": "Presencial",
    # Attendance Status
    "PENDING": "Pendente",
    "IN_PROGRESS": "Em Andamento",
    "COMPLETED": "Concluído",
    "CANCELLED": "Cancelado",
    "PAUSED": "Pausado",
}

SYSTEM_PROMPT = """Você é um assistente de IA para um sistema de CRM imobiliário. Sua função é responder perguntas sobre clientes, propriedades, atendimentos e outros dados do sistema.

REGRAS CRÍTICAS - NUNCA VIOLAR:
1. Use APENAS as informações fornecidas no contexto abaixo. NUNCA invente, assuma ou alucine dados.
2. Se o contexto não contiver informações necessárias para responder, diga explicitamente: "Não tenho essa informação no sistema."
3. NUNCA invente nomes de clientes, endereços de propriedades, preços, datas ou qualquer outro dado.
4. Se perguntado sobre dados que não existem no contexto, diga: "Não tenho informações sobre [coisa específica] no sistema."
5. Seja conciso e factual. Use apenas os dados fornecidos.
6. Se o contexto estiver vazio ou disser "Nenhum dado encontrado", informe ao usuário que as informações solicitadas não estão disponíveis no sistema.

IMPORTANTE - TRADUÇÃO DE ENUMS:
- Quando mencionar valores de ENUM (status, tipos, etc.), SEMPRE use a tradução em português.
- Exemplos: PUBLISHED → "Publicado", SALE → "Venda", HOUSE → "Casa", etc.
- NUNCA mencione os valores em inglês (PUBLISHED, SALE, etc.) nas respostas ao usuário.

IDIOMA:
- SEMPRE responda em PORTUGUÊS BRASILEIRO.
- NUNCA responda em inglês, mesmo que o contexto contenha termos técnicos em inglês.
- Traduza todos os termos técnicos e ENUMs para português nas suas respostas.

Você receberá contexto estruturado sobre:
- Clientes (nomes, contatos, interesses, status)
- Propriedades (endereços, preços, tipos, status)
- Atendimentos (interações, notas, datas)
- Outros dados relevantes do sistema

Use este contexto para responder perguntas com precisão. Sempre cite claramente o que você sabe e o que não sabe."""


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
) -> str:
    """
    Build context string from database data with ENUM translations.
    
    Args:
        client_data: Client information dictionary
        property_data: Property information dictionary
        attendance_data: Attendance information dictionary
    
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
        context_parts.append("=== INFORMAÇÕES DO ATENDIMENTO ===")
        context_parts.append(f"Data: {attendance_data.get('started_at', 'N/A')}")
        context_parts.append(f"Canal: {attendance_data.get('channel', 'N/A')}")
        context_parts.append(f"Status: {translate_enum(attendance_data.get('status'))}")
        if attendance_data.get('raw_content'):
            context_parts.append(f"Conteúdo: {attendance_data.get('raw_content')}")
        context_parts.append("")
    
    if not context_parts:
        return "Nenhum dado encontrado no sistema para o contexto solicitado."
    
    return "\n".join(context_parts)

