from run_time_python.drive_gdb import Location
import requests

EXPLANATION_BASE_URL = "https://comp1511unsw.github.io/dcc/"
LLM_EXPLANATION_BASE_URL = "http://localhost:80/api/"


def explanation_url(page):
    return EXPLANATION_BASE_URL + page + ".html"



def explain_dcc_output_via_llm(location: Location, source: str, error: str):
    """Explain a source code line via the LLM."""
    # hit the LLM API to explain the source code line
    request_data = {
        "location": location,
        "source": source,
        "error": error,
    }

    request = requests.get(LLM_EXPLANATION_BASE_URL, json=request_data)
    print(request.json())

    # todo: implement this function
