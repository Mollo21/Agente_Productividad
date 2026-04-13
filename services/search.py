from duckduckgo_search import DDGS

def search_web(query: str, max_results: int = 3):
    """Busca en la web usando DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No encontré resultados para esa búsqueda."
            
            response = ""
            for r in results:
                response += f"- {r['title']}: {r['body']}\n"
            return response
    except Exception as e:
        return f"Error en la búsqueda web: {str(e)}"
