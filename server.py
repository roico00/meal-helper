import json
import os
import random
import requests
from flask import Flask, render_template, jsonify, request, redirect, abort

app = Flask(__name__)

PERSONAL_RECIPES_FILE = "personal_recipes.json"


def load_personal_recipes() -> list:
    """Helper to load personal recipes from the local JSON file."""
    if not os.path.exists(PERSONAL_RECIPES_FILE):
        return []
    with open(PERSONAL_RECIPES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_personal_recipes(recipes: list) -> None:
    """Helper to save personal recipes to the local JSON file."""
    with open(PERSONAL_RECIPES_FILE, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=4)


def get_recipe_for(main_ingredient: str) -> dict | None:
    """
    Fetch a random recipe with a specified main ingredient.
    Searches both the local personal recipes list and "themealdb" API.
    """
    # 1. Normalize underscores to spaces for matching against personal recipes
    normalized_ingredient = main_ingredient.replace("_", " ").strip().lower()
    personal_recipes = load_personal_recipes()
    matching_personal = [
        r for r in personal_recipes
        if any(normalized_ingredient in ing.lower() for ing in r.get("ingredients", {}))
    ]

    # 2. Fetch matching recipe stubs from TheMealDB API (keeps original underscores)
    filter_url = "https://www.themealdb.com/api/json/v1/1/filter.php"
    response = requests.get(filter_url, params={"i": main_ingredient})
    api_meals = response.json().get("meals") or []

    # 3. Combine both sources into a single pool of candidates
    all_candidates = [("personal", r) for r in matching_personal] + [("api", m) for m in api_meals]

    if not all_candidates:
        return None

    # 4. Pick a random candidate from the combined pool
    source, chosen = random.choice(all_candidates)

    if source == "personal":
        return chosen

    # 5. If the chosen candidate came from the API, fetch its full details
    meal_id = chosen["idMeal"]
    lookup_url = "https://www.themealdb.com/api/json/v1/1/lookup.php"
    detail_response = requests.get(lookup_url, params={"i": meal_id})
    meal_data = detail_response.json()["meals"][0]

    # Build ingredients dictionary: {ingredient: measure}
    ingredients = {}
    for i in range(1, 21):
        ing = meal_data.get(f"strIngredient{i}")
        measure = meal_data.get(f"strMeasure{i}")
        if ing and ing.strip():
            ingredients[ing.strip()] = measure.strip() if measure else ""

    return dict(
        name=meal_data.get("strMeal") or "",
        image=meal_data.get("strMealThumb") or "",
        video=meal_data.get("strYoutube") or "",
        instructions=meal_data.get("strInstructions") or "",
        ingredients=ingredients,
    )


@app.route('/')
def index():
    """
    Renders and returns the main page HTML.
    """
    return render_template("index.html")


@app.route('/recipe/<ingredient>')
def recipe(ingredient):
    """
    Renders and returns an HTML page with a random recipe for a given main ingredient.
    """
    recipe_data = get_recipe_for(ingredient)
    if not recipe_data:
        abort(404)

    return render_template("recipe.html",
                           ingredient=ingredient,
                           recipe=recipe_data)


@app.route('/recipe/<ingredient>/json')
def recipe_json(ingredient):
    """
    Returns a JSON with the output of `get_recipe_for`.
    """
    recipe_data = get_recipe_for(ingredient)
    if not recipe_data:
        return jsonify({"error": f"No recipes found for {ingredient}"}), 404

    return jsonify(recipe_data)


# BONUS ENDPOINTS:

@app.route('/personal', methods=['POST'])
def add_personal_recipe():
    """
    Receives a recipe JSON in the request body, saves it to a JSON file,
    and redirects to the newly saved recipe page.
    """
    new_recipe = request.get_json()
    if not new_recipe or "name" not in new_recipe:
        return jsonify({"error": "Invalid recipe JSON or missing 'name'"}), 400

    recipes = load_personal_recipes()
    recipes.append(new_recipe)
    save_personal_recipes(recipes)

    return redirect(f"/personal/{new_recipe['name']}/0")


@app.route('/personal/<name>/<int:json_flag>', methods=['GET'])
def get_personal_recipe(name, json_flag):
    """
    Returns the recipe page if `json_flag == 0`, or a JSON if `json_flag == 1`.
    Returns a 404 response for flag values other than 0 or 1.
    """
    if json_flag not in (0, 1):
        abort(404)

    recipes = load_personal_recipes()
    found_recipe = next((r for r in recipes if r.get("name") == name), None)

    if not found_recipe:
        abort(404)

    if json_flag == 1:
        return jsonify(found_recipe)

    return render_template("recipe.html",
                           ingredient=name,
                           recipe=found_recipe)


@app.route('/personal/<name>', methods=['DELETE'])
def delete_personal_recipe(name):
    """
    Deletes the recipe with the given name.
    """
    recipes = load_personal_recipes()
    updated_recipes = [r for r in recipes if r.get("name") != name]

    if len(updated_recipes) == len(recipes):
        return jsonify({"error": "Recipe not found"}), 404

    save_personal_recipes(updated_recipes)
    return jsonify({"message": f"Recipe '{name}' deleted successfully"}), 200


@app.route('/personal/all', methods=['GET'])
def get_all_personal_recipes():
    """
    Returns a JSON with the list of personal recipes.
    """
    return jsonify(load_personal_recipes())


if __name__ == '__main__':
    app.run(debug=True)