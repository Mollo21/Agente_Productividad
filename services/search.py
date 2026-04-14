from ddgs import DDGS
import logging

logger = logging.getLogger(__name__)

def search_web(query: str, max_results: int = 8) -> str:
    """Busca en la web usando DuckDuckGo. Retorna los resultados más relevantes."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No encontré resultados para esa búsqueda."
            
            response = ""
            for r in results:
                response += f"**{r['title']}**\n{r['body']}\n🔗 {r.get('href', '')}\n\n"
            return response.strip()
    except Exception as e:
        logger.error(f"Error buscando en web: {e}")
        return f"Error en la búsqueda web: {str(e)}"


def search_news(query: str, max_results: int = 8) -> str:
    """Busca NOTICIAS recientes usando DuckDuckGo News."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
            if not results:
                # Fallback a búsqueda general
                return search_web(query, max_results=max_results)
            
            response = ""
            for r in results:
                fecha = r.get('date', 'Sin fecha')
                response += f"📰 **{r['title']}**\n{r['body']}\n📅 {fecha}\n🔗 {r.get('url', '')}\n\n"
            return response.strip()
    except Exception as e:
        logger.error(f"Error buscando noticias: {e}")
        # Fallback a búsqueda general
        return search_web(query, max_results=max_results)


def search_topic_comprehensive(topic: str) -> str:
    """
    Búsqueda comprensiva sobre un tema.
    Hace múltiples búsquedas con variaciones para obtener contexto amplio.
    Ideal para suscripciones diarias y resúmenes.
    """
    all_results = []
    
    # Variaciones simples para DuckDuckGo (prefiere queries cortos)
    search_variations = [
        f"{topic} noticias",
        f"{topic}",
    ]
    
    try:
        with DDGS() as ddgs:
            for search_query in search_variations:
                try:
                    # DuckDuckGo falla si el query de noticias es muy específico
                    results = list(ddgs.news(search_query, max_results=5))
                    if not results:
                        results = list(ddgs.text(search_query, max_results=5))
                    
                    for r in results:
                        title = r.get('title', '')
                        # Evitar duplicados por título
                        if not any(title.lower() == existing.get('title', '').lower() for existing in all_results):
                            all_results.append(r)
                except Exception:
                    continue
    except Exception as e:
        logger.error(f"Error en búsqueda comprensiva: {e}")
    
    if not all_results:
        return f"No encontré información actualizada sobre '{topic}'."
    
    response = f"📊 **Resumen completo sobre: {topic}**\n\n"
    for i, r in enumerate(all_results[:10], 1):
        body = r.get('body', r.get('snippet', 'Sin detalle'))
        fecha = r.get('date', '')
        url = r.get('url', r.get('href', ''))
        response += f"{i}. **{r['title']}**\n   {body}\n"
        if fecha:
            response += f"   📅 {fecha}\n"
        if url:
            response += f"   🔗 {url}\n"
        response += "\n"
    
    return response.strip()
