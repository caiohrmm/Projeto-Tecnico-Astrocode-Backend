"""System prompts for AI chat agent to prevent hallucination."""

SYSTEM_PROMPT = """You are a helpful AI assistant for a real estate CRM system. Your role is to answer questions about clients, properties, attendances, and other system data.

CRITICAL RULES - NEVER VIOLATE THESE:
1. ONLY use information provided in the context below. NEVER invent, assume, or hallucinate data.
2. If the context does not contain information needed to answer a question, explicitly state: "I don't have that information in the system."
3. NEVER make up client names, property addresses, prices, dates, or any other data.
4. If asked about data that doesn't exist in the context, say: "I don't have information about [specific thing] in the system."
5. Be concise and factual. Use only the data provided.
6. If the context is empty or says "No data found", inform the user that the requested information is not available in the system.

You will receive structured context about:
- Clients (names, contacts, interests, status)
- Properties (addresses, prices, types, status)
- Attendances (interactions, notes, dates)
- Other relevant system data

Use this context to answer questions accurately. Always cite what you know and what you don't know clearly."""


def build_context_prompt(
    client_data: dict | None = None,
    property_data: dict | None = None,
    attendance_data: dict | None = None,
) -> str:
    """
    Build context string from database data.
    
    Args:
        client_data: Client information dictionary
        property_data: Property information dictionary
        attendance_data: Attendance information dictionary
    
    Returns:
        Formatted context string for the AI
    """
    context_parts = []
    
    if client_data:
        context_parts.append("=== CLIENT INFORMATION ===")
        context_parts.append(f"Name: {client_data.get('name', 'N/A')}")
        context_parts.append(f"Email: {client_data.get('email', 'N/A')}")
        context_parts.append(f"Phone: {client_data.get('phone', 'N/A')}")
        context_parts.append(f"Status: {client_data.get('current_status', 'N/A')}")
        context_parts.append(f"Lead Score: {client_data.get('current_lead_score', 'N/A')}")
        if client_data.get('current_interest_type'):
            context_parts.append(f"Interest Type: {client_data.get('current_interest_type')}")
        if client_data.get('current_budget_min') or client_data.get('current_budget_max'):
            context_parts.append(
                f"Budget: R$ {client_data.get('current_budget_min', 'N/A')} - "
                f"R$ {client_data.get('current_budget_max', 'N/A')}"
            )
        if client_data.get('current_city_interest'):
            context_parts.append(f"City Interest: {client_data.get('current_city_interest')}")
        context_parts.append("")
    
    if property_data:
        context_parts.append("=== PROPERTY INFORMATION ===")
        context_parts.append(f"Code: {property_data.get('code', 'N/A')}")
        context_parts.append(f"Title: {property_data.get('title', 'N/A')}")
        context_parts.append(f"Type: {property_data.get('property_type', 'N/A')}")
        context_parts.append(f"Business Type: {property_data.get('business_type', 'N/A')}")
        context_parts.append(f"Status: {property_data.get('status', 'N/A')}")
        if property_data.get('city'):
            context_parts.append(
                f"Address: {property_data.get('street', '')} {property_data.get('number', '')}, "
                f"{property_data.get('neighborhood', '')}, {property_data.get('city', '')}, "
                f"{property_data.get('state', '')}"
            )
        if property_data.get('price'):
            context_parts.append(f"Sale Price: R$ {property_data.get('price')}")
        if property_data.get('rent_price'):
            context_parts.append(f"Rent Price: R$ {property_data.get('rent_price')}")
        if property_data.get('bedrooms'):
            context_parts.append(f"Bedrooms: {property_data.get('bedrooms')}")
        if property_data.get('bathrooms'):
            context_parts.append(f"Bathrooms: {property_data.get('bathrooms')}")
        if property_data.get('area_total'):
            context_parts.append(f"Total Area: {property_data.get('area_total')} m²")
        context_parts.append("")
    
    if attendance_data:
        context_parts.append("=== ATTENDANCE INFORMATION ===")
        context_parts.append(f"Date: {attendance_data.get('started_at', 'N/A')}")
        context_parts.append(f"Channel: {attendance_data.get('channel', 'N/A')}")
        context_parts.append(f"Status: {attendance_data.get('status', 'N/A')}")
        if attendance_data.get('raw_content'):
            context_parts.append(f"Content: {attendance_data.get('raw_content')}")
        context_parts.append("")
    
    if not context_parts:
        return "No data found in the system for the requested context."
    
    return "\n".join(context_parts)

