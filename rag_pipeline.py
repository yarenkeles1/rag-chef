import os
import uuid
from dotenv import load_dotenv
load_dotenv()
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse
from sentence_transformers import SentenceTransformer
from llm_service import generate_answer
from langchain_text_splitters import RecursiveCharacterTextSplitter

QDRANT_HOST = os.getenv("QDRANT_HOST", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

qdrant = QdrantClient(
    url=QDRANT_HOST,
    api_key=QDRANT_API_KEY,
)

try:
    embedding_model = SentenceTransformer(
        os.getenv("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base")
    )
    print("DEBUG: Embedding model loaded successfully.")
    print(f"DEBUG: Embedding dimension: {embedding_model.get_sentence_embedding_dimension()}")
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load embedding model: {e}")
    embedding_model = None

COLLECTION_NAME = "Belge"


def create_qdrant_collection(recreate: bool = False):
    """
    Creates or resets the Qdrant collection.

    Args:
        recreate (bool): If True, deletes and recreates the existing collection.
    """
    try:
        if qdrant.collection_exists(collection_name=COLLECTION_NAME):
            if recreate:
                qdrant.delete_collection(collection_name=COLLECTION_NAME)
                print(f"DEBUG: Collection '{COLLECTION_NAME}' deleted (recreate=True).")
            else:
                info = qdrant.get_collection(collection_name=COLLECTION_NAME)
                print(f"DEBUG: Collection '{COLLECTION_NAME}' already exists. Point count: {info.points_count}")
                return

        if embedding_model is not None:
            qdrant.recreate_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=embedding_model.get_sentence_embedding_dimension(),
                    distance=Distance.COSINE
                ),
            )
            print(f"DEBUG: Collection '{COLLECTION_NAME}' created successfully.")
        else:
            print("ERROR: Embedding model unavailable, collection could not be created.")
    except Exception as e:
        print(f"ERROR: Failed to create collection: {e}")


def add_documents_to_qdrant(documents):
    """
    Splits documents into chunks, generates embeddings,
    and upserts them into Qdrant.

    Args:
        documents (list): List of parsed document elements with type, content, and metadata.
    """
    try:
        if embedding_model is None:
            print("ERROR: Embedding model unavailable, documents cannot be added.")
            return

        print("DEBUG: Splitting documents into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=100,
            length_function=len,
            add_start_index=True
        )

        all_chunks = []
        for doc in documents:
            content_to_split = ""
            if doc['type'] in ('text', 'table'):
                content_to_split = doc['content']

            if content_to_split.strip():
                chunks = text_splitter.split_text(content_to_split)
                for i, chunk_text in enumerate(chunks):
                    meta = doc['metadata'].copy()
                    meta['content'] = chunk_text
                    meta['chunk_id'] = f"{doc['metadata'].get('doc_id', str(uuid.uuid4()))}-{doc['type']}-{i}"
                    meta['original_doc_type'] = doc['type']
                    all_chunks.append({"text": chunk_text, "metadata": meta})

        print(f"DEBUG: {len(all_chunks)} chunks created.")
        if not all_chunks:
            print("WARNING: No chunks found to add.")
            return

        texts = [c["text"] for c in all_chunks]
        texts = ["passage: " + t for t in texts]
        embeddings = embedding_model.encode(texts, show_progress_bar=True).tolist()
        print("DEBUG: Embeddings generated successfully.")

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings[i],
                payload=all_chunks[i]["metadata"]
            )
            for i in range(len(all_chunks))
        ]

        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            wait=True,
            points=points
        )
        print(f"DEBUG: {len(points)} points upserted into Qdrant.")

    except Exception as e:
        print(f"ERROR: Failed to add documents to Qdrant: {e}")
        raise


def get_answer(question: str) -> str:
    """
    Encodes the question, searches Qdrant for relevant context,
    and generates an answer using the LLM.

    Args:
        question (str): The user's question.

    Returns:
        str: The generated answer or a fallback message.
    """
    try:
        if embedding_model is None:
            return "Error: Embedding model is not available."

        question_vector = embedding_model.encode("query: " + question).tolist()

        search_result = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=question_vector,
            limit=3,
            with_payload=True,
            with_vectors=False
        ).points

        print(f"DEBUG: {len(search_result)} result(s) found.")

        if not search_result:
            temp = qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=question_vector,
                limit=1,
                with_payload=True
            ).points
            if temp:
                print(f"DEBUG: Best score (no threshold): {temp[0].score:.4f}")
            else:
                print("DEBUG: Collection is empty or model mismatch.")
            return "I could not find any relevant information on this topic."

        context_parts = []
        for i, hit in enumerate(search_result):
            print(f"DEBUG: Result {i+1} - Score: {hit.score:.4f}, Source: {hit.payload.get('source_file', 'N/A')}")
            context_parts.append(hit.payload.get("content", ""))

        context = "\n---\n".join(context_parts)

        if not context.strip() or len(context.strip()) < 10:
            return "I could not find any relevant information on this topic."

        prompt = f"""You are a cooking recipe assistant. Your task is to answer users' questions about recipes **solely based on the provided context**.

        RULES:
        - Only use the information present in the context below.
        - Do not invent or guess any information that is not in the context.
        - Specify ingredient quantities, cooking times, and steps completely.
        - If the question is unrelated to the context or there is insufficient information in the context, simply respond: "I do not have information on this topic."
        - Avoid unnecessary introductory sentences; go straight to the answer.

        CONTEXT:
        ---
        {context}
        ---

        QUESTION: {question}

        ANSWER:"""

        print("DEBUG: Sending prompt to Llama 3...")
        answer = generate_answer(prompt)

        if "Answer:" in answer:
            answer = answer.split("Answer:", 1)[-1].strip()
        else:
            answer = answer.strip()

        if not answer or len(answer) < 20 or "sorry" in answer.lower():
            return "I could not find any relevant information on this topic."

        return answer

    except UnexpectedResponse as e:
        print(f"ERROR: Qdrant connection error: {e}")
        return "Could not connect to the database or collection not found."
    except Exception as e:
        print(f"ERROR: Unexpected error in get_answer: {e}")
        return "Sorry, an error occurred while retrieving the information."