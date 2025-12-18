import sqlite3
import requests
import json
from datetime import datetime

DB_NAME = "meal_planner.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:1b"

# -------------------------------
# DATABASE SETUP / HELPERS
# -------------------------------

def get_connection():
    return sqlite3.connect(DB_NAME)

def create_database():
    conn = get_connection()
    cursor = conn.cursor()

    # Recipes table with personalization + feedback fields
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredients TEXT,
            avoid_ingredients TEXT,
            meal_type TEXT,
            diet_type TEXT,
            cooking_time INTEGER,
            goal TEXT,
            spice_level TEXT,
            tags TEXT,
            recipe_output TEXT,
            rating INTEGER,
            notes TEXT
        )
    """)

    # Plans table (day-level plans)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name TEXT,
            created_at TEXT,
            breakfast_recipe_id INTEGER,
            lunch_recipe_id INTEGER,
            dinner_recipe_id INTEGER,
            FOREIGN KEY (breakfast_recipe_id) REFERENCES recipes(id),
            FOREIGN KEY (lunch_recipe_id) REFERENCES recipes(id),
            FOREIGN KEY (dinner_recipe_id) REFERENCES recipes(id)
        )
    """)

    conn.commit()
    conn.close()

def insert_recipe(ingredients, avoid_ingredients, meal_type, diet_type,
                  cooking_time, goal, spice_level, tags, recipe_output):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO recipes
        (ingredients, avoid_ingredients, meal_type, diet_type, cooking_time,
         goal, spice_level, tags, recipe_output, rating, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
    """, (ingredients, avoid_ingredients, meal_type, diet_type, cooking_time,
          goal, spice_level, tags, recipe_output))
    recipe_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return recipe_id

def update_recipe_feedback(recipe_id, rating, notes):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE recipes
        SET rating = ?, notes = ?
        WHERE id = ?
    """, (rating, notes, recipe_id))
    conn.commit()
    conn.close()

def find_existing_recipe(ingredients, avoid_ingredients, meal_type, diet_type,
                         cooking_time, goal, spice_level):
    """
    Try to reuse a recipe with exactly same key constraints.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, recipe_output, tags
        FROM recipes
        WHERE ingredients = ?
          AND IFNULL(avoid_ingredients, '') = ?
          AND meal_type = ?
          AND diet_type = ?
          AND cooking_time = ?
          AND IFNULL(goal, '') = ?
          AND IFNULL(spice_level, '') = ?
    """, (ingredients, avoid_ingredients, meal_type, diet_type,
          cooking_time, goal, spice_level))
    row = cursor.fetchone()
    conn.close()
    return row  # (id, recipe_output, tags) or None

def list_all_recipes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ingredients, meal_type, diet_type, cooking_time, goal,
               spice_level, tags, rating
        FROM recipes
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\nNo recipes stored yet.")
        return

    print("\n=== Stored Recipes (Summary) ===")
    for r in rows:
        (rid, ingredients, meal_type, diet_type, cooking_time,
         goal, spice_level, tags, rating) = r
        rating_str = "Not rated" if rating is None else f"{rating}/5"
        print(f"[{rid}] {meal_type} | {diet_type} | {cooking_time} min | Goal: {goal or '-'}")
        print(f"    Spice: {spice_level or '-'} | Tags: {tags or '-'} | Rating: {rating_str}")
        print(f"    Ingredients: {ingredients}")

def view_recipe_by_id():
    try:
        recipe_id = int(input("Enter recipe ID to view: ").strip())
    except ValueError:
        print("Invalid ID.")
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ingredients, avoid_ingredients, meal_type, diet_type,
               cooking_time, goal, spice_level, tags, recipe_output, rating, notes
        FROM recipes
        WHERE id = ?
    """, (recipe_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        print("Recipe not found.")
        return

    (rid, ingredients, avoid_ingredients, meal_type, diet_type,
     cooking_time, goal, spice_level, tags, recipe_output,
     rating, notes) = row

    print("\n=== Recipe Detail ===")
    print(f"ID: {rid}")
    print(f"Ingredients: {ingredients}")
    print(f"Avoid Ingredients: {avoid_ingredients or '-'}")
    print(f"Meal Type: {meal_type}")
    print(f"Diet Type: {diet_type}")
    print(f"Cooking Time: {cooking_time} minutes")
    print(f"Goal: {goal or '-'}")
    print(f"Spice Level: {spice_level or '-'}")
    print(f"Tags: {tags or '-'}")
    rating_str = "Not rated" if rating is None else f"{rating}/5"
    print(f"Rating: {rating_str}")
    print(f"Notes: {notes or '-'}")
    print("\n--- Generated Recipe ---")
    print(recipe_output)

def search_recipes_by_ingredient():
    keyword = input("Enter ingredient keyword to search: ").strip().lower()
    if not keyword:
        print("Keyword cannot be empty.")
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ingredients, meal_type, diet_type, cooking_time, goal, tags
        FROM recipes
        WHERE LOWER(ingredients) LIKE ?
        ORDER BY id DESC
    """, (f"%{keyword}%",))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\nNo recipes found with that ingredient.")
        return

    print(f"\nRecipes containing '{keyword}':")
    for r in rows:
        rid, ingredients, meal_type, diet_type, cooking_time, goal, tags = r
        print(f"[{rid}] {meal_type} | {diet_type} | {cooking_time} min | Goal: {goal or '-'}")
        print(f"    Tags: {tags or '-'}")
        print(f"    Ingredients: {ingredients}")

# -------------------------------
# PLANS (DAY-LEVEL PLANNING)
# -------------------------------

def insert_plan(plan_name, breakfast_id, lunch_id, dinner_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO plans (plan_name, created_at, breakfast_recipe_id,
                           lunch_recipe_id, dinner_recipe_id)
        VALUES (?, ?, ?, ?, ?)
    """, (plan_name, datetime.now().isoformat(),
          breakfast_id, lunch_id, dinner_id))
    conn.commit()
    conn.close()

def list_plans():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, plan_name, created_at,
               breakfast_recipe_id, lunch_recipe_id, dinner_recipe_id
        FROM plans
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\nNo plans created yet.")
        return

    print("\n=== Meal Plans ===")
    for r in rows:
        pid, plan_name, created_at, b_id, l_id, d_id = r
        print(f"[{pid}] {plan_name} ({created_at})")
        print(f"    Breakfast Recipe ID: {b_id}")
        print(f"    Lunch Recipe ID: {l_id}")
        print(f"    Dinner Recipe ID: {d_id}")

# -------------------------------
# LLM CALL (OLLAMA HTTP API)
# -------------------------------

def generate_recipe_from_llm(ingredients, avoid_ingredients, meal_type,
                             diet_type, cooking_time, goal, spice_level,
                             previous_context=None):
    """
    Ask LLM for:
    - recipe
    - rough tags (light/moderate/heavy, macro focus)
    Return (recipe_output_text, tags_string)
    """
    avoid_text = avoid_ingredients or "None"
    goal_text = goal or "general"
    spice_text = spice_level or "medium"

    context_section = ""
    if previous_context:
        context_section = f"\nPrevious meals in this plan:\n{previous_context}\n"

    prompt = f"""
You are a cooking assistant for a personalized meal planner.

User details:
- Goal: {goal_text} (examples: weight loss, maintenance, weight gain)
- Spice preference: {spice_text}
- Diet type: {diet_type}
- Meal type: {meal_type}
- Available cooking time: {cooking_time} minutes
- Ingredients available: {ingredients}
- Ingredients to AVOID: {avoid_text}
{context_section}

Tasks:
1. Generate ONE simple recipe:
   - Recipe name
   - Estimated cooking time (<= available time)
   - Step-by-step instructions suitable for a beginner.
   - Respect diet type and avoid ingredients.
   - Respect goal and spice preference.

2. At the end, add a short line: "Tags: ..." where you:
   - Qualitatively label the meal as light / moderate / heavy.
   - Mention a primary macro focus (e.g., high protein, high carbs, balanced).

Keep response concise and easy to understand.
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=90
        )
        response.raise_for_status()
        data = response.json()
        full_text = data.get("response", "").strip()
        tags = ""
        # Extract "Tags: ..." line if present
        for line in full_text.splitlines():
            if line.strip().lower().startswith("tags:"):
                tags = line.strip()[5:].strip()
        return full_text, tags
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return None, None

# -------------------------------
# INPUT FLOWS
# -------------------------------

def get_common_inputs():
    ingredients = input("Enter available ingredients (comma-separated): ").strip()
    if not ingredients:
        print("Ingredients cannot be empty.")
        return None

    avoid_ingredients = input("Enter ingredients to AVOID (comma-separated, or leave blank): ").strip()

    # cooking time
    while True:
        cooking_time_str = input("Enter cooking time (minutes): ").strip()
        try:
            cooking_time = int(cooking_time_str)
            if cooking_time <= 0:
                print("Time must be positive.")
                continue
            break
        except ValueError:
            print("Please enter a valid number for time.")

    diet_type = input("Enter diet type (Veg / Non-Veg): ").strip().title()
    if diet_type not in ["Veg", "Non-Veg"]:
        print("Invalid diet type. Defaulting to Veg.")
        diet_type = "Veg"

    print("Goal options: weight loss / maintenance / weight gain / (leave blank)")
    goal = input("Enter your goal: ").strip().lower()
    if goal not in ["weight loss", "maintenance", "weight gain", ""]:
        print("Invalid goal. Setting as blank.")
        goal = ""

    print("Spice level options: mild / medium / spicy / (leave blank)")
    spice_level = input("Enter spice level: ").strip().lower()
    if spice_level not in ["mild", "medium", "spicy", ""]:
        print("Invalid spice level. Setting as blank.")
        spice_level = ""

    return ingredients, avoid_ingredients, cooking_time, diet_type, goal, spice_level

def get_meal_type():
    meal_type = input("Enter meal type (Breakfast / Lunch / Dinner): ").strip().title()
    if meal_type not in ["Breakfast", "Lunch", "Dinner"]:
        print("Invalid meal type. Defaulting to Lunch.")
        meal_type = "Lunch"
    return meal_type

def ask_for_feedback(recipe_id):
    ans = input("Would you like to rate this recipe? (y/n): ").strip().lower()
    if ans != "y":
        return
    try:
        rating_str = input("Rate from 1 to 5: ").strip()
        rating = int(rating_str)
        if rating < 1 or rating > 5:
            print("Rating must be between 1 and 5. Feedback skipped.")
            return
    except ValueError:
        print("Invalid rating. Feedback skipped.")
        return

    notes = input("Any comments/notes about this recipe? (optional): ").strip()
    update_recipe_feedback(recipe_id, rating, notes)
    print("Thank you! Feedback saved.")

# -------------------------------
# RECIPE GENERATION FLOWS
# -------------------------------

def generate_single_recipe_flow():
    common = get_common_inputs()
    if common is None:
        return
    ingredients, avoid_ingredients, cooking_time, diet_type, goal, spice_level = common
    meal_type = get_meal_type()

    # Try reuse
    existing = find_existing_recipe(
        ingredients, avoid_ingredients, meal_type, diet_type,
        cooking_time, goal, spice_level
    )
    if existing:
        rid, recipe_output, tags = existing
        print("\n--- Retrieved Saved Recipe ---")
        print(f"(Recipe ID: {rid})")
        print(recipe_output)
        ask_for_feedback(rid)
        return

    print("\nGenerating new personalized recipe with LLM...")
    recipe_output, tags = generate_recipe_from_llm(
        ingredients, avoid_ingredients, meal_type, diet_type,
        cooking_time, goal, spice_level
    )

    if not recipe_output:
        print("Failed to generate recipe.")
        return

    recipe_id = insert_recipe(
        ingredients, avoid_ingredients, meal_type, diet_type,
        cooking_time, goal, spice_level, tags, recipe_output
    )
    print("\n--- Generated Recipe ---")
    print(f"(Recipe ID: {recipe_id})")
    print(recipe_output)
    ask_for_feedback(recipe_id)

def plan_my_day_flow():
    """
    Generate Breakfast, Lunch, Dinner in one go, sharing common constraints.
    """
    print("\n=== Plan My Day (Breakfast, Lunch, Dinner) ===")
    common = get_common_inputs()
    if common is None:
        return
    ingredients, avoid_ingredients, cooking_time, diet_type, goal, spice_level = common

    # total time is per meal; keep it simple
    previous_context = ""
    ids = {}

    for meal_type in ["Breakfast", "Lunch", "Dinner"]:
        print(f"\nGenerating {meal_type} recipe...")
        recipe_output, tags = generate_recipe_from_llm(
            ingredients, avoid_ingredients, meal_type, diet_type,
            cooking_time, goal, spice_level, previous_context=previous_context
        )

        if not recipe_output:
            print(f"Failed to generate {meal_type} recipe. Aborting plan.")
            return

        recipe_id = insert_recipe(
            ingredients, avoid_ingredients, meal_type, diet_type,
            cooking_time, goal, spice_level, tags, recipe_output
        )

        ids[meal_type] = recipe_id
        print(f"\n--- {meal_type} Recipe (ID: {recipe_id}) ---")
        print(recipe_output)

        previous_context += f"\n{meal_type} (Recipe ID {recipe_id}):\n{recipe_output}\n"

    plan_name = input("\nEnter a name for this day plan (e.g., 'Monday Healthy Plan'): ").strip()
    if not plan_name:
        plan_name = "Unnamed Plan"

    insert_plan(
        plan_name,
        ids.get("Breakfast"),
        ids.get("Lunch"),
        ids.get("Dinner")
    )

    print("\nDay plan saved successfully!")
    print(f"Breakfast ID: {ids.get('Breakfast')}, Lunch ID: {ids.get('Lunch')}, Dinner ID: {ids.get('Dinner')}")

# -------------------------------
# MAIN MENU
# -------------------------------

def main_menu():
    create_database()

    while True:
        print("\n=== Smart Meal Planner (Personalized) ===")
        print("1. Generate personalized recipe")
        print("2. List all recipes (summary)")
        print("3. View recipe by ID")
        print("4. Search recipes by ingredient")
        print("5. Plan my day (Breakfast–Lunch–Dinner)")
        print("6. List saved day plans")
        print("7. Exit")

        choice = input("Choose an option (1-7): ").strip()

        if choice == "1":
            generate_single_recipe_flow()
        elif choice == "2":
            list_all_recipes()
        elif choice == "3":
            view_recipe_by_id()
        elif choice == "4":
            search_recipes_by_ingredient()
        elif choice == "5":
            plan_my_day_flow()
        elif choice == "6":
            list_plans()
        elif choice == "7":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1-7.")

if __name__ == "__main__":
    main_menu()
