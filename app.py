from flask import Flask, request, jsonify, render_template
import os
from rag_pipeline import create_qdrant_collection, get_answer, qdrant

app = Flask(__name__, template_folder='templates')


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.json
    question = data.get("question")

    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400

    try:
        print(f"DEBUG: Incoming question: {question}")
        answer = get_answer(question)
        print(f"DEBUG: Generated answer: {answer}")
        return jsonify({"answer": answer})
    except Exception as e:
        print(f"ERROR: Exception in /ask endpoint: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


if __name__ == "__main__":
    print("Starting application...")
    print(qdrant.get_collection("Belge"))
    create_qdrant_collection()

    port = int(os.getenv("PORT", 5000))
    print(f"Local URL: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)