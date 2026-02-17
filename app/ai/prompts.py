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
    "LOST": "Perdido",
    "ABANDONED": "Abandonado",
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
        context_parts.append(f"Data: {attendance_data.get('created_at', 'N/A')}")
        context_parts.append(f"Status: {translate_enum(attendance_data.get('status'))}")
        if attendance_data.get('raw_content'):
            context_parts.append(f"Conteúdo: {attendance_data.get('raw_content')}")
        context_parts.append("")
    
    if not context_parts:
        return "Nenhum dado encontrado no sistema para o contexto solicitado."
    
    return "\n".join(context_parts)

