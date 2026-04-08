from langchain_ollama import OllamaLLM

llm = OllamaLLM(
    model="llama3.2:3b",
    base_url="http://localhost:11434",
    temperature=0.7
)

def generate_response(prompt: str) -> str:
    """
    Sends a request to the Llama 3 model via the Ollama API
    and returns the generated response.

    Args:
        prompt (str): The input text prompt to be processed by the model.

    Returns:
        str: The generated response from the model or an error message.
    """
    try:
        response = llm.invoke(prompt)
        return response

    except ConnectionError:
        print("ERROR: Unable to connect to Ollama. Is 'ollama serve' running?")
        return "Ollama service is not running."

    except KeyError:
        print(f"ERROR: Unexpected API response format: {response.json()}")
        return "Failed to retrieve a valid response from the model."

    except Exception as e:
        print(f"ERROR: {e}")
        return f"Error: {e}"


generate_answer = generate_response


# Debug log to confirm module load and model configuration
print("DEBUG: llm_service.py loaded successfully. Model: Llama 3 (Ollama)")