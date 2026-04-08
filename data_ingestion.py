import os
from rag_pipeline import create_qdrant_collection, add_documents_to_qdrant
from document_parser import parse_recipes_from_pdf


def convert_recipe_to_chunks(recipes):
    chunks = []

    for r in recipes:

        base_meta = {
            "doc_id": r["id"],
            "title": r["title"],
            "source": "RECIPES.pdf"
        }

        if r.get("description"):
            chunks.append({
                "type": "text",
                "content": f"Recipe: {r['title']}\nDescription: {r['description']}",
                "metadata": {**base_meta, "section": "description"}
            })

        if r.get("ingredients"):
            chunks.append({
                "type": "text",
                "content": f"Recipe: {r['title']}\nIngredients:\n" + "\n".join(r["ingredients"]),
                "metadata": {**base_meta, "section": "ingredients"}
            })

        if r.get("instructions"):
            chunks.append({
                "type": "text",
                "content": f"Recipe: {r['title']}\nInstructions:\n" + "\n".join(r["instructions"]),
                "metadata": {**base_meta, "section": "instructions"}
            })

        if r.get("tip"):
            chunks.append({
                "type": "text",
                "content": f"Recipe: {r['title']}\nTip: {r['tip']}",
                "metadata": {**base_meta, "section": "tip"}
            })

    return chunks


if __name__ == "__main__":
    print("Starting data ingestion process...")

    print("Creating or resetting Qdrant collection...")
    create_qdrant_collection(recreate=True)

    PDF_PATH = os.path.join(os.path.dirname(__file__), "RECIPES.pdf")

    try:
        print(f"Reading document from: '{PDF_PATH}'...")
        parsed_elements = parse_recipes_from_pdf(PDF_PATH)

        print("\n--- Sample of Extracted Elements (DEBUG) ---")
        if parsed_elements:
            for i, element in enumerate(parsed_elements[:3]):
                print(f"Element {i + 1} Title: {element['title']}")
                print(f"Description: {str(element['description'])[:100]}...")
                print(f"Ingredients: {element['ingredients'][:3]}")
                print(f"Metadata: {element['metadata']}\n")
                print(f"Metadata: {element['metadata']}\n")
        else:
            print("No elements were extracted from the document.")
        print("---------------------------------------------------\n")

        if not parsed_elements:
            print("WARNING: No content extracted or document may be empty.")
            exit()

        print("Uploading document chunks to Qdrant...")

        # 🔥 DEĞİŞTİRİLDİ: artık chunk'lı ingestion
        chunked_documents = convert_recipe_to_chunks(parsed_elements)

        add_documents_to_qdrant(chunked_documents)

        print("Data successfully uploaded to Qdrant!")

    except FileNotFoundError:
        print(f"ERROR: File not found: {PDF_PATH}")
        print("Please verify and update the PDF_PATH variable.")
    except Exception as e:
        print(f"ERROR: An issue occurred during data ingestion: {e}")