import sqlite3
import requests
import json

DB_NAME = "meal_planner.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3"

# -------------------------------
# DATABASE SETUP
# -------------------------------

def create_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredients TEXT,
            meal_type TEXT,
            diet_type TEXT,
            cooking_time INTEGER,
            recipe_output TEXT
        )
    """)
    conn.commit()
    conn.close()

# -------------------------------
# LLM CALL (OLLAMA HTTP API)
# -------------------------------

def generate_recipe(prompt):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(
        OLLAMA_URL,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"}
    )

    return response.json()["response"]

# -------------------------------
# MAIN PROGRAM
# -------------------------------

def main():
    print("=== Smart Meal Planner ===")

    ingredients = input("Enter available ingredients: ")
    cooking_time = input("Enter cooking time (minutes): ")
    diet_type = input("Enter diet type (Veg / Non-Veg): ")
    meal_type = input("Enter meal type (Breakfast / Lunch / Dinner): ")

    prompt = f"""
You are a cooking assistant.
Generate one simple recipe using:

Ingredients: {ingredients}
Meal type: {meal_type}
Diet type: {diet_type}
Cooking time: {cooking_time} minutes

Provide:
1. Recipe name
2. Step-by-step instructions
"""

    recipe = generate_recipe(prompt)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO recipes
        (ingredients, meal_type, diet_type, cooking_time, recipe_output)
        VALUES (?, ?, ?, ?, ?)
    """, (ingredients, meal_type, diet_type, cooking_time, recipe))
    conn.commit()
    conn.close()

    print("\n--- Generated Recipe ---")
    print(recipe)

# -------------------------------
# EXECUTION
# -------------------------------

create_database()
main()
