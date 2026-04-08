import os
import re
import pdfplumber
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_special_characters(text: str) -> str:
    """
    Cleans LaTeX-like and malformed special characters commonly found in PDFs.
    """
    text = re.sub(r'\$([0-9/]+)\$', r'\1', text)
    text = re.sub(r'\$(\d+)\^\{\\circ\}C\$', r'\1°C', text)
    text = re.sub(r'\$(\d+)\^\{\\circ\}F\$', r'\1°F', text)
    text = text.replace('^{\\circ}C', '°C').replace('^{\\circ}F', '°F')
    text = text.replace('$', '')
    return text


def generate_id(title: str) -> str:
    """
    Generates a normalized ID from the recipe title.
    """
    return re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')


def parse_recipes_from_pdf(pdf_path: str) -> list:
    """
    Parses a recipe PDF and extracts structured recipe data.

    Returns:
        List of dictionaries containing structured recipe information.
    """
    if not os.path.exists(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        return []

    all_text = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Opened PDF: {os.path.basename(pdf_path)} ({len(pdf.pages)} pages)")

            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    all_text += extracted + "\n"

    except Exception as e:
        logger.error(f"Error while reading PDF: {e}")
        return []

    # Clean text artifacts
    all_text = clean_special_characters(all_text)

    # Normalize lines
    lines = [line.strip() for line in all_text.split('\n') if line.strip()]

    recipes = []
    current_recipe = None
    current_section = None

    meta_pattern = re.compile(
        r"Prep Time:\s*(.*?)\s*\|\s*Cook Time:\s*(.*?)\s*\|\s*Servings:\s*(.*?)\s*\|\s*Difficulty:\s*(.*)"
    )

    for i, line in enumerate(lines):
        meta_match = meta_pattern.search(line)

        # --- Detect new recipe ---
        if meta_match:
            if current_recipe:
                recipes.append(current_recipe)

            # Safer title detection
            title = lines[i - 1] if i > 0 else "Unknown Recipe"

            if "Prep Time" in title or title.upper() == "RECIPES":
                title = lines[i + 1] if i + 1 < len(lines) else "Unknown Recipe"

            current_recipe = {
                "id": generate_id(title),
                "title": title,
                "metadata": {
                    "prep_time": meta_match.group(1).strip(),
                    "cook_time": meta_match.group(2).strip(),
                    "servings": meta_match.group(3).strip(),
                    "difficulty": meta_match.group(4).strip()
                },
                "description": "",
                "ingredients": [],
                "instructions": [],
                "tip": ""
            }

            current_section = "description"
            continue

        if not current_recipe:
            continue

        # --- Section detection ---
        if line.startswith("Ingredients:"):
            current_section = "ingredients"
            continue

        elif line.startswith("Instructions"):
            current_section = "instructions"
            continue

        elif line.startswith("Tip:"):
            current_section = "tip"
            current_recipe["tip"] = line.replace("Tip:", "").strip()
            continue

        # --- Section parsing ---
        if current_section == "description":
            current_recipe["description"] += line + " "

        elif current_section == "ingredients":
            if line.startswith('•'):
                current_recipe["ingredients"].append(line.replace('•', '').strip())
            else:
                if current_recipe["ingredients"]:
                    current_recipe["ingredients"][-1] += " " + line
                else:
                    current_recipe["ingredients"].append(line)

        elif current_section == "instructions":
            if re.match(r'^\d+\.', line):
                clean_step = re.sub(r'^\d+\.\s*', '', line)
                current_recipe["instructions"].append(clean_step)
            else:
                if current_recipe["instructions"]:
                    current_recipe["instructions"][-1] += " " + line

        elif current_section == "tip":
            current_recipe["tip"] += " " + line

    if current_recipe:
        recipes.append(current_recipe)

    # Final cleanup
    for recipe in recipes:
        recipe["description"] = recipe["description"].strip()
        recipe["ingredients"] = [ing.strip() for ing in recipe["ingredients"]]

    logger.info(f"Total recipes extracted: {len(recipes)}")

    return recipes